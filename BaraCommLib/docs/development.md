# PC Development & Cross-Platform Testing Guide

BaraCommLib enables full robot software development on Windows, macOS, or Linux without requiring a Raspberry Pi. The library automatically detects when running on non-RPi hardware and switches to **transparent mocking** for GPIO and I2C operations.

---

## Why Mocking Matters

Developing robot code on a PC offers significant advantages:
- No need for physical hardware during development
- Faster iteration cycles (no boot time, no wiring issues)
- Test edge cases safely without risking damage
- CI/CD integration possible
- Team collaboration easier (everyone develops on same platform)

**The challenge**: GPIO pins and I2C buses don't exist on Windows/Mac. BaraCommLib solves this with intelligent mocking.

---

## How Mocking Works

### Automatic Detection

When you import `RPi.GPIO`, the library checks if it's actually available:

```python
# In baracommlib/__init__.py and other modules:
try:
    import RPi.GPIO as GPIO  # ← Try to import real GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO  # ← Fall back to mock!
```

### GPIO Mock Implementation (`_MockGPIO`)

The `_MockGPIO` class masks the real `RPi.GPIO` with a dictionary-based implementation:

```python
# _MockGPIO implementation (simplified)
class _MockGPIO:
    def __init__(self):
        self._pins = {}  # Pin number → state dictionary
    
    def setup(self, pin, mode, pull_up_down=GPIO.PUD_OFF):
        """Does nothing - just tracks that this pin is 'used'"""
        pass
    
    def output(self, pin, value):
        """Records the intended output state"""
        self._pins[pin] = value  # Store in memory, not silicon!
    
    def input(self, pin):
        """Returns what was last set with output()"""
        return self._pins.get(pin, 0)  # Return cached value
    
    def PWM(self, pin, frequency):
        """Mock PWM object that does nothing"""
        class MockPWM:
            def start(self, duty_cycle): pass
            def ChangeDutyCycle(self, val): pass
            def stop(self): pass
        return MockPWM()

# Your code works identically on both platforms!
GPIO.setup(12, GPIO.OUT)      # Mock: records in dict
GPIO.output(12, GPIO.HIGH)    # Mock: stores HIGH
state = GPIO.input(12)         # Mock: returns HIGH (from cache)
```

### I2C Mock Implementation (Blinka)

Similarly, Blinka libraries are mocked with stub classes:

```python
# In sensors.py:
try:
    import board
    import busio
    import adafruit_vl53l1x  # ← Real hardware
except (ImportError, NotImplementedError):
    class _MockBoard: pass
    class _MockBusIO:
        class I2C:
            def __init__(self, scl, sda, frequency=100000): pass
            def unlock(self): pass
    
    board = _MockBoard()
    busio = _MockBusIO()

# Sensor initialization succeeds but returns safe fallbacks:
sensor = VL53L1X(i2c_bus)  # Mock: creates stub object
distance = sensor.distance  # Returns 0.0 (safe default, not None!)
```

---

## Running Code on PC

### Method 1: PYTHONPATH (Recommended)

```bash
# From BaraCommLib directory
cd /path/to/BaraCommLib
PYTHONPATH=./src python main.py

# Or from anywhere else
PYTHONPATH=/full/path/to/BaraCommLib/src python /path/to/your/script/main.py
```

### Method 2: Virtual Environment Setup

Create a development environment:

```bash
# Create venv
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies (optional, for testing real hardware later)
pip install opencv-python numpy

# Run your code
PYTHONPATH=$PWD python main.py
```

### Method 3: IDE Configuration

**VS Code:**
1. Add to `.vscode/settings.json`:
```json
{
    "python.defaultInterpreterPath": "/path/to/venv/bin/python",
    "python.envFile": "${workspaceFolder}/.env"
}
```

2. Add `PYTHONPATH` to environment variables in launch configuration:
```json
{
    "name": "Debug Robot Code",
    "type": "debugpy",
    "request": "launch",
    "program": "${file}",
    "env": {
        "PYTHONPATH": "${workspaceFolder}/src"
    }
}
```

**PyCharm:**
1. Go to Run → Edit Configurations
2. Add environment variable: `PYTHONPATH=/full/path/to/BaraCommLib/src`
3. Select the correct interpreter (your venv)

---

## What Gets Mocked

### GPIO System

