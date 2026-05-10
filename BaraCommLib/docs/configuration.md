# Configuration Management - Complete Guide

The `ConfigManager` class ensures your robot's YAML configuration is valid, safe, and free from hardware conflicts before any initialization occurs. This "fail-fast" approach prevents dangerous misconfigurations at runtime.

---

## Overview

When you call `load_and_validate()`, the ConfigManager performs these steps:

1. **File Existence Check**: If `baraconfig.yaml` doesn't exist, copies `default_config.yaml` from library and raises an error asking user to fill it out
2. **Type Validation**: Ensures integers are integers, strings match allowed values
3. **Hardware Collision Detection** (Most Important!):
   - **GPIO Pin Collisions**: Prevents two devices from sharing the same pin
   - **I2C Address Collisions**: Blocks duplicate addresses on the same bus

> [!TIP]
> The library uses "fail-fast" style access (`config["key"]`) rather than `.get()`. If validation somehow lets an empty field pass, the program crashes with a traceable `KeyError` - better than silent failures later.

---

## Usage Example

```python
from baracommlib.config_manager import ConfigManager

manager = ConfigManager("my_robot.yaml")
try:
    config = manager.load_and_validate()
    print("Configuration valid!")
    base_speed = config["robot"]["base_speed"]  # Safe to use - validated!
except RuntimeError as e:
    print(f"Critical error: {e}")
    # Shut down safely before retrying
```

---

## Complete YAML Structure Reference

### Root Level

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `robot` | dict | Yes | Robot metadata and defaults |
| `drivetrain` | dict | Yes | Motor control configuration |
| `sensors` | dict | Yes | Sensor definitions and I2C buses |
| `io` | dict | No | Buttons, LEDs, buzzers |
| `vision` | dict | No | Computer vision settings |

---

## Robot Section

```yaml
robot:
  name: "My Robot"              # Human-readable name (string)
  version: "1.0.0"              # Version string
  base_speed: 100               # Default speed for movements (int, 0-100)
```

### Validation Rules

- `base_speed`: Must be integer ≤ `drivetrain.max_pwm_value`
- If `base_speed > max_pwm_value`, validation fails with error message

---

## Drivetrain Section

```yaml
drivetrain:
  max_pwm_value: 100            # Maximum PWM duty cycle (protects hardware)
  
  motors:
    left:                       # Motor A configuration
      in1: 12                   # H-bridge IN1 pin (int, required)
      in2: 13                   # H-bridge IN2 pin (int, required)
      pwm: 19                   # PWM pin (int, required)
      mounted_backwards: false  # True if motor spins opposite direction
      
    right:                      # Motor B configuration
      in1: 14
      in2: 18
      pwm: 29
      mounted_backwards: false

  encoders:                     # Optional wheel encoder setup
    exists: true                # Set to false to disable encoder features
    
    ticks_per_rev: 360          # Encoder pulses per wheel revolution (int)
    wheel_circumference_mm: 200 # Wheel circumference in mm (float/int)
    
    left:                       # Left wheel encoder pins
      pin_a: 32
      pin_b: 33                 # Optional - enables quadrature direction detection
      
    right:                      # Right wheel encoder pins
      pin_a: 34
      pin_b: 35
```

### Validation Rules

- `max_pwm_value`: Must be positive integer
- All motor pins (`in1`, `in2`, `pwm`) must be unique integers (no collisions)
- If `encoders.exists: true`, both left and right encoders required with valid pin_a/pin_b
- Encoder pins must not collide with other device pins

### Pin Collision Detection Example

```yaml
# ❌ INVALID - Pin 15 used twice!
sensors:
  tof:
    - id: "front"
      xshut_pin: 15  # ← Collision!

io:
  buttons:
    - id: "start"
      pin: 15        # ← Already used by ToF XSHUT
```

**Error message:** `Config validation failed: Pin collision! Pin 15 is used by 'tof_front_xshut' and 'button_start'`

---

## Sensors Section

### I2C Bus Definition (Required)

```yaml
sensors:
  buses:
    - id: "i2c_1"              # Must start with "i2c_" prefix
      type: "i2c"
      scl_pin: 22              # SCL pin (int, required)
      sda_pin: 21              # SDA pin (int, required)
      frequency: 400000        # Bus clock in Hz (default: 400kHz)
```

