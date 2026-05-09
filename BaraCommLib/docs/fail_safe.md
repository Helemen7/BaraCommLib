# Fail-Safe & Sensor Recovery System

> [!NOTE]
> This feature was introduced in version 1.0.0 to provide commercial-grade robustness for autonomous robots running unattended.

## Overview

BaraCommLib includes an intelligent fail-safe system that automatically detects persistent sensor failures, halts the drivetrain to prevent damage, and attempts to reinitialize the affected sensors without requiring a full robot restart.

---

## How It Works

### 1. Continuous Error Monitoring

Each sensor runs in a dedicated background thread (via `AbstractSensor._polling_loop`). Every time a hardware read fails, the system logs the error and increments a consecutive error counter.

```python
# Simplified logic inside _polling_loop
try:
    val = self._read_hardware()
    self._latest_reading = SensorReading(val, time.time(), is_valid=True)
    if consecutive_errors > 0:
        logging.info(f"Sensor {self.sensor_id} recovered after {consecutive_errors} errors.")
        consecutive_errors = 0  # Reset on success
except Exception as e:
    consecutive_errors += 1
    if first_error_time is None:
        first_error_time = time.time()
```

### 2. Exponential Backoff

To prevent flooding the I2C bus with failing requests, the system implements **exponential backoff**:

- First failure: immediate retry (30ms poll rate)
- Second failure: 45ms wait
- Third failure: 67ms wait
- ...and so on, maxing out at **5 seconds** between retries

> [!TIP]
> This backoff prevents the CPU from spinning uselessly while allowing the sensor a chance to recover (e.g., if it was temporarily disconnected or experiencing I2C noise).

### 3. 5-Second Failure Threshold

If the sensor continuously fails for **5 or more seconds**, the fail-safe triggers:

```python
if time.time() - first_error_time >= 5.0:
    logging.critical(f"Sensor {self.sensor_id} failed for 5+ seconds! Triggering fail-safe reinit.")
    if self.on_critical_failure:
        threading.Thread(target=self.on_critical_failure, args=(self.sensor_type, self.bus_id)).start()
```

> [!WARNING]
> The 5-second threshold is a hardcoded constant. If you need different behavior, you can modify `sensors.py` in the `_polling_loop` method.

---

## Fail-Safe Sequence

When the threshold is reached, the following actions occur **automatically**:

1. **Stop Drivetrain**: The motors are immediately halted via `drivetrain.coast()` to prevent the robot from driving blindly into obstacles.

2. **Sensor Reinitialization**: The `SensorsManager` iterates through all sensors of the failed type (e.g., all ToF sensors) on the affected I2C bus:
   - Stops the failing sensor threads
   - Removes them from the active sensor dictionary
   - Recreates new sensor instances with fresh hardware initialization
   - Restarts them sequentially (important for ToF to avoid address collisions)

> [!IMPORTANT]
> Only sensors on the same I2C bus and of the same type as the failing sensor are reinitialized. This prevents unnecessary disruption to working sensors.

---

## Configuration

The fail-safe system requires **no explicit configuration**—it is always enabled by default. However, ensure your `baraconfig.yaml` has proper I2C bus definitions:

```yaml
sensors:
  buses:
    - id: "i2c_1"
      type: "i2c"
      scl_pin: 22
      sda_pin: 21
      frequency: 400000
```

> [!CAUTION]
> If you have only one I2C bus and a sensor fails, ALL sensors of that type on that bus will be reinitialized. This is expected behavior but may cause temporary data loss from other sensors.

---

## Integration Points

### Custom Sensors

If you create custom sensors extending `AbstractSensor`, the fail-safe is **automatically inherited** as long as:

1. Your sensor calls `super().__init__(..., sensor_type="your_type", bus_id="your_bus")` with appropriate type and bus IDs
2. The `_read_hardware()` method raises an exception on failure (do not return invalid data silently)

### Callback Injection

The `SensorsManager` receives a `stop_robot_callback` during initialization, which is triggered when the fail-safe activates:

```python
# In BaraRobot.__init__
self.drivetrain = Motors(self.config)
self.sensors_manager = SensorsManager(self.config, stop_robot_callback=self.drivetrain.stop)
```

> [!NOTE]
> The callback runs in a separate thread to prevent deadlock when the sensor's own thread is dying.

---

## Testing

You can verify the fail-safe works on a PC without hardware using the included test:

```bash
cd BaraCommLib
PYTHONPATH=./src python tests/test_general.py
```

The test injects a `FailingSensor` that always raises exceptions, waits for 5+ seconds of continuous errors, and verifies the drivetrain stops and the robot remains responsive.

---

## Troubleshooting

### "Sensor thread stopped after 5.5s - fail-safe triggered!" but robot didn't stop

- Ensure the sensor was added to `SensorsManager.sensors` with correct `sensor_type` and `bus_id`
- Verify the `stop_robot_callback` was passed during `SensorsManager` initialization

### Sensor keeps failing even after reinit

- Check hardware connections (loose I2C wiring is the most common cause)
- Try lowering the I2C frequency in your config: `frequency: 100000` instead of 400000
- Verify you're using the correct sensor model (VL53L1X vs VL53L0X vs VL53L4CD)

> [!CAUTION]
> If a sensor consistently fails after reinit more than 3 times in a row, there is likely a hardware issue. The system will keep trying, but you should inspect the wiring and sensor.