| Real RPi | PC Mock | Behavior |
|----------|---------|----------|
| `RPi.GPIO` module | `_MockGPIO` class | Tracks pin states in memory dictionary |
| `GPIO.setup()` | No-op | Records intended configuration |
| `GPIO.output(pin, value)` | Stores in dict | Caches output state |
| `GPIO.input(pin)` | Returns cached value | Returns what was last set |
| `GPIO.PWM()` | Mock PWM object | Does nothing (no actual PWM) |
| `GPIO.cleanup()` | Clears dictionary | Resets mock state |

**Key Insight**: All your logic code (PID calculations, safety checks, health monitoring) works **exactly the same** on PC as on RPi. The mock just doesn't affect real hardware because there is none!

### I2C/Blinka System

| Real RPi | PC Mock | Behavior |
|----------|---------|----------|
| `adafruit_blinka` | Stub classes | No actual I2C communication |
| `board.Dx` | Mock pin objects | No real GPIO access |
| `busio.I2C()` | Mock I2C object | No hardware bus creation |
| Sensor initialization | Creates stub objects | Succeeds without error |
| `_read_hardware()` | Returns safe defaults | e.g., 0.0 for distance, {} for IMU |

**Important**: Sensors return **safe fallback values**, not `None` or exceptions:
- ToF sensors → `0.0` cm (not `None`)
- IMU sensors → `{"yaw": 0.0, "pitch": 0.0, "roll": 0.0}`
- This allows your main loop to run without errors

---

## Testing Scenarios on PC

### Test 1: Basic Motor Control Logic

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# This runs fine on PC - GPIO mock handles it!
for i in range(5):
    robot.drivetrain.move_forward_action(80)
    
    # Health check works (mock returns True since no actual pins to check)
    if not robot.drivetrain.health_check():
        print("Motor desync!")
        
    time.sleep(1)

robot.cleanup()  # Mock GPIO cleanup - does nothing but safe
```

**Output on PC:**
```
Using Mock GPIO for development.
[No hardware errors - all operations succeed]
```

### Test 2: Sensor Reading Patterns

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Background threads start (mocked)
# They run but return safe defaults instead of actual sensor data

while True:
    # These never block - mock returns instantly!
    distance = robot.sensor.get("front_tof")  # Returns 0.0
    
    age = robot.sensor.get_sensor("front_tof").get_reading_age()
    print(f"Distance: {distance}, Age: {age}s")  # Always fresh (mocked)
    
    time.sleep(0.1)

robot.cleanup()
```

**Output on PC:**
```
Using Mock I2C/Board for development.
Distance: 0.0, Age: 0.0s
Distance: 0.0, Age: 0.0s
...
```

### Test 3: Vision System (No Camera Required)

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# If vision enabled but no camera connected:
# - Model loads successfully (file check only)
# - Camera thread starts with mock VideoCapture
# - get_latest_frame() returns None (safe default)

while True:
    result = robot.vision.classify("main_cam")
    
    if "error" in result:
        print(f"Vision error (expected on PC): {result['error']}")
        
    time.sleep(0.1)

robot.cleanup()  # Releases mock camera resources
```

### Test 4: Fail-Safe System

```python
from baracommlib.BaraRobot import BaraRobot

robot = BaraRobot("baraconfig.yaml")

# Simulate sensor failure by manually setting reading to None
sensor = robot.sensor.get_sensor("front_tof")
if sensor:
    # Mock behavior - consecutive errors tracked but never reach 5s threshold
    for i in range(10):
        print(f"Test {i+1}: Sensor would fail here (mocked)")
        
# On PC, the mock doesn't actually fail - it just returns safe defaults
# This is intentional: you can't test actual hardware failures without hardware!

robot.cleanup()
```

**Note**: You **cannot** fully test fail-safe behavior on PC because there's no real hardware to fail. The mocking prevents crashes but also prevents failure scenarios. Use the automated test suite (`tests/test_general.py`) which injects simulated failures programmatically.

---

## Migration Checklist: PC → Raspberry Pi

Before deploying to actual hardware, verify these items:

### Pre-Deployment Checks

```bash
# 1. Validate configuration
python validate_config.py
# Must output "Configuration is valid!"

# 2. Check all dependencies installed on RPi
sudo apt list --installed | grep -E "(adafruit|opencv|numpy)"
pip3 list | grep -E "(tflite|tensorflow)"

# 3. Verify I2C enabled in raspi-config
# Run: sudo raspi-config → Interface Options → I2C → Enable