### ToF Sensors Configuration

```yaml
sensors:
  tof:
    - id: "front"              # Unique identifier for code access
      direction: "front"       # Logical grouping string (any name works)
      model: "VL53L1X"         # Supported: VL53L0X, VL53L1X, VL53L4CD
      
      bus: "i2c_1"             # Must match a defined I2C bus
      
      xshut_pin: 15            # GPIO pin controlling power (required)
      default_address: 0x29    # Default I2C address (usually 0x29)
      new_address: 0x30        # Unique address after initialization
      
    - id: "left"
      direction: "left"
      model: "VL53L1X"
      bus: "i2c_1"
      xshut_pin: 16
      default_address: 0x29
      new_address: 0x31
      
    - id: "right"
      direction: "right"
      model: "VL53L1X"
      bus: "i2c_1"
      xshut_pin: 17
      default_address: 0x29
      new_address: 0x32
```

### ToF Validation Rules

- `id`: Required string identifier
- `direction`: Required string for logical grouping (used by `get_by_direction()`)
- `model`: Optional, must be one of VL53L0X/VL53L1X/VL53L4CD if provided
- `bus`: Must reference a defined I2C bus ID
- `xshut_pin`: Required GPIO pin (must not collide with other devices)
- `new_address`: Optional, must be unique per bus if provided

### IMU Configuration

```yaml
sensors:
  imu:
    - id: "main_gyro"          # Unique identifier
      model: "BNO085"          # Supported: MPU6050, BNO055, BNO085
      bus: "i2c_1"
      
      address: 0x4A            # Optional I2C address (sensor-specific default if omitted)
      
      # Axis mapping: maps raw sensor axes [X,Y,Z] to robot [Yaw,Pitch,Roll]
      # 0=X axis, 1=Y axis, 2=Z axis
      axis_mapping: [0, 1, 2]  # Default: yaw=x, pitch=y, roll=z
      
      # Invert axes if sensor mounted differently
      inverted_axes: [false, false, true]  # Negates Yaw/Pitch/Roll after mapping
```

### IMU Validation Rules

- `id`: Required string identifier
- `model`: Optional but recommended (defaults to BNO085)
- `bus`: Must reference a defined I2C bus ID
- `address`: Optional, must be unique per bus if provided
- `axis_mapping`: If provided, must be list of exactly 3 integers (0, 1, or 2 each)
- `inverted_axes`: If provided, must be list of exactly 3 booleans

---

## IO Section

### Buttons Configuration

```yaml
io:
  buttons:
    - id: "start"              # Unique identifier for code access
      pin: 0                   # GPIO pin (int, required)
      pull: "up"               # Internal resistor: 'up', 'down', or 'none' (default: none)
      debounce_ms: 50          # Debounce delay in ms after press detected (optional, default: 50)
```

### LEDs Configuration

```yaml
io:
  leds:
    - id: "status_led"         # Unique identifier
      pin: 2                   # GPIO pin (int, required)
      pwm: false               # True for dimmable PWM control (optional, default: false)
```

### Buzzers Configuration

```yaml
io:
  buzzers:
    - id: "alarm"              # Unique identifier
      pin: 3                   # GPIO pin (int, required)
```

---

## Vision Section

```yaml
vision:
  enabled: true               # Enable vision subsystem
  
  model_path: "robot_brain.tflite"  # Path to TFLite model file
  
  cameras:
    - id: "main_cam"          # Unique camera identifier
      source: 0               # Camera device (int for USB/CSI, e.g., 0=/dev/video0)
      resolution: [640, 480]  # Force this capture size [width, height]
```

### Color Tracking Configuration

```yaml
vision:
  color_tracking:
    enabled: true             # Enable color tracking
    
    colors:                   # Custom color overrides (optional)
      custom_red:
        hsv:                  # HSV bounds for OpenCV
          lower: [0, 120, 70]
          upper: [10, 255, 255]
        bgr:                  # BGR bounds (OpenCV's default color space)
          lower: [0, 0, 150]
          upper: [100, 100, 255]
```

### Vision Validation Rules

- `enabled`: Boolean flag
- If enabled and `cameras` defined:
  - Each camera must have valid `id` string
  - `resolution` must be list of exactly 2 integers [width, height]
