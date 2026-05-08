import threading
import time
import logging
from enum import Enum
from typing import Dict, Any, Optional

try:
    import board
    import busio
    import digitalio
    
except (ImportError, NotImplementedError):
    logging.warning("Adafruit Blinka not found or not running on RPi. Using Mock I2C/Board for development.")
    class _MockBoard:
        pass
    class _MockBusIO:
        class I2C:
            def __init__(self, scl, sda, frequency=100000):
                pass
            def unlock(self):
                pass
    class _MockDigitalIO:
        class DigitalInOut:
            def __init__(self, pin):
                pass
            def switch_to_output(self, value=False):
                pass
            @property
            def value(self):
                return False
            @value.setter
            def value(self, val):
                pass
    board = _MockBoard()
    busio = _MockBusIO()
    digitalio = _MockDigitalIO()

class SensorReading:
    """A wrapper for readings that includes timestamps to verify freshness."""
    def __init__(self, value: Any, timestamp: float, is_valid: bool = True):
        self.value = value
        self.timestamp = timestamp
        self.is_valid = is_valid

class AbstractSensor:
    """
    Highly abstract base class for any sensor. 
    It handles background polling in a dedicated thread so reads are instantaneous.
    """
    def __init__(self, config_node: dict, i2c_bus=None):
        self.config = config_node
        self.sensor_id = config_node.get("id", "unknown")
        self.i2c_bus = i2c_bus
        
        self._lock = threading.Lock()
        self._latest_reading: Optional[SensorReading] = None
        self._running = False
        self._paused = False
        self._thread: Optional[threading.Thread] = None
        self._poll_rate = 0.03  # Default 30ms sleep between reads
        
        self._sensor_instance = None
    
    def _initialize_hardware(self):
        """Override to instantiate specific sensor hardware."""
        raise NotImplementedError
        
    def _read_hardware(self) -> Any:
        """Override to perform the actual hardware reading."""
        raise NotImplementedError
        
    def start(self):
        """Initializes hardware and starts the background polling thread."""
        if self._running:
            return
            
        self._initialize_hardware()
        self._running = True
        self._paused = False
        self._thread = threading.Thread(target=self._polling_loop, name=f"SensorPoll_{self.sensor_id}", daemon=True)
        self._thread.start()
        
    def stop(self):
        """Stops the polling thread gracefully."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            
    def pause(self):
        """Temporarily suspends reading hardware to save CPU/I2C bandwidth."""
        self._paused = True
        
    def resume(self):
        """Resumes hardware reading."""
        self._paused = False
        
    def set_poll_rate(self, rate_seconds: float):
        """Adjusts how fast the background thread queries the hardware."""
        self._poll_rate = rate_seconds
        
    def _polling_loop(self):
        while self._running:
            if not self._paused:
                try:
                    val = self._read_hardware()
                    with self._lock:
                        self._latest_reading = SensorReading(val, time.time(), is_valid=True)
                except Exception as e:
                    logging.error(f"Error reading sensor {self.sensor_id}: {e}")
                    with self._lock:
                        self._latest_reading = SensorReading(None, time.time(), is_valid=False)
            time.sleep(self._poll_rate)
            
    def get_value(self) -> Any:
        """Returns the latest read value instantly, without blocking for I2C."""
        with self._lock:
            if self._latest_reading and self._latest_reading.is_valid:
                return self._latest_reading.value
            return None
            
    def get_reading_age(self) -> float:
        """Returns how many seconds ago the last reading was taken."""
        with self._lock:
            if self._latest_reading:
                return time.time() - self._latest_reading.timestamp
            return float('inf')

class ToFSensor(AbstractSensor):
    """
    Implementation for VL53L0X, VL53L1X, VL53L4CD Time of Flight sensors.
    """
    def __init__(self, config_node: dict, i2c_bus, direction_enum_cls):
        super().__init__(config_node, i2c_bus)
        self.model = config_node.get("model", "VL53L1X")
        
        # Resolve the string direction to the dynamically built Enum
        dir_str = config_node.get("direction", "UNKNOWN").upper()
        self.direction = getattr(direction_enum_cls, dir_str, getattr(direction_enum_cls, "UNKNOWN"))
        
        self.xshut_pin = config_node.get("xshut_pin")
        self.xshut_io = None
        
        if self.xshut_pin is not None:
            # Map integer pin to Adafruit Blinka's board.Dx
            pin_name = f"D{self.xshut_pin}"
            if hasattr(board, pin_name):
                self.xshut_io = digitalio.DigitalInOut(getattr(board, pin_name))
                self.xshut_io.switch_to_output(value=False) # Keep in reset initially (LOW)
        
    def turn_on(self):
        """Releases the XSHUT pin to turn on the sensor."""
        if self.xshut_io:
            self.xshut_io.value = True
            time.sleep(0.01) # Give it time to boot (10ms)
            
    def turn_off(self):
        """Pulls the XSHUT pin low to turn off the sensor."""
        if self.xshut_io:
            self.xshut_io.value = False
            
    def _initialize_hardware(self):
        self.turn_on()
        
        target_addr = self.config.get("new_address")
        
        try:
            if self.model == "VL53L0X":
                import adafruit_vl53l0x
                self._sensor_instance = adafruit_vl53l0x.VL53L0X(self.i2c_bus)
                if target_addr:
                    self._sensor_instance.set_address(target_addr)
                    
            elif self.model == "VL53L1X":
                import adafruit_vl53l1x
                self._sensor_instance = adafruit_vl53l1x.VL53L1X(self.i2c_bus)
                if target_addr:
                    self._sensor_instance.set_address(target_addr)
                self._sensor_instance.start_ranging()
                
            elif self.model == "VL53L4CD":
                import adafruit_vl53l4cd
                self._sensor_instance = adafruit_vl53l4cd.VL53L4CD(self.i2c_bus)
                if target_addr:
                    self._sensor_instance.set_address(target_addr)
                self._sensor_instance.start_ranging()
                
            else:
                raise ValueError(f"Unsupported ToF model: {self.model}")
        except Exception as e:
            logging.error(f"Failed to initialize ToF {self.model} on {self.sensor_id}: {e}")
            self._sensor_instance = None
            
    def _read_hardware(self) -> Any:
        if not self._sensor_instance:
            return 0.0 # Mock fallback
            
        if self.model == "VL53L0X":
            return self._sensor_instance.range
        elif self.model == "VL53L1X":
            if self._sensor_instance.data_ready:
                self._sensor_instance.clear_interrupt()
                return self._sensor_instance.distance
        elif self.model == "VL53L4CD":
            if self._sensor_instance.data_ready:
                self._sensor_instance.clear_interrupt()
                return self._sensor_instance.distance
                
        return self.get_value() # Keep old value if data isn't ready


class SensorsManager:
    """
    High-level manager that initializes multiple sensors across multiple I2C buses.
    Handles complex logic like sequential XSHUT toggling to prevent address collisions.
    """
    def __init__(self, config: dict):
        self.config = config
        self.buses = {}
        self.sensors: Dict[str, AbstractSensor] = {}
        
        # Dynamically build Direction Enum based on config directions
        self.Direction = self._build_dynamic_direction_enum()
        
        self._init_buses()
        self._init_sensors()
        
    def _build_dynamic_direction_enum(self) -> Enum:
        directions_set = set()
        sensors_cfg = self.config.get("sensors", {})
        
        for tof in sensors_cfg.get("tof", []):
            if "direction" in tof:
                directions_set.add(tof["direction"].lower())
                
        for imu in sensors_cfg.get("imu", []):
            if "direction" in imu:
                directions_set.add(imu["direction"].lower())
                
        # Drop duplicates inherently handled by set(), now map to Enum
        # E.g. {"front": 0, "back": 1, "weird_angle": 2}
        enum_dict = {d.upper(): i for i, d in enumerate(directions_set)}
        
        # Add a fallback for unknown configs
        enum_dict["UNKNOWN"] = len(enum_dict)
        
        return Enum('SensorDirection', enum_dict)
        
    def _init_buses(self):
        sensors_cfg = self.config.get("sensors", {})
        for bus_cfg in sensors_cfg.get("buses", []):
            bid = bus_cfg.get("id")
            scl_pin_num = bus_cfg.get("scl_pin")
            sda_pin_num = bus_cfg.get("sda_pin")
            
            # Map integers to Adafruit board pins
            scl_pin = getattr(board, f"D{scl_pin_num}", getattr(board, "SCL", None))
            sda_pin = getattr(board, f"D{sda_pin_num}", getattr(board, "SDA", None))
            
            freq = bus_cfg.get("frequency", 400000)
            
            if scl_pin and sda_pin:
                try:
                    self.buses[bid] = busio.I2C(scl_pin, sda_pin, frequency=freq)
                except Exception as e:
                    logging.error(f"Failed to initialize I2C bus {bid}: {e}")
            else:
                logging.error(f"Could not resolve SCL/SDA pins for bus {bid}")

    def _init_sensors(self):
        sensors_cfg = self.config.get("sensors", {})
        
        # 1. Pre-instantiate all ToF sensors so their XSHUT pins are held LOW
        tof_sensors = []
        for tof_cfg in sensors_cfg.get("tof", []):
            bus_id = tof_cfg.get("bus")
            if bus_id in self.buses:
                sensor = ToFSensor(tof_cfg, self.buses[bus_id], self.Direction)
                self.sensors[sensor.sensor_id] = sensor
                tof_sensors.append(sensor)
                
        # 2. Sequentially start them to avoid default 0x29 address collisions
        for sensor in tof_sensors:
            sensor.start()
            # Give it time to change its address before booting the next one
            time.sleep(0.05) 
                
    def get_sensor(self, sensor_id: str) -> Optional[AbstractSensor]:
        """Gets the sensor object itself."""
        return self.sensors.get(sensor_id)
        
    def get_reading(self, sensor_id: str) -> Any:
        """Helper to get the instantaneous cached reading of a sensor."""
        sensor = self.get_sensor(sensor_id)
        if sensor:
            return sensor.get_value()
        return None

    def get_readings_by_direction(self, direction: Enum) -> Dict[str, Any]:
        """Returns a dict of all sensors pointing in a specific direction and their values."""
        results = {}
        for sid, sensor in self.sensors.items():
            if getattr(sensor, "direction", None) == direction:
                results[sid] = sensor.get_value()
        return results

    def stop_all(self):
        """Stops all sensor threads."""
        for sensor in self.sensors.values():
            sensor.stop()
