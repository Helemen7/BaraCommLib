import os
import sys

# Temporarily add the library to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from baracommlib.vision import DatasetTool

def main():
    print("--- Vision Module: Dataset Generation Example ---")
    
    # We will create a dummy raw_data folder to demonstrate
    # In reality, you would manually put photos of objects in these folders
    input_folder = "raw_data"
    os.makedirs(os.path.join(input_folder, "red_ball"), exist_ok=True)
    os.makedirs(os.path.join(input_folder, "soda_can"), exist_ok=True)
    
    print(f"Please place at least one .jpg image in '{input_folder}/red_ball' and '{input_folder}/soda_can'.")
    print("If you just want to test without images, it will print an error, but the code structure is correct.")
    
    output_folder = "ready_dataset"
    
    try:
        DatasetTool.generate(
            input_folder=input_folder,
            output_folder=output_folder,
            image_size=(224, 224),
            variants_per_image=10, # Generate 10 variations per photo (rotations, noise, brightness)
            create_background_class=True # Auto-generate a "background" class with noise
        )
        print("\nDataset generation finished! Check the 'ready_dataset' folder.")
    except Exception as e:
        print(f"Error during generation: {e}")

if __name__ == "__main__":
    main()
