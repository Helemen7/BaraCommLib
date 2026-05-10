# Vision Module

BaraCommLib optionally ships a **computer‑vision** stack based on OpenCV and TensorFlow Lite.
It consists of three main components:
1. :class:`~baracommlib.vision.vision_manager.VisionManager` – background camera capture, model inference thread.
2. :class:`~baracommlib.vision.auto_trainer.AutoTrainer` – command‑line helper that trains a TFLite classifier from an image dataset.
3. :class:`~baracommlib.vision.color_tracker.ColorTracker` – utility for pixel‑level color segmentation used in the example classification script.

> The vision subsystem is entirely optional; it will only start if `configuration.yaml:vision.enabled == true`.  All tests and most core robot logic run fine without any camera hardware.

---
## Class :class:`VisionManager`
```python
from baracommlib.vision import VisionManager
vm = VisionManager(config)          # config comes from ConfigManager
frame = vm.get_latest_frame("main_cam")  # blocking read of the most recent frame
```
| Method | Parameters | Return Value | Description |
|--------|------------|--------------|-------------|
| ``__init__(config: dict, model_path=None)`` | *config*: full YAML config. `model_path` can override the path specified in the configuration for quick experimentation.
|  – | Starts a dedicated thread that continuously polls each configured camera (via OpenCV’s VideoCapture). For every frame it optionally runs TFLite inference if `vision.model_path` is set, and stores both raw frames and processed detection results.
| ``get_latest_frame(cam_id: str) -> np.ndarray`` | *cam_id*: the name defined in config under `cameras`. |
| – | Returns the most recently captured frame (BGR image).  If no camera is available it raises an informative error. |
| ``stop()`` | – | Terminates background thread and releases all VideoCapture objects.

Internally each worker loop performs:
1. Capture frame using `cv2.VideoCapture.read()`.
2. Convert from YUV to BGR if the camera provides that format.
3. If a TFLite model is loaded, it calls :py:meth:`_run_inference` which runs the interpreter and stores predictions in ``self._latest_predictions`` keyed by *cam_id*.
4. Maintains timestamps so callers can verify freshness via `vm.get_frame_age(cam_id)` (not shown here but available).

The class exposes helper attributes like :py:attr:`VisionManager.cameras` for introspection, and a read‑only property ``model_loaded`` that tells whether a TFLite model was successfully loaded.

---
## Class :class:`AutoTrainer`
```python
from baracommlib.vision.auto_trainer import AutoTrainer
AutoTrainer.train_classifier(dataset_folder="ready_dataset", output_model_path="robot_brain.tflite")
```
| Argument | Description |
|----------|-------------|
| ``dataset_folder`` | Path to a folder containing sub‑folders named after each class.  Each subfolder must contain JPEG/PNG images that belong to that label.
| ``output_model_path`` | File path where the converted TFLite model will be written.
| ``epochs``, ``image_size``, ``batch_size`` | Training hyperparameters; defaults are tuned for a small Raspberry‑Pi friendly network but can be overridden via keyword arguments. |

The `train_classifier()` routine performs:
1. Builds a simple CNN (MobileNetV2‑style) using TensorFlow/Keras.
2. Loads the image dataset with ``tf.keras.utils.image_dataset_from_directory``.
3. Trains for *epochs* epochs, optionally fine‑tuning on top of ImageNet weights if `fine_tune=True`.
4. Converts the trained model to a TFLite flatbuffer using TensorFlow Lite converter and writes it out.

The method prints progress bars during training; in headless environments you can suppress them by passing ``verbose=0``.

---
## Class :class:`ColorTracker`
```python
from baracommlib.vision.color_tracker import ColorTracker
tracker = ColorTracker()
has_red = tracker.check_region_color(frame, x=10, y=20, w=50, h=30, target_color="red", color_space='hsv', threshold=0.2)
```
| Method | Parameters | Return Value |
|--------|------------|--------------|
| ``__init__(custom_bounds=None)`` | Optional dictionary to add or override HSV/BGR bounds for custom colors.
|  – | Stores default presets (red, green …).  If `custom_bounds` is provided it merges into the preset map. |
| ``check_region_color(frame, x, y, w, h, target_color, color_space='hsv', threshold=0.2)`` | *frame*: OpenCV BGR image; ROI coordinates and size; name of a predefined or custom colour.
|  – | Returns `True` if the selected region contains more than ``threshold`` fraction (default 20%) of pixels within the specified color bounds, otherwise `False`. |
|
The method works as follows:
1. **Bounds lookup** – finds HSV/BGR limits for *target_color*; raises :class:`ValueError` if not defined.
2. Extracts ROI (`frame[y:y+h, x:x+w]`).
3. Converts to the requested color space (HSV via `cv2.cvtColor`; BGR stays as‑is).
4. Builds a mask with ``cv2.inRange`` and counts non‑zero pixels using :func:`cv2.countNonZero`.
5. Computes ratio of masked area to total ROI size; compares against *threshold*.

The class also exposes `get_available_colors()` which returns the list of colour names currently registered (the defaults plus any custom additions).

---
## Integrating Vision into Your Robot
1. **Enable** in your YAML: ``vision.enabled:true`` and provide a valid TFLite model path.
2. Create a :class:`VisionManager` instance after the robot is initialised:
   ```python
   vm = VisionManager(robot.config)
   frame = vm.get_latest_frame("main_cam")
   predictions = vm.last_predictions["main_cam"]  # dict with class labels and probabilities.
   ```
3. Use the `predictions` dictionary to make high‑level decisions (e.g., stop if a red ball is detected).

Because all camera work happens in background threads, your main loop remains lightweight – you simply poll for new frames or predictions at whatever frequency makes sense.
