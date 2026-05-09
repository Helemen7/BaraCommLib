"""
PID Controller for precise movement control.
Provides both position (distance) and velocity (speed) control.
"""

import time
from typing import Optional, Callable

class PIDController:
    """
    Generic PID Controller.
    
    PID stands for Proportional-Integral-Derivative. This controller
    attempts to correct the error between a measured process variable
    and a desired setpoint by calculating and outputting a corrective
    action that can be applied to the system.
    """
    
    def __init__(
        self,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.0,
        setpoint: float = 0.0,
        output_min: float = -100.0,
        output_max: float = 100.0,
        integral_limit: Optional[float] = None
    ):
        """
        Initialize the PID controller.
        
        Args:
            kp: Proportional gain. Controls reaction to current error.
            ki: Integral gain. Controls reaction to past errors (accumulation).
            kd: Derivative gain. Controls reaction to rate of error change.
            setpoint: The target value the PID tries to achieve.
            output_min: Minimum output value (e.g., -100 for PWM).
            output_max: Maximum output value (e.g., 100 for PWM).
            integral_limit: Optional limit for integral term to prevent windup.
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint
        
        self.output_min = output_min
        self.output_max = output_max
        self.integral_limit = integral_limit
        
        self._previous_error = 0.0
        self._previous_time = time.time()
        self._integral = 0.0
        
    def reset(self):
        """Reset internal state (integral, previous error)."""
        self._previous_error = 0.0
        self._previous_time = time.time()
        self._integral = 0.0
        
    def compute(self, current_value: float, dt: Optional[float] = None) -> float:
        """
        Compute the PID output given the current process variable.
        
        Args:
            current_value: The current measured value (feedback).
            dt: Optional delta time. If None, computed automatically.
            
        Returns:
            Corrective output value bounded by output_min/output_max.
        """
        if dt is None:
            current_time = time.time()
            dt = current_time - self._previous_time
            self._previous_time = current_time
            
        error = self.setpoint - current_value
        
        # Proportional term
        p_term = self.kp * error
        
        # Integral term (with anti-windup)
        self._integral += error * dt
        if self.integral_limit is not None:
            self._integral = max(-self.integral_limit, min(self.integral_limit, self._integral))
        i_term = self.ki * self._integral
        
        # Derivative term
        if dt > 0:
            d_term = self.kd * (error - self._previous_error) / dt
        else:
            d_term = 0.0
            
        self._previous_error = error
        
        # Calculate output and clamp
        output = p_term + i_term + d_term
        return max(self.output_min, min(self.output_max, output))
    
    def set_setpoint(self, setpoint: float):
        """Update the target setpoint."""
        self.setpoint = setpoint


class PositionPID:
    """
    Position-based PID for reaching specific distances or angles.
    Used for: drive(distance=100), turn(angle=90)
    """
    
    def __init__(
        self,
        kp: float = 1.5,
        ki: float = 0.05,
        kd: float = 0.5,
        max_speed: int = 100
    ):
        self.controller = PIDController(
            kp=kp, ki=ki, kd=kd,
            output_min=-max_speed, output_max=max_speed,
            integral_limit=max_speed * 0.5
        )
        self.target_reached = False
        
    def compute(self, current_position: float, target_position: float) -> int:
        """
        Compute motor speed to reach target position.
        
        Args:
            current_position: Current encoder ticks or distance in mm
            target_position: Target encoder ticks or distance in mm
            
        Returns:
            Speed value (negative = backward, positive = forward)
        """
        self.controller.set_setpoint(target_position)
        speed = int(self.controller.compute(current_position))
        
        # Check if target reached (within tolerance)
        if abs(target_position - current_position) < 5:
            self.target_reached = True
            
        return speed
        
    def reset(self):
        self.controller.reset()
        self.target_reached = False


class VelocityPID:
    """
    Velocity-based PID for maintaining constant speed.
    Used for: maintaining steady speed regardless of surface/battery
    """
    
    def __init__(
        self,
        kp: float = 1.0,
        ki: float = 0.1,
        kd: float = 0.05,
        max_pwm: int = 100
    ):
        self.controller = PIDController(
            kp=kp, ki=ki, kd=kd,
            output_min=-max_pwm, output_max=max_pwm,
            integral_limit=max_pwm * 0.3
        )
        
    def compute(self, current_speed: float, target_speed: float) -> int:
        """
        Compute PWM to maintain target speed.
        
        Args:
            current_speed: Current measured speed (ticks/sec or mm/sec)
            target_speed: Desired speed
            
        Returns:
            PWM value
        """
        self.controller.set_setpoint(target_speed)
        return int(self.controller.compute(current_speed))
    
    def reset(self):
        self.controller.reset()