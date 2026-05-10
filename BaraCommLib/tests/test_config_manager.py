import os
from baracomllib.config_manager import ConfigManager

def test_load_and_validate_minimal(tmp_path):
    cfg_file = tmp_path / "minimal.yml"
    yaml_content = """
robot:
  base_speed: 50
# minimal drivetrain settings required for validation

drivetrain:
  max_pwm_value: 100
  motors:
    left:
      in1: 12
      in2: 13
      pwm: 19
    right:
      in1: 14
      in2: 18
      pwm: 29
"""
    cfg_file.write_text(yaml_content)
    cm = ConfigManager(str(cfg_file))
    config_dict = cm.load_and_validate()
    assert isinstance(config_dict, dict) and 'robot' in config_dict

def test_default_injection(tmp_path):
    non_existent_cfg = tmp_path / "nonexistent_config.yml"
    cm = ConfigManager(str(non_existent_cfg))
    try:
        cm.load_and_validate()
    except RuntimeError as e:
        assert "Default file created" in str(e)
    else:
        raise AssertionError("Expected RuntimeError due to missing config")