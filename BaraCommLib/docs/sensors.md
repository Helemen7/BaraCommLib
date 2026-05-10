# Sensors System

BaraCommLib abstracts all hardware sensors behind a common interface so that higher‑level code can work with *values* instead of raw I²C reads.
The sensor layer is split into three parts:
1. **AbstractSensor** – generic polling thread, error handling and fail‑safe hooks.
2. Concrete subclasses for the two supported families: ToF (`VL53L0X/L1X/L4CD`) and IMU (MPU6050 / BNO055 / BNO085).
3. **SensorsManager** – a high‑level orchestrator that instantiates all sensors defined in your YAML config, starts their polling threads and exposes convenient lookup helpers.

> All sensor classes live under :mod:`baracommlib.sensors`.

---
## AbstractSensor (Base Class)
```python
from baracomllb import SensorsManager  # for type hinting only
```
| Method | Parameters | Return Value | Side Effects |
|--------|------------|--------------|-------------|
| ``__init__(config_node: dict, i2c_bus=None,
    sensor_type: str = "unknown",
    bus_id: str = "unknown", on_critical_failure = None)`` | *config_node*: parsed YAML entry for the particular sensor.<br>*i2c_bus:* shared :class:`busio.I2C` instance or ``None`` (mock mode).<br>*sensor_type*, *bus_id*: metadata used by fail‑safe logic. <br>*on_critical_failure*: callable that is triggered after 5 s of continuous errors.<br>| None – sets up internal lock, thread placeholders and state flags.| No hardware interaction yet; just prepares the polling infrastructure.
