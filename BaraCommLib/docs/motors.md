# Motors & Movement Control

The `Motors` class provides comprehensive low-level and high-level motor control for differential drive robots. It handles H-bridge configuration, encoder-based odometry, and precise movement primitives using gyroscopic feedback.

---

## Quick Start

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Basic movements (speed: 0-100)
robot.drivetrain.move_forward_action(80)
robot.drivetrain.turn_left_action(50)
robot.drivetrain.turn_right_action(50)

# Stop methods
robot.drivetrain.coast()      # Cut power to motors
robot.drivetrain.force_brake(100)  # Electrical brake (short terminals)
robot.drivetrain.stop()       # Alias for coast()

# Encoder-based precise movement
robot.drivetrain.drive_distance(distance_mm=500)  # Drive 500mm forward
robot.drivetrain.spin(degrees=90, use_gyro=True)  # Precise 90° turn
```

---

## Motor Control Methods

### Basic Actions

| Method | Description | Parameters |
|--------|-------------|------------|
| `move_forward_action(speed)` | Drive both wheels forward | `speed`: int (0-100, max from config) |
| `turn_left_action(speed)` | Spin left in place | `speed`: int (0-100) |
| `turn_right_action(speed)` | Spin right in place | `speed`: int (0-100) |
| `coast()` | Stop motors (cut power) | None |
| `force_brake(max_pwm_value)` | Electrical brake | `max_pwm_value`: int (0-100) |
| `stop()` | Alias for coast() | None |

> [!NOTE]
> All speed values are capped by `drivetrain.max_pwm_value` in the configuration. Exceeding this raises `MaxPowerExceededException`.

>[!WARNING]
> Staying at values close to max motor speed for a long time may cause strain on all components. Please modulate power accordingly to use case

### Manual Motor Control

Direct control of individual motors (useful for differential steering or recovery):

```python
from baracommlib.Motors import Motor

# Set power to Motor A only
robot.drivetrain.assign_manual_power(Motor.A, power=70)  # Forward at 70%
robot.drivetrain.assign_manual_power(Motor.B, power=-50)  # Reverse at 50%

# Check if motors are in forced mode (brake/coast)
if robot.drivetrain.are_forced():
    print("Motors are braked or coasting")

# Read motor direction state
state = robot.drivetrain.get_motor_state(Motor.A, MotorDirection.FORWARD)
print(f"Motor A forward pin: {state}")  # 1=HIGH (forward), 0=LOW
```

---

## Encoder-Based Odometry

Encoders provide precise distance and position tracking. Requires encoder configuration in `baraconfig.yaml`.

### Reading Encoders

```python
# Get raw tick counts from both wheels
ticks = robot.drivetrain.get_encoder_ticks()
print(ticks)  # {'left': 1234, 'right': 1230}

# Get distance traveled (mm)
distances = robot.drivetrain.get_encoder_distance_mm()
print(distances)  # {'left': 500.5, 'right': 498.2}

# Reset encoders to zero
robot.drivetrain.reset_encoders()
```

### Encoder Properties

```python
encoder_left = robot.drivetrain.encoder_left  # Encoder object or None
encoder_right = robot.drivetrain.encoder_right  # Encoder object or None

if encoder_left:
    print(f"Revolutions: {encoder_left.get_revolutions():.3f}")
    print(f"Speed (tps): {encoder_left.get_speed_tps()}")  # ticks per second
```

---

## High-Level Movement Primitives

### Time-Based Drive

Drive for a specific duration using the configured `base_speed`:

```python
# Use base speed from config
robot.drivetrain.drive(duration_seconds=2.0)

# Override speed
robot.drivetrain.drive(duration_seconds=1.5, speed=70)
```

### Distance-Based Drive (Encoder-Dependent)

Precise movement using wheel encoders:

```python
# Drive exactly 1 meter forward
robot.drivetrain.drive_distance(distance_mm=1000)