- Color tracking colors (if provided):
  - Keys must be strings (color names)
  - Values must contain HSV and/or BGR bounds
  - Each bound must be array of exactly 3 integers

---

## Adding New Configuration Fields

The `_validate_field()` helper makes adding new fields easy:

### Example: Add a "robot_color" field

**Step 1:** Add to `default_config.yaml`:
```yaml
robot:
  color: "blue"  # Only red, blue, green allowed
```

**Step 2:** Add validation in `config_manager.py`:
```python
robot = config.get('robot', {})
if not self._validate_field(robot, 'color', str, 
                            allowed_values=["red", "blue", "green"], 
                            context="robot"): 
    return False
```

### Example: Add a nested configuration section

**Step 1:** Add to `default_config.yaml`:
```yaml
advanced:
  debug_mode: false
  log_level: "info"  # Allowed: debug, info, warning, error
```

**Step 2:** Add validation:
```python
advanced = config.get('advanced', {})
if not self._validate_field(advanced, 'debug_mode', bool, context="advanced"): 
    return False
    
if not self._validate_field(advanced, 'log_level', str, 
                            allowed_values=["debug", "info", "warning", "error"], 
                            context="advanced"): 
    return False
```

---

## Validation Helper: `_validate_field()`

Signature:
```python
_validate_field(data: dict, field: str, expected_type=None, 
                allowed_values=None, required=True, context="") -> bool
```

**Parameters:**
- `data`: Configuration dictionary to validate from
- `field`: Field name to check
- `expected_type`: Python type (str, int, bool, etc.) - optional
- `allowed_values`: List of acceptable values - optional
- `required`: Whether field must exist (default: True)
- `context`: Human-readable context for error messages

**Returns:** `True` if valid, `False` otherwise

---

## Troubleshooting Configuration Issues

### "Pin collision!" Error

**Cause**: Two devices assigned the same GPIO pin.

**Solution**: Check all pin assignments in config:
```bash
# Find duplicate pins
python3 -c "
import yaml
with open('baraconfig.yaml') as f:
    config = yaml.safe_load(f)

pins = {}
for section, name in [('drivetrain.motors.left', 'motor_left'), 
                       ('drivetrain.motors.right', 'motor_right'),
                       ('sensors.tof', 'tof'),
                       ('io.buttons', 'button')]:
    # Parse pins from config...
    pass
"
```

### "I2C Address collision!" Error

**Cause**: Two sensors on same bus with same I2C address.

**Solution**: Ensure each ToF has unique `new_address`:
```yaml
tof:
  - id: "front"
    new_address: 0x30  # ← Unique!
    
  - id: "left"  
    new_address: 0x31  # ← Different from front!
```

### Missing Required Field Error

**Cause**: Validation expects a field that's not in config.

**Solution**: Check validation rules above for required fields, or set to default value.

---

## Testing Configuration Before Deployment

### Automated Test Suite

```bash
cd BaraCommLib
PYTHONPATH=./src python tests/test_general.py
```

This test validates:
- Config file exists and is valid YAML
- All required fields present with correct types
- No pin collisions detected
- No I2C address conflicts

### Manual Validation Script

Create `validate_config.py`:
```python
#!/usr/bin/env python3
from baracommlib.config_manager import ConfigManager

def main():
    manager = ConfigManager("baraconfig.yaml")
    
    try:
        config = manager.load_and_validate()
        
        print("Configuration is valid!")
        print(f"   Robot: {config.get('robot', {}).get('name', 'Unknown')}")
        print(f"   Base speed: {config['robot'].get('base_speed')}")
        print(f"   Max PWM: {config['drivetrain']['max_pwm_value']}")
        
        tof_count = len(config.get('sensors', {}).get('tof', []))
        print(f"   ToF sensors: {tof_count}")
        
        imu_count = len(config.get('sensors', {}).get('imu', []))
        print(f"   IMU sensors: {imu_count}")
        
    except RuntimeError as e:
        print(f"Configuration error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
```

Run before deploying to hardware:
```bash
python validate_config.py
# Only proceed if output shows "Configuration is valid!"
```

---

## Related Documentation

- [BaraRobot](./bararobot.md) - Runtime configuration usage
- [Motors](./motors.md) - Drivetrain configuration details
- [Sensors](./sensors.md) - Sensor setup patterns