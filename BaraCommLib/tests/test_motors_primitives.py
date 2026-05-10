# Path configured in tests/conftest.py
from baracomllib import BaraRobot
import time
import pytest

# Helper dummy sensor getter that returns a yaw dict with constant 0.
def dummy_sensor_get(sid):
    return {'yaw': 0}

@pytest.fixture(scope="module")
def robot():
    # Create one instance for all tests in this module
    r = BaraRobot()
    yield r

# Test drive() primitive (time based)
def test_drive_primitive(robot):
    # Drive forward for 0.1s at speed 40
    robot.drivetrain.drive(0.15, speed=40)
    assert robot.drivetrain._current_action == "forward"

# Test spin with gyro-assisted mode (uses dummy sensor getter)
def test_spin_gyro(robot):
    # Spin right 90 degrees using gyro assistance; should end in coast state.
    robot.drivetrain.spin(degrees=90, speed=50, use_gyro=True,
                          gyro_sensor_id="main_gyro", sensor_getter=dummy_sensor_get)
    assert robot.drivetrain._current_action is None

# Test drive_distance with mocked encoder ticks to avoid infinite loop.
def test_drive_distance(robot):
    # Monkeypatch the left encoder get_ticks() method to return a large number immediately.
    class DummyEncoder:
        def __init__(self, target=1000):
            self._target = target
        def get_ticks(self):
            return self._target
    robot.drivetrain.reset_encoders()
    setattr(robot.drivetrain, "_encoder_a", DummyEncoder(120))  # ensure loop exits quickly
    try:
        robot.drivetrain.drive_distance(distance_mm=200)
    except Exception as e:
        pytest.fail(f"drive_distance raised an exception: {e}")

# Test reset_encoders() leaves tick count at zero.
def test_reset_encoder_ticks(robot):
    # Reset and verify ticks are 0 (original encoder returns 0).
    robot.drivetrain.reset_encoders()
    if hasattr(robot.drivetrain, "_encoder_a"):
        assert robot.drivetrain._encoder_a.get_ticks() == 0
