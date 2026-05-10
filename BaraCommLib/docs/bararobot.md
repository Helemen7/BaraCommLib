# BaraRobot Class - Complete API Reference

The `BaraRobot` class is the main entry point of BaraCommLib, providing a unified interface to all robot subsystems. It abstracts hardware complexity and offers a "commercial-grade" ready-to-use API.

---

## Quick Start

```python
from baracommlib.BaraRobot import BaraRobot

# Initialize - auto-loads config, validates pins, starts motors/sensors/vision
robot = BaraRobot("baraconfig.yaml")

try:
    while True:
        # Access all subsystems instantly
        distance = robot.sensor.get("front_tof")
        gyro = robot.sensor.get("main_gyro")
        
        if distance < 100:
            robot.drivetrain.coast()
            
except KeyboardInterrupt:
    pass
finally:
    robot.cleanup()  # ← CRITICAL! Releases all hardware resources
```

---

## Initialization

### Constructor

```python
BaraRobot(config_filepath: str = "baraconfig.yaml")
```

**Parameters:**
- `config_filepath`: Path to YAML configuration file (default: `"baraconfig.yaml"`)

**What happens during initialization:**
1. Loads and validates `baraconfig.yaml` via `ConfigManager`
2. Initializes `Motors` with drivetrain configuration
3. Sets up GPIO pins for all devices (motors, sensors, buttons, LEDs)
4. Starts background I2C threads for all sensors
5. If vision enabled: loads TFLite model and starts camera threads
6. Initializes IO devices (LEDs, buzzers, button listeners)

**Raises:**
- `RuntimeError`: Configuration validation failed
- `FileNotFoundError`: Config file missing (will create from default template)

---

## Drivetrain Access (`robot.drivetrain`)

Access to the `Motors` class for all movement control:

```python
# Basic actions
robot.drivetrain.move_forward_action(80)
robot.drivetrain.turn_left_action(50)
robot.drivetrain.coast()

# Encoder-based precision
robot.drivetrain.drive_distance(distance_mm=1000)
robot.drivetrain.spin(degrees=90, use_gyro=True)

# Manual control
from baracommlib.Motors import Motor
robot.drivetrain.assign_manual_power(Motor.A, power=70)

# Diagnostics
status = robot.drivetrain.get_status()  # Full motor state info
health_ok = robot.drivetrain.health_check()
```

**See [Motors Guide](./motors.md)** for complete API reference.

---

## Sensor Access (`robot.sensor`)

Proxy interface to `SensorsManager` providing instant O(1) sensor access:

### Methods

#### `get(sensor_id: str)` - Single Sensor Reading

Returns the latest cached value for a specific sensor.

```python
# ToF distance
distance = robot.sensor.get("front_tof")  # Returns: float (cm) or None

# IMU orientation  
gyro = robot.sensor.get("main_gyro")      # Returns: dict {'yaw': ..., 'pitch': ..., 'roll': ...}

# Check validity
if distance is not None and distance > 0:
    print(f"Distance: {distance:.1f} cm")
```

**Returns:** Sensor value or `None` if reading failed/invalid

#### `get_by_direction(direction: str)` - Grouped Access

Fetches all sensors grouped under a logical direction.

```python
# Get all front-facing sensors as dictionary
front_dict = robot.sensor.get_by_direction("front")
print(front_dict)  # {"front_left": 120, "front_right": 125}

# Works with any direction from config
diagonal = robot.sensor.get_by_direction("diagonal_right")
```

**Returns:** `dict[str, Any]` mapping sensor IDs to values

#### `get_average_by_direction(direction: str)` - Robust Averaging

Averages all valid numerical readings for a direction, filtering out failures.

```python
avg_dist = robot.sensor.get_average_by_direction("front")

if avg_dist is not None and avg_dist < 100:
    print("Wall detected!")
else:
    print("No obstacle or no valid readings")
```

**Returns:** `float` (average) or `None` if no valid readings

#### `get_sensor(sensor_id: str)` - Get Sensor Object

Returns the actual sensor object for advanced operations.

```python
sensor_obj = robot.sensor.get_sensor("front_tof")

# Check reading age
age = sensor_obj.get_reading_age()  # Returns: float (seconds) or inf

if age > 0.5:
    print(f"Warning: Sensor stale ({age:.1f}s)")

# Pause/resume individual sensors
sensor_obj.pause()   # Stop polling to save CPU
sensor_obj.resume()  # Resume polling
```

