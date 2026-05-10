# Computer Vision & AI Subsystem

BaraCommLib provides a complete computer vision pipeline for Raspberry Pi robots: dataset generation, transfer learning training, and real-time inference - all optimized for ARM processors.

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PC Development Tools                     │
│  ┌──────────────────┐         ┌─────────────────────────┐   │
│  │   DatasetTool    │───────▶│     AutoTrainer         │   │
│  │                  │         │                         │   │
│  │ • Data           │         │ • Downloads MobileNetV2 │   │
│  │   Augmentation   │         │ • Freezes base layers   │   │
│  │ • Generates      │         │ • Trains custom head    │   │
│  │   variants       │         │ • Exports TFLite        │   │
│  └──────────────────┘         └─────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   Raspberry Pi Runtime                      │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              VisionManager (Background Thread)       │   │
│  │  ┌──────────────┐    ┌────────────────────────────┐  │   │
│  │  │ Camera Poll  │──▶│   TFLite Inference         │  │   │
│  │  │ (O(1) Cache) │    │   (20-50ms on RPi 5)       │  │   │ 
│  │  └──────────────┘    └────────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## Part 1: Dataset Generation (PC Tools)

### `DatasetTool` - Automatic Data Augmentation

Deep learning models need hundreds of training images. `DatasetTool` automatically generates variations from a few raw photos.

#### Usage

```python
from baracommlib.vision import DatasetTool

# Organize your raw photos:
# raw_data/
# ├── red_ball/
# │   ├── img1.jpg
# │   └── img2.jpg
# └── soda_can/
#     └── can1.jpg

DatasetTool.generate(
    input_folder="raw_data",              # Folder with your photos
    output_folder="ready_dataset",        # Output folder (auto-created)
    image_size=(224, 224),                # Required: MobileNetV2 input size
    variants_per_image=50,                # Generate 50 variations per photo
    create_background_class=True          # Add "background" class (recommended!)
)

print("Dataset generated!")
# Output folder structure:
# ready_dataset/
# ├── red_ball/
# │   ├── img1_v0.jpg
# │   ├── img1_v1.jpg
# │   └── ...
# ├── soda_can/
# └── background/  # Noise-only images for "nothing detected" cases
```

#### Data Augmentation Techniques

`DatasetTool` applies these transformations automatically:
- **Rotation**: ±360° in random increments
- **Brightness**: -50% to +150%
- **Contrast**: Variable adjustments
- **Noise**: Gaussian and salt-and-pepper noise
- **Blur**: Motion blur simulation
- **Color jitter**: Hue/saturation shifts

> [!TIP]
> Setting `create_background_class=True` is crucial. It prevents false positives when neither object class is recognized by teaching the model what "empty scene" looks like.

---

## Part 2: Transfer Learning Training (PC Tools)

### `AutoTrainer` - One-Click Model Training

Automatically downloads MobileNetV2, freezes base layers, and trains custom classification head.

#### Usage

```python
from baracommlib.vision import AutoTrainer

# Train your classifier
AutoTrainer.train_classifier(
    dataset_folder="ready_dataset",      # Output from DatasetTool
    output_model_path="robot_brain.tflite",  # Save location on PC
    epochs=10                            # Training iterations (higher = better accuracy)
)

print("Training complete!")
# Generated files:
# • robot_brain.tflite          # Optimized model for Raspberry Pi
# • robot_brain_labels.json     # Class names mapping
```

#### Training Process

1. **Downloads MobileNetV2**: Lightweight architecture (5MB, ~7.4M params)
2. **Freezes base layers**: Pre-trained ImageNet weights remain frozen
3. **Attaches custom head**: New classification layer for your classes
4. **Trains with transfer learning**: Only trains new layers (~10-60 minutes)

#### Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `epochs` | 10 | Number of training iterations (5-20 recommended) |
| `batch_size` | 32 | Images per batch (adjust for GPU memory) |
| `learning_rate` | 0.001 | Training step size |

> [!IMPORTANT]
> Copy **both** generated files to your Raspberry Pi:
> - `robot_brain.tflite` (the model)
> - `robot_brain_labels.json` (class names)

---

## Part 3: Real-Time Inference (Robot Runtime)

### VisionManager Configuration

Add vision to your `baraconfig.yaml`:

```yaml
vision:
  enabled: true                          # Enable vision subsystem
  model_path: "robot_brain.tflite"       # Path to TFLite model
  cameras:
    - id: "main_cam"                     # Unique camera identifier
      source: 0                          # Camera device (0=/dev/video0, 1=/dev/video1)
      resolution: [640, 480]             # Force this capture size
```

