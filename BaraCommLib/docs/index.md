# BaraCommLib - Official Documentation

Welcome to the comprehensive documentation of **BaraCommLib**. This library provides a robust, safe, asynchronous, and fail-safe interface for controlling Raspberry Pi-based robots (like the Capybara project).

---

## Complete Documentation Index

### Guides (Detailed Reference)

| Guide | Description | Link |
|-------|-------------|------|
| **BaraRobot Class** | Complete API reference with all methods, parameters, and advanced patterns | [bararobot.md](bararobot.md) |
| **Motors & Movement** | Encoder odometry, precise turns, health checks, manual control | [motors.md](motors.md) |
| **Sensors & Perception** | Async polling, IMU fusion, ToF management, reading age tracking | [sensors.md](sensors.md) |
| **Fail-Safe System** | Automatic crash recovery, sensor reinitialization, emergency stop | [fail_safe.md](fail_safe.md) |
| **Configuration Management** | Complete YAML reference, validation rules, troubleshooting | [configuration.md](configuration.md) |
| **PC Development & Mocking** | Cross-platform testing guide, migration checklist | [development.md](development.md) |

### Quick Reference Guides

- **[Computer Vision & AI](vision.md)** - Real-time inference pipeline with color tracking
- **[PID Controller & IO](pid_io.md)** - Motion control, LEDs, buzzers, obstacle avoidance, state machines
- **[BaraRobot Quick Guide](bararobot.md)** - High-level API overview
- **[Motors Quick Guide](motors.md)** - Basic motor control reference
- **[Sensors Quick Guide](sensors.md)** - Sensor access patterns
- **[Fail-Safe Overview](fail_safe.md)** - Crash recovery basics

---

## Architecture Overview

The architecture is divided into three main pillars:
1. **Configuration** - Hardware validation and pin management
2. **Movement (Drivetrain)** - Motor control with encoder feedback
3. **Sensors & Perception** - Asynchronous sensor polling and computer vision

> [!NOTE]
> Everything has been designed to be fully testable even on non-ARM PCs via a sophisticated automatic Mocking system for GPIO and I2C.

---

## Documentation Index

### Core Components (Start Here!)

1. **[BaraRobot Class](bararobot.md)** - **Complete High-Level API**  
   One class for everything: motors, sensors, vision, IO devices
   
2. **[Motors & Movement](motors.md)** - **Differential Drive Control**  
   Encoder-based odometry, precise turns, health checks, manual motor control

3. **[Sensors & Perception](sensors.md)** - **Asynchronous Sensor System**  
   Background polling, IMU fusion, ToF management, reading age tracking

### Advanced Features

4. **[Fail-Safe System](fail_safe.md)** - **Automatic Crash Recovery**  
   5-second failure detection, sensor reinitialization, emergency stop

5. **[Computer Vision & AI](vision.md)** - **Real-Time Inference Pipeline**  
   Dataset generation, transfer learning, color tracking, multi-region detection

6. **[PID Controller & IO](pid_io.md)** - **Motion Control & Output Devices**  
   Position/velocity PID, LEDs, buzzers, obstacle avoidance, state machines

### Configuration & Development

7. **[Configuration Management](configuration.md)** - **YAML Validation & Safety**  
   Pin collision detection, I2C address validation, default config injection

8. **[PC Development & Mocking](development.md)** - **Cross-Platform Testing**  
   GPIO/I2C mocking for Windows/Mac/Linux development without Raspberry Pi

---

## Quick Start Example

Here's how all components come together in a classic `main.py` file:

```python
import time
from baracommlib.BaraRobot import BaraRobot

# 1. Initialize robot (auto-loads config, validates pins, starts motors)
robot = BaraRobot("baraconfig.yaml")

try:
    while True:
        # Hardware safety check
        if not robot.drivetrain.health_check():
            print("CRITICAL: Motors desynchronized!")
            robot.cleanup()
            break
            
        # Instant O(1) sensor access (non-blocking!)
        front_distance = robot.sensor.get_average_by_direction("front")
        
        # Obstacle avoidance logic
        if front_distance and front_distance < 150:
            robot.drivetrain.turn_left_action(50)
        else:
            robot.drivetrain.move_forward_action(80)
            
        time.sleep(0.05)

except KeyboardInterrupt:
    print("Shutting down...")
finally:
    # Critical: Always call cleanup to release hardware!
    robot.cleanup()
```

