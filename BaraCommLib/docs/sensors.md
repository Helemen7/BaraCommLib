# Sensors & Perception System

The `SensorsManager` class provides asynchronous, thread-based sensor polling for instant $O(1)$ data access. This architecture prevents blocking your main robot loop while waiting for slow I2C sensors to respond.

---

## Architecture Overview

### How Background Polling Works

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Main Loop     │───▶│  Sensor Thread   │───▶│    I2C Bus      │
│   (Your Code)   │◀───│  (Background)    │◀───│  (Hardware)     │
└─────────────────┘     └──────────────────┘     └─────────────────┘
       ▲                        │
       │                        ▼
       │              ┌─────────────────┐
       └────────────▶│ Latest Reading  │◀───────────┐
                      │ (Thread-Safe)   │             │
                      └─────────────────┘             │
                                                      │
                    ┌─────────────────────────────────┘
                    ▼
              ┌─────────────────┐
              │  Instant O(1)   │◀── Your code reads here
              │    Access       │
              └─────────────────┘
```

**Key Benefits:**
- **Non-blocking**: Main loop never waits for I2C (typically 30-100ms per sensor)
- **Thread-safe**: All shared data protected by `threading.Lock`
- **Freshness tracking**: Each reading includes timestamp for age verification
- **Automatic recovery**: Failed sensors trigger fail-safe reinitialization

---

## Quick Start

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Instant O(1) sensor access (no blocking!)
distance = robot.sensor.get("front_tof")  # e.g., 152.0 cm
gyro = robot.sensor.get("main_gyro")       # {'yaw': 45.1, 'pitch': 0.2, 'roll': 1.5}

# Grouped sensor access by direction
front_sensors = robot.sensor.get_by_direction("front")
print(front_sensors)  # {"front_left": 120, "front_right": 122}

# Automatic averaging of grouped sensors
avg_distance = robot.sensor.get_average_by_direction("front")
if avg_distance and avg_distance < 100:
    print("Wall detected!")
```

---

## Sensor Reading Methods

### `get(sensor_id)` - Single Sensor Access

Returns the latest cached reading for a specific sensor by its unique ID.

```python
# ToF distance sensor
front_dist = robot.sensor.get("front_tof")  # Returns: float (cm) or None

# IMU orientation
gyro_data = robot.sensor.get("main_gyro")   # Returns: dict with yaw/pitch/roll

# Check if reading is valid
if front_dist is not None and front_dist > 0:
    print(f"Distance: {front_dist:.1f} cm")
```

> [!NOTE]
> If a sensor has failed or returned invalid data, `get()` returns `None`. Always check for `None` before using the value.

### `get_by_direction(direction)` - Grouped Access

Fetches all sensors grouped under a logical direction (defined in YAML). Returns a dictionary mapping sensor IDs to values.

```python
# Get all front-facing sensors
front_dict = robot.sensor.get_by_direction("front")
print(front_dict)  
# Output: {"front_left": 120, "front_right": 125}

# Works with any direction string from config
diagonal = robot.sensor.get_by_direction("diagonal_right")
back = robot.sensor.get_by_direction("rear")
```

### `get_average_by_direction(direction)` - Robust Averaging

Automatically averages all valid numerical readings for sensors in a direction, filtering out broken/disconnected sensors.

```python
# Get average distance from all front sensors (ignores failures)
avg_dist = robot.sensor.get_average_by_direction("front")

if avg_dist is not None:
    print(f"Average front distance: {avg_dist:.1f} cm")
else:
    print("No valid readings available!")
```

### `get_sensor(sensor_id)` - Get Sensor Object

Returns the actual sensor object for advanced operations (pause/resume, custom methods).

```python
sensor_obj = robot.sensor.get_sensor("front_tof")

# Check reading age (how many seconds since last read)
age = sensor_obj.get_reading_age()  # Returns: float in seconds or inf

if age > 0.5:
    print(f"Warning: Sensor hasn't updated for {age:.1f}s!")
    
# Pause/resume individual sensors (advanced)
sensor_obj.pause()   # Stop polling to save CPU/I2C bandwidth
sensor_obj.resume()  # Resume polling
```

---

## IMU / Gyroscope Features

BaraCommLib supports multiple IMU models with automatic sensor fusion:

### Supported Models

| Model | Type | Features |
|-------|------|----------|
| **MPU6050** | 6-DOF | Accelerometer + Gyro (no compass) |
| **BNO055** | 9-DOF | Accel + Gyro + Magnetometer (hardware fusion) |
| **BNO085** | 9-DOF | Advanced fusion with motion tracking |

### MPU6050 Software Sensor Fusion

For MPU6050 (which lacks a built-in compass), BaraCommLib implements a **complementary filter**:

```python
# Under the hood in IMUSensor._read_hardware():
# Pitch/Roll: 98% gyro + 2% accelerometer (stable + responsive)
# Yaw: Pure gyro integration (fast but drifts over time)

mpu_pitch = 0.98 * (mpu_pitch + gyro_x * dt) + 0.02 * accel_pitch
mpu_roll = 0.98 * (mpu_roll + gyro_y * dt) + 0.02 * accel_roll
mpu_yaw += gyro_z * dt  # No absolute reference - drifts
```

### Axis Mapping & Inversion

Physical IMU orientation often differs from robot coordinate frames. Configure in YAML:

