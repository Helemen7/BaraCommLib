try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO

from typing import *
from enum import Enum

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
    # This represents difference between AIN1 and AIN2 etc
    FORWARD=0
    BACKWARD=1


class Motors:
    # This class should be the only one accessing its pins. Undefined behaviour might happen if pins are edited
    def __init__(self, config: dict):
        self.config = config
        
        # Accessing nested dictionaries directly to fail fast with KeyError if configuration is missing
        drivetrain_config = self.config["drivetrain"]
        motors = drivetrain_config["motors"]
        leftA = motors["left"]
        rightB = motors["right"]

        self.AIN1 = MotorIN(leftA["in1"])
        self.AIN2 = MotorIN(leftA["in2"])
        self.BIN1 = MotorIN(rightB["in1"])
        self.BIN2 = MotorIN(rightB["in2"])

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

        # Set default state
        self.coast()

    def move_forward_action(self, speed: int):
        if speed > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = False
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
        self.AIN1.set(GPIO.HIGH)
        self.AIN2.set(GPIO.LOW)
        self.BIN1.set(GPIO.LOW)
        self.BIN2.set(GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def coast(self):
        self._is_forced = False
        self.AIN1.set(GPIO.LOW)
        self.AIN2.set(GPIO.LOW)
        self.BIN1.set(GPIO.LOW)
        self.BIN2.set(GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(0)
        self.pwm_b.ChangeDutyCycle(0)

    def force_brake(self, max_pwm_value: int):
        # This shouldn't be kept on for more then a few seconds because it puts strains on components like H bridge and motors.
        # Should this be wrapped in a thread that coasts and blocks execution if this state is kept for too long
        if max_pwm_value > self.config["drivetrain"]["max_pwm_value"]:
            raise MaxPowerExceededException("Max power exceeded. Set max_pwm_value in config or lower speed.")
        self._is_forced = True
        self.AIN1.set(GPIO.HIGH)
        self.AIN2.set(GPIO.HIGH)
        self.BIN1.set(GPIO.HIGH)
        self.BIN2.set(GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(max_pwm_value)
        self.pwm_b.ChangeDutyCycle(max_pwm_value)
    
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
        """
        Returns the actual motor assigned state read directly from the hardware pin.
        """
        if motor == Motor.A:
            if direction == MotorDirection.FORWARD:
                return GPIO.input(self.AIN1.pin)
            elif direction == MotorDirection.BACKWARD:
                return GPIO.input(self.AIN2.pin)
        elif motor == Motor.B:
            if direction == MotorDirection.FORWARD:
                return GPIO.input(self.BIN1.pin)
            elif direction == MotorDirection.BACKWARD:
                return GPIO.input(self.BIN2.pin)
        
        raise RuntimeError(f"Invalid motor {motor} or direction {direction}")
    
    def health_check(self) -> bool:
        """
        Checks if all motor pins' actual hardware states match the last assigned states.
        Returns True if healthy (synced), False if out of sync.
        """
        pins_to_check = [self.AIN1, self.AIN2, self.BIN1, self.BIN2]
        
        for motor_in in pins_to_check:
            # Read the actual hardware state
            actual_state = GPIO.input(motor_in.pin)
            
            # Compare with the internal software state
            if actual_state != motor_in.lastState:
                return False
                
        return True