# Requires encoder configuration! Raises RuntimeError if not configured.
```

> [!CAUTION]
> `drive_distance()` does NOT use PID control - it simply waits until the target distance is reached. For precise positioning with error correction, implement your own PID loop using encoder feedback.

### Gyro-Assisted Spin (Precise Turns)

Execute accurate rotations using IMU/gyroscope data:

```python
# Simple time-based spin (approximate)
robot.drivetrain.spin(degrees=90)  # ~2.5 seconds at speed 50

# Precise gyro-assisted turn
robot.drivetrain.spin(
    degrees=90,                    # Turn right 90°
    use_gyro=True,                 # Enable gyro feedback
    gyro_sensor_id="main_gyro",    # IMU sensor ID from config
    sensor_getter=lambda: robot.sensor.get("main_gyro")  # Reading function
)

# Negative degrees for left turns
robot.drivetrain.spin(degrees=-45, use_gyro=True)
```

> [!TIP]
> Gyro-assisted spins have a built-in 2° tolerance. The turn stops automatically when the target angle is reached within this margin.

---

## Encoder Configuration

Add encoders to your `baraconfig.yaml`:

```yaml
drivetrain:
  max_pwm_value: 100
  
  encoders:
    exists: true  # Set to false to disable encoder features
    
    # Wheel specifications (used for distance calculation)
    ticks_per_rev: 360          # Encoder pulses per wheel revolution
    wheel_circumference_mm: 200 # Wheel circumference in mm (~80mm diameter wheels)
    
    left:
      pin_a: 32
      pin_b: 33                 # Optional - enables direction detection (quadrature mode)
      
    right:
      pin_a: 34
      pin_b: 35
```

> [!IMPORTANT]
> For accurate odometry, ensure `pin_b` is configured for quadrature decoding. Single-channel mode (`pin_b` not set) only counts pulses without direction detection.

---

## Health Check & Diagnostics

Monitor motor health and detect wiring issues:

```python
# Check if motor control pins are stable (detect floating/shorted wires)
if robot.drivetrain.health_check():
    print("Motors healthy - all control pins stable")
else:
    print("WARNING: Motor pin instability detected! Possible wiring issue.")
    
# Get comprehensive motor status for debugging
status = robot.drivetrain.get_status()
print(status)
# {
#     "action": "forward",
#     "speed": 80,
#     "is_forced": False,
#     "encoders": {"left": 1234, "right": 1230},
#     "distances_mm": {"left": 500.5, "right": 498.2}
# }
```

---

## Advanced: Custom Encoder Callbacks

For precise speed control using encoder feedback, implement your own callback:

```python
from baracommlib.Motors import Encoder

encoder = robot.drivetrain.encoder_left

def on_change(channel):
    """Callback registered by Encoder class for edge detection."""
    a_state = GPIO.input(encoder.pin_a)
    
    if encoder.pin_b:
        b_state = GPIO.input(encoder.pin_b)
        
        # Quadrature direction detection
        if (a_state and not b_state) or (not a_state and b_velocity):
            encoder._ticks += 1
        else:
            encoder._ticks -= 1
    else:
        encoder._ticks += 1
        
    encoder._last_a_state = a_state
    encoder._last_time = time.time()

# Register callback (advanced usage)
GPIO.add_event_detect(encoder.pin_a, GPIO.BOTH, callback=on_change)
```

---

## Troubleshooting

### "Max power exceeded" error
- **Cause**: Speed value exceeds `drivetrain.max_pwm_value` in config
- **Fix**: Lower the speed parameter or increase `max_pwm_value`

### Encoder returns 0 or incorrect values
- **Check**: 
  - Encoders configured with `exists: true`
  - Correct `ticks_per_rev` and `wheel_circumference_mm`
  - GPIO pins connected (check wiring)
  
### Robot spins instead of moving forward
- **Cause**: Motors mounted backwards or encoder phase mismatch
- **Fix**: Set `mounted_backwards: true` in config for affected motor

---

## Related Documentation

- [BaraRobot Class](./bararobot.md) - High-level API wrapper
- [Sensors & IMU](./sensors.md) - Gyro-assisted movement
- [PID Controller](./pid_io.md) - Advanced motion control