# 4. Check camera permissions (if using vision)
sudo apt install libcamera-bin  # Or v4l-utils for older Pi
```

### Deployment Steps

1. **Copy files to RPi:**
   ```bash
   scp -r src/ pi@raspberrypi:/home/pi/baracommlib/
   scp main.py pi@raspberrypi:/home/pi/
   scp baraconfig.yaml pi@raspberrypi:/home/pi/
   ```

2. **Update PYTHONPATH on RPi:**
   ```bash
   # Add to ~/.bashrc or ~/.profile
   export PYTHONPATH=/home/pi/baracommlib/src:$PYTHONPATH
   
   source ~/.bashrc
   ```

3. **Test with real hardware:**
   ```bash
   cd /home/pi
   python main.py
   
   # Watch for: "RPi.GPIO not found" → Should NOT appear on RPi!
   ```

4. **Verify sensor readings are actual values (not mocks):**
   ```python
   distance = robot.sensor.get("front_tof")
   print(f"Distance: {distance}")  # Should be real measurement, not 0.0
   
   if distance == 0.0 and you_know_there's_an_obstacle:
       print("Still getting mock values - check I2C wiring!")
   ```

---

## Debugging Mock vs Real Behavior

### Common Issue: Code Works on PC but Not on RPi

**Symptom**: Logic works perfectly in development, fails after deployment.

**Diagnosis:**
```python
# Add this to your code temporarily:
import sys
print(f"Platform: {sys.platform}")  # linux -> RPi, win32/win64 -> Windows

try:
    import RPi.GPIO as GPIO
    print("Real GPIO imported")
except ImportError:
    print("Using mock GPIO")
```

**Solution**: Ensure all dependencies are installed on target hardware.

### Common Issue: Sensor Returns 0.0 (Mock Value)

**Symptom**: Distance always shows 0.0 even with obstacles present.

**Diagnosis:**
```python
sensor = robot.sensor.get_sensor("front_tof")
if sensor:
    age = sensor.get_reading_age()
    
    if age > 1.0:  # More than 1 second old
        print(f"Sensor thread stalled! Age: {age:.1f}s")
    else:
        print("Sensor thread active (mock or real)")
```

**Solution**: Check I2C wiring, power supply, and sensor model matching.

---

## Advanced: Custom Mock Behavior

For testing specific scenarios without hardware, you can customize mock behavior:

### Test Button Presses Programmatically

```python
# In your test script
from baracommlib.BaraRobot import BaraRobot
import time

robot = BaraRobot("baraconfig.yaml")

# Simulate button press by directly manipulating mock state
if hasattr(robot, '_button_callbacks'):
    # Trigger callback manually (bypasses actual GPIO polling)
    if "start" in robot._button_callbacks:
        print("Simulating start button press...")
        robot._button_callbacks["start"]()  # Your function runs!

robot.cleanup()
```

### Test Sensor Failures with Time Control

```python
import time

def test_sensor_failure_recovery():
    """Test fail-safe by waiting for 5+ seconds of mock failures"""
    
    # On PC, you can't trigger real hardware failure
    # But you can test the logic path:
    
    print("Testing fail-safe timeout logic...")
    
    # This would take 5+ seconds in real code
    # For testing, use a shorter threshold temporarily
    
    start_time = time.time()
    while (time.time() - start_time) < 2.0:  # Shortened for testing
        print(f"Waiting for failure detection... {time.time() - start_time:.1f}s")
        time.sleep(0.5)
    
    print("Test complete - fail-safe would trigger after 5s on real hardware")

test_sensor_failure_recovery()
```

---

## Related Documentation

- [BaraRobot](./bararobot.md) - Runtime usage patterns
- [Fail-Safe System](./fail_safe.md) - Testing procedures
- [Configuration Guide](./configuration.md) - YAML setup for different hardware

---

## Quick Reference: Development Commands

```bash
# PC Development (Windows/Mac/Linux without RPi)
PYTHONPATH=./src python main.py

# Validate configuration before deployment
python validate_config.py

# Run automated tests (includes mock testing)
PYTHONPATH=./src python tests/test_general.py

# Generate dataset on powerful PC
PYTHONPATH=./src python tests/example_dataset_gen.py

# Train model on powerful PC  
PYTHONPATH=./src python tests/example_model_train.py

# Deploy to RPi:
scp -r src/ pi@raspberrypi:/home/pi/baracommlib/
scp main.py baraconfig.yaml pi@raspberrypi:/home/pi/
```
