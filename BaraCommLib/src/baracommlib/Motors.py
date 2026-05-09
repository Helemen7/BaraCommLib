import time
import threading
from typing import Optional, Dict, Any

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO

from typing import Literal
from enum import Enum
import math

from .exceptions.MaxPowerExceededException import MaxPowerExceededException

class Motor(Enum):
    A = 0
    B = 1

class MotorIN:
    def __init__(self, pin: int):
        self.pin = pin
        self.lastState = 0

    def set(self, state: Literal[0, 1]):
        GPIO.output(self.pin, state)
        self.lastState = state

class MotorDirection(Enum):
    FORWARD=0
    BACKWARD=1

class Encoder:
    """
    Quadrature encoder reader for wheel odometry.
    Supports both single-channel (tick counting) and dual-channel (direction detection).
    """
    def __init__(self, pin_a: int, pin_b: Optional[int] = None, ticks_per_rev: int = 360):
        """
        Args:
            pin_a: GPIO pin for channel A (required)
            pin_b: GPIO pin for channel B (optional - if None, uses single-channel mode)
            ticks_per_rev: Number of ticks per full wheel revolution (default: 360)
        """
        self.pin_a = pin_a
        self.pin_b = pin_b
        self.ticks_per_rev = ticks_per_rev
        
        self._ticks = 0
        self._last_a_state = 0
        self._last_time = time.time()
        self._lock = threading.Lock()
        
        # Setup GPIO
        GPIO.setup(self.pin_a, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        if self.pin_b:
            GPIO.setup(self.pin_b, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self._last_b_state = GPIO.input(self.pin_b)
        
        # Initial read
        self._last_a_state = GPIO.input(self.pin_a)
        
    def get_ticks(self) -> int:
        """Get total tick count (cumulative)."""
        with self._lock:
            return self._ticks
            
    def reset_ticks(self):
        """Reset tick counter to zero."""
        with self._lock:
            self._ticks = 0
            
    def get_revolutions(self) -> float:
        """Get total revolutions (float)."""
        return self.get_ticks() / self.ticks_per_rev
        
    def get_speed_tps(self) -> float:
        """
        Get current speed in ticks per second.
        Call this frequently (e.g., every 50ms) for accurate readings.
        """
        with self._lock:
            current_time = time.time()
            dt = current_time - self._last_time
            if dt <= 0:
                return 0.0
            # Approximate - this would ideally use callbacks for proper edge detection
            return 0.0 # Will be updated by callback
        
    def _update_callback(self, channel):
        """Callback for edge detection on pin A."""
        with self._lock:
            a_state = GPIO.input(self.pin_a)
            
            if self.pin_b:
                # Quadrature mode - detect direction
                b_state = GPIO.input(self.pin_b)
                
                # Simple direction detection
                if a_state != self._last_a_state:
                    if (a_state and not b_state) or (not a_state and b_state):
                        self._ticks += 1
                    else:
                        self._ticks -= 1
            else:
                # Single channel mode - just count pulses
                self._ticks += 1
                
            self._last_a_state = a_state
            self._last_time = time.time()


class Motors:
    # This class should be the only one accessing its pins.
    def __init__(self, config: dict):
        self.config = config
        
        drivetrain_config = self.config["drivetrain"]
        motors = drivetrain_config["motors"]
        leftA = motors["left"]
        rightB = motors["right"]

        self.AIN1 = MotorIN(leftA["in1"])
        self.AIN2 = MotorIN(leftA["in2"])
        self.BIN1 = MotorIN(rightB["in1"])
        self.BIN2 = MotorIN(rightB["in2"])

        if drivetrain_config["motors"]["left"]["mounted_backwards"]:
            self.AIN1, self.AIN2 = self.AIN2, self.AIN1
        if drivetrain_config["motors"]["right"]["mounted_backwards"]:
            self.BIN1, self.BIN2 = self.BIN2, self.BIN1
        
        self.PWMA = leftA["pwm"]
        self.PWMB = rightB["pwm"]

        GPIO.setmode(GPIO.BCM)
        GPIO.setup([self.AIN1.pin, self.AIN2.pin, self.BIN1.pin, self.BIN2.pin], GPIO.OUT)
        GPIO.setup([self.PWMA, self.PWMB], GPIO.OUT)

        self.pwm_a = GPIO.PWM(self.PWMA, 1000)
        self.pwm_b = GPIO.PWM(self.PWMB, 1000)
        self.pwm_a.start(0)
        self.pwm_b.start(0)
        
        self._is_forced = False
        self._current_action = None  # "forward", "left", "right", None
        self._current_speed = 0
        
        # --- ENCODER SETUP ---
        self._encoder_a: Optional[Encoder] = None
        self._encoder_b: Optional[Encoder] = None
        
        encoders_cfg = drivetrain_config.get("encoders", {})
        if encoders_cfg.get("exists", False):
            ticks = encoders_cfg.get("ticks_per_rev", 360)
            wheel_circ = encoders_cfg.get("wheel_circumference_mm", 200)  # Default ~200mm wheel
            
            left_enc = encoders_cfg.get("left", {})
            if "pin_a" in left_enc:
                self._encoder_a = Encoder(
                    pin_a=left_enc["pin_a"],
                    pin_b=left_enc.get("pin_b"),
                    ticks_per_rev=ticks
                )
                
            right_enc = encoders_cfg.get("right", {})
            if "pin_a" in right_enc:
                self._encoder_b = Encoder(
                    pin_a=right_enc["pin_a"],
                    pin_b=right_enc.get("pin_b"),
                    ticks_per_rev=ticks
                )
                
            # Store wheel params for distance calc
            self._wheel_circumference_mm = wheel_circ
            
        self.coast()

    @property
    def encoder_left(self) -> Optional[Encoder]:
        return self._encoder_a
    
    @property
    def encoder_right(self) -> Optional[Encoder]:
        return self._encoder_b

    def get_encoder_ticks(self) -> Dict[str, int]:
        """Get both encoder tick counts."""
        return {
            "left": self._encoder_a.get_ticks() if self._encoder_a else 0,
            "right": self._encoder_b.get_ticks() if self._encoder_b else 0
        }
        
    def get_encoder_distance_mm(self) -> Dict[str, float]:
        """Get distance traveled in mm for each wheel."""
        ticks_per_mm = self._wheel_circumference_mm / (self._encoder_a.ticks_per_rev if self._encoder_a else 360)
        return {
            "left": (self._encoder_a.get_ticks() if self._encoder_a else 0) * ticks_per_mm,
            "right": (self._encoder_b.get_ticks() if self._encoder_b else 0) * ticks_per_mm
        }
        
    def reset_encoders(self):
        """Reset both encoder tick counters."""
        if self._encoder_a:
            self._encoder_a.reset_ticks()
        if self._encoder_b:
            self._encoder_b.reset_ticks()

    # --- BASIC ACTIONS ---
    
    def move_forward_action(self, speed: int):
        if speed > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = False
        self._current_action = "forward"
        self._current_speed = speed
        
        self.AIN1.set(GPIO.HIGH)
        self.AIN2.set(GPIO.LOW)
        self.BIN1.set(GPIO.HIGH)
        self.BIN2.set(GPIO.LOW)

        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def turn_left_action(self, speed: int):
        if speed > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = False
        self._current_action = "left"
        self._current_speed = speed
        
        self.AIN1.set(GPIO.LOW)
        self.AIN2.set(GPIO.HIGH)
        self.BIN1.set(GPIO.HIGH)
        self.BIN2.set(GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def turn_right_action(self, speed: int):
        if speed > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = False
        self._current_action = "right"
        self._current_speed = speed
        
        self.AIN1.set(GPIO.HIGH)
        self.AIN2.set(GPIO.LOW)
        self.BIN1.set(GPIO.LOW)
        self.BIN2.set(GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def coast(self):
        self._is_forced = False
        self._current_action = None
        self._current_speed = 0
        
        self.AIN1.set(GPIO.LOW)
        self.AIN2.set(GPIO.LOW)
        self.BIN1.set(GPIO.LOW)
        self.BIN2.set(GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(0)
        self.pwm_b.ChangeDutyCycle(0)

    def force_brake(self, max_pwm_value: int):
        if max_pwm_value > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = True
        self._current_action = "brake"
        self._current_speed = 0
        
        self.AIN1.set(GPIO.HIGH)
        self.AIN2.set(GPIO.HIGH)
        self.BIN1.set(GPIO.HIGH)
        self.BIN2.set(GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(max_pwm_value)
        self.pwm_b.ChangeDutyCycle(max_pwm_value)

    def stop(self):
        """Stops the drivetrain safely (same as coast). Used by fail-safe recovery."""
        self.coast()
    
    def assign_manual_power(self, motor: Motor, power: int):
        if power > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = False
        if motor == Motor.A:
            self.pwm_a.ChangeDutyCycle(power)
        elif motor == Motor.B:
            self.pwm_b.ChangeDutyCycle(power)
    
    def are_forced(self) -> bool:
        return self._is_forced
    
    def get_motor_state(self, motor: Motor, direction: MotorDirection) -> Literal[0, 1]:
        if motor == Motor.A:
            if direction == MotorDirection.FORWARD:
                return 1 if GPIO.input(self.AIN1.pin) else 0
            elif direction == MotorDirection.BACKWARD:
                return 1 if GPIO.input(self.AIN2.pin) else 0
        elif motor == Motor.B:
            if direction == MotorDirection.FORWARD:
                return 1 if GPIO.input(self.BIN1.pin) else 0
            elif direction == MotorDirection.BACKWARD:
                return 1 if GPIO.input(self.BIN2.pin) else 0
        
        raise RuntimeError(f"Invalid motor {motor} or direction {direction}")
    
    def health_check(self) -> bool:
        pins_to_check = [self.AIN1, self.AIN2, self.BIN1, self.BIN2]
        
        for motor_in in pins_to_check:
            actual_state = GPIO.input(motor_in.pin)
            if actual_state != motor_in.lastState:
                return False
                
        return True
    
    # --- HIGH-LEVEL PRIMITIVES ---
    
    def drive(self, duration_seconds: float, speed: Optional[int] = None):
        """
        Drive forward for a specific duration.
        
        Args:
            duration_seconds: How long to drive
            speed: Optional speed override (uses base_speed from config if None)
        """
        if speed is None:
            speed = self.config.get("robot", {}).get("base_speed", 50)
            
        self.move_forward_action(speed)
        time.sleep(duration_seconds)
        self.coast()
        
    def drive_distance(self, distance_mm: float, speed: Optional[int] = None):
        """
        Drive forward for a specific distance using encoders.
        Requires encoders to be configured!
        
        Args:
            distance_mm: Target distance in millimeters
            speed: Optional speed override
        """
        if not self._encoder_a or not self._encoder_b:
            raise RuntimeError("Encoders not configured. Cannot use drive_distance().")
            
        if speed is None:
            speed = self.config.get("robot", {}).get("base_speed", 50)
            
        self.reset_encoders()
        
        # Calculate target ticks
        ticks_per_mm = self._encoder_a.ticks_per_rev / self._wheel_circumference_mm
        target_ticks = int(distance_mm * ticks_per_mm)
        
        self.move_forward_action(speed)
        
        # Wait until either wheel reaches target
        while abs(self._encoder_a.get_ticks()) < target_ticks:
            time.sleep(0.01)
            
        self.coast()
        
    def spin(self, degrees: float, speed: Optional[int] = None, use_gyro: bool = False, gyro_sensor_id: Optional[str] = None, sensor_getter=None):
        """
        Spin in place for a specific angle.
        
        Args:
            degrees: Angle to spin (positive = right, negative = left)
            speed: Speed for turning
            use_gyro: If True, use gyro for precise angle (requires sensor_getter)
            gyro_sensor_id: ID of the gyro sensor
            sensor_getter: Function to get sensor reading (lambda)
        """
        if speed is None:
            speed = self.config.get("robot", {}).get("base_speed", 50)
            
        if use_gyro and sensor_getter and gyro_sensor_id:
            # Use PID-like approach with gyro for precise turns
            initial = sensor_getter(gyro_sensor_id)
            if not initial:
                raise RuntimeError(f"Gyro sensor '{gyro_sensor_id}' not available")
                
            initial_yaw = initial.get("yaw", 0)
            target_yaw = (initial_yaw + degrees) % 360.0
            
            if degrees > 0:
                self.turn_right_action(speed)
            else:
                self.turn_left_action(speed)
                
            while True:
                current = sensor_getter(gyro_sensor_id)
                if not current:
                    continue
                current_yaw = current.get("yaw", 0)
                
                diff = (target_yaw - current_yaw + 180) % 360 - 180
                if abs(diff) <= 2.0:  # 2 degree tolerance
                    break
                time.sleep(0.01)
                
            self.coast()
        else:
            # Time-based spin (less precise)
            # Rough estimate: 360 degrees ~ 2.5 seconds at speed 50
            # This is approximate and depends on surface/battery
            time_factor = abs(degrees) / 360.0 * 2.5  # seconds for full rotation
            time_seconds = time_factor * (50 / speed)  # scale by speed
            
            if degrees > 0:
                self.turn_right_action(speed)
            else:
                self.turn_left_action(speed)
                
            time.sleep(time_seconds)
            self.coast()

    # --- TELEMETRY ---
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive motor status for debugging."""
        return {
            "action": self._current_action,
            "speed": self._current_speed,
            "is_forced": self._is_forced,
            "encoders": self.get_encoder_ticks() if (self._encoder_a or self._encoder_b) else None,
            "distances_mm": self.get_encoder_distance_mm() if (self._encoder_a and self._encoder_b) else None
        }