### Basic Usage

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Vision is automatically initialized by BaraRobot constructor!

while True:
    # Instant O(1) classification (no blocking!)
    result = robot.vision.classify("main_cam")
    
    if "error" not in result:
        label = result["label"]
        confidence = result["confidence"]  # 0.0 to 1.0
        
        print(f"I see a {label} ({confidence*100:.1f}% confident)")
        
        # React to detections
        if label == "red_ball" and confidence > 0.85:
            robot.drivetrain.move_forward_action(60)
        elif label == "background":
            robot.drivetrain.coast()  # Nothing detected
            
    time.sleep(0.1)  # Limit to ~10 FPS (adjust for your needs)
```

### Classification Result Format

```python
result = {
    "label": "red_ball",              # Detected class name from labels.json
    "confidence": 0.92,               # Probability score (0-1)
    "inference_time_ms": 35.4         # Time taken for inference
}

# Error cases:
result = {
    "error": "No frame available from camera 'main_cam'."
}
```

---

## Color Tracking System

BaraCommLib includes a robust color detection system using OpenCV's HSV/BGR color spaces.

### Built-in Color Presets

10 pre-calibrated colors for both HSV and BGR:

| Color | HSV Range | Use Case |
|-------|-----------|----------|
| Red | 0-10, 120-255, 70-255 | Traffic lights, markers |
| Green | 40-90, 50-255, 50-255 | Plants, targets |
| Blue | 100-140, 150-255, 0-255 | Water, sky detection |
| Yellow | 20-40, 100-255, 100-255 | Warnings, markers |
| Orange | 10-25, 100-255, 100-255 | Construction, safety |
| Purple | 130-160, 50-255, 50-255 | Rare targets |
| Cyan | 80-100, 100-255, 100-255 | Water, screens |
| Magenta | 140-170, 100-255, 100-255 | Markers, indicators |
| White | 0-180, 0-30, 200-255 | Surfaces, clouds |
| Black | 0-180, 0-255, 0-50 | Text, shadows |

### ColorTracker Usage

```python
from baracommlib.vision.color_tracker import ColorTracker
import cv2

# Initialize with default presets
tracker = ColorTracker()

# Check if a color exists in a region of interest (ROI)
has_red = tracker.check_region_color(
    frame=current_frame,           # OpenCV BGR numpy array
    x=320, y=0, w=320, h=240,      # ROI: top-right quadrant
    target_color='red',            # Color name from presets
    color_space='hsv',             # 'hsv' (recommended) or 'bgr'/'rgb'
    threshold=0.2                  # True if >20% of area matches
)

if has_red:
    robot.drivetrain.stop()
    print("Red detected in target area!")
```

### Custom Color Definitions

Override presets or add new colors:

```python
custom_colors = {
    'my_pink': {
        'hsv': {'lower': (160, 50, 50), 'upper': (170, 255, 255)},
        'bgr': {'lower': (255, 100, 200), 'upper': (255, 192, 203)}
    },
    'custom_blue': {
        'hsv': {'lower': (100, 80, 40), 'upper': (130, 255, 255)},
        # No BGR bounds - will use HSV only
    }
}

tracker = ColorTracker(custom_colors)

# Now 'my_pink' and 'custom_blue' are available
has_custom = tracker.check_region_color(
    frame, x=0, y=0, w=320, h=240,
    target_color='my_pink', color_space='hsv'
)
```

### Advanced Color Tracking Patterns

#### Multi-Region Detection

Check multiple colors across different screen regions:

```python
def scan_for_colors(tracker, frame):
    """Scan 4 quadrants for specific colors."""
    h, w = frame.shape[:2]
    
    results = {}
    
    # Top-left quadrant - look for yellow
    results['top_left_yellow'] = tracker.check_region_color(
        frame, x=0, y=0, w=w//2, h=h//2,
        target_color='yellow', color_space='hsv'
    )
    
    # Bottom-right - look for green
    results['bottom_right_green'] = tracker.check_region_color(
        frame, x=w//2, y=h//2, w=w//2, h=h//2,
        target_color='green', color_space='hsv'
    )
    
    return results

# Usage in main loop
color_scan = scan_for_colors(tracker, robot.vision.get_latest_frame("main_cam"))
if color_scan['top_left_yellow']:
    print("Yellow detected top-left!")
