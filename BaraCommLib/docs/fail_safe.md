# Fail-Safe & Sensor Recovery System

BaraCommLib includes an intelligent fail-safe architecture that automatically detects persistent sensor failures, halts the drivetrain to prevent damage, and attempts to reinitialize affected sensors without requiring a full robot restart.

---

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Sensor Failure Detection                 │
│  ┌──────────────────┐     ┌──────────────────────────────┐  │
│  │   Background     │────▶│   Error Counter              │  │
│  │   Polling Thread │     │   (consecutive_errors)       │  │
│  └──────────────────┘     └──────────────────────────────┘  │
│                                    ▼                        │
│                        ┌──────────────────────────────┐     │
│                        │  Exponential Backoff         │     │
│                        │  (30ms → 45ms → ... → 5s)    │     │
│                        └──────────────────────────────┘     │
│                                    ▼                        │
│                        ┌──────────────────────────────┐     │
│                        │   5+ Second Threshold        │     │
│                        │   TRIGGER FAIL-SAFE          │     │
│                        └──────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## How It Works

### 1. Continuous Error Monitoring

Each sensor runs in a dedicated background thread (`AbstractSensor._polling_loop`). Every hardware read attempt is monitored:

```python
# Inside AbstractSensor._polling_loop():
consecutive_errors = 0
first_error_time = None

while self._running:
    try:
        val = self._read_hardware()  # Actual I2C/GPIO read
        
        # Success! Reset error counter
        with self._lock:
            self._latest_reading = SensorReading(val, time.time(), is_valid=True)
        
        if consecutive_errors > 0:
            logging.info(f"Sensor {self.sensor_id} recovered after {consecutive_errors} errors.")
            consecutive_errors = 0
            first_error_time = None
            
    except Exception as e:
        consecutive_errors += 1
        
        # Record when failures started
        if first_error_time is None:
            first_error_time = time.time()
        
        logging.error(f"Error reading sensor {self.sensor_id} (x{consecutive_errors}): {e}")
        
        with self._lock:
            self._latest_reading = SensorReading(None, time.time(), is_valid=False)
```

### 2. Exponential Backoff Strategy

To prevent I2C bus flooding from repeated failed requests, the system implements exponential backoff:

| Failure # | Wait Time | Calculation | Purpose |
|-----------|-----------|-------------|---------|
| 1st | 30ms | `base_rate` (0.03s) | Quick retry for transient errors |
| 2nd | 45ms | `0.03 × 1.5¹` | Allow sensor recovery time |
| 3rd | 67ms | `0.03 × 1.5²` | Prevent I2C bus saturation |
| 4th | 101ms | `0.03 × 1.5³` | ... |
| 5th | 151ms | `0.03 × 1.5⁴` | ... |
| ... | Increasing | `0.03 × 1.5^(n-1)` | ... |
| Max (8+) | **5.0s** | `min(5.0, ...)` | Prevent CPU spinning |

> [!TIP]
> This strategy balances two competing needs: giving sensors time to recover from temporary issues while preventing the robot from operating with stale or invalid sensor data.

### 3. 5-Second Failure Threshold

If a sensor continuously fails for **5+ seconds**, the fail-safe triggers automatically:

```python
# Critical failure detection
if time.time() - first_error_time >= 5.0:
    logging.critical(f"Sensor {self.sensor_id} failed for 5+ seconds!")
    
    # Trigger fail-safe reinitialization
    if self.on_critical_failure:
        threading.Thread(
            target=self.on_critical_failure, 
            args=(self.sensor_type, self.bus_id)
        ).start()
    
    first_error_time = None  # Reset to avoid spamming logs
    self._running = False   # Kill this thread (will be reinitialized)
    break                   # Exit polling loop
```

---

## Fail-Safe Sequence

When the threshold is reached, these actions occur **automatically**:

### Step 1: Stop Drivetrain

```python
# In SensorsManager._handle_sensor_failure():
if self.stop_robot_callback:
    logging.critical("Stopping drivetrain due to sensor failure...")
    self.stop_robot_callback()  # Calls robot.drivetrain.coast() or .stop()
```

**Why?** Prevents the robot from driving blindly into obstacles with invalid distance data.

### Step 2: Sensor Reinitialization

The `SensorsManager` reinitializes all sensors of the failed type on the affected I2C bus:

