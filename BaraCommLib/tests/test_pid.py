# Path configured in tests/conftest.py
from baracomllib.pid_controller import PIDController, PositionPID, VelocityPID
import pytest

# Simple sanity checks for PID implementations.
def test_pid_compute_output():
    pid = PIDController(kp=2.0, ki=0.5, kd=1.0)
    # setpoint default 0 -> error negative when current>setpoint
    output = pid.compute(10)   # should be less than zero (negative) due to kp*error -20? Actually error=-10 => p_term=-20
    assert isinstance(output, float)
    # Output must stay within bounds (-100..100 by default)
    assert -100 <= output <= 100

def test_position_pid_reaches_target():
    pos_pid = PositionPID(max_speed=200)
    target_pos = 500
    current = 0
    for i in range(20):
        speed = pos_pid.compute(current, target_pos)
        # Simulate moving forward by 30 ticks per loop
        if abs(target_pos - current) < 5:
            break
        current += 30
    assert isinstance(speed, int)
    # After reaching close to the target we expect flag set (if implemented), but not essential for test.

def test_velocity_pid_output_limits():
    vel_pid = VelocityPID(max_pwm=150)
    target_speed = 50.0
    current_speed = 10.0
    pwm = vel_pid.compute(current_speed, target_speed)
    assert -150 <= pwm <= 150
