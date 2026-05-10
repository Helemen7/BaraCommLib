# PID Controller & IO Devices

This module provides advanced motion control and output device management:
- **PID Controllers**: Position-based and velocity-based control loops
- **IO Devices**: LED control, buzzer/beep functionality
- **Telemetry**: Debug logging and performance monitoring
- **Obstacle Avoidance**: Reactive navigation using sensor data
- **State Machine**: Hierarchical behavior organization
- **Line Follower**: Analog reflective sensor support

## Quick Reference

### PID Controllers
```python
from baracommlib.pid_controller import PositionPID, VelocityPID

# Reach specific distance/angle
pos_pid = PositionPID(kp=1.5, ki=0.05, kd=0.5)
speed = pos_pid.compute(current_position, target_position)

# Maintain constant speed
vel_pid = VelocityPID(kp=1.0, ki=0.1, kd=0.05)
pwm = vel_pid.compute(current_speed, target_speed)
```

### IO Devices
```python
robot.io.led("status", on=True)
robot.io.beep("alarm", duration_ms=200)
```

## Full Documentation

For comprehensive examples and advanced patterns:
- [Vision Guide](./vision.md) - Complete computer vision system
- [BaraRobot](./bararobot.md) - All high-level features

## Basic PID

```python
from baracommlib.pid_controller import PIDController

pid = PIDController(kp=1.0, ki=0.05, kd=0.1, output_min=-100, output_max=100)
pid.set_setpoint(100)

# In a loop:
output = pid.compute(current_value)
# output is the corrective action
```

## Position PID (for distances)

```python
from baracommlib.pid_controller import PositionPID

pos_pid = PositionPID(kp=1.5, ki=0.05, kd=0.5, max_speed=100)
target_position = 500  # ticks or mm

while not pos_pid.target_reached:
    current = get_encoder_position()
    speed = pos_pid.compute(current, target_position)
    motor.set_speed(speed)
```

## Velocity PID (for constant speed)

```python
from baracommlib.pid_controller import VelocityPID

vel_pid = VelocityPID(kp=1.0, ki=0.1, kd=0.05, max_pwm=100)
target_speed = 200  # ticks per second

# In loop:
current_speed = get_encoder_speed()
pwm = vel_pid.compute(current_speed, target_speed)
motor.set_pwm(pwm)
```

---

# IO Devices (LEDs & Buzzers)

Control status LEDs and buzzers from your config.

## Configuration

```yaml
io:
  leds:
    - id: "status"
      pin: 2
      pwm: false  # true for dimmable LED
    - id: "power"
      pin: 3
      pwm: true
  
  buzzers:
    - id: "alarm"
      pin: 4
```

## Usage

```python
robot = BaraRobot()

# Quick access
robot.io.led("status", on=True)
robot.io.beep("alarm", duration_ms=200)

# Direct control
status_led = robot.io.get_led("status")
status_led.on()
status_led.blink(times=3, duration_ms=150)

alarm = robot.io.get_buzzer("alarm")
alarm.beep(100)  # 100ms beep
alarm.play_sequence([(440, 200), (880, 200), (440, 200)])  # RTTTL-like
```

---

# Telemetry & Debug

Monitor your robot's health and performance.

```python
from baracommlib.telemetry import get_telemetry, DebugPrinter

telemetry = get_telemetry()

# In main loop:
telemetry.log(
    sensor_readings={"front": robot.sensor.get("front")},
    motor_status=robot.drivetrain.get_status(),
    vision_fps=robot.vision.get_fps() if robot.vision else None
)

# Debug print
DebugPrinter.sensors("", robot.sensor.get("front"))
DebugPrinter.motors("", robot.drivetrain.get_status())
DebugPrinter.loop_timing("", loop_time, target_hz=20)

# At end of program:
telemetry.print_summary()
```

---

# Obstacle Avoidance

Reactive obstacle avoidance using ToF sensors.

```python
from baracommlib.obstacle_avoidance import ObstacleAvoider

avoider = ObstacleAvoider(
    get_sensor_reading=lambda sid: robot.sensor.get(sid),
    move_forward=lambda s: robot.drivetrain.move_forward_action(s),
    turn_left=lambda s: robot.drivetrain.turn_left_action(s),
    turn_right=lambda s: robot.drivetrain.turn_right_action(s),
    coast=lambda: robot.drivetrain.coast(),
    front_sensor_ids=["front", "front_left", "front_right"],
    left_sensor_ids=["left"],
    right_sensor_ids=["right"],
    safe_distance_mm=150,
    speed=50
)

# In main loop:
while True:
    avoider.update()  # Returns True if action taken
    time.sleep(0.05)
```

---

# State Machine

Define complex robot behaviors as states.

```python
from baracommlib.state_machine import StateMachine, RobotState, State

class DriveForwardState(State):
    def update(self, machine):
        # Your logic
        if machine.get_data("obstacle_detected"):
            return RobotState.AVOIDING
        return None

sm = StateMachine()
sm.add_state(RobotState.IDLE, IdleState())
sm.add_state(RobotState.RUNNING, DriveForwardState())
sm.set_initial(RobotState.IDLE)
sm.start()

while True:
    sm.update()
```

---

# Line Follower

Support for analog reflective sensors.

```python
from baracommlib.line_follower import MultiLineSensor

# Sensors configured in config as line_follower type
line_sensor = MultiLineSensor(robot.config)

# Get position relative to line
position = line_sensor.get_line_position(["lf_1", "lf_2", "lf_3", "lf_4"])
# Returns: "left", "center", "right", or "none"

# Get offset for PID line following
offset = line_sensor.get_line_center_offset(
    sensor_ids=["lf_1", "lf_2", "lf_3", "lf_4"],
    positions=[-30, -10, 10, 30]  # mm from center
)
```