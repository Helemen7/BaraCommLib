"""
Config Manager
================

This module is responsible for loading the YAML configuration that drives all of BaraCommLib.
The library ships a **default_config.yaml** with sane defaults.  When an end‑user runs the robot on their own hardware, they are expected to copy this file as `baraconfig.yaml` next to :py:class:`~baracommlib.BaraRobot`.  The constructor of :class:`ConfigManager`
looks for that path and if it is missing will:

1. Copy ``default_config.yaml`` into the current working directory.
2. Raise a `RuntimeError` with an explanatory message, forcing the developer to edit the file before re‑running.

The public API of this class is intentionally tiny – only one method is exposed,
:py:meth:`load_and_validate`.  All heavy lifting happens in helper methods that are
documented inline.  The implementation performs **deep validation**:
- Every required field must exist and have the correct type.
- Pin numbers cannot collide across motors, encoders or sensors; a global map is maintained during checks.
- I²C addresses on each bus are checked for duplication as well.

The method returns a plain ``dict`` that can be passed straight to :class:`~baracommlib.BaraRobot`.
"""
import os
import yaml
import shutil

# ---------------------------------------------------------------------------
# Helper functions (private)
# ---------------------------------------------------------------------------
class ConfigManager:
    """Load and validate the robot configuration.

    Parameters
    ----------
    config_filepath : str, optional
        Path to a YAML file.  Defaults to ``baraconfig.yaml`` in the current working directory.

    The class does **not** modify user files unless they are missing; it simply copies the bundled default and raises an error so that developers can edit their configuration before proceeding.
    """

    def __init__(self, config_filepath: str = "baraconfig.yaml"):
        self.config_filepath = config_filepath
        self.config = {}

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def load_and_validate(self) -> dict:
        """Read the YAML file, validate its contents and return a dictionary.

        Returns
        -------
        dict
            Parsed configuration.  All keys are present and have been type‑checked.

        Raises
        ------
        RuntimeError
            If *config_filepath* does not exist – in that case the default file is copied first
            to let the user edit it, then a detailed error message explains what went wrong.
        """
        if not os.path.exists(self.config_filepath):
            self._inject_default_config()
            raise RuntimeError(
                f"Cannot create robot without config. Read the docs. Default file created at {self.config_filepath}"
            )

        with open(self.config_filepath, "r") as config_file:
            self.config = yaml.safe_load(config_file)

        if not self._isConfigHealthy(self.config):
            raise RuntimeError("Config is not healthy")

        return self.config

    # ---------------------------------------------------------------------
    # Private helpers – each with a single responsibility.
    # ---------------------------------------------------------------------
    def _inject_default_config(self):
        """Copy ``default_config.yaml`` from the package into *config_filepath*.

        The file is shipped inside :mod:`baracommlib`.  If it cannot be found, a hard error
        is raised because the library would not operate correctly without any configuration.
        """
        src_path = os.path.join(os.path.dirname(__file__), 'default_config.yaml')
        if os.path.exists(src_path):
            shutil.copy(src_path, self.config_filepath)
        else:
            raise RuntimeError("CRITICAL LIBRARY ERROR: Library default_config.yaml is missing!")

    def _validate_field(
        self,
        data: dict,
        field: str,
        expected_type=None,
        allowed_values=None,
        required=True,
        context="",
    ) -> bool:
        """Validate a single configuration entry.

        Parameters are intentionally generic so the same helper can be reused for any key in the YAML file.  It prints diagnostic messages to :py:mod:`logging` and returns ``False`` when validation fails, which is then propagated by :meth:`_isConfigHealthy`.
        """
        if field not in data:
            if required:
                print(f"Config validation failed: Missing required field '{field}' in {context}")
                return False
            return True

        val = data[field]
        if expected_type and not isinstance(val, expected_type):
            print(
                f"Config validation failed: Field '{field}' in {context} must be of type {expected_type.__name__}, got {type(val).__name__}")
            return False

        if allowed_values and val not in allowed_values:
            print(f"Config validation failed: Field '{field}' in {context} must be one of {allowed_values}, got '{val}'")
            return False

        return True

    def _isConfigHealthy(self, config: dict) -> bool:
        """Run a comprehensive sanity check on the entire configuration.

        The logic is split into logical blocks – robot, drivetrain, sensors, IO and vision.  Each block checks for required keys, type correctness and cross‑parameter constraints such as pin collisions or address duplication.
        Returning ``True`` guarantees that all subsequent components can safely instantiate hardware objects without additional defensive programming.
        """
        if not isinstance(config, dict):
            print("Config validation failed: Root must be a dictionary")
            return False

        used_pins = {}
        def _register_pin(pin, owner):
            if not isinstance(pin, int): return True  # let other checks fail
            if pin in used_pins:
                print(
                    f"Config validation failed: Pin collision! Pin {pin} is used by '{used_pins[pin]}' and '{owner}'"
                )
                return False
            used_pins[pin] = owner
            return True
        bus_addresses = {}  # bus_id -> {address: owner}
        def _register_i2c_address(bus_id, addr, owner):
            if not isinstance(addr, int): return True
            if bus_id not in bus_addresses:
                bus_addresses[bus_id] = {}
            if addr in bus_addresses[bus_id]:
                print(
                    f"Config validation failed: I2C Address collision! Address {hex(addr)} on bus '{bus_id}' used by '{bus_addresses[bus_id][addr]}' and '{owner}"
                )
                return False
            bus_addresses[bus_id][addr] = owner
            return True
        try:
            # 0. Robot validation
            robot = config.get('robot', {})
            if not self._validate_field(robot, 'base_speed', int, context="robot"):
                return False
            if robot['base_speed'] > config.get('drivetrain', {}).get('max_pwm_value', 100):
                print("Config validation failed: base speed is greater than max_pwm_value.")
                return False
            # 1. Drivetrain Validation
            dt = config.get('drivetrain')
            if not dt:
                print("Config validation failed: Missing 'drivetrain' fundamental section")
                return False
            if not self._validate_field(dt, 'max_pwm_value', int, context="drivetrain"):
                return False
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
                if not self._validate_field(m, 'in1', int, context=ctx):
                    return False
                if not self._validate_field(m, 'in2', int, context=ctx):
                    return False
                if not self._validate_field(m, 'pwm', int, context=ctx):
                    return False
                if not self._validate_field(
                        m,
                        'mounted_backwards',
                        bool,
                        required=False,
                        context=ctx,
                ):
                    return False
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
                    if not self._validate_field(enc, 'pin_a', int, context=ctx):
                        return False
                    if not self._validate_field(enc, 'pin_b', int, context=ctx):
                        return False
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
                    if not self._validate_field(bus, 'scl_pin', int, context=ctx):
                        return False
                    if not self._validate_field(bus, 'sda_pin', int, context=ctx):
                        return False
                    if not _register_pin(bus['scl_pin'], f"bus_{bid}_scl") or \
                       not _register_pin(bus['sda_pin'], f"bus_{bid}_sda"):
                        return False
            if 'tof' in sensors:
                allowed_tof = [
                    "VL53L0X",
                    "VL53L1X",
                    "VL53L4CD",
                ]
                for tof in sensors['tof']:
                    tid = tof.get('id')
                    ctx = f"sensors.tof[{tid}]"
                    if not self._validate_field(tof, 'direction', str, context=ctx):
                        return False
                    if not self._validate_field(
                            tof,
                            'model',
                            str,
                            allowed_values=allowed_tof,
                            required=False,
                            context=ctx,
                    ):
                        return False
                    bus_id = tof.get('bus')
                    if bus_id not in defined_buses:
                        print(
                            f"Config validation failed: ToF {tid} uses undefined bus '{bus_id}'"
                        )
                        return False
                    if not self._validate_field(tof, 'xshut_pin', int, context=ctx):
                        return False
                    if _register_pin(tof['xshut_pin'], f"tof_{tid}_xshut"):
                        pass
                    else:  # register failed
                        return False
                    if 'new_address' in tof:
                        if not _register_i2c_address(bus_id, tof['new_address'], f"tof_{tid}"):
                            return False
            if 'imu' in sensors:
                for imu in sensors['imu']:
                    iid = imu.get('id')
                    ctx = f"sensors.imu[{iid}]"
                    if not self._validate_field(imu, 'direction', str, context=ctx, required=False):
                        return False
                    bus_id = imu.get('bus')
                    if bus_id not in defined_buses:
                        print(
                            f"Config validation failed: IMU {iid} uses undefined bus '{bus_id}'"
                        )
                        return False
                    if 'address' in imu and not _register_i2c_address(bus_id, imu['address'], f"imu_{iid}"):
                        return False
            # 3. IO Validation
            io_cfg = config.get('io', {})
            if 'buttons' in io_cfg:
                for btn in io_cfg['buttons']:
                    bid = btn.get('id')
                    ctx = f"io.buttons[{bid}]"
                    if not self._validate_field(btn, 'pin', int, context=ctx):
                        return False
                    if not self._validate_field(
                            btn,
                            'pull',
                            str,
                            allowed_values=["up", "down", "none"],
                            context=ctx,
                    ):
                        return False
                    if not _register_pin(btn['pin'], f"button_{bid}"):
                        return False
            if 'leds' in io_cfg:
                for led in io_cfg['leds']:
                    lid = led.get('id')
                    ctx = f"io.leds[{lid}]"
                    if not self._validate_field(led, 'pin', int, context=ctx):
                        return False
                    if not _register_pin(led['pin'], f"led_{lid}"):
                        return False
            # 4. Vision Validation
            vision = config.get('vision', {})
            if vision.get('enabled', False) and 'cameras' in vision:
                for cam in vision['cameras']:
                    res = cam.get('resolution')
                    if not isinstance(res, list) or len(res) != 2:
                        print(
                            f"Config validation failed: Camera {cam.get('id')} resolution must be [width, height]"
                        )
                        return False
            return True
        except Exception as e:
            print(f"Config validation failed with unexpected error: {e}")
            return False