```yaml
imu:
  - id: "main_gyro"
    model: "MPU6050"
    bus: "i2c_1"
    
    # Map raw sensor axes [X, Y, Z] to robot [Yaw, Pitch, Roll]
    # 0=X axis, 1=Y axis, 2=Z axis
    axis_mapping: [0, 1, 2]  # Default: yaw=x, pitch=y, roll=z
    
    # Invert axes if needed (e.g., sensor mounted upside down)
    inverted_axes: [false, false, true]  # Negates Roll
```

### IMU Calibration

Calibrate your IMU to remove offset errors:

```python
from baracommlib.sensors import SensorsManager

sensors = robot.sensor.get_sensor("main_gyro")

# Calibrate while holding robot perfectly still
offsets = sensors.calibrate(samples=100, delay_ms=10)
print(f"Calibration offsets: {offsets}")
# {'yaw': 0.5, 'pitch': -0.3, 'roll': 1.2}

# Apply calibration automatically to future readings
adjusted = sensors.get_value_adjusted()
print(adjusted)  # Offsets already subtracted

# Reset orientation (set current as "home/zero")
sensors.reset_orientation()
```

---

## ToF Sensor Configuration

### XSHUT Pin Management (Multi-Sensor Setup)

When using multiple ToF sensors, they all boot at address `0x29` by default. BaraCommLib handles sequential initialization:

```yaml
tof:
  - id: "front"
    direction: "front"
    model: "VL53L1X"
    bus: "i2c_1"
    xshut_pin: 15      # GPIO pin controlling power
    default_address: 0x29
    new_address: 0x30  # Unique address after initialization
    
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

**Initialization Sequence:**
1. All XSHUT pins held LOW (sensors off)
2. Turn on first sensor → change address to `0x30`
3. Wait 50ms
4. Turn on second sensor → change address to `0x31`
5. Repeat for all sensors

### Supported ToF Models

| Model | Notes |
|-------|-------|
| VL53L0X | Basic model, limited features |
| VL53L1X | Most common, good range (up to 2m) |
| VL53L4CD | Advanced, multi-target detection |

---

## Sensor Failure Detection & Recovery

### Automatic Fail-Safe

Sensors continuously monitored for failures:

```python
# Inside AbstractSensor._polling_loop():
consecutive_errors = 0
first_error_time = None

try:
    val = self._read_hardware()
    self._latest_reading = SensorReading(val, time.time(), is_valid=True)
    consecutive_errors = 0  # Reset on success
except Exception as e:
    consecutive_errors += 1
    first_error_time = time.time() if first_error_time is None else first_error_time
    
    # Exponential backoff (max 5 seconds)
    time.sleep(min(5.0, poll_rate * 1.5 ** consecutive_errors))
    
    # Trigger fail-safe after 5+ seconds of continuous failure
    if time.time() - first_error_time >= 5.0:
        logging.critical(f"Sensor {self.sensor_id} failed for 5+ seconds!")
        self.on_critical_failure(sensor_type, bus_id)
```

### Exponential Backoff Strategy

| Failure # | Wait Time | Purpose |
|-----------|-----------|---------|
| 1st | 30ms (base rate) | Quick retry |
| 2nd | 45ms | Allow sensor recovery |
| 3rd | 67ms | Prevent I2C flooding |
| ... | Increasing | Max out at 5s |

> [!TIP]
> This prevents CPU spinning while giving sensors time to recover from temporary issues (loose connections, I2C noise).

---

## Custom Sensor Development

Extend `AbstractSensor` for custom hardware:

```python
from baracommlib.sensors import AbstractSensor, SensorsManager
import time

class CustomSensor(AbstractSensor):
    def __init__(self, config_node, i2c_bus, sensor_type="custom", bus_id="main"):
        super().__init__(config_node, i2c_bus, sensor_type, bus_id)
        
    def _initialize_hardware(self):
        # Initialize your custom hardware here
        self._sensor_instance = YourHardwareClass(i2c_bus)
        
    def _read_hardware(self):
        try:
            return self._sensor_instance.read_value()
        except Exception as e:
            raise  # Let fail-safe handle it

# Register in SensorsManager (automatic via config)
```

---

## Sensor Reading Age Monitoring

Track how fresh your sensor data is:

```python
sensor = robot.sensor.get_sensor("front_tof")
age = sensor.get_reading_age()

if age > 0.1:  # More than 100ms old
    print(f"Sensor reading stale ({age:.2f}s)")
elif age > 0.5:  # More than 500ms old
    print(f"Sensor thread may be stuck!")

# Use in critical loops
while True:
    distance = robot.sensor.get("front_tof")
    age = robot.sensor.get_sensor("front_tof").get_reading_age()
    
    if age < 0.1 and distance is not None:  # Fresh reading
        if distance < 200:
            robot.drivetrain.coast()
            
    time.sleep(0.05)
```

---

## Troubleshooting

### "Sensor thread stopped after 5.5s" but robot didn't stop
- Verify `stop_robot_callback` passed to `SensorsManager`:
  ```python
  sensors = SensorsManager(config, stop_robot_callback=robot.drivetrain.stop)
  ```

### Sensor returns constant value (no updates)
- Check I2C wiring and power
- Lower I2C frequency: `frequency: 100000` in config
- Verify sensor model matches actual hardware

### Multiple sensors on same bus all fail
- All sensors of that type will be reinitialized together
- This is expected behavior - check individual sensor wiring

---

## Related Documentation

- [Fail-Safe System](./fail_safe.md) - Automatic crash recovery
- [BaraRobot Class](./bararobot.md) - High-level sensor access
- [IMU Configuration](./configuration.md#imu-setup) - Axis mapping details