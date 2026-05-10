# Motors & Movement

## Basic Actions

The `Motors` class provides low-level motor control:

```python
robot = BaraRobot()

# Directional actions
robot.drivetrain.move_forward_action(50)  # speed 0-100
robot.drivetrain.turn_left_action(50)
robot.drivetrain.turn_right_action(50)
robot.drivetrain.coast()  # stop motors
robot.drivetrain.force_brake(100)  # emergency brake
```

## High-Level Primitives (Encoder-based)

> [!NOTE]
> Requires encoders to be configured in `baraconfig.yaml`.

```python
# Time-based drive (approximate)
robot.drivetrain.drive(duration_seconds=2.0)  # uses base_speed from config
robot.drivetrain.drive(duration_seconds=1.0, speed=70)

# Distance-based drive (precise, uses encoders)
robot.drivetrain.drive_distance(distance_mm=500)

# Spin/turn in place
robot.drivetrain.spin(degrees=90)  # right 90 degrees (time-based, approximate)
robot.drivetrain.spin(degrees=-90)  # left 90 degrees

# Gyro-assisted spin (precise!)
robot.drivetrain.spin(
    degrees=90,
    use_gyro=True,
    gyro_sensor_id="main_gyro",
    sensor_getter=robot.sensor.get
)
```

## Encoders

If configured, you can read encoder data:

```python
# Get raw tick counts
ticks = robot.drivetrain.get_encoder_ticks()
# {'left': 1234, 'right': 1230}

# Get distance in mm
dists = robot.drivetrain.get_encoder_distance_mm()
# {'left': 500.0, 'right': 495.0}

# Reset encoders
robot.drivetrain.reset_encoders()
```

## Configuration (baraconfig.yaml)

```yaml
drivetrain:
  max_pwm_value: 100
  
  encoders:
    exists: true
    ticks_per_rev: 360      # Encoder ticks per wheel revolution
    wheel_circumference_mm: 200  # Wheel circumference in mm
    left:
      pin_a: 32
      pin_b: 33
    right:
      pin_a: 34
      pin_b: 35
```

> [!CAUTION]
> If `exists: false`, `drive_distance()` and encoder methods will raise an error. Always check encoder configuration before using precision movement.