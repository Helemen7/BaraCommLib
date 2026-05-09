"""
IO Module: LEDs, Buzzers, and general output devices.
"""

import time
import threading
from typing import Optional

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO

class LED:
    """Simple LED control."""
    
    def __init__(self, pin: int, pwm_enabled: bool = False):
        self.pin = pin
        self.pwm_enabled = pwm_enabled
        self._pwm = None
        self._is_on = False
        
        GPIO.setup(pin, GPIO.OUT)
        
        if pwm_enabled:
            self._pwm = GPIO.PWM(pin, 1000)  # 1kHz PWM
            self._pwm.start(0)
    
    def on(self, brightness: int = 100):
        """Turn LED on."""
        if self.pwm_enabled:
            self._pwm.ChangeDutyCycle(brightness)
        else:
            GPIO.output(self.pin, GPIO.HIGH)
        self._is_on = True
        
    def off(self):
        """Turn LED off."""
        if self.pwm_enabled:
            self._pwm.ChangeDutyCycle(0)
        else:
            GPIO.output(self.pin, GPIO.LOW)
        self._is_on = False
        
    def toggle(self):
        """Toggle LED state."""
        if self._is_on:
            self.off()
        else:
            self.on()
            
    def blink(self, times: int = 1, duration_ms: int = 200):
        """Blink LED N times."""
        for _ in range(times):
            self.on()
            time.sleep(duration_ms / 1000.0)
            self.off()
            time.sleep(duration_ms / 1000.0)
            
    def cleanup(self):
        if self._pwm:
            self._pwm.stop()

class Buzzer:
    """Simple buzzer/beeper control."""
    
    def __init__(self, pin: int):
        self.pin = pin
        self._pwm = None
        self._is_playing = False
        
        GPIO.setup(pin, GPIO.OUT)
        self._pwm = GPIO.PWM(pin, 1000)
        self._pwm.start(0)
        
    def beep(self, duration_ms: int = 100, frequency: int = 1000):
        """Play a single beep."""
        self._pwm.ChangeFrequency(frequency)
        self._pwm.ChangeDutyCycle(50)
        time.sleep(duration_ms / 1000.0)
        self._pwm.ChangeDutyCycle(0)
        
    def tone(self, frequency: int = 1000, duration_ms: Optional[int] = None):
        """Play a tone at given frequency."""
        self._pwm.ChangeFrequency(frequency)
        self._pwm.ChangeDutyCycle(50)
        self._is_playing = True
        
        if duration_ms:
            time.sleep(duration_ms / 1000.0)
            self.stop()
            
    def stop(self):
        """Stop playing."""
        self._pwm.ChangeDutyCycle(0)
        self._is_playing = False
        
    def play_sequence(self, notes: list):
        """
        Play a sequence of beeps.
        notes format: [(frequency, duration_ms), ...]
        Example: [(440, 200), (880, 200), (440, 200)]
        """
        for freq, duration in notes:
            self.tone(freq, duration)
            time.sleep(0.05)  # Small gap between notes
            
    def cleanup(self):
        if self._pwm:
            self._pwm.stop()

class IOManager:
    """
    Manages all IO devices from config.
    """
    def __init__(self, config: dict):
        self.config = config
        self._leds: dict[str, LED] = {}
        self._buzzers: dict[str, Buzzer] = {}
        
        self._init_devices()
        
    def _init_devices(self):
        io_config = self.config.get("io", {})
        
        # Initialize LEDs
        leds_config = io_config.get("leds", [])
        for led_cfg in leds_config:
            led_id = led_cfg.get("id")
            pin = led_cfg.get("pin")
            pwm = led_cfg.get("pwm", False)
            
            if led_id and pin is not None:
                self._leds[led_id] = LED(pin, pwm_enabled=pwm)
                
        # Initialize Buzzers
        buzzers_config = io_config.get("buzzers", [])
        for buzz_cfg in buzzers_config:
            buzz_id = buzz_cfg.get("id")
            pin = buzz_cfg.get("pin")
            
            if buzz_id and pin is not None:
                self._buzzers[buzz_id] = Buzzer(pin)
                
    def get_led(self, led_id: str) -> Optional[LED]:
        return self._leds.get(led_id)
    
    def get_buzzer(self, buzzer_id: str) -> Optional[Buzzer]:
        return self._buzzers.get(buzzer_id)
    
    def led(self, led_id: str, on: bool = True, brightness: int = 100):
        """Quick access to control LED."""
        led = self.get_led(led_id)
        if led:
            if on:
                led.on(brightness)
            else:
                led.off()
                
    def beep(self, buzzer_id: str, duration_ms: int = 100):
        """Quick access to beep buzzer."""
        buzzer = self.get_buzzer(buzzer_id)
        if buzzer:
            buzzer.beep(duration_ms)
            
    def cleanup(self):
        for led in self._leds.values():
            led.cleanup()
        for buzzer in self._buzzers.values():
            buzzer.cleanup()
            
    def get_status(self) -> dict:
        """Get status of all IO devices."""
        return {
            "leds": {led_id: led._is_on for led_id, led in self._leds.items()},
            "buzzers": {buzz_id: buzz._is_playing for buzz_id, buzz in self._buzzers.items()}
        }