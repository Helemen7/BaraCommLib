# Path configured in tests/conftest.py
from baracomllib import BaraRobot
import pytest

@pytest.fixture(scope="module")
def robot():
    return BaraRobot()

# Test LED control via IOManager.
def test_led_control(robot):
    led = robot.io.get_led("status")
    assert led is not None
    # Turn on
    robot.io.led('status', on=True)
    assert getattr(led, "_is_on", False) == True
    # Turn off via io method
    robot.io.led('status', on=False)
    assert led._is_on == False

# Test buzzer functions.
def test_buzzer_functions(robot):
    buz = robot.io.get_buzzer("alarm")
    assert buz is not None
    # Beep single (shouldn't raise error)
    try:
        buz.beep(100, frequency=440)
    except Exception as e:
        pytest.fail(f"Buzzer beep raised exception: {e}")
    # Play a small sequence
    seq = [(440, 200), (880, 150)]
    try:
        buz.play_sequence(seq)
    except Exception as e:
        pytest.fail("play_sequence failed")
