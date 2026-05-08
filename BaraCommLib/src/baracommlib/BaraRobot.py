import time
import threading
from typing import Callable, Any, Optional

try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO

from .config_manager import ConfigManager
from .sensors import SensorsManager
from .Motors import Motors
from .vision.vision_manager import VisionManager

class _SensorProxy:
    def __init__(self, manager: SensorsManager):
        self._manager = manager

    def get(self, sensor_id: str) -> Any:
        return self._manager.get_reading(sensor_id)
        
    def get_by_direction(self, direction: str) -> dict:
        return self._manager.get_readings_by_direction(direction)
        
    def get_average_by_direction(self, direction: str) -> Optional[float]:
        return self._manager.get_average_by_direction(direction)

class BaraRobot:
    def __init__(self, config_filepath: str = "baraconfig.yaml"):
        # Delegate config loading and validation to ConfigManager
        config_manager = ConfigManager(config_filepath)
        self.config = config_manager.load_and_validate()

        self.sensors_manager = SensorsManager(self.config)
        self.sensor = _SensorProxy(self.sensors_manager)
        
        self.drivetrain = Motors(self.config)
        
        # Initialize vision if enabled
        vision_cfg = self.config.get("vision", {})
        if vision_cfg.get("enabled", False):
            self.vision = VisionManager()
        else:
            self.vision = None
        
        self._button_callbacks = {}
        self._button_threads = []
        self._running = True

        # Config is safe to use now
        self._setup_hw()
        
    def _setup_hw(self):
        # Initialize PWMs, initialize ToFs, initialize Gyro, initialize button, set them all to default state
        buttons_cfg = self.config.get("io", {}).get("buttons", [])
        for btn in buttons_cfg:
            pin = btn.get("pin")
            if pin is not None:
                pull = btn.get("pull", "none").lower()
                if pull == "up":
                    pud = GPIO.PUD_UP
                elif pull == "down":
                    pud = GPIO.PUD_DOWN
                else:
                    pud = GPIO.PUD_OFF
                    
                GPIO.setup(pin, GPIO.IN, pull_up_down=pud)
                
        # Setup Vision subsystem
        if self.vision:
            vision_cfg = self.config.get("vision", {})
            model_path = vision_cfg.get("model_path")
            if model_path:
                try:
                    self.vision.load_model(model_path)
                except Exception as e:
                    import logging
                    logging.error(f"Failed to load vision model: {e}")
                    
            cameras = vision_cfg.get("cameras", [])
            for cam in cameras:
                cam_id = cam.get("id")
                source = cam.get("source", 0)
                res = cam.get("resolution", [640, 480])
                if cam_id is not None:
                    self.vision.start_camera(cam_id, source=source, resolution=tuple(res))
                
    def setupSensors(self):
        pass

    def on_button_pressed(self, button_id: str):
        """
        Decorator to register a callback when a button is pressed.
        Starts a background thread to poll the button and handles debouncing automatically.
        """
        def decorator(func: Callable):
            self._button_callbacks[button_id] = func
            
            # Find the button config
            buttons_cfg = self.config.get("io", {}).get("buttons", [])
            btn_cfg = next((b for b in buttons_cfg if b.get("id") == button_id), None)
            
            if btn_cfg:
                thread = threading.Thread(
                    target=self._button_listener,
                    args=(btn_cfg, func),
                    daemon=True,
                    name=f"ButtonListener_{button_id}"
                )
                self._button_threads.append(thread)
                thread.start()
            else:
                import logging
                logging.error(f"Button id '{button_id}' not found in config.")
                
            return func
        return decorator

    def _button_listener(self, btn_cfg: dict, callback: Callable):
        pin: int = btn_cfg.get("pin")
        pull = btn_cfg.get("pull", "none").lower()
        debounce_ms = btn_cfg.get("debounce_ms", 50)
        
        # Typically if pull is UP, active is LOW.
        active_state = GPIO.LOW if pull == "up" else GPIO.HIGH
        
        while self._running:
            if GPIO.input(pin) == active_state:
                time.sleep(debounce_ms / 1000.0) # debounce wait
                if GPIO.input(pin) == active_state:
                    callback()
                    # Wait for release to avoid multiple rapid triggers
                    while GPIO.input(pin) == active_state and self._running:
                        time.sleep(0.01)
            time.sleep(0.01)

    def is_button_pressed(self, button_id: str) -> bool:
        """Normal synchronous check for a button state."""
        buttons_cfg = self.config.get("io", {}).get("buttons", [])
        btn_cfg = next((b for b in buttons_cfg if b.get("id") == button_id), None)
        if not btn_cfg:
            return False
            
        pin = btn_cfg.get("pin")
        pull = btn_cfg.get("pull", "none").lower()
        active_state = GPIO.LOW if pull == "up" else GPIO.HIGH
        
        return GPIO.input(pin) == active_state

    def turn(self, angle: float, speed: int = -1, tolerance: float = 2.0):
        """
        Turns the robot by a specific relative angle using the main IMU/gyro.
        Positive angle -> Right turn. Negative angle -> Left turn.
        Blocks until the turn is complete.
        """
        if speed == -1:
            speed = self.config.get("robot", {}).get("base_speed", 50)      # Defaulting to base speed
            
        # Find the main gyro
        gyro_id = None
        for imu in self.config.get("sensors", {}).get("imu", []):
            gyro_id = imu.get("id")
            break
            
        if not gyro_id:
            raise RuntimeError("No IMU configured. Cannot perform relative turn(angle).")
            
        initial_reading = self.sensor.get(gyro_id)
        if initial_reading is None:
            raise RuntimeError(f"Gyro reading for '{gyro_id}' is None. Is the sensor connected?")
            
        initial_yaw = initial_reading["yaw"]
        target_yaw = (initial_yaw + angle) % 360.0
        
        # Determine direction: Shortest path to target yaw
        diff = (target_yaw - initial_yaw + 180) % 360 - 180
        
        if diff > 0:
            self.drivetrain.turn_right_action(speed)
        else:
            self.drivetrain.turn_left_action(speed)
            
        while self._running:
            current_reading = self.sensor.get(gyro_id)
            if not current_reading:
                continue
                
            current_yaw = current_reading["yaw"]
            
            # Check if we are within tolerance
            current_diff = (target_yaw - current_yaw + 180) % 360 - 180
            if abs(current_diff) <= tolerance:
                break
                
            time.sleep(0.01)
            
        self.drivetrain.coast()

    def cleanup(self):
        """Critical function to safely stop motors and release hardware pins."""
        if getattr(self, '_cleaned_up', False):
            return
        self._cleaned_up = True
        self._running = False
        
        # Stop all actuators
        if hasattr(self, 'drivetrain') and self.drivetrain:
            try:
                self.drivetrain.coast()
            except Exception:
                pass
            
        # Stop background sensor threads safely
        if hasattr(self, 'sensors_manager') and self.sensors_manager:
            try:
                self.sensors_manager.stop_all()
            except Exception:
                pass
                
        # Stop vision cameras gracefully
        if hasattr(self, 'vision') and self.vision:
            try:
                self.vision.stop_all()
            except Exception:
                pass
            
        # Stop listener threads
        if hasattr(self, '_button_threads'):
            for thread in self._button_threads:
                if thread.is_alive():
                    try:
                        thread.join(timeout=1.0)
                    except Exception:
                        pass
                
        # Clean up GPIOs
        try:
            GPIO.cleanup()
        except Exception:
            pass

    def __del__(self):
        """Ensures cleanup is called when the BaraRobot object is destroyed by the garbage collector."""
        self.cleanup()