```python
def _handle_sensor_failure(self, sensor_type: str, bus_id: str):
    # Stop and remove existing failing sensors
    to_remove = []
    for sid, sensor in self.sensors.items():
        if sensor.sensor_type == sensor_type and sensor.bus_id == bus_id:
            sensor.stop()
            to_remove.append(sid)
    
    for sid in to_remove:
        del self.sensors[sid]
    
    # Recreate fresh sensor instances
    sensors_cfg = self.config.get("sensors", {})
    
    if sensor_type == "tof":
        tof_sensors = []
        for tof_cfg in sensors_cfg.get("tof", []):
            if tof_cfg.get("bus") == bus_id:
                # Create NEW sensor instance with fresh hardware init
                sensor = ToFSensor(
                    tof_cfg, 
                    self.buses[bus_id], 
                    self.Direction,
                    sensor_type="tof", 
                    bus_id=bus_id,
                    on_critical_failure=self._handle_sensor_failure
                )
                self.sensors[sensor.sensor_id] = sensor
                tof_sensors.append(sensor)
        
        # Sequential startup (critical for ToF address management!)
        for sensor in tof_sensors:
            sensor.start()
            time.sleep(0.05)  # Wait before activating next sensor
            
    elif sensor_type == "imu":
        for imu_cfg in sensors_cfg.get("imu", []):
            if imu_cfg.get("bus") == bus_id:
                sensor = IMUSensor(...)
                self.sensors[sensor.sensor_id] = sensor
                sensor.start()
```

> [!IMPORTANT]
> Only sensors on the **same I2C bus** and of the **same type** as the failing sensor are reinitialized. This prevents unnecessary disruption to working sensors.

---

## Configuration Requirements

The fail-safe system requires **no explicit configuration** - it's always enabled by default. However, ensure your `baraconfig.yaml` has proper I2C bus definitions:

```yaml
sensors:
  buses:
    - id: "i2c_1"
      type: "i2c"
      scl_pin: 22
      sda_pin: 21
      frequency: 400000   # Lower to 100000 if experiencing interference
  
  tof:
    - id: "front_tof"
      direction: "front"
      model: "VL53L1X"
      bus: "i2c_1"
      xshut_pin: 15
      default_address: 0x29
      new_address: 0x30
  
  imu:
    - id: "main_gyro"
      model: "BNO085"
      bus: "i2c_1"
```

---

## Custom Sensor Integration

The fail-safe system is **automatically inherited** by custom sensors that extend `AbstractSensor`:

### Requirements for Automatic Fail-Safe Support

1. **Proper initialization**: Call parent constructor with type and bus ID
   ```python
   super().__init__(config_node, i2c_bus, sensor_type="your_type", bus_id="your_bus")
   ```

2. **Exception-raising on failure**: Your `_read_hardware()` must raise exceptions (not return invalid data silently)
   ```python
   def _read_hardware(self):
       try:
           # Attempt hardware read
           val = self.hardware.read()
           return val
       except Exception as e:
           raise  # Let fail-safe handle it!
   ```

### Example Custom Sensor with Fail-Safe

```python
from baracommlib.sensors import AbstractSensor, SensorsManager
import time

class UltrasonicSensor(AbstractSensor):
    """Custom ultrasonic distance sensor with automatic fail-safe."""
    
    def __init__(self, config_node, i2c_bus=None, sensor_type="ultrasonic", bus_id="main"):
        # Required: pass sensor_type and bus_id for fail-safe integration
        super().__init__(config_node, i2c_bus, sensor_type=sensor_type, bus_id=bus_id)
        
    def _initialize_hardware(self):
        self._trigger_pin = GPIO.Pin(config_node.get("pin"))
        self._echo_pin = GPIO.Pin(config_node.get("echo"))
        GPIO.setup(self._trigger_pin, GPIO.OUT)
        GPIO.setup(self._echo_pin, GPIO.IN)
        
    def _read_hardware(self):
        try:
            # Trigger measurement
            GPIO.output(self._trigger_pin, True)
            time.sleep(0.000010)  # 10µs trigger
            GPIO.output(self._trigger_pin, False)
            
            # Read echo duration (simplified)
            start = time.time()
            while not GPIO.input(self._echo_pin):
                pass
            end = time.time()
            
            duration = (end - start) * 1000000  # microseconds
            distance = duration / 58.0  # cm
            
            return distance
            
        except Exception as e:
            raise  # Fail-safe will catch this!

# Usage in SensorsManager (automatic fail-safe integration!)
sensors_manager = SensorsManager(config)
```

---

## Callback Injection

The `SensorsManager` receives a `stop_robot_callback` during initialization, which is triggered when the fail-safe activates:

### In BaraRobot.__init__

