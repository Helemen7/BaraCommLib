# Configuration Management

BaraCommLib ships a **default** YAML file (`default_config.yaml`) that contains sane, hardware‑agnostic defaults for every subsystem.
When the robot starts it looks for ``baraconfig.yaml`` in its working directory.  If it is missing the library will copy the default into place and raise an exception so you can edit it before re‑running.

The whole validation pipeline lives inside :class:`~baracommlib.config_manager.ConfigManager`.  It guarantees that:
* every required section exists,
* all values are of the expected type, and
* hardware resources (GPIO pins, I²C addresses) do not collide across subsystems.

> **Why validate?**
>
> A mis‑configured pin or duplicate address can leave your robot in an unrecoverable state.  By catching these errors early you avoid expensive debugging on the target board.

## Class :class:`ConfigManager`

```python
from baracommlib.config_manager import ConfigManager
cm = ConfigManager("baraconfig.yaml")
cfg_dict = cm.load_and_validate()
```

| Method | Parameters | Return Value | Notes |
|--------|------------|--------------|-------|
| ``__init__(config_filepath: str = "baraconfig.yaml")`` | Path to the YAML file.  Default is a relative path that will resolve in the current working directory.| None – just stores arguments for later use. | Raises no error on construction; validation happens when you call :py:meth:`load_and_validate`. |
| ``load_and_validate() -> dict`` | – | The fully parsed and validated configuration dictionary.
|  –| If file is missing it copies the bundled default, raises a descriptive `RuntimeError` with instructions to edit the new file. |

### Private helpers (implementation details)
The library keeps all heavy lifting in private helper methods that are **well documented** inline in the source for reference.

#### `_inject_default_config()`
* Copies ``default_config.yaml`` from the package directory into *config_filepath*.  If it cannot be found a hard error is raised because the rest of the system depends on at least some configuration to start.

#### `_validate_field(data: dict, field: str, expected_type=None,
    allowed_values=None, required=True, context="") -> bool`
* Checks that *field* exists in *data*, optionally verifies its type and membership.  It prints a human‑readable error message to :py:mod:`logging` and returns ``False`` so the caller can abort.

#### `_isConfigHealthy(config: dict) -> bool`
This is the heart of validation – it walks through every top‑level section in order:
1. **Root** must be a dictionary.
2. **Robot** – checks mandatory keys like `base_speed`, ensures they are integers and within hardware limits.
3. **Drivetrain** – verifies PWM pins, motor directions, encoder pins (if enabled) and that all used GPIO pins are unique across motors/encoders/sensors.
4. **Sensors** – walks through I²C buses, ToF sensors (`VL53` series), IMUs (`BNO`, `MPU`).  It checks for missing mandatory keys, pin collisions, duplicate I²C addresses and that each sensor’s bus exists in the defined list of buses.
5. **IO** – validates button/pin assignments, pull‑up/down configuration, LED pins.
6. **Vision** – ensures camera resolution lists contain exactly two integers if vision is enabled.

Each subsection logs a clear message such as *"Pin collision! Pin 15 used by 'motor_left_in1' and 'tof_front_xshut'"