**Returns:** `AbstractSensor` object or `None` if not found

---

## Vision Access (`robot.vision`)

Access to the `VisionManager` for computer vision operations:

### When Available

Vision is only initialized if `vision.enabled: true` in config. Check with:

```python
if robot.vision:
    # Vision subsystem available
else:
    print("Vision not enabled in configuration")
```

### Methods

#### `classify(cam_id: str)` - Object Classification

Runs TFLite inference on the latest camera frame.

```python
result = robot.vision.classify("main_cam")

if "error" not in result:
    label = result["label"]
    confidence = result["confidence"]  # 0.0 to 1.0
    
    print(f"I see a {label} ({confidence*100:.1f}% confident)")
    
    if label == "red_ball" and confidence > 0.85:
        robot.drivetrain.move_forward_action(60)

# Error case
if "error" in result:
    print(f"Error: {result['error']}")
```

**Returns:** `dict` with keys:
- `"label"`: Detected class name (or error message)
- `"confidence"`: Probability score (0.0-1.0)
- `"inference_time_ms"`: Time taken for inference

#### `get_latest_frame(cam_id: str)` - Non-Blocking Frame Access

Returns the latest OpenCV frame without blocking the main loop.

```python
frame = robot.vision.get_latest_frame("main_cam")

if frame is not None:
    # Process frame with OpenCV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    # ... your vision logic
    
# Frame may be None if camera hasn't captured yet or stopped
```

**Returns:** `numpy.ndarray` (BGR image) or `None`

#### `stop_all()` - Graceful Shutdown

Stops all camera threads and releases hardware resources.

```python
try:
    while True:
        pass  # Your main loop
except KeyboardInterrupt:
    robot.vision.stop_all()  # Release /dev/video* devices
finally:
    robot.cleanup()  # Full cleanup including vision
```

**See [Vision Guide](../vision.md)** for complete API reference.

---

## IO Access (`robot.io`)

Access to the `IOManager` for LEDs, buzzers, and button handling:

### Methods

#### `led(led_id: str, on: bool = True, brightness: int = 100)` - Quick LED Control

```python
# Turn LED on/off
robot.io.led("status", on=True)
robot.io.led("power", on=False)

# Dimmable PWM LEDs (brightness: 0-100)
robot.io.led("breathing", on=50)  # 50% brightness
```

#### `beep(buzzer_id: str, duration_ms: int = 100)` - Quick Beep

```python
# Short alert
robot.io.beep("alarm", duration_ms=200)

# Longer tone
robot.io.beep("alarm", duration_ms=500)
```

#### `get_led(led_id: str)` / `get_buzzer(buzzer_id: str)` - Get Device Object

Returns the actual device object for advanced control.

```python
status_led = robot.io.get_led("status")
if status_led:
    status_led.blink(times=3, duration_ms=150)  # Blink 3 times
    
alarm = robot.io.get_buzzer("alarm")
if alarm:
    alarm.play_sequence([(440, 200), (880, 200)])  # Two-tone sequence
```

**See [IO Devices](../pid_io.md)** for complete API reference.

---

## Button Handling

### Decorator: `@robot.on_button_pressed(button_id)`

Register a callback that runs when a button is pressed. Handles debouncing automatically in a background thread.

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Define your callback function
@robot.on_button_pressed("start")
def start_routine():
    print("Start button pressed!")
    robot.drivetrain.move_forward_action(80)

# The library automatically:
# - Creates a background thread to monitor the button
# - Debounces mechanical contact (configurable delay)
# - Calls your function only once per press
```

**Parameters:**
- `button_id`: Must match `"id"` field in config under `io.buttons`

**Returns:** The decorated function (for chaining)

### Synchronous Check: `is_button_pressed(button_id)`

Check button state within a loop or state machine.

```python
if robot.is_button_pressed("start"):
    print("Button is currently being held down")
    
# Returns True if active, False otherwise
```

---

## Turn Method (`robot.turn`)

Execute precise relative turns using the IMU/gyroscope:

```python
# Turn RIGHT by 90 degrees at base speed with 2° tolerance
robot.turn(angle=90.0, speed=50, tolerance=2.0)

