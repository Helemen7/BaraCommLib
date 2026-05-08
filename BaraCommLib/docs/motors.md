# Motor Control (Drivetrain)

The `Motors.py` file exposes the `Motors` class, designed to interface with standard H-Bridge motor drivers (like L298N or L293D) via the `RPi.GPIO` library.

## Architecture and Safety

The class is built with two intrinsic safety layers:

1.  **Safety Clamping (Soft-Limit)**: Every time you call a movement function (e.g., `move_forward_action(speed)`), the library checks that `speed` does not exceed the `max_pwm_value` set in the YAML. If it does, a `MaxPowerExceededException` is raised. This prevents unforeseen current spikes.
2.  **`_is_forced` Tracking**: The class internally tracks if the motors are in a "Force Brake" state (magnetic braking/short circuit).

> [!CAUTION]
> **About using `force_brake(max_pwm_value)`**
> This function sets all four direction pins (IN1, IN2) to `HIGH`. This short-circuits the motors, generating an extremely strong magnetic braking force. It **must never** be kept active for more than a few seconds, otherwise it will overheat and potentially burn out the H-Bridge driver chips! Use `coast()` to free-wheel and stop safely.

## `health_check()`: Hardware Truth vs Software

One of the biggest issues in robotics is interference. If another Python script or a system daemon modifies the state of GPIO pin 12 (assigned to the motor), your script's internal `lastState` variable will still show `0`, but the hardware will be receiving `1` (the motor spins on its own!).

The `health_check()` function prevents this. It physically reads the silicon state using `GPIO.input(pin)` for the pins configured as `OUT`, and compares them with the known logical state.

```python
from baracommlib.Motors import Motors

motors = Motors(config)

motors.move_forward_action(50)

# Later in the code...
if not motors.health_check():
    print("ALARM: Something else is writing to the motor pins!")
    # Intervention: re-assert control!
    motors.coast()
```

## Movement Examples

The APIs to move the robot are self-explanatory and designed for differential drive robots (Skid-Steer/Tank drive).

```python
# Move forward at 100% (or max allowed)
motors.move_forward_action(100)

# Turn on the spot (Tank Turn)
motors.turn_left_action(50)

# Manual and asymmetrical movements
from baracommlib.Motors import Motor
motors.assign_manual_power(Motor.A, 80)
motors.assign_manual_power(Motor.B, 30)

# Stop by cutting power (Free-wheel / Coast)
motors.coast()
```