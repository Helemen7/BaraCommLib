# BaraRobot Class (High-Level API)

The `BaraRobot` class is the main entry point of the library. It is designed to hide the underlying hardware complexity and offer a "commercial-like", clean, safe, and ready-to-use interface.

Once instantiated, `BaraRobot` automatically reads the `baraconfig.yaml` file, starts the motors, sets up the pins, and launches the background I2C threads for super-fast sensor caching.

```python
from baracommlib.BaraRobot import BaraRobot

# Initializes all the hardware defined in the YAML automatically
robot = BaraRobot("baraconfig.yaml")
```

---

## 1. Motors and Drivetrain (`robot.drivetrain`)
The `drivetrain` module (based on the `Motors` class) is pre-configured and ready to use.
It takes into account physically inverted motor configurations (defined in the YAML) without requiring you to change your logical code.

```python
# Basic movements
robot.drivetrain.move_forward_action(speed=80)
robot.drivetrain.turn_left_action(speed=50)

# Braking (Coast: cuts power; Force Brake: shorts terminals to brake electrically)
robot.drivetrain.coast()
robot.drivetrain.force_brake(max_pwm_value=100)

# Manual control of a single motor
from baracommlib.Motors import Motor
robot.drivetrain.assign_manual_power(Motor.A, power=70)
```

---

## 2. Sensors: Instant $O(1)$ Access (`robot.sensor`)
Sensor polling happens continuously in the background. When you call a method from `robot.sensor`, you get the value **instantly** from the last reading cycle without blocking the main thread (which is crucial for timing-sensitive algorithms like PIDs).

The `robot.sensor` proxy interface exposes three handy methods:

### `get(sensor_id)`
Returns the value of the last sampling of the sensor specified in the YAML via its unique ID.

```python
# Front reading (ToF)
distance = robot.sensor.get("front") # Example: 152.0

# Gyro reading (IMU)
gyro = robot.sensor.get("main_gyro")
# Example: {"yaw": 45.1, "pitch": 0.2, "roll": 1.5}
```

### `get_by_direction(direction)`
If you have grouped multiple sensors under the same "direction" in the YAML (e.g., two diagonal sensors `front_left` and `front_right` logically mapped as `front`), you can fetch all their values at once in a dictionary. It accepts strings ("front") or Enums.

```python
front_values = robot.sensor.get_by_direction("front")
# Expected: {"front_right": 120, "front_left": 118}
```

### `get_average_by_direction(direction)`
Takes all sensors pointing in a specific direction, discards broken/disconnected ones (which return `None`), and automatically performs a mathematical average to give you a robust estimate cleansed of noise or individual hardware failures.

```python
avg_distance = robot.sensor.get_average_by_direction("front")
if avg_distance is not None and avg_distance < 100:
    print("Wall nearby!")
```

---

## 3. Events and Button Management
You no longer have to pollute your main loop with `if GPIO.input(PIN): ...` with the risk of floating readings. The library handles **debouncing** and multithreading for you.

### Asynchronous Decorator
Add `@robot.on_button_pressed` above a function. The library will create a dedicated thread to listen in the background for user interactions in total safety.

```python
@robot.on_button_pressed("start")
def start_routine():
    print("The robot detected user input!")
    # This code will only trigger once per press, thanks to automatic debouncing.
```

### Synchronous Reading
If you prefer to check the button state within a state machine or your main loop, you can use the synchronous function:
```python
if robot.is_button_pressed("start"):
    print("Button is currently being held down.")
```

---

## 4. Advanced Movement (Relative Navigation)
Having natively integrated a gyroscopic sensor fusion layer, `BaraRobot` offers a convenient API to turn by precise relative angles on the spot.

```python
# Turns RIGHT by 90 degrees with speed 50.
# Blocks execution until the turn is completed with a precision (tolerance) of 2°.
robot.turn(angle=90.0, speed=50, tolerance=2.0)

# Turns LEFT by 45 degrees
robot.turn(angle=-45.0)
```

---

## 5. Safe Teardown and Cleanup (`cleanup`)
When the application terminates, it is **mandatory** to stop the motors and release the GPIO/I2C resources. `BaraRobot` integrates a solid garbage collection implementation (`__del__`), meaning that upon script closure, the library autonomously attempts to clean up resources.

However, it is "best practice" to call it explicitly at the end of the main loop. This guarantees that motors won't go crazy continuing to receive old PWM signals in case of a software crash.

```python
try:
    while True:
        pass # Your code...
except KeyboardInterrupt:
    pass
finally:
    # Stops motors, kills sensor threads safely, and cleans up GPIO
    robot.cleanup()
```