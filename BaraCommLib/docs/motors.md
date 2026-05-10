# Motors & Drive Train

The **Motors** module is responsible for translating high‑level movement commands (e.g., *drive forward*, *turn left*) into direct GPIO/PWM signals that control the robot’s H‑bridge or motor driver.  It also optionally reads quadrature wheel encoders so distance and speed can be measured.

All hardware access goes through :mod:`RPi.GPIO`.  When running on a non‑Raspberry‑Pi platform (e.g., during unit tests) the library silently falls back to :class:`~baracommlib.mock_gpio.GPIO`, which implements the same API but does nothing – this keeps test code simple and ensures that no hardware is touched.

---
## Class: `Motors`
```python
from baracomllb import Motors
motors = Motors(config_dict)
```
| Method | Parameters | Return Value | Side Effects |
|--------|------------|--------------|-------------|
| ``__init__(config: dict)`` | *config*: the full YAML configuration (must contain `drivetrain` section).  The constructor extracts motor pin numbers, PWM channels and optional encoder pins.
|  – | Instantiates :class:`MotorIN` objects for each of the four direction inputs (`AIN1`, `AIN2`, `BIN1`, `BIN2`) and sets up two :class:`GPIO.PWM` instances (one per side).<br>When encoders are present it creates :class:`Encoder` instances for left/right wheels.
| ``move_forward_action(speed: int)`` | *speed*: PWM duty cycle 0‑100. Must not exceed `config["drivetrain"]["max_pwm_value"]`. |
| – | Sets direction pins to forward, updates current state variables and calls :py:meth:`pwm_a.ChangeDutyCycle`/`:b.ChangeDutyCycle`.
| ``turn_left_action(speed: int)``, ``turn_right_action(speed: int)`` | Same as above but with reversed pin states. |
| ``coast()`` | – | Stops all motors by pulling direction pins low and setting duty cycle to 0.
| ``force_brake(max_pwm_value: int)`` | *max_pwm_value*: The maximum PWM value allowed for a hard brake. |
| – | Drives both sides in the same high state (high‑current braking).  Raises :class:`MaxPowerExceededException` if the argument exceeds configuration.
| ``stop()`` | – | Alias to `coast()` used by fail‑safe logic.
| ``assign_manual_power(motor: Motor, power: int)`` | *motor*: Enum value (`Motor.A`, `Motor.B`).  *power* is a PWM duty cycle. |
| – | Directly sets the chosen motor's speed without touching direction pins; useful for fine‑tuned manual overrides.
| ``are_forced() -> bool`` | – | Returns whether any motor is in forced mode (i.e., `force_brake` was called).
| ``get_motor_state(motor: Motor, direction: MotorDirection) -> int`` | *motor*, *direction* enum. |
| – | Reads the GPIO pin for the requested side/direction and returns 1 if high, else 0.
| ``health_check() -> bool`` | – | Verifies that every motor input is still in its last known state; useful during runtime diagnostics.

---
## Encoder Support (Optional)
If your configuration declares `encoders.exists: true` and provides pin numbers for each side, :class:`Motors` will instantiate a small quadrature decoder:
```python
self._encoder_a = Encoder(pin_a=left_enc["pin_a"], pin_b=left_enc.get("pin_b"))
```
The encoder object exposes:
- ``get_ticks()`` – cumulative tick count.
- ``reset_ticks()`` – zero the counter.
- ``get_revolutions()``, ``get_speed_tps()`` (stub in current implementation).

Distance calculations are performed inside :py:meth:`drive_distance` using the configured `wheel_circumference_mm`.  The method converts requested millimetres into target ticks:
```python
ticks_per_mm = self._encoder_a.ticks_per_rev / self._wheel_circumference_mm
target_ticks = int(distance_mm * ticks_per_mm)
```
and loops until the left encoder reaches that tick count.

---
## High‑Level Primitives
| Primitive | Description |
|-----------|-------------|
| ``drive(duration_seconds: float, speed=None)`` | Drives forward for a specified time.  If *speed* is omitted it uses `config["robot"]["base_speed"]`.
| ``drive_distance(distance_mm: float, speed=None)`` | Uses the encoder to move an exact distance in millimetres; raises :class:`RuntimeError` if encoders are not enabled.
| ``spin(degrees: float, speed=None, use_gyro=False, gyro_sensor_id=None, sensor_getter=None)`` | Spins either time‑based or gyroscope‑based.  If `use_gyro=True`, it repeatedly polls the provided *sensor_getter* until a yaw change of ±2° is achieved.

All primitives automatically call ``coast()`` when finished to avoid inadvertent continuous motion during tests.

---
## Error Handling & Safety
The library enforces PWM limits by raising :class:`MaxPowerExceededException` if you attempt to drive faster than the maximum allowed value configured in `drivetrain.max_pwm_value`.  The exception is also raised inside ``force_brake`` when a brake intensity above this limit would be applied.

When a sensor failure triggers the robot’s fail‑safe (see :doc:`fail_safe`), it calls :py:meth:`Motors.stop`, which in turn invokes `coast()` and clears any forced state.
