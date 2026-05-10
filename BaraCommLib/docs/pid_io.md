# PID Controllers

The library bundles a small but fully‑featured **PID controller** implementation that is reused by both position (distance or angle) and velocity control primitives.
All three classes share the same internal algorithm defined in :class:`~baracommlib.pid_controller.PIDController`.  The specialised wrappers simply set sensible defaults for gains, output limits and expose a convenient `compute()` method tuned to the specific application.

---
## Class: `PIDController`
```python
pid = PIDController(kp=2.0, ki=0.5, kd=1.0)
speed = pid.compute(current_value=10)  # returns corrective output in range [-100..100]
```
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| ``kp`` | float | `1.0` | Proportional gain – how aggressively the controller reacts to current error.
| ``ki`` | float | `0.0` | Integral gain – accumulates past errors; helps eliminate steady‑state offset.
| ``kd`` | float | `0.0` | Derivative gain – predicts future trend, damping oscillations.
| ``setpoint`` | float | `0.0` | Desired target value for the controlled variable (e.g., distance in mm or speed in ticks/s).
| ``output_min/max`` | float | `-100/100` | Saturation limits applied to the raw PID output before it is returned.
| ``integral_limit`` | Optional[float] | None | If set, clamps the running integral term to prevent wind‑up during prolonged error conditions.  A common heuristic is a fraction of the output range (e.g., `max_speed * 0.5`). |

### Core Methods
- **`reset()`** – clears internal state: previous error = 0, integral accumulator = 0, timestamp to current time.
- **`set_setpoint(setpoint)`** – updates target value; useful when the goal changes mid‑run.
- **`compute(current_value: float, dt=None) -> float`** – main control loop.
  - If *dt* is ``None`` it measures elapsed seconds from last call (defaulting to ~1 s on first invocation).
  - Error = `setpoint − current_value`.
  - **P term:** `kp * error`. |
  - **I term:** add `error * dt` to the integral accumulator, then clamp if ``integral_limit`` is set; multiply by ``ki``. |
  - **D term:** `(error − previous_error)/dt * kd`, zeroed when *dt* == 0.
  - Update internal `_previous_error` and timestamp for next iteration.
  - Sum P+I+D, clamp to `[output_min, output_max]` and return the result. |

The controller is deliberately lightweight; it does **not** use any external libraries or callbacks – all calculations happen inline so that you can drop a single class into unit tests without dependencies on hardware.

---
## Class: `PositionPID`
A thin wrapper around :class:`PIDController` tuned for *distance* (or angle) control.  It converts encoder ticks / millimetres into motor PWM commands.
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| ``kp``/``ki``/``kd`` | float | `1.5`, `0.05`, `0.5` | PID gains used by the underlying controller; chosen to give a reasonably fast response without overshoot.
| ``max_speed`` | int | `100` | The maximum PWM duty cycle allowed for motors, which becomes both the output upper bound and half of the integral limit (`integral_limit = max_speed * 0.5`). |

### Methods
- **`compute(current_position: float, target_position: float) -> int`** –
    - Sets controller setpoint to ``target_position``.
    - Calls underlying `PIDController.compute()` with the current encoder value and casts the result to an integer PWM command.
    - Updates flag :py:meth:`target_reached`: true if the absolute error is below 5 units (tolerance). |
- **`reset()`** – Resets both the internal controller state and `target_reached`.|

Typical usage inside a drivetrain spin or drive‑distance routine:
```python
pid = PositionPID()
speed_cmd = pid.compute(current_ticks, target_ticks)
motors.move_forward_action(speed=speed_cmd)
```
The returned value is already clamped to the motor’s power limits.

---
## Class: `VelocityPID`
Analogous to :class:`PositionPID` but designed for *speed* regulation.  It receives a current speed estimate (ticks per second or mm/s) and outputs a PWM command that keeps the robot running at the desired velocity.
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| ``kp``/``ki``/``kd`` | float | `1.0`, `0.1`, `0.05` | PID gains; tuned for smooth acceleration/deceleration.
| ``max_pwm`` | int | `100` | Output saturation limits and half of the integral bound (`integral_limit = max_pwm * 0.3`). |

### Methods
- **`compute(current_speed: float, target_speed: float) -> int`** – Similar flow to :class:`PositionPID`, but the controller’s setpoint is a speed value.
- **`reset()`** – Clears internal state for a fresh start.

The velocity PID is most useful in high‑level motion primitives such as maintaining steady forward motion during obstacle avoidance or when you want to decouple acceleration from motor commands.
