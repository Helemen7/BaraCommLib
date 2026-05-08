import os
import json
import logging
from typing import Tuple
import sys

# Suppress scary C++ TensorFlow warnings and info logs before importing TF
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 

try:
    import tensorflow as tf
    tf.get_logger().setLevel('ERROR') # Suppress TF Python warnings
    
    # Suppress absl warnings (often used by TFLite converter)
    import absl.logging
    absl.logging.set_verbosity(absl.logging.ERROR)
    
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
                         output_model_path: str = "robot_brain.tflite", 
                         epochs: int = 10,
                         image_size: Tuple[int, int] = (224, 224),
                         batch_size: int = 32,
                         fine_tune: bool = False,
                         early_stop_at_98: bool = True):
        """
        Automatically trains a computer vision model using transfer learning.
        
        Args:
            dataset_folder: Path to the generated dataset (folders = class names)
            output_model_path: Path where the .tflite model will be saved
            epochs: Number of training iterations
            image_size: Target resolution (must match what DatasetTool used)
            batch_size: Number of images to process at once
            fine_tune: Perform a secondary fine-tuning phase
            early_stop_at_98: Stop training early if accuracy reaches 98%
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

        callbacks = []
        if early_stop_at_98:
            # Custom callback to stop at 98% accuracy
            class EarlyStopAt98(tf.keras.callbacks.Callback):
                def on_epoch_end(self, epoch, logs=None):
                    if logs is None:
                        logs = {}
                    # Check both accuracy and val_accuracy
                    if logs.get('accuracy', 0) >= 0.98 and logs.get('val_accuracy', 0) >= 0.98:
                        logging.info(f"\nReached 98% accuracy at epoch {epoch+1}. Stopping early to prevent overfitting!")
                        self.model.stop_training = True

            callbacks.append(EarlyStopAt98())

        logging.info(f"Starting training for {epochs} epochs...")
        
        model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=epochs,
            callbacks=callbacks
        )

        # Fine tuning (optional, but greatly improves accuracy for similar objects)
        if fine_tune:
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
                epochs=max(1, int(epochs * 0.5)), # fewer epochs for fine tuning
                callbacks=callbacks
            )

        logging.info("Training complete. Converting to optimized TFLite model...")
        
        # Save temporarily to disk to avoid 'NoneType' object is not callable in newer TF versions
        import tempfile
        import shutil
        import sys
        
        temp_dir = tempfile.mkdtemp()
        
        # C-level stdout/stderr silencing to block absl and tf_tfl_flatbuffer_helpers C++ spam
        devnull_fd = os.open(os.devnull, os.O_WRONLY)
        old_stdout_fd = os.dup(1)
        old_stderr_fd = os.dup(2)
        
        try:
            os.dup2(devnull_fd, 1)
            os.dup2(devnull_fd, 2)
            
            model.export(temp_dir)
            converter = tf.lite.TFLiteConverter.from_saved_model(temp_dir)
            # Optimize for speed / size
            converter.optimizations = [tf.lite.Optimize.DEFAULT]
            tflite_model = converter.convert()

            with open(output_model_path, 'wb') as f:
                f.write(tflite_model)
                
        finally:
            # Restore stdout/stderr and close devnull
            os.dup2(old_stdout_fd, 1)
            os.dup2(old_stderr_fd, 2)
            os.close(old_stdout_fd)
            os.close(old_stderr_fd)
            os.close(devnull_fd)
            shutil.rmtree(temp_dir, ignore_errors=True)
            
        logging.info(f"Model saved successfully to {output_model_path}")
        logging.info(f"Labels saved successfully to {labels_path}")
        logging.info("You can now copy these files to your robot for inference!")