```python
self.drivetrain = Motors(self.config)

# Pass drivetrain.stop as callback for automatic emergency stop
self.sensors_manager = SensorsManager(
    self.config, 
    stop_robot_callback=self.drivetrain.stop  # ← Critical!
)
```

### Why Run in Background Thread?

The callback runs in a separate thread to prevent deadlock:

```python
# Inside AbstractSensor._polling_loop():
if time.time() - first_error_time >= 5.0:
    if self.on_critical_failure:
        # Run in background to not block the dying thread
        threading.Thread(
            target=self.on_critical_failure, 
            args=(self.sensor_type, self.bus_id)
        ).start()
```

---

## Testing the Fail-Safe System

### Automated Test Suite

Run the included test to verify fail-safe functionality:

```bash
cd BaraCommLib
PYTHONPATH=./src python tests/test_general.py
```

The test injects a `FailingSensor` that always raises exceptions and verifies:
1. Drivetrain stops after 5+ seconds of continuous failures
2. Robot remains responsive to commands during recovery
3. Sensors are successfully reinitialized

### Manual Testing (Hardware Required)

**⚠ WARNING**: This test involves intentional sensor failure!

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Monitor fail-safe activation
import time

print("Waiting for fail-safe to trigger...")
for i in range(10):
    print(f"Time: {i*5}s - Sensor health check: {robot.drivetrain.health_check()}")
    
    # Check if robot stopped (fail-safe triggered)
    status = robot.drivetrain.get_status()
    if status['action'] is None:
        print("FAIL-SAFE TRIGGERED! Drivetrain stopped.")
        break
    
    time.sleep(5)

print("\nFail-safe test complete!")
```

---

## Troubleshooting

### "Sensor thread stopped after 5.5s - fail-safe triggered!" but robot didn't stop

**Possible causes:**
1. Missing `stop_robot_callback` in SensorsManager initialization
2. Sensor not properly registered with correct `sensor_type` and `bus_id`

**Solution:**
```python
# Ensure callback is passed:
self.sensors_manager = SensorsManager(
    self.config, 
    stop_robot_callback=self.drivetrain.stop  # ← Don't forget this!
)
```

### Sensor keeps failing even after reinitialization

**Checklist:**
- [ ] Hardware connections (loose I2C wiring is most common cause)
- [ ] Try lowering I2C frequency: `frequency: 100000` in config
- [ ] Verify correct sensor model (VL53L0X vs VL53L1X vs VL53L4CD)
- [ ] Check power supply (insufficient voltage causes intermittent failures)

> [!CAUTION]
> If a sensor consistently fails after reinit more than 3 times in a row, there is likely a hardware issue. The system will keep trying indefinitely - consider manual intervention or robot shutdown. (or it might just need to fully power off and back on, sometimes these things happen randomly)

### Multiple sensors on same bus all fail simultaneously

**Expected behavior**: All sensors of the same type on the same I2C bus are reinitialized together. This can cause temporary data loss from other working sensors on that bus.

**Mitigation:**
- Use separate I2C buses for critical sensors
- Lower I2C frequency to reduce contention
- Add capacitors (0.1µF) near sensor power pins

---

## Advanced: Custom Fail-Safe Behavior

Override the default fail-safe behavior for specialized robots:

```python
class CustomFailSafeHandler:
    def __init__(self, drivetrain):
        self.drivetrain = drivetrain
        
    def handle_tof_failure(self, bus_id):
        """Custom handling for ToF sensor failure."""
        print("ToF failed - switching to backup ultrasonic sensors!")
        
        # Your custom recovery logic here
        # Could activate alternative sensors, enter safe mode, etc.
        
    def handle_imu_failure(self, bus_id):
        """Custom handling for IMU failure."""
        print("IMU failed - entering drift-compensated mode!")
        
        # Disable gyro-assisted movements
        # Use time-based positioning instead

# Usage in BaraRobot.__init__:
self.sensors_manager = SensorsManager(
    self.config, 
    stop_robot_callback=self.drivetrain.stop
)

# Register custom handlers (advanced - modify sensors.py if needed)
for sensor_id, sensor in self.sensors_manager.sensors.items():
    if sensor.sensor_type == "tof":
        sensor.on_critical_failure = lambda t, b: CustomFailSafeHandler(self.drivetrain).handle_tof_failure(b)
```

---

## Related Documentation

- [Sensors Module](./sensors.md) - Sensor architecture and configuration
- [BaraRobot Class](./bararobot.md) - High-level API with fail-safe integration
- [Configuration Guide](./configuration.md) - Setting up sensors for optimal reliability
