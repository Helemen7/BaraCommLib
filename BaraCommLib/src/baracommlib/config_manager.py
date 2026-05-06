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
            if not config.get('robot', {}).get('base_speed') or not isinstance(config.get('robot', {}).get('base_speed'), int) or config.get('robot', {}).get('base_speed') > config.get('drivetrain', {}).get('max_pwm_value'):
                print("Config validation failed: Missing or wrong base speed.")
                return False
                
            # 1. Drivetrain Validation
            dt = config.get('drivetrain')
            if not dt:
                print("Config validation failed: Missing 'drivetrain' fundamental section")
                return False
                
            if not isinstance(dt.get('max_pwm_value'), int) or dt.get('max_pwm_value') <= 0:
                print("Config validation failed: drivetrain.max_pwm_value must be a positive integer")
                return False
                
            motors = dt.get('motors')
            if not motors or 'left' not in motors or 'right' not in motors:
                print("Config validation failed: drivetrain.motors must contain 'left' and 'right'")
                return False
                
            for side in ['left', 'right']:
                m = motors[side]
                if not isinstance(m.get('in1'), int) or not isinstance(m.get('in2'), int):
                    print(f"Config validation failed: drivetrain.motors.{side} 'in1' and 'in2' must be integers")
                    return False
                if not _register_pin(m.get('in1'), f"motor_{side}_in1") or \
                   not _register_pin(m.get('in2'), f"motor_{side}_in2"):
                    return False
                
                if not isinstance(m.get('mounted_backwards', False), bool):
                    print(f"Config validation failed: drivetrain.motors.{side}.mounted_backwards must be a boolean")
                    return False

            encoders = dt.get('encoders', {})
            if encoders.get('exists', False):
                for side in ['left', 'right']:
                    if side not in encoders:
                        print(f"Config validation failed: drivetrain.encoders missing '{side}'")
                        return False
                    enc = encoders[side]
                    if not isinstance(enc.get('pin_a'), int) or not isinstance(enc.get('pin_b'), int):
                        print(f"Config validation failed: drivetrain.encoders.{side} pins must be integers")
                        return False
                    if not _register_pin(enc.get('pin_a'), f"encoder_{side}_a") or \
                       not _register_pin(enc.get('pin_b'), f"encoder_{side}_b"):
                        return False

            # 2. Sensors Validation
            sensors = config.get('sensors', {})
            defined_buses = set()
            if 'buses' in sensors:
                for bus in sensors['buses']:
                    bid = bus.get('id')
                    defined_buses.add(bid)
                    if not isinstance(bus.get('scl_pin'), int) or not isinstance(bus.get('sda_pin'), int):
                        print(f"Config validation failed: Bus {bid} SCL/SDA pins must be integers")
                        return False
                    if not _register_pin(bus.get('scl_pin'), f"bus_{bid}_scl") or \
                       not _register_pin(bus.get('sda_pin'), f"bus_{bid}_sda"):
                        return False

            if 'tof' in sensors:
                allowed_tof = ["VL53L0X", "VL53L1X", "VL53L4CD"]
                for tof in sensors['tof']:
                    tid = tof.get('id')
                    model = tof.get('model', 'VL53L1X') # Fallback
                    if model not in allowed_tof:
                        print(f"Config validation failed: ToF {tid} model '{model}' not supported.")
                        return False
                    
                    bus_id = tof.get('bus')
                    if bus_id not in defined_buses:
                        print(f"Config validation failed: ToF {tid} uses undefined bus '{bus_id}'")
                        return False
                        
                    xshut = tof.get('xshut_pin')
                    if not isinstance(xshut, int):
                        print(f"Config validation failed: ToF {tid} xshut_pin must be integer")
                        return False
                    if not _register_pin(xshut, f"tof_{tid}_xshut"):
                        return False
                        
                    new_addr = tof.get('new_address')
                    if new_addr is not None:
                        if not _register_i2c_address(bus_id, new_addr, f"tof_{tid}"):
                            return False

            if 'imu' in sensors:
                for imu in sensors['imu']:
                    iid = imu.get('id')
                    bus_id = imu.get('bus')
                    if bus_id not in defined_buses:
                        print(f"Config validation failed: IMU {iid} uses undefined bus '{bus_id}'")
                        return False
                    
                    addr = imu.get('address')
                    if addr is not None:
                        if not _register_i2c_address(bus_id, addr, f"imu_{iid}"):
                            return False
                            
                    inv = imu.get('inverted_axes')
                    if inv is not None and (not isinstance(inv, list) or len(inv) != 3):
                        print(f"Config validation failed: IMU {iid} inverted_axes must be a list of 3 booleans")
                        return False

            # 3. IO Validation
            io_cfg = config.get('io', {})
            if 'buttons' in io_cfg:
                for btn in io_cfg['buttons']:
                    bid = btn.get('id')
                    bpin = btn.get('pin')
                    if not isinstance(bpin, int):
                        print(f"Config validation failed: Button {bid} pin must be an integer")
                        return False
                    if not _register_pin(bpin, f"button_{bid}"):
                        return False
                    if btn.get('pull') not in ['up', 'down', 'none']:
                        print(f"Config validation failed: Button {bid} pull must be 'up', 'down', or 'none'")
                        return False

            if 'leds' in io_cfg:
                for led in io_cfg['leds']:
                    lid = led.get('id')
                    lpin = led.get('pin')
                    if not isinstance(lpin, int):
                        print(f"Config validation failed: LED {lid} pin must be an integer")
                        return False
                    if not _register_pin(lpin, f"led_{lid}"):
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
