import os
import json
import logging
from typing import Tuple

try:
    import tensorflow as tf
    from tensorflow.keras.applications import MobileNetV2
    from tensorflow.keras.layers import Dense, GlobalAveragePooling2D, Dropout
    from tensorflow.keras.models import Model
except ImportError:
    logging.warning("TensorFlow not found. Please install it to train models: pip install tensorflow")

class AutoTrainer:
    """
    A 1-click trainer for Transfer Learning on Raspberry Pi robots.
    It takes an augmented dataset, trains a lightweight MobileNetV2 model,
    and exports a highly optimized .tflite file and a labels.json file.
    This shouldn't be in the same script as your robot's code, as training
    is only requested once for a vision need.
    """

    @classmethod
    def train_classifier(cls, 
                         dataset_folder: str, 
                         output_model_path: str = "robot_model.tflite", 
                         epochs: int = 10,
                         image_size: Tuple[int, int] = (224, 224),
                         batch_size: int = 32):
        """
        Automatically trains a computer vision model using transfer learning.
        
        Args:
            dataset_folder: Path to the generated dataset (folders = class names)
            output_model_path: Path where the .tflite model will be saved
            epochs: Number of training iterations
            image_size: Target resolution (must match what DatasetTool used)
            batch_size: Number of images to process at once
        """
        if not os.path.exists(dataset_folder):
            raise FileNotFoundError(f"Dataset folder '{dataset_folder}' not found.")

        logging.info("Loading dataset...")
        
        # Load dataset with 80/20 train/validation split
        train_ds = tf.keras.utils.image_dataset_from_directory(
            dataset_folder,
            validation_split=0.2,
            subset="training",
            seed=123,
            image_size=image_size,
            batch_size=batch_size
        )
        
        val_ds = tf.keras.utils.image_dataset_from_directory(
            dataset_folder,
            validation_split=0.2,
            subset="validation",
            seed=123,
            image_size=image_size,
            batch_size=batch_size
        )

        class_names = train_ds.class_names
        num_classes = len(class_names)
        logging.info(f"Found {num_classes} classes: {class_names}")

        # Save class names alongside the model for the VisionManager to use later
        base_path = os.path.splitext(output_model_path)[0]
        labels_path = f"{base_path}_labels.json"
        with open(labels_path, "w") as f:
            json.dump(class_names, f)

        # Prefetching for performance
        AUTOTUNE = tf.data.AUTOTUNE
        train_ds = train_ds.prefetch(buffer_size=AUTOTUNE)
        val_ds = val_ds.prefetch(buffer_size=AUTOTUNE)

        logging.info("Building lightweight MobileNetV2 model...")
        
        # Base Model: MobileNetV2 (very fast on ARM/Raspberry Pi)
        # We exclude the top classification layer to add our own
        base_model = MobileNetV2(
            input_shape=image_size + (3,),
            include_top=False,
            weights='imagenet'
        )
        base_model.trainable = False # Freeze base weights

        # Build custom top layers
        # MobileNet expects inputs [-1, 1], so we use a Rescaling layer to map [0, 255] -> [-1, 1]
        inputs = tf.keras.Input(shape=image_size + (3,))
        x = tf.keras.layers.Rescaling(1./127.5, offset=-1)(inputs)
        x = base_model(x, training=False)
        x = GlobalAveragePooling2D()(x)
        x = Dropout(0.2)(x)
        outputs = Dense(num_classes, activation='softmax')(x)
        
        model = Model(inputs, outputs)

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
            loss=tf.keras.losses.SparseCategoricalCrossentropy(),
            metrics=['accuracy']
        )

        logging.info(f"Starting training for {epochs} epochs...")
        
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs
        )

        # Fine tuning (optional, but greatly improves accuracy for similar objects)
        logging.info("Fine-tuning top layers...")
        base_model.trainable = True
        # Freeze all but the last 20 layers
        for layer in base_model.layers[:-20]:
            layer.trainable = False

        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001), # Much slower learning rate
            loss=tf.keras.losses.SparseCategoricalCrossentropy(),
            metrics=['accuracy']
        )
        
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=int(epochs * 0.5) # fewer epochs for fine tuning
        )

        logging.info("Training complete. Converting to optimized TFLite model...")
        
        converter = tf.lite.TFLiteConverter.from_keras_model(model)
        # Optimize for speed / size
        converter.optimizations = [tf.lite.Optimize.DEFAULT]
        tflite_model = converter.convert()

        with open(output_model_path, 'wb') as f:
            f.write(tflite_model)
            
        logging.info(f"Model saved successfully to {output_model_path}")
        logging.info(f"Labels saved successfully to {labels_path}")
        logging.info("You can now copy these files to your robot for inference!")
