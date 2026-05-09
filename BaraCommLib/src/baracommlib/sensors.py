import threading
import time
import logging
import math
from enum import Enum
from typing import cast
from typing import Dict, Any, Optional, Type, Union

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
    def __init__(self, config_node: dict, i2c_bus=None, sensor_type: str = "unknown", bus_id: str = "unknown", on_critical_failure = None):
        self.config = config_node
        self.sensor_id = config_node.get("id", "unknown")
        self.i2c_bus = i2c_bus
        
        self.sensor_type = sensor_type
        self.bus_id = bus_id
        self.on_critical_failure = on_critical_failure
        
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
        consecutive_errors = 0
        first_error_time = None
        
        while self._running:
            if not self._paused:
                try:
                    val = self._read_hardware()
                    with self._lock:
                        self._latest_reading = SensorReading(val, time.time(), is_valid=True)
                    if consecutive_errors > 0:
                        logging.info(f"Sensor {self.sensor_id} recovered after {consecutive_errors} errors.")
                        consecutive_errors = 0
                        first_error_time = None
                except Exception as e:
                    consecutive_errors += 1
                    if first_error_time is None:
                        first_error_time = time.time()
                        
                    logging.error(f"Error reading sensor {self.sensor_id} (x{consecutive_errors}): {e}")
                    with self._lock:
                        self._latest_reading = SensorReading(None, time.time(), is_valid=False)
                        
                    # Check for 5 second continuous failure
                    if time.time() - first_error_time >= 5.0:
                        logging.critical(f"Sensor {self.sensor_id} failed for 5+ seconds! Triggering fail-safe reinit.")
                        if self.on_critical_failure:
                            # Run in background to not block the thread dying
                            threading.Thread(target=self.on_critical_failure, args=(self.sensor_type, self.bus_id)).start()
                        first_error_time = None # Reset to avoid spamming
                        self._running = False # Kill this thread as it will be reinitialized
                        break
                        
                    # Exponential backoff maxing out at 5 seconds
                    time.sleep(min(5.0, self._poll_rate * (1.5 ** consecutive_errors)))
                    continue
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
    def __init__(self, config_node: dict, i2c_bus, direction_enum_cls, sensor_type: str = "unknown", bus_id: str = "unknown", on_critical_failure = None):
        super().__init__(config_node, i2c_bus, sensor_type=sensor_type, bus_id=bus_id, on_critical_failure=on_critical_failure)
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


