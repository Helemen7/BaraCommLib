"""
Obstacle Avoidance helpers.
Provides reactive behaviors for autonomous navigation.
"""

import time
from typing import Optional, Callable, Dict, Any, List
from enum import Enum

class BehaviorState(Enum):
    IDLE = "idle"
    FORWARD = "forward"
    AVOIDING = "avoiding"
    WALL_FOLLOWING = "wall_following"

class ObstacleAvoider:
    """
    Simple reactive obstacle avoidance using ToF sensors.
    """
    
    def __init__(
        self,
        get_sensor_reading: Callable[[str], Optional[float]],
        move_forward: Callable[[int], None],
        turn_left: Callable[[int], None],
        turn_right: Callable[[int], None],
        coast: Callable[[], None],
        front_sensor_ids: List[str] = None,
        left_sensor_ids: List[str] = None,
        right_sensor_ids: List[str] = None,
        safe_distance_mm: int = 150,
        very_close_mm: int = 80,
        speed: int = 50
    ):
        """
        Args:
            get_sensor_reading: Function to get sensor value by ID
            move_forward/turn_left/turn_right: Motor control functions
            coast: Stop function
            front_sensor_ids: List of front sensor IDs to check
            left_sensor_ids: Left sensor IDs
            right_sensor_ids: Right sensor IDs
            safe_distance_mm: Distance to start avoiding
            very_close_mm: Distance to trigger emergency stop
            speed: Default movement speed
        """
        self._get_sensor = get_sensor_reading
        self._forward = move_forward
        self._left = turn_left
        self._right = turn_right
        self._coast = coast
        
        self._front_sensors = front_sensor_ids or []
        self._left_sensors = left_sensor_ids or []
        self._right_sensors = right_sensor_ids or []
        
        self._safe_dist = safe_distance_mm
        self._very_close = very_close_mm
        self._speed = speed
        self._state = BehaviorState.IDLE
        
    @property
    def state(self) -> BehaviorState:
        return self._state
        
    def _read_sensors(self, sensor_ids: List[str]) -> List[float]:
        """Read all sensors in a list and return valid readings."""
        readings = []
        for sid in sensor_ids:
            val = self._get_sensor(sid)
            if val is not None and val > 0:  # Only valid positive readings
                readings.append(val)
        return readings
    
    def _get_min_distance(self, sensor_ids: List[str]) -> float:
        """Get minimum distance from a group of sensors."""
        readings = self._read_sensors(sensor_ids)
        return min(readings) if readings else float('inf')
    
    def update(self):
        """
        Call this in your main loop to update behavior.
        Returns True if action was taken, False if idle.
        """
        front_dist = self._get_min_distance(self._front_sensors)
        left_dist = self._get_min_distance(self._left_sensors)
        right_dist = self._get_min_distance(self._right_sensors)
        
        # Very close - emergency stop
        if front_dist < self._very_close:
            self._state = BehaviorState.AVOIDING
            self._coast()
            # Quick random turn
            if left_dist > right_dist:
                self._left(self._speed)
                time.sleep(0.2)
            else:
                self._right(self._speed)
                time.sleep(0.2)
            return True
            
        # Safe distance - move forward
        if front_dist > self._safe_dist:
            self._state = BehaviorState.FORWARD
            self._forward(self._speed)
            return True
            
        # Something ahead but not too close - avoid
        # Determine best direction
        if left_dist > right_dist and left_dist > self._safe_dist:
            self._state = BehaviorState.AVOIDING
            self._left(self._speed)
            return True
        elif right_dist > left_dist and right_dist > self._safe_dist:
            self._state = BehaviorState.AVOIDING
            self._right(self._speed)
            return True
        else:
            # Dead end - back up and turn
            self._state = BehaviorState.AVOIDING
            self._coast()
            time.sleep(0.1)
            # Would need reverse - for now just turn
            self._left(self._speed)
            time.sleep(0.3)
            return True
            
    def stop(self):
        """Stop all behavior."""
        self._state = BehaviorState.IDLE
        self._coast()


class WallFollower:
    """
    Follow a wall on the left or right side using side sensors.
    """
    
    def __init__(
        self,
        get_sensor_reading: Callable[[str], Optional[float]],
        move_forward: Callable[[int], None],
        turn_left: Callable[[int], None],
        turn_right: Callable[[int], None],
        coast: Callable[[], None],
        side_sensor_ids: List[str],
        side: str = "left",  # "left" or "right"
        target_distance_mm: int = 100,
        speed: int = 40
    ):
        self._get_sensor = get_sensor_reading
        self._forward = move_forward
        self._left = turn_left
        self._right = turn_right
        self._coast = coast
        
        self._side_sensors = side_sensor_ids
        self._side = side
        self._target_dist = target_distance_mm
        self._speed = speed
        self._running = False
        
        # PID-like controller for wall following
        self._integral = 0.0
        self._last_error = 0.0
        
    def start(self):
        self._running = True
        
    def stop(self):
        self._running = False
        self._coast()
        
    def update(self):
        """Call this in main loop."""
        if not self._running:
            return
            
        # Read side distance
        readings = []
        for sid in self._side_sensors:
            val = self._get_sensor(sid)
            if val and val > 0:
                readings.append(val)
                
        if not readings:
            # No wall - spiral search
            self._forward(self._speed // 2)
            return
            
        current_dist = min(readings)
        error = current_dist - self._target_dist
        
        # Simple P controller
        correction = int(error * 0.5)  # P gain
        
        # Clamp
        correction = max(-30, min(30, correction))
        
        if self._side == "left":
            # Left side follow: too close = turn right, too far = turn left
            base_speed = self._speed
            turn_correction = correction
        else:
            # Right side follow: inverted
            base_speed = self._speed
            turn_correction = -correction
            
        # Apply
        left_speed = base_speed - turn_correction
        right_speed = base_speed + turn_correction
        
        # Direct motor control (would need to add to Motors class)
        self._forward(max(left_speed, right_speed))  # Simplified