---

##  Key Features

### Fail Fast, Fail Safe
> [!TIP]
> If you misconfigure a pin (e.g., two components share the same GPIO), the library immediately raises an exception at boot - long before the robot can move or cause damage.

### Non-Blocking by Design
> [!NOTE]
> Sensor readings happen in background threads. Your main logic **never** has to wait 30-100ms for I2C sensors to respond. Critical for timing-sensitive algorithms like PIDs and vision loops.

### Hardware-Truth Validation
> [!WARNING]
> `health_check` functions don't blindly trust software variables - they directly poll hardware pins to detect desynchronizations, floating wires, or external interference.

---

##  Component Deep Dives

### 1. BaraRobot Class

The main entry point that abstracts all hardware complexity:

```python
robot = BaraRobot("baraconfig.yaml")

# Access subsystems
robot.drivetrain      # Motor control with encoders
robot.sensor          # Instant sensor access (O(1))
robot.vision          # Computer vision & AI
robot.io              # LEDs, buzzers, buttons
```

**Key Methods:**
- `on_button_pressed(button_id)` - Async button handler decorator
- `turn(angle=90, speed=50)` - Gyro-assisted relative turns
- `cleanup()` - **Mandatory** for safe shutdown

### 2. Motors & Movement

Precise differential drive control:

```python
# Basic actions
robot.drivetrain.move_forward_action(80)
robot.drivetrain.turn_left_action(50)

# Encoder-based precision
robot.drivetrain.drive_distance(distance_mm=1000)  # Drive exactly 1m
robot.drivetrain.spin(degrees=90, use_gyro=True)   # Precise turn

# Manual control
from baracommlib.Motors import Motor
robot.drivetrain.assign_manual_power(Motor.A, power=70)
```

### 3. Sensors & Perception

Asynchronous sensor polling with automatic averaging:

```python
# Single sensor (instant O(1))
distance = robot.sensor.get("front_tof")

# Grouped by direction
front_sensors = robot.sensor.get_by_direction("front")
avg_distance = robot.sensor.get_average_by_direction("front")  # Auto-filters failures

# IMU with calibration
gyro = robot.sensor.get("main_gyro")
offsets = gyro.calibrate(samples=100)
adjusted = gyro.get_value_adjusted()  # Offsets applied automatically
```

### 4. Computer Vision

Complete AI pipeline from dataset to inference:

```python
# Dataset generation (PC tools)
from baracommlib.vision import DatasetTool, AutoTrainer

DatasetTool.generate(
    input_folder="raw_photos",
    output_folder="dataset",
    variants_per_image=50,
    create_background_class=True
)

AutoTrainer.train_classifier(
    dataset_folder="dataset",
    output_model_path="robot_brain.tflite",
    epochs=10
)

# Runtime inference (Raspberry Pi)
result = robot.vision.classify("main_cam")
print(f"I see a {result['label']} with {result['confidence']*100:.1f}% certainty!")
```

### 5. Fail-Safe System

Automatic recovery from sensor failures:

```python
# Automatic after 5+ seconds of continuous failure:
# 1. Stop drivetrain immediately
# 2. Reinitialize failed sensors on same I2C bus
# 3. Sequential startup (critical for ToF address management)

# No configuration needed - always enabled!
robot = BaraRobot("baraconfig.yaml")
```

### 6. PID Controller

Precise motion control:

```python
from baracommlib.pid_controller import PositionPID, VelocityPID

# Position PID (reach specific distance/angle)
pos_pid = PositionPID(kp=1.5, ki=0.05, kd=0.5, max_speed=100)
while not pos_pid.target_reached:
    current = robot.drivetrain.get_encoder_distance_mm()['left']
    speed = pos_pid.compute(current, target_position=1000)
    robot.drivetrain.move_forward_action(speed)

# Velocity PID (maintain constant speed)
vel_pid = VelocityPID(kp=1.0, ki=0.1, kd=0.05, max_pwm=100)
current_speed = get_encoder_speed()  # From encoder callback
pwm = vel_pid.compute(current_speed, target_speed=200)
```

---

##  Configuration Guide

### Minimal Working Config

