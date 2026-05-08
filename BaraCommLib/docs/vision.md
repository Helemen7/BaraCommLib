# Computer Vision Subsystem

BaraCommLib introduces a revolutionary, "plug-and-play" Computer Vision layer specifically designed for Raspberry Pi robots. 
Training neural networks and running them efficiently on ARM processors is usually a daunting task that involves mastering OpenCV, TensorFlow, PyTorch, and TFLite exports.

We abstracted all this complexity away. You can now generate datasets, train a lightweight transfer-learning model, and run $O(1)$ real-time classifications using fewer than 5 lines of code.

> [!INFO]
> The Vision module is divided into two distinct parts:
> 1. **PC Tools**: `DatasetTool` and `AutoTrainer` (Used on your powerful computer to prepare the AI).
> 2. **Robot API**: The `robot.vision` object (Used on the Raspberry Pi for instant inference).

---

## 1. Preparing the Dataset (`DatasetTool`)
Deep learning models need hundreds of images to understand what an object looks like under different lighting or angles. Capturing hundreds of photos manually is tedious.

The `DatasetTool` automatically performs **Data Augmentation**. You just provide a few raw photos of your objects, and it will artificially generate thousands of variations (rotated, noisy, brightened).

### Usage (Run this on your PC)
Organize your raw photos in folders named after the classes you want to detect:
```text
raw_data/
├── red_ball/
│   ├── img1.jpg
│   └── img2.jpg
└── soda_can/
    └── can1.jpg
```

Then, run the generator:
```python
from baracommlib.vision import DatasetTool

DatasetTool.generate(
    input_folder="raw_data", 
    output_folder="ready_dataset", 
    image_size=(224, 224),          # Required resolution for MobileNetV2
    variants_per_image=50,          # Generates 50 new images from each raw photo
    create_background_class=True    # Auto-generates a "background" class with noise
)
```

> [!TIP]
> Setting `create_background_class=True` is highly recommended. It prevents your robot from giving false positives when neither the ball nor the can are in the camera's view.

---

## 2. 1-Click Transfer Learning (`AutoTrainer`)
Once your `ready_dataset` is generated, you need to train a Neural Network. 
`AutoTrainer` automatically downloads a lightweight `MobileNetV2` architecture, freezes its core layers, attaches custom layers for your specific classes, and trains them using Transfer Learning.

### Usage (Run this on your PC)
```python
from baracommlib.vision import AutoTrainer

AutoTrainer.train_classifier(
    dataset_folder="ready_dataset",
    output_model_path="robot_brain.tflite",
    epochs=10 # Higher epochs = better accuracy, but longer training time
)
```

> [!SUCCESS]
> The script will output two files: `robot_brain.tflite` (the optimized Neural Network) and `robot_brain_labels.json` (the text names of your classes). Copy **both** of these files to your Raspberry Pi!

---

## 3. Real-Time Inference on the Robot (`BaraRobot`)

> [!WARNING]
> Before writing code, ensure you have enabled vision in your `baraconfig.yaml` and specified the path to your `.tflite` model. The labels JSON must be in the same folder.

**baraconfig.yaml:**
```yaml
vision:
  enabled: true 
  model_path: "robot_brain.tflite" 
  cameras:
    - id: "main_cam"
      source: 0 # 0 for USB/CSI Camera
      resolution: [640, 480]
```

### Usage (Run this on your Raspberry Pi)
Reading from a camera with OpenCV is inherently blocking. BaraCommLib solves this by launching a dedicated background thread that continuously polls the camera. 

When you call `classify()`, you get the inference of the absolute latest frame in $O(1)$ time, preventing your main motor/PID loops from stuttering.

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# The model and camera threads are already loaded by the BaraRobot constructor!

while True:
    # Instant classification
    result = robot.vision.classify("main_cam")
    
    if "error" not in result:
        label = result["label"]
        confidence = result["confidence"]
        
        print(f"I see a {label} with {confidence*100:.1f}% certainty!")
        
        if label == "red_ball" and confidence > 0.85:
            robot.drivetrain.move_forward_action(50)
        elif label == "background":
            robot.drivetrain.coast()
```

> [!CAUTION]
> Because camera threads hold system hardware resources, always ensure you call `robot.cleanup()` when your program exits to safely release `/dev/video0`.
