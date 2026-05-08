# Asynchronous Sensors (`sensors.py`)

Reading data from the I2C bus is an inherently "slow" operation compared to the clock cycles of a modern Raspberry Pi. Executing consecutive readings of three ToF sensors in the main thread could take 60-100ms, ruining the performance of a line-follower robot's PID controller or the timing of camera-based visual analysis.

The `SensorsManager` class radically solves this problem by using Threading.

## How Background Polling Works

1.  Every instantiated sensor creates its own `threading.Thread` marked as `daemon=True` (so it automatically dies when the program exits).
2.  An infinite loop (`_polling_loop`) runs inside this thread, continuously reading the hardware on the I2C bus (e.g., `_sensor_instance.distance`).
3.  The read value is stored in a shared variable protected by a `threading.Lock`. Along with the value, a _Timestamp_ is saved.
4.  When you call `sensors.get_reading("front")` in your main code, the library **does not poll the sensor**; it simply returns the latest saved variable. This happens in **$O(1)$** and is completely instantaneous.

## XSHUT Pins and I2C Conflicts Management

By default, ToF sensors (e.g., VL53L1X) all boot up on the same I2C address: `0x29`. If you connect 3 of them, they will all talk at once and lock up.
The `SensorsManager` natively implements a sequential startup routine:
1. It pulls all ToF XSHUT pins to LOW (turning off the sensors).
2. It turns on the first one (HIGH).
3. Via I2C, it commands it to change its address (e.g., `0x30`).
4. It waits for a technical delay (50ms).
5. It turns on the second one, and so forth.

> [!IMPORTANT]
> For this magic to work, you must specify the `xshut_pin` and the `new_address` (if necessary) in the `baraconfig.yaml`.

## Dynamic Enum for Directions

Instead of hardcoding words like `FRONT`, `LEFT`, etc. in the code, the library reads your YAML. If you write `direction: "diagonal_right"` in the YAML, the `SensorsManager` will dynamically create `manager.Direction.DIAGONAL_RIGHT` for you.

This enables incredibly powerful grouped queries.

## Usage Examples

```python
from baracommlib.sensors import SensorsManager

# The manager will read the config, build the Enum, initialize the I2C
# buses via blinka, and start threads for all sensors.
sensors = SensorsManager(config)

# Gather grouped values
# .Direction was created based on the strings found in the YAML
front_dict = sensors.get_readings_by_direction(sensors.Direction.FRONT)
# Expected Output: {"front_left": 120, "front_right": 122}

# Check data freshness
my_sensor = sensors.get_sensor("front_tof")
age = my_sensor.get_reading_age()

if age > 0.5:
    print("Warning: The front sensor thread hasn't responded for half a second!")
```

## IMU / Gyroscope Features

The library ships with a highly customizable and unified interface for Inertial Measurement Units (IMUs), implemented in the `IMUSensor` class. 

### Supported Models

- **BNO055** and **BNO085**: High-end sensors with built-in hardware Sensor Fusion. The library automatically fetches and normalizes the absolute Euler angles calculated natively by the chip's internal co-processor.
- **MPU6050**: An entry-level 6-DOF IMU that strictly provides raw Accelerometer and Gyroscope data. Since it lacks a hardware compass or fusion processor, the `IMUSensor` class natively implements a **Software Complementary Filter** running under the hood in the polling thread. It fuses the Accelerometer gravity vectors (for absolute Pitch/Roll stability) with the Gyroscope integrations (for fast response and Yaw tracking), meaning your application code will never have to perform complex math.

### Axis Mapping and Inversions

Physical orientation inside your robot chassis often differs from the sensor board's standard axes. The library allows arbitrary mappings and inversions so that `{"yaw": ..., "pitch": ..., "roll": ...}` always match your robot's coordinate frame, strictly wrapped continuously between `0` and `360` degrees.

This is managed entirely via the `baraconfig.yaml` configuration using two parameters:
- `axis_mapping`: A list like `[0, 1, 2]` which remaps the raw `(Yaw, Pitch, Roll)` variables to different indices. 
- `inverted_axes`: A list like `[False, True, False]` to negate angles.

### Gyroscope Example Usage

```python
# Assuming you named your IMU 'main_gyro' in your YAML file
gyro_reading = sensors.get_reading("main_gyro")

if gyro_reading:
    yaw = gyro_reading["yaw"]
    pitch = gyro_reading["pitch"]
    roll = gyro_reading["roll"]
    
    print(f"Current Robot Heading: {yaw:.1f}°")
    
    # Simple threshold logic without doing complex vector math
    if pitch > 30.0 and pitch < 180.0:
        print("Warning: Robot is climbing a steep incline!")
```