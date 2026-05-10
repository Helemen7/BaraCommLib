# Configuration Management

The `config_manager.py` file contains the `ConfigManager` class, responsible for ensuring that the user-provided YAML settings are valid, safe, and free from logical or hardware paradoxes.

## Internal Workflow

When you call `load_and_validate()`, the class performs these steps:

1.  **File Existence**: Checks if `baraconfig.yaml` exists. If not, it copies a base version from `default_config.yaml` and raises an exception asking the user to fill it out.
2.  **Type Validation**: Through the abstract `_validate_field` function, it ensures that an integer is actually an integer and that a string belongs to the expected values (e.g., `allowed_values=['up', 'down']`).
3.  **Hardware Collision Detection**: *This is the most important feature.*
    *   **GPIO Pin Collisions**: Maintains an internal `used_pins` dictionary. If you declare pin 15 for a ToF sensor and then accidentally use 15 for the left motor's `in1`, the validator will print `Pin collision! Pin 15 is used by...` and halt execution.
    *   **I2C Address Collisions**: If you assign `0x29` to two different sensors on the same bus (`i2c_1`), the validator will immediately block you.

> [!TIP]
> Access to the validated configuration in the rest of the library is done in a "fail-fast" style (e.g., `config["mandatory_key"]`) rather than using `.get()`. This way, if validation somehow lets an empty field pass, the program will crash with a easily traceable `KeyError`.

## How to add a new YAML field

Writing validation code for nested dictionaries is tedious. That's why `_validate_field()` was implemented.

If you add the following field to `default_config.yaml`:
```yaml
robot:
  color: "blue" # Only red, blue, green allowed
```

You just need to go into `config_manager.py` and add:
```python
robot = config.get('robot', {})
if not self._validate_field(robot, 'color', str, allowed_values=["red", "blue", "green"], context="robot"): 
    return False
```

## Usage Example

```python
from baracommlib.config_manager import ConfigManager

manager = ConfigManager("my_robot.yaml")
try:
    config = manager.load_and_validate()
    print("Perfect Configuration! Base speed is:", config["robot"]["base_speed"])
except RuntimeError as e:
    print(f"Critical configuration error: {e}")
    # Shut down the system
```

---

## Color Tracking Configuration

> [!NOTE]
> The Color Tracking feature is optional. If disabled, the configuration can be omitted entirely.

The `vision.color_tracking` section allows you to define custom HSV or BGR/RGB bounds for color detection. This is useful for overriding the default presets or adding new colors specific to your task.

### Structure

```yaml
vision:
  color_tracking:
    enabled: true  # Set to false to disable (or omit this section entirely)
    colors:
      custom_red:
        hsv:
          lower: [0, 120, 70]
          upper: [10, 255, 255]
        bgr:
          lower: [0, 0, 150]
          upper: [100, 100, 255]
```

### Validation Rules

The `ConfigManager` enforces strict validation on color tracking settings:

1. **Valid Color Spaces**: Only `hsv`, `bgr`, or `rgb` are allowed as color space keys.
2. **Bounds Required**: Each color space must define both `lower` and `upper` bounds.
3. **Tuple Size**: Both bounds must be arrays of exactly **3 integers** (representing the 3 channels).

> [!WARNING]
> If you provide invalid bounds (e.g., wrong number of channels), the robot will refuse to start and print a validation error.

### Default Presets

If you don't define any custom colors, the `ColorTracker` automatically uses these built-in presets (available in both HSV and BGR):

- `red`, `green`, `blue`, `yellow`, `orange`, `purple`, `cyan`, `magenta`, `white`, `black`

> [!TIP]
> The built-in presets are optimized for general-purpose use. Only override them if your lighting conditions are unusual or you need very specific color thresholds.