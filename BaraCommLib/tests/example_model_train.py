import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from baracommlib.vision import AutoTrainer

def main():
    print("--- Vision Module: Model Training Example ---")
    
    dataset_folder = "ready_dataset"
    output_model = "robot_brain.tflite"
    
    if not os.path.exists(dataset_folder):
        print(f"Error: Dataset folder '{dataset_folder}' not found.")
        print("Please run example_dataset_gen.py first and ensure there are generated images.")
        return
        
    print(f"Starting AutoTrainer on dataset '{dataset_folder}'...")
    print("This might take a few minutes depending on your PC.")
    
    try:
        AutoTrainer.train_classifier(
            dataset_folder=dataset_folder,
            output_model_path=output_model,
            epochs=5, # Number of training passes. Increase to 10-20 for better accuracy
            image_size=(224, 224),
            batch_size=16
        )
        print(f"\nTraining completed! Your model is saved as '{output_model}'.")
        print("You can now move this model to your Raspberry Pi.")
    except Exception as e:
        print(f"Error during training: {e}")

if __name__ == "__main__":
    main()
