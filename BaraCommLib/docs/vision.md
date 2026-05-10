# Computer Vision Subsystem

BaraCommLib introduces a revolutionary, "plug-and-play" Computer Vision layer specifically designed for Raspberry Pi robots. 
Training neural networks and running them efficiently on ARM processors is usually a daunting task that involves mastering OpenCV, TensorFlow, PyTorch, and TFLite exports.

We abstracted all this complexity away. You can now generate datasets, train a lightweight transfer-learning model, and run $O(1)$ real-time classifications using fewer than 5 lines of code.

> [!NOTE]
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
> Setting `create_background_class=True` is highly recommended. It prevents your robot from giving false positives when neither the classes are recognized. 

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

> [!IMPORTANT]
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

## Color Tracker (OpenCV Wrapper)

BaraCommLib includes a highly adaptable `ColorTracker` abstraction for OpenCV. This allows you to check if a specific color exists within a specific region of the camera frame.

### Basic Usage

The tracker comes preloaded with **10 common color presets** (red, green, blue, yellow, orange, purple, cyan, magenta, white, black) calibrated for both HSV and BGR/RGB color spaces. You don't need to define them unless you want to override or add new custom colors.

```python
from baracommlib.vision.color_tracker import ColorTracker
import cv2

# Initialize the tracker. 
# It will load the presets automatically.
tracker = ColorTracker()

# If you want to define a custom color or override an existing one:
# custom_colors = {
#     'custom_pink': {
#         'hsv': {'lower': (160, 50, 50), 'upper': (170, 255, 255)},
#         'rgb': {'lower': (255, 100, 200), 'upper': (255, 192, 203)}
#     }
# }
# tracker = ColorTracker(custom_colors)
```

### Checking Regions

To use the tracker, provide the frame and the specific Region Of Interest (ROI) dimensions: `x`, `y`, `width`, `height`. You can also specify the `color_space` ('hsv' is the default and strongly recommended for hardware as it ignores shadows, but 'rgb'/'bgr' is fully supported if you prefer).

```python
# Assuming you have a frame from cv2.VideoCapture or the VisionManager
# Check if the top-right quadrant (e.g., x=320, y=0, w=320, h=240) contains red
has_red = tracker.check_region_color(
    frame=current_frame,
    x=320, y=0, w=320, h=240,
    target_color='red',
    color_space='hsv', # or 'rgb'
    threshold=0.2 # Returns True if color covers >20% of the area
)

if has_red:
    robot.drivetrain.stop()
    print("Red detected in the targeted area!")
```

---

## Advanced Color Tracker Patterns

### Combining with VisionManager

The `ColorTracker` works seamlessly with the `VisionManager` background thread:

```python
from baracommlib import BaraRobot
from baracommlib.vision.color_tracker import ColorTracker

robot = BaraRobot("baraconfig.yaml")
tracker = ColorTracker()

# Get the latest frame from the background camera thread (non-blocking!)
frame = robot.vision.get_latest_frame("main_cam")

if frame is not None:
    # Split screen into 4 quadrants for line following
    h, w = frame.shape[:2]
    
    # Check each quadrant for specific colors
    left quadrant_has_yellow = tracker.check_region_color(
        frame, x=0, y=h//2, w=w//2, h=h//2, 
        target_color="yellow", color_space="hsv"
    )
    
    right_quadrant_has_green = tracker.check_region_color(
        frame, x=w//2, y=h//2, w=w//2, h=h//2, 
        target_color="green", color_space="hsv"
    )
    
    if left_quadrant_has_yellow:
        robot.drivetrain.turn_left_action(50)
    elif right_quadrant_has_green:
        robot.drivetrain.turn_right_action(50)
```

> [!IMPORTANT]
> `get_latest_frame()` is an **O(1)** operation because the VisionManager maintains a shared reference to the latest frame. It never blocks waiting for the camera.

### Adaptive Thresholding

For more nuanced applications, you can dynamically adjust the threshold based on lighting conditions:

```python
import numpy as np

def adaptive_color_check(tracker, frame, region, target_color):
    """Adjusts threshold based on ambient light estimation."""
    # Get average brightness in the region (V channel in HSV)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    region_v = hsv[region[1]:region[1]+region[3], region[0]:region[0]+region[2], 2]
    avg_brightness = np.mean(region_v)
    
    # Darker environment = lower threshold for better detection
    threshold = 0.3 if avg_brightness < 100 else 0.15
    
    return tracker.check_region_color(
        frame, *region, target_color=target_color, 
        color_space="hsv", threshold=threshold
    )
```

### Multi-Color Detection

To detect multiple colors simultaneously without scanning the image twice:

```python
def detect_all_colors(tracker, frame, regions):
    """Checks multiple colors across multiple regions in one pass."""
    detections = {}
    
    for region_name, (x, y, w, h) in regions.items():
        detections[region_name] = {}
        
        for color in ['red', 'green', 'blue']:
            has_color = tracker.check_region_color(
                frame, x, y, w, h, color, color_space='hsv', threshold=0.15
            )
            detections[region_name][color] = has_color
            
    return detections

# Usage
regions = {
    'left': (0, 100, 200, 200),
    'center': (220, 100, 200, 200),
    'right': (440, 100, 200, 200)
}

results = detect_all_colors(tracker, frame, regions)
# Results: {'left': {'red': True, 'green': False, 'blue': False}, ...}
```

---

## Troubleshooting Vision Module

> [!CAUTION]
> **Camera not releasing**: If your program crashes without calling `cleanup()`, the camera device (`/dev/video0`) may remain locked. Kill orphaned Python processes or reboot the Pi to release it.

> [!WARNING]
> **Low FPS on Raspberry Pi**: If inference is slow, ensure your TFLite model is quantized. The `AutoTrainer` does this automatically, but never use a full-precision `model.tflite` on ARM.

> [!TIP]
> **Black frames**: If `classify()` returns `None`, check that your camera's `source` ID in the config matches your actual device (`ls -l /dev/video*`).

> [!NOTE]
> **YUV vs BGR**: OpenCV defaults to BGR, but some USB cameras output YUV. If colors look wrong, the `VisionManager` automatically converts the frame to BGR before inference to ensure consistent results.