```yaml
# baraconfig.yaml

robot:
  name: "My Robot"
  base_speed: 100

drivetrain:
  max_pwm_value: 100
  motors:
    left:
      in1: 12
      in2: 13
      pwm: 19
      mounted_backwards: false
    right:
      in1: 14
      in2: 18
      pwm: 29
      mounted_backwards: false

sensors:
  buses:
    - id: "i2c_1"
      scl_pin: 22
      sda_pin: 21
      frequency: 400000
  
  tof:
    - id: "front"
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

io:
  buttons:
    - id: "start"
      pin: 0
      pull: "up"
  
  leds:
    - id: "status"
      pin: 2
      pwm: false
  
  buzzers:
    - id: "alarm"
      pin: 3

vision:
  enabled: false
```

> [!TIP]
> Run `python tests/test_general.py` to validate your configuration before deploying to hardware.

---

## Development on PC (No Raspberry Pi Required)

BaraCommLib includes transparent mocking for cross-platform development:

```bash
# On Windows/Mac - just run your code!
PYTHONPATH=./src python main.py

# Output will show: "Using Mock GPIO for development."
# All logic works identically to RPi - no changes needed!
```

**What gets mocked:**
- `RPi.GPIO` → `_MockGPIO` (dictionary-based pin state)
- `adafruit_blinka`, `board`, `busio` → Stub classes
- I2C sensors return safe fallback values (e.g., 0.0 for distance)

> [!IMPORTANT]
> The mock output is intentionally visible so you don't forget to install real libraries before deploying!

---

## Telemetry & Debugging

Monitor robot health and performance:

```python
from baracommlib.telemetry import get_telemetry, DebugPrinter

telemetry = get_telemetry()

while True:
    telemetry.log(
        sensor_readings={"front": robot.sensor.get("front")},
        motor_status=robot.drivetrain.get_status(),
        vision_fps=robot.vision.get_fps() if robot.vision else None
    )
    
    DebugPrinter.sensors("", {"front": 150})
    DebugPrinter.motors("", robot.drivetrain.get_status())
    DebugPrinter.loop_timing("", loop_time, target_hz=20)
```

---

## Best Practices

### Always Call cleanup()

```python
try:
    while True:
        # Your main loop
        pass
except KeyboardInterrupt:
    pass
finally:
    robot.cleanup()  # ← CRITICAL! Releases GPIO, I2C, cameras
```

**Why?** Without `cleanup()`:
- Motors may continue receiving old PWM signals after crash
- GPIO pins remain in undefined states
- Camera devices (`/dev/video0`) stay locked - require reboot to release

### Validate Configuration First

```bash
# Test config before deploying to hardware
python tests/test_general.py

# Or programmatically:
from baracommlib.config_manager import ConfigManager
manager = ConfigManager("baraconfig.yaml")
try:
    config = manager.load_and_validate()
    print("Configuration valid!")
except RuntimeError as e:
    print(f"Error: {e}")
```

### Use Average for Grouped Sensors

```python
# Better than individual readings (filters out failures/noise):
avg_distance = robot.sensor.get_average_by_direction("front")

if avg_distance and avg_distance < 100:
    # React to obstacle
    pass
```

---

## 🔧 Troubleshooting Quick Reference

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| "Pin collision!" error | Duplicate GPIO pin assignment | Check config for duplicate pins |
| Sensor returns None continuously | I2C wiring/power issue | Verify connections, check power supply |
| Robot spins instead of moving forward | Motors mounted backwards | Set `mounted_backwards: true` in config |
| Low FPS on vision module | Model not quantized / high resolution | Use 320x240 res, ensure int8 TFLite model |
| Fail-safe triggers but robot doesn't stop | Missing callback | Add `stop_robot_callback=drivetrain.stop` to SensorsManager |

---

## Dependencies

### Raspberry Pi (Runtime)
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip -y
pip3 install adafruit-circuitpython-blinka adafruit-circuitpython-gpio adafruit-circuitpython-boarddetect
pip3 install opencv-python numpy tflite-runtime
```

### PC (Development)
No additional dependencies required! Mocking is built-in.

---

## Contributing & Support

Found undocumented features or bugs? Check the source code in `BaraCommLib/src/baracommlib/`. The library follows a "document what exists" philosophy - if you find functionality not documented, please open an issue or PR!

---

## External Resources

- [Issue Tracker](https://github.com/Helemen7/BaraCommLib/issues)
- [Raspberry Pi Documentation](https://www.raspberrypi.com/documentation/)
