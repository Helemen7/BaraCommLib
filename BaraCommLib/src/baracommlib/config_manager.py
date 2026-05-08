import os
import yaml
import shutil

class ConfigManager:
    def __init__(self, config_filepath: str = "baraconfig.yaml"):
        self.config_filepath = config_filepath
        self.config = {}

    def load_and_validate(self) -> dict:
        if not os.path.exists(self.config_filepath):
            self._inject_default_config()
            raise RuntimeError(f"Cannot create robot without config. Read the docs. Default file created at {self.config_filepath}")
            
        with open(self.config_filepath, 'r') as config_file:
            self.config = yaml.safe_load(config_file)

        if not self._isConfigHealthy(self.config):
            raise RuntimeError("Config is not healthy")

        return self.config
        
    def _inject_default_config(self):
        # Copy libs default_config.yaml to baraconfig.yaml in user folder
        src_path = os.path.join(os.path.dirname(__file__), 'default_config.yaml')
        if os.path.exists(src_path):
            shutil.copy(src_path, self.config_filepath)
        else:
            raise RuntimeError("CRITICAL LIBRARY ERROR: Library default_config.yaml is missing!")

    def _validate_field(self, data: dict, field: str, expected_type=None, allowed_values=None, required=True, context="") -> bool:
        """Helper to quickly validate config fields and types/values to make adding new settings easier."""
        if field not in data:
            if required:
                print(f"Config validation failed: Missing required field '{field}' in {context}")
                return False
            return True
            
        val = data[field]
        if expected_type and not isinstance(val, expected_type):
            print(f"Config validation failed: Field '{field}' in {context} must be of type {expected_type.__name__}, got {type(val).__name__}")
            return False
            
        if allowed_values and val not in allowed_values:
            print(f"Config validation failed: Field '{field}' in {context} must be one of {allowed_values}, got '{val}'")
            return False
            
        return True

    def _isConfigHealthy(self, config: dict) -> bool:
        if not isinstance(config, dict):
            print("Config validation failed: Root must be a dictionary")
            return False
            
        used_pins = {}
        def _register_pin(pin, owner):
            if not isinstance(pin, int): return True # let other checks fail
            if pin in used_pins:
                print(f"Config validation failed: Pin collision! Pin {pin} is used by '{used_pins[pin]}' and '{owner}'")
                return False
            used_pins[pin] = owner
            return True

        bus_addresses = {} # bus_id -> {address: owner}
        def _register_i2c_address(bus_id, addr, owner):
            if not isinstance(addr, int): return True
            if bus_id not in bus_addresses:
                bus_addresses[bus_id] = {}
            if addr in bus_addresses[bus_id]:
                print(f"Config validation failed: I2C Address collision! Address {hex(addr)} on bus '{bus_id}' used by '{bus_addresses[bus_id][addr]}' and '{owner}'")
                return False
            bus_addresses[bus_id][addr] = owner
            return True

        try:
            # 0. Robot validation
            robot = config.get('robot', {})
            if not self._validate_field(robot, 'base_speed', int, context="robot"): return False
            if robot['base_speed'] > config.get('drivetrain', {}).get('max_pwm_value', 100):
                print("Config validation failed: base speed is greater than max_pwm_value.")
                return False
                
            # 1. Drivetrain Validation
            dt = config.get('drivetrain')
            if not dt:
                print("Config validation failed: Missing 'drivetrain' fundamental section")
                return False
                
            if not self._validate_field(dt, 'max_pwm_value', int, context="drivetrain"): return False
            if dt['max_pwm_value'] <= 0:
                print("Config validation failed: drivetrain.max_pwm_value must be positive")
                return False
                
            motors = dt.get('motors')
            if not motors or 'left' not in motors or 'right' not in motors:
                print("Config validation failed: drivetrain.motors must contain 'left' and 'right'")
                return False
                
            for side in ['left', 'right']:
                m = motors[side]
                ctx = f"drivetrain.motors.{side}"
                if not self._validate_field(m, 'in1', int, context=ctx): return False
                if not self._validate_field(m, 'in2', int, context=ctx): return False
                if not self._validate_field(m, 'pwm', int, context=ctx): return False
                if not self._validate_field(m, 'mounted_backwards', bool, required=False, context=ctx): return False
                
                if not _register_pin(m['in1'], f"motor_{side}_in1") or \
                   not _register_pin(m['in2'], f"motor_{side}_in2") or \
                   not _register_pin(m['pwm'], f"motor_{side}_pwm"):
                    return False

            encoders = dt.get('encoders', {})
            if encoders.get('exists', False):
                for side in ['left', 'right']:
                    if side not in encoders:
                        print(f"Config validation failed: drivetrain.encoders missing '{side}'")
                        return False
                    enc = encoders[side]
                    ctx = f"drivetrain.encoders.{side}"
                    if not self._validate_field(enc, 'pin_a', int, context=ctx): return False
                    if not self._validate_field(enc, 'pin_b', int, context=ctx): return False
                    
                    if not _register_pin(enc['pin_a'], f"encoder_{side}_a") or \
                       not _register_pin(enc['pin_b'], f"encoder_{side}_b"):
                        return False

            # 2. Sensors Validation
            sensors = config.get('sensors', {})
            defined_buses = set()
            if 'buses' in sensors:
                for bus in sensors['buses']:
                    bid = bus.get('id', '')
                    ctx = f"sensors.buses[{bid}]"
                    if not bid.startswith("i2c_"):
                        print(f"Config validation failed: I2C bus id '{bid}' is not correct")
                        return False
                    defined_buses.add(bid)
                    if not self._validate_field(bus, 'scl_pin', int, context=ctx): return False
                    if not self._validate_field(bus, 'sda_pin', int, context=ctx): return False
                    
                    if not _register_pin(bus['scl_pin'], f"bus_{bid}_scl") or \
                       not _register_pin(bus['sda_pin'], f"bus_{bid}_sda"):
                        return False

            if 'tof' in sensors:
                allowed_tof = ["VL53L0X", "VL53L1X", "VL53L4CD"]
                for tof in sensors['tof']:
                    tid = tof.get('id')
                    ctx = f"sensors.tof[{tid}]"
                    
                    if not self._validate_field(tof, 'direction', str, context=ctx): return False
                    if not self._validate_field(tof, 'model', str, allowed_values=allowed_tof, required=False, context=ctx): return False
                    
                    bus_id = tof.get('bus')
                    if bus_id not in defined_buses:
                        print(f"Config validation failed: ToF {tid} uses undefined bus '{bus_id}'")
                        return False
                        
                    if not self._validate_field(tof, 'xshut_pin', int, context=ctx): return False
                    if not _register_pin(tof['xshut_pin'], f"tof_{tid}_xshut"):
                        return False
                        
                    if 'new_address' in tof:
                        if not _register_i2c_address(bus_id, tof['new_address'], f"tof_{tid}"):
                            return False

            if 'imu' in sensors:
                for imu in sensors['imu']:
                    iid = imu.get('id')
                    ctx = f"sensors.imu[{iid}]"
                    
                    if not self._validate_field(imu, 'direction', str, context=ctx, required=False): return False
                    
                    bus_id = imu.get('bus')
                    if bus_id not in defined_buses:
                        print(f"Config validation failed: IMU {iid} uses undefined bus '{bus_id}'")
                        return False
                    
                    if 'address' in imu:
                        if not _register_i2c_address(bus_id, imu['address'], f"imu_{iid}"):
                            return False
                            
                    if 'axis_mapping' in imu:
                        am = imu['axis_mapping']
                        if not isinstance(am, list) or len(am) != 3 or not all(isinstance(x, int) and 0 <= x <= 2 for x in am):
                            print(f"Config validation failed: IMU {iid} axis_mapping must be a list of 3 integers (0, 1, or 2)")
                            return False

                    if 'inverted_axes' in imu:
                        inv = imu['inverted_axes']
                        if not isinstance(inv, list) or len(inv) != 3:
                            print(f"Config validation failed: IMU {iid} inverted_axes must be a list of 3 booleans")
                            return False
                    
                    if 'address' in imu:
                        if not _register_i2c_address(bus_id, imu['address'], f"imu_{iid}"):
                            return False
                            
                    if 'inverted_axes' in imu:
                        inv = imu['inverted_axes']
                        if not isinstance(inv, list) or len(inv) != 3:
                            print(f"Config validation failed: IMU {iid} inverted_axes must be a list of 3 booleans")
                            return False

            # 3. IO Validation
            io_cfg = config.get('io', {})
            if 'buttons' in io_cfg:
                for btn in io_cfg['buttons']:
                    bid = btn.get('id')
                    ctx = f"io.buttons[{bid}]"
                    if not self._validate_field(btn, 'pin', int, context=ctx): return False
                    if not self._validate_field(btn, 'pull', str, allowed_values=['up', 'down', 'none'], context=ctx): return False
                    
                    if not _register_pin(btn['pin'], f"button_{bid}"):
                        return False

            if 'leds' in io_cfg:
                for led in io_cfg['leds']:
                    lid = led.get('id')
                    ctx = f"io.leds[{lid}]"
                    if not self._validate_field(led, 'pin', int, context=ctx): return False
                    if not _register_pin(led['pin'], f"led_{lid}"):
                        return False

            # 4. Vision Validation
            vision = config.get('vision', {})
            if vision.get('enabled', False) and 'cameras' in vision:
                for cam in vision['cameras']:
                    res = cam.get('resolution')
                    if not isinstance(res, list) or len(res) != 2:
                        print(f"Config validation failed: Camera {cam.get('id')} resolution must be [width, height]")
                        return False

            return True

        except Exception as e:
            print(f"Config validation failed with unexpected error: {e}")
            return False
