import os
import random
import logging
from typing import Tuple
import shutil

try:
    import cv2
    import numpy as np
except ImportError:
    logging.warning("OpenCV or Numpy not found. Please install them to use the Vision module: pip install opencv-python numpy")

class DatasetTool:
    """
    A utility class to generate expanded datasets from a few raw images.
    It automatically applies transformations (rotation, noise, brightness) to 
    increase the robustness of the trained model.
    """

    @staticmethod
    def _add_noise(image):
        row, col, ch = image.shape
        mean = 0
        sigma = 15  # noise intensity
        gauss = np.random.normal(mean, sigma, (row, col, ch))
        noisy = image + gauss
        noisy = np.clip(noisy, 0, 255).astype(np.uint8)
        return noisy

    @staticmethod
    def _rotate_image(image, angle):
        image_center = tuple(np.array(image.shape[1::-1]) / 2)
        rot_mat = cv2.getRotationMatrix2D(image_center, angle, 1.0)
        result = cv2.warpAffine(image, rot_mat, image.shape[1::-1], flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return result

    @staticmethod
    def _adjust_brightness(image, factor):
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        hsv = np.array(hsv, dtype=np.float64)
        hsv[:, :, 2] = hsv[:, :, 2] * factor
        hsv[:, :, 2][hsv[:, :, 2] > 255] = 255
        hsv = np.array(hsv, dtype=np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)

    @classmethod
    def generate(cls, 
                 input_folder: str, 
                 output_folder: str, 
                 image_size: Tuple[int, int] = (224, 224), 
                 variants_per_image: int = 30, 
                 create_background_class: bool = True):
        """
        Takes raw images from input_folder (organized in subfolders by class),
        augments them, resizes them, and saves them to output_folder.
        
        Args:
            input_folder: Path to raw data (e.g. 'raw_data/red_ball/1.jpg')
            output_folder: Path to save the ready dataset
            image_size: Resize target (width, height)
            variants_per_image: How many augmented variants to create per raw image
            create_background_class: If True, generates random noise/blank images as a "background" class
        """
        if not os.path.exists(input_folder):
            raise FileNotFoundError(f"Input folder '{input_folder}' does not exist.")

        os.makedirs(output_folder, exist_ok=True)

        classes = [d for d in os.listdir(input_folder) if os.path.isdir(os.path.join(input_folder, d))]
        
        if not classes:
            logging.error(f"No class folders found in '{input_folder}'. Create subfolders for each class.")
            return

        total_generated = 0

        for class_name in classes:
            class_in_path = os.path.join(input_folder, class_name)
            class_out_path = os.path.join(output_folder, class_name)
            os.makedirs(class_out_path, exist_ok=True)

            images = [f for f in os.listdir(class_in_path) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            for img_name in images:
                img_path = os.path.join(class_in_path, img_name)
                image = cv2.imread(img_path)
                
                if image is None:
                    logging.warning(f"Could not read image {img_path}")
                    continue

                # Resize original
                image = cv2.resize(image, image_size)
                
                # Save original
                base_name = os.path.splitext(img_name)[0]
                cv2.imwrite(os.path.join(class_out_path, f"{base_name}_orig.jpg"), image)
                total_generated += 1

                # Generate variants
                for i in range(variants_per_image):
                    variant = image.copy()
                    
                    # 1. Random rotation (-30 to 30 degrees)
                    angle = random.uniform(-30, 30)
                    variant = cls._rotate_image(variant, angle)
                    
                    # 2. Random brightness (0.5 to 1.5)
                    brightness = random.uniform(0.5, 1.5)
                    variant = cls._adjust_brightness(variant, brightness)
                    
                    # 3. Random noise (30% chance)
                    if random.random() < 0.3:
                        variant = cls._add_noise(variant)
                        
                    cv2.imwrite(os.path.join(class_out_path, f"{base_name}_var_{i}.jpg"), variant)
                    total_generated += 1

        # Create an artificial background class if requested
        if create_background_class:
            bg_out_path = os.path.join(output_folder, "background")
            os.makedirs(bg_out_path, exist_ok=True)
            
            # Generate random noise images and solid colors
            bg_count = max(50, total_generated // (len(classes) + 1))
            for i in range(bg_count):
                if random.random() < 0.5:
                    # Random noise
                    bg_img = np.random.randint(0, 256, (image_size[1], image_size[0], 3), dtype=np.uint8)
                else:
                    # Solid color with slight variation
                    color = [random.randint(0, 255) for _ in range(3)]
                    bg_img = np.full((image_size[1], image_size[0], 3), color, dtype=np.uint8)
                    bg_img = cls._add_noise(bg_img)
                    
                cv2.imwrite(os.path.join(bg_out_path, f"bg_{i}.jpg"), bg_img)

        logging.info(f"Dataset generated successfully at '{output_folder}'. Total images: {total_generated + (bg_count if create_background_class else 0)}")