class IMUSensor(AbstractSensor):
    """
    Implementation for MPU6050, BNO055, BNO085 Inertial Measurement Units.
    """
    def __init__(self, config_node: dict, i2c_bus, direction_enum_cls, sensor_type: str = "unknown", bus_id: str = "unknown", on_critical_failure = None):
        super().__init__(config_node, i2c_bus, sensor_type=sensor_type, bus_id=bus_id, on_critical_failure=on_critical_failure)
        self.model = config_node.get("model", "BNO085")
        
        # Optional direction for IMU
        dir_str = config_node.get("direction", "UNKNOWN").upper()
        self.direction = getattr(direction_enum_cls, dir_str, getattr(direction_enum_cls, "UNKNOWN", None))
        
        self.address = config_node.get("address")
        self.axis_mapping = config_node.get("axis_mapping", [0, 1, 2])
        self.inverted_axes = config_node.get("inverted_axes", [False, False, False])
        
        # Internal variables for MPU6050 software sensor fusion
        self._last_time = time.time()
        self._mpu_yaw = 0.0
        self._mpu_pitch = 0.0
        self._mpu_roll = 0.0
        
    def _initialize_hardware(self):
        try:
            if self.model == "MPU6050":
                import mpu6050
                # mpu6050 uses its own standard i2c implementation in this specific library
                addr = self.address if self.address else 0x68
                self._sensor_instance = mpu6050.mpu6050(addr)
                
            elif self.model == "BNO055":
                import adafruit_bno055
                addr = self.address if self.address else 0x28
                self._sensor_instance = adafruit_bno055.BNO055_I2C(self.i2c_bus, address=addr)
                
            elif self.model == "BNO085":
                from adafruit_bno08x.i2c import BNO08X_I2C
                from adafruit_bno08x import BNO_REPORT_EULER
                addr = self.address if self.address else 0x4A
                self._sensor_instance = BNO08X_I2C(self.i2c_bus, address=addr)
                self._sensor_instance.enable_feature(BNO_REPORT_EULER)
                
            else:
                raise ValueError(f"Unsupported IMU model: {self.model}")
        except Exception as e:
            logging.error(f"Failed to initialize IMU {self.model} on {self.sensor_id}: {e}")
            self._sensor_instance = None
            
    def _read_hardware(self) -> Any:
        if not self._sensor_instance:
            return {"yaw": 0.0, "pitch": 0.0, "roll": 0.0} # Mock fallback
            
        raw_tuple = (0.0, 0.0, 0.0)
        
        try:
            if self.model == "MPU6050":
                # MPU6050 lacks a compass. We use a software Complementary Filter 
                # fusing Accelerometer (for stable Pitch/Roll) and Gyro (for fast response and Yaw integration)
                accel = self._sensor_instance.get_accel_data()
                gyro = self._sensor_instance.get_gyro_data()
                
                current_time = time.time()
                dt = current_time - self._last_time
                self._last_time = current_time
                
                # Calculate absolute Pitch and Roll from gravity vector (Accelerometer)
                # accel values are in g. 
                acc_pitch = math.degrees(math.atan2(accel['y'], math.sqrt(accel['x']**2 + accel['z']**2)))
                acc_roll = math.degrees(math.atan2(-accel['x'], accel['z']))
                
                # Fast complementary filter (98% gyro, 2% accelerometer)
                self._mpu_pitch = 0.98 * (self._mpu_pitch + gyro['x'] * dt) + 0.02 * acc_pitch
                self._mpu_roll = 0.98 * (self._mpu_roll + gyro['y'] * dt) + 0.02 * acc_roll
                
                # Yaw has no absolute reference (no compass), so it's pure integration (subject to slow drift)
                self._mpu_yaw += gyro['z'] * dt
                
                raw_tuple = (self._mpu_yaw, self._mpu_pitch, self._mpu_roll)
                
            elif self.model == "BNO055":
                # BNO055 has hardware Sensor Fusion (Accel + Gyro + Magnetometer)
                euler = self._sensor_instance.euler
                if euler and None not in euler:
                    # Usually returns (heading/yaw, roll, pitch)
                    raw_tuple = (euler[0], euler[2], euler[1])
                else:
                    return self.get_value()
                
            elif self.model == "BNO085":
                # BNO085 has advanced hardware Sensor Fusion
                euler = self._sensor_instance.euler
                if euler and None not in euler:
                    raw_tuple = euler 
                else:
                    return self.get_value()
                    
        except Exception as e:
            logging.error(f"Error reading IMU {self.model}: {e}")
            return self.get_value() # Keep old valid value if I2C fails
            
        # 1. Apply user-defined Axis Mapping
        mapped_yaw = raw_tuple[self.axis_mapping[0]]
        mapped_pitch = raw_tuple[self.axis_mapping[1]]
        mapped_roll = raw_tuple[self.axis_mapping[2]]
        
        # 2. Apply user-defined Inversions
        if self.inverted_axes[0]: mapped_yaw = -mapped_yaw
        if self.inverted_axes[1]: mapped_pitch = -mapped_pitch
        if self.inverted_axes[2]: mapped_roll = -mapped_roll
        
        # 3. Strictly wrap angles to 0-360 degrees
        return {
            "yaw": mapped_yaw % 360.0,
            "pitch": mapped_pitch % 360.0,
            "roll": mapped_roll % 360.0
        }