# Turn LEFT by 45 degrees (negative angle = left turn)
robot.turn(angle=-45.0)  # Uses base_speed and default 2° tolerance
```

**Parameters:**
- `angle`: Degrees to turn (positive = right, negative = left)
- `speed`: Movement speed (default: from config `base_speed`)
- `tolerance`: Stop when within this many degrees of target (default: 2.0°)

**Raises:**
- `RuntimeError`: No IMU configured or gyro reading unavailable

---

## Cleanup Method (`robot.cleanup()`)

**CRITICAL**: Always call this method to safely release all hardware resources!

```python
try:
    while True:
        # Your main loop
        pass
except KeyboardInterrupt:
    pass
finally:
    robot.cleanup()  # ← Don't forget this!
```

### What cleanup does:

1. **Stops motors**: Calls `drivetrain.coast()` to cut power
2. **Stops sensor threads**: Safely terminates all background I2C polling threads
3. **Stops vision cameras**: Releases `/dev/video*` devices (prevents need for reboot)
4. **Joins button listener threads**: Waits for background threads to finish
5. **Cleans up GPIO**: Resets all pins to default state

**Why it's critical:**
- Without `cleanup()`, motors may continue receiving old PWM signals after crash
- Camera devices stay locked - require full reboot to release
- GPIO pins remain in undefined states, causing unpredictable behavior on next boot

---

## Private Attributes (For Advanced Usage)

### `_button_callbacks: dict[str, Callable]`

Maps button IDs to their callback functions. Used internally by the decorator system.

```python
# Access registered callbacks (advanced - use with caution!)
callbacks = robot._button_callbacks
print(callbacks["start"])  # The function that runs on button press
```

### `_button_threads: list[threading.Thread]`

List of background threads monitoring buttons. Used internally for cleanup.

---

## Error Handling

### Configuration Errors

Raised during initialization if config is invalid:

```python
from baracommlib.BaraRobot import BaraRobot

try:
    robot = BaraRobot("baraconfig.yaml")  # May raise RuntimeError
except RuntimeError as e:
    print(f"Configuration error: {e}")
    # Shut down safely
    GPIO.cleanup() if 'GPIO' in dir() else None
```

### Sensor Readings

Always check for `None` before using sensor values:

```python
distance = robot.sensor.get("front_tof")

if distance is not None and distance > 0:
    # Safe to use
    pass
else:
    print("Sensor reading unavailable - skipping action")
```

### Vision Errors

Classification may return error messages:

```python
result = robot.vision.classify("main_cam")

if "error" in result:
    print(f"Vision error: {result['error']}")
    # Fallback behavior (e.g., stop, coast, or use last known state)
else:
    label = result["label"]
    confidence = result["confidence"]
```

---

## Best Practices

### 1. Always Use Try-Finally with cleanup()

```python
robot = BaraRobot("baraconfig.yaml")

try:
    while True:
        # Your main loop
        pass
except KeyboardInterrupt:
    print("Interrupted by user")
finally:
    robot.cleanup()  # Guaranteed to run even on exceptions
```

### 2. Check Sensor Validity Before Use

```python
# Good practice
distance = robot.sensor.get("front_tof")
if distance is not None and distance > 0:
    if distance < 100:
        robot.drivetrain.coast()
else:
    # Fallback: stop or use last known safe state
    print("Sensor unavailable - stopping for safety")
```

### 3. Use Average for Grouped Sensors

```python
# Better than individual readings (filters failures/noise)
avg_distance = robot.sensor.get_average_by_direction("front")

if avg_distance and avg_distance < 150:
    # React to obstacle
    pass
```

### 4. Monitor Reading Age in Critical Loops

```python
sensor = robot.sensor.get_sensor("front_tof")
distance = sensor.get_value()
age = sensor.get_reading_age()

if age > 0.1 and distance is not None:  # Fresh reading (< 100ms)
    if distance < 200:
        robot.drivetrain.coast()
```

---

## Related Documentation

- [Motors Guide](./motors.md) - Complete drivetrain API
- [Sensors Guide](./sensors.md) - Sensor access patterns
- [Vision Guide](./vision.md) - Computer vision API
- [Fail-Safe System](./fail_safe.md) - Automatic recovery mechanisms