| ``start()`` | – | Starts background read loop in a daemon thread. If already running it returns immediately. | Thread starts executing :py:meth:`_polling_loop` which calls `_read_hardware()` each *poll_rate* seconds.<br>Initialises hardware by calling :py:meth:`_initialize_hardware`. |
| ``stop()`` | – | Signals thread to terminate and joins it with a 1 s timeout. | The polling loop exits, leaving the sensor instance in an idle state.
| ``pause()/resume()`** | – | Pauses or resumes reads without stopping the background thread.| Useful for low‑power scenarios; all callbacks will still fire but `_read_hardware` is skipped while paused.<br>Read age continues to increase during pause.
| ``set_poll_rate(rate_seconds: float)`` | *rate* | Adjusts time between consecutive sensor polls. Default 0.03 s (≈30 Hz). |
| ``get_value() -> Any`` | – | Thread‑safe access to the most recent **valid** reading, or ``None`` if no valid value yet.<br>It checks :py:attr:`_latest_reading.is_valid`. |
| ``get_reading_age() -> float`` | – | Time in seconds since last read (or ``inf`` before any poll). Useful for freshness filtering. |

### Internal polling loop (`_polling_loop`)
The core of the class is a simple while‑loop that repeatedly:
1. Calls `_read_hardware()` inside a try/except.
2. Stores result in :class:`SensorReading(value, timestamp)` (or marks as invalid on error).
3. Tracks consecutive errors – after 5 s it invokes ``on_critical_failure`` **in the background** and shuts itself down to allow re‑initialisation by *SensorsManager*.
4. Implements exponential backoff: each successive failure multiplies sleep time by 1.5 up to a maximum of 5 seconds, preventing a tight error loop on broken hardware.

### Concrete subclasses
They only need to implement ``_initialize_hardware`` and ``_read_hardware``; the base class takes care of everything else.

---
## ToFSensor (VL53L0X/L1X/L4CD)
| Method | Parameters | Return Value |
|--------|------------|--------------|
| ``__init__(config_node: dict, i2c_bus,
    direction_enum_cls, sensor_type: str = "unknown",
    bus_id: str = "unknown", on_critical_failure = None)`` | Same as :class:`AbstractSensor`; additionally parses *model*, *xshut_pin* and optional *new_address*. |
| ``turn_on() / turn_off()`` | – | Manipulates the XSHUT GPIO pin.  `True` to power‑up, `False` for reset.
| ``_initialize_hardware(self) -> None`` | – | Calls :py:func:`adafruit_vl53x.*` constructors based on *model* and sets a new I²C address if requested.
| ``_read_hardware() -> Any`` | – | Returns distance in millimetres.  If the sensor is not ready or hardware fails, falls back to cached value (`self.get_value()`), otherwise returns `0.0`.

The class automatically handles **address collision** by powering all sensors low at boot (via XSHUT) and then sequentially enabling them with a short delay between each so that they negotiate their unique I²C address without clashing on the bus.

---
## IMUSensor (MPU6050 / BNO055 / BNO085)
| Method | Parameters | Return Value |
|--------|------------|--------------|
| ``__init__(config_node: dict, i2c_bus,
    direction_enum_cls, sensor_type: str = "unknown",
    bus_id: str = "unknown", on_critical_failure = None)`` | Parses *model*, optional *axis_mapping* and *inverted_axes*. |
| ``_initialize_hardware() -> None`` | – | Instantiates the appropriate Adafruit / mpu6050 library class, configures address.
| ``_read_hardware() -> Any`` | – | Returns a dictionary with keys `yaw`, `pitch` and `roll`.  For MPU6050 it performs an on‑device complementary filter; for BNO series it reads the fused Euler angles directly.

The IMU sensor also exposes :py:meth:`calibrate()` to compute offset samples, but this is optional – by default raw values are returned.

---
## SensorsManager (High‑Level Orchestrator)
This class ties everything together and provides a **single entry point** for the rest of the library.
```python
from baracommlib.sensors import SensorsManager
manager = SensorsManager(config, stop_robot_callback=robot.stop_drivetrain)  # example callback
```
| Method | Parameters | Return Value |
|--------|------------|--------------|
| ``__init__(config: dict, stop_robot_callback=None) -> None`` | *config*: the full YAML configuration.<br>*stop_robot_callback:* callable that stops drivetrain when a critical sensor error occurs. | Instantiates I²C buses, builds `SensorDirection` enum from all configured directions and creates concrete sensors.
| ``start_all()`` | – | Starts every sensor thread (calls :py:meth:`AbstractSensor.start`). |
| ``stop_all()`` | – | Stops every sensor thread gracefully. |
| ``get_reading(sensor_id: str) -> Any`` | ID of the desired sensor | Returns latest value or ``None`` if not found.<br>Uses :py:meth:`AbstractSensor.get_value` internally.
| ``get_sensor(sensor_id: str) -> AbstractSensor`` | – | Direct access to the underlying class instance. |
| ``get_readings_by_direction(direction: Union[Enum, str]) -> Dict[str, Any]`` | *direction* name or enum value | Returns a dictionary mapping sensor id → latest reading for all sensors that point in the specified direction.
| ``_handle_sensor_failure(sensor_type: str, bus_id: str)`` | Called automatically by any concrete sensor when 5 s of consecutive errors are detected. |

### Fail‑Safe Integration
When a sensor reports continuous failures, :py:meth:`SensorsManager._handle_sensor_failure`:
1. Calls ``stop_robot_callback()`` – usually the robot's drivetrain is halted.
2. Stops and removes all sensors of that type on the affected bus to avoid further error noise.
3. Re‑initialises them from scratch (calling their constructors again) so they can rejoin with a clean state.

This behaviour is exercised in ``tests/test_general.py`` where an injected *FailingSensor* triggers the fail‑safe after ~5 s of errors and asserts that the drivetrain stops gracefully.

---
## Using Sensors from Your Code
```python
# Example: read distance from front ToF sensor
front_distance = robot.sensors_manager.get_reading("front")  # returns mm or None
```
Because all sensors run on a background thread, ``get_value()`` is **instantaneous** – no blocking I²C transaction happens in your main loop.