class SensorsManager:
    """
    High-level manager that initializes multiple sensors across multiple I2C buses.
    Handles complex logic like sequential XSHUT toggling to prevent address collisions.
    """
    def __init__(self, config: dict, stop_robot_callback=None):
        """Already initializes sensors and buses, no need to do it externally"""
        self.config = config
        self.stop_robot_callback = stop_robot_callback
        self.buses = {}
        self.sensors: Dict[str, AbstractSensor] = {}
        
        # Dynamically build Direction Enum based on config directions
        self.Direction = self._build_dynamic_direction_enum()
        
        self._init_buses()
        self._init_sensors()
        
    def _build_dynamic_direction_enum(self) -> Type[Enum]:
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

    def _handle_sensor_failure(self, sensor_type: str, bus_id: str):
        if self.stop_robot_callback:
            logging.critical("Stopping drivetrain due to sensor failure...")
            self.stop_robot_callback()
            
        logging.critical(f"Reinitializing all {sensor_type} sensors on I2C bus '{bus_id}'...")
        
        # Stop and remove existing sensors of this type on this bus
        to_remove = []
        for sid, sensor in self.sensors.items():
            if sensor.sensor_type == sensor_type and sensor.bus_id == bus_id:
                sensor.stop()
                to_remove.append(sid)
                
        for sid in to_remove:
            del self.sensors[sid]
            
        sensors_cfg = self.config.get("sensors", {})
        
        if sensor_type == "tof":
            tof_sensors = []
            for tof_cfg in sensors_cfg.get("tof", []):
                if tof_cfg.get("bus") == bus_id:
                    sensor = ToFSensor(tof_cfg, self.buses[bus_id], self.Direction, sensor_type="tof", bus_id=bus_id, on_critical_failure=self._handle_sensor_failure)
                    self.sensors[sensor.sensor_id] = sensor
                    tof_sensors.append(sensor)
            for sensor in tof_sensors:
                sensor.start()
                time.sleep(0.05)
                
        elif sensor_type == "imu":
            for imu_cfg in sensors_cfg.get("imu", []):
                if imu_cfg.get("bus") == bus_id:
                    sensor = IMUSensor(imu_cfg, self.buses[bus_id], self.Direction, sensor_type="imu", bus_id=bus_id, on_critical_failure=self._handle_sensor_failure)
                    self.sensors[sensor.sensor_id] = sensor
                    sensor.start()

    def _init_sensors(self):
        sensors_cfg = self.config.get("sensors", {})
        
        # 1. Pre-instantiate all ToF sensors so their XSHUT pins are held LOW
        tof_sensors = []
        for tof_cfg in sensors_cfg.get("tof", []):
            bus_id = tof_cfg.get("bus")
            if bus_id in self.buses:
                sensor = ToFSensor(tof_cfg, self.buses[bus_id], self.Direction, sensor_type="tof", bus_id=bus_id, on_critical_failure=self._handle_sensor_failure)
                self.sensors[sensor.sensor_id] = sensor
                tof_sensors.append(sensor)
                
        # 2. Sequentially start them to avoid default 0x29 address collisions
        for sensor in tof_sensors:
            sensor.start()
            # Give it time to change its address before booting the next one
            time.sleep(0.05) 
                
        # 3. Instantiate IMUs
        for imu_cfg in sensors_cfg.get("imu", []):
            bus_id = imu_cfg.get("bus")
            if bus_id in self.buses:
                sensor = IMUSensor(imu_cfg, self.buses[bus_id], self.Direction, sensor_type="imu", bus_id=bus_id, on_critical_failure=self._handle_sensor_failure)
                self.sensors[sensor.sensor_id] = sensor
                sensor.start()
                
    def get_sensor(self, sensor_id: str) -> Optional[AbstractSensor]:
        """Gets the sensor object itself."""
        return self.sensors.get(sensor_id)
        
    def get_reading(self, sensor_id: str) -> Any:
        """Helper to get the instantaneous cached reading of a sensor."""
        sensor = self.get_sensor(sensor_id)
        if sensor:
            return sensor.get_value()
        return None

    def get_readings_by_direction(self, direction: Union[Enum, str]) -> Dict[str, Any]:
        """Returns a dict of all sensors pointing in a specific direction and their values."""
        if isinstance(direction, str):
            fallback = list(self.Direction)[0] if self.Direction else None
            direction = cast(Enum, getattr(self.Direction, direction.upper(), fallback))
            
        results = {}
        for sid, sensor in self.sensors.items():
            if getattr(sensor, "direction", None) == direction:
                results[sid] = sensor.get_value()
        return results

    def get_average_by_direction(self, direction: Union[Enum, str]) -> Optional[float]:
        """
        Returns the mathematical average of all valid numerical readings 
        for sensors pointing in the specified direction.
        Returns None if no valid numerical readings are available.
        """
        readings = self.get_readings_by_direction(direction)
        
        valid_values = []
        for val in readings.values():
            if val is not None and isinstance(val, (int, float)):
                valid_values.append(val)
                
        if not valid_values:
            return None
            
        return sum(valid_values) / len(valid_values)

    def stop_all(self):
        """Stops all sensor threads."""
        for sensor in self.sensors.values():
            sensor.stop()