```

#### Adaptive Thresholding

Adjust detection sensitivity based on lighting conditions:

```python
import numpy as np

def adaptive_color_check(tracker, frame, region, target_color):
    """Dynamically adjust threshold based on ambient light."""
    x, y, w, h = region
    
    # Get average brightness in ROI (V channel in HSV)
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    roi_v = hsv[y:y+h, x:x+w, 2]
    avg_brightness = np.mean(roi_v)
    
    # Darker environment = lower threshold for better detection
    if avg_brightness < 80:
        threshold = 0.15  # Low light - be more permissive
    elif avg_brightness < 150:
        threshold = 0.2   # Normal lighting
    else:
        threshold = 0.3   # Bright - require stronger match
    
    return tracker.check_region_color(
        frame, x, y, w, h, target_color, 
        color_space='hsv', threshold=threshold
    )

# Usage
if adaptive_color_check(tracker, frame, (0, 100, 200, 200), 'red'):
    print("Red detected with adaptive threshold!")
```

#### Line Following with Color

Detect colored lines for navigation:

```python
def follow_colored_line(tracker, frame):
    """Follow a red line using center sensor."""
    h, w = frame.shape[:2]
    
    # Check center region for red line
    has_red = tracker.check_region_color(
        frame, x=w//2-50, y=h//2-10, w=100, h=20,
        target_color='red', color_space='hsv', threshold=0.3
    )
    
    if has_red:
        robot.drivetrain.move_forward_action(50)
    else:
        robot.drivetrain.coast()  # Lost the line

follow_colored_line(tracker, robot.vision.get_latest_frame("main_cam"))
```

---

## Camera Configuration Options

### Resolution Settings

Force specific capture resolution for optimal performance:

```yaml
cameras:
  - id: "main_cam"
    source: 0
    resolution: [320, 240]   # Lower res = faster inference on RPi
```

> [!TIP]
> Smaller resolutions (320x240) work well for object classification. Use 640x480 or higher only if you need detailed visual analysis.

### Multiple Cameras

Support for multiple camera inputs:

```yaml
vision:
  enabled: true
  model_path: "robot_brain.tflite"
  cameras:
    - id: "front_cam"
      source: 0
      resolution: [640, 480]
    - id: "side_cam"
      source: 1
      resolution: [320, 240]

# Usage
front_result = robot.vision.classify("front_cam")
side_result = robot.vision.classify("side_cam")
```

---

## Performance Optimization

### Inference Speed Guidelines

| RPi Model | Resolution | Expected FPS |
|-----------|------------|--------------|
| RPi 3 B+ | 320x240    | ~5-8 FPS     |
| RPi 4 (4GB) | 640x480   | ~15-20 FPS   |
| RPi 5 | 640x480    | ~25-35 FPS   |

### Tips for Better Performance

1. **Use quantized TFLite models**: `AutoTrainer` exports int8 by default
2. **Lower resolution**: 320x240 is often sufficient for classification
3. **Limit update rate**: Don't call `classify()` every frame - throttle to 5-15 FPS
4. **Use background thread**: `get_latest_frame()` is O(1) and non-blocking

```python
# Throttled inference (recommended pattern)
last_inference = 0
while True:
    current_time = time.time()
    
    if current_time - last_inference > 0.1:  # Max 10 FPS
        result = robot.vision.classify("main_cam")
        last_inference = current_time
        
        # Process result...
        
    time.sleep(0.02)  # Cap at ~50 FPS max loop rate
```

---

## Troubleshooting

### "Model file not found"
- Ensure `robot_brain.tflite` is in the same directory as your script
- Verify file was copied from PC to Pi (both model AND labels.json required)

### Camera returns black frames
- Check camera source ID: `ls -l /dev/video*`
- Verify USB camera is powered and connected
- Try different resolution settings

### Low FPS / Slow inference
- Use smaller resolution in config
- Ensure model is quantized (check file size: ~2MB for int8 vs ~4MB for float32)
- Close other CPU-intensive applications

### Colors look wrong
- OpenCV uses BGR by default, not RGB
- Always use `color_space='hsv'` for best results (lighting-invariant)
- Check if camera outputs YUV instead of BGR (rare USB cameras)

---

## Related Documentation

- [PID Controller](./pid_io.md) - Combine vision with precise movement
- [State Machine](./pid_io.md#state-machine) - Organize vision-based behaviors
- [Obstacle Avoidance](../pid_io.md#obstacle-avoidance) - Multi-sensor fusion patterns