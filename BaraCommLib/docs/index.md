# BaraCommLib - Official Documentation

Welcome to the hyper-detailed documentation of **BaraCommLib**. This library is designed to provide a robust, safe, asynchronous, and fail-safe interface for controlling Raspberry Pi-based robots (like the Capybara project).

> [!NOTE]
> The architecture is divided into three main pillars: **Configuration**, **Movement (Drivetrain)**, and **Sensors (Perception)**. Everything has been designed to be fully testable even on non-ARM PCs via a sophisticated automatic Mocking system.

## Documentation Index
1. [BaraRobot Class (High-Level API)](bararobot.md) - **Start Here!**
2. [Configuration Management (`config_manager.py`)](configuration.md)
3. [Motor Control and Drivetrain (`Motors.py`)](motors.md)
4. [Asynchronous Sensors and I2C (`sensors.py`)](sensors.md)
5. [PC Development and Mocking (`mock_gpio.py`)](development.md)

## Library Philosophy
- **Fail Fast, Fail Safe**: If you misconfigure a pin (e.g., two components share the same pin), the library immediately raises an exception at boot, long before the robot can move or cause damage.
- **Non-blocking by design**: Sensor readings, especially on I2C buses (which are slow), happen in the background. Your main logic or AI loop will **never** have to wait 30ms to read a distance sensor.
- **Hardware-Truth Validation**: `health_check` functions do not blindly trust software variables. They directly poll the hardware to detect desynchronizations or external interferences.

---

### Quick Example (Main Loop)
Here is an example of how all components come together in a classic `main.py` file:

```python
import time
from baracommlib.config_manager import ConfigManager
from baracommlib.Motors import Motors
from baracommlib.sensors import SensorsManager

# 1. Load and validate the configuration
cfg_manager = ConfigManager()
config = cfg_manager.load_and_validate()

# 2. Initialize subsystems
motors = Motors(config)
sensors = SensorsManager(config)

# 3. Main Loop
try:
    while True:
        # Hardware safety check
        if not motors.health_check():
            print("CRITICAL: Motors desynchronized. Emergency stop!")
            motors.coast()
            break
            
        # Instant O(1) reading from sensor threads
        front_sensors = sensors.get_readings_by_direction(sensors.Direction.FRONT)
        
        # Basic obstacle avoidance logic
        if any(dist and dist < 150 for dist in front_sensors.values()):
            motors.turn_left_action(50)
        else:
            motors.move_forward_action(config["robot"]["base_speed"])
            
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Shutting down...")
finally:
    motors.coast()
    sensors.stop_all()
```