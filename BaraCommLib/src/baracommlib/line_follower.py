"""
Line Follower sensor support.
Analog reflective sensors (e.g., TCRT5000, QRE1113).
"""

from .sensors import AbstractSensor, SensorsManager
from typing import Optional

class LineFollowerSensor(AbstractSensor):
    """
    Analog line follower sensor.
    Returns value from 0 (black/line) to 1023 (white/surface).
    """
    
    def __init__(self, config_node: dict, i2c_bus=None, direction_enum_cls=None):
        super().__init__(config_node, i2c_bus, sensor_type="line_follower", bus_id=config_node.get("bus", "unknown"))
        self.pin = config_node.get("pin")  # Analog GPIO pin (will need ADC)
        self.threshold = config_node.get("threshold", 500)  # Default threshold for line detection
        self._sensor_instance = None
        
    def _initialize_hardware(self):
        # Would need ADC support (e.g., MCP3008/ADS1115)
        # For now, placeholder
        pass
        
    def _read_hardware(self) -> int:
        # Would read from ADC
        # Return 0-1023 (10-bit ADC)
        return 0
        
    def is_on_line(self) -> bool:
        """Returns True if sensor detects line (value below threshold)."""
        val = self.get_value()
        return val is not None and val < self.threshold
        
    def get_raw(self) -> Optional[int]:
        """Get raw analog value."""
        return self.get_value()


class MultiLineSensor(SensorsManager):
    """
    Manages multiple line follower sensors positioned in a row.
    """
    
    def __init__(self, config: dict):
        super().__init__(config)
        
    def get_line_position(self, sensor_ids: list) -> Optional[str]:
        """
        Determine robot position relative to line.
        
        Returns:
            "left" - line is to the left
            "center" - line is roughly under center sensor
            "right" - line is to the right  
            "none" - no line detected
            None - error
        """
        readings = []
        for sid in sensor_ids:
            val = self.get_reading(sid)
            if val is not None:
                readings.append((sid, val))
                
        if not readings:
            return "none"
            
        # Find sensor with minimum value (most likely on line)
        min_sensor = min(readings, key=lambda x: x[1])
        
        # This would depend on actual sensor positions
        # Simplified logic
        return "center"
        
    def get_line_center_offset(self, sensor_ids: list, positions: list[int]) -> Optional[float]:
        """
        Calculate weighted center offset for PID line following.
        
        Args:
            sensor_ids: List of sensor IDs in order
            positions: X positions of each sensor (e.g., [-30, -10, 10, 30] mm)
            
        Returns:
            Offset from center (negative = left, positive = right)
        """
        total_weight = 0
        weighted_sum = 0
        
        for sid, pos in zip(sensor_ids, positions):
            val = self.get_reading(sid)
            if val is not None and val < 500:  # Line detected
                weight = 500 - val  # More weight for darker
                weighted_sum += pos * weight
                total_weight += weight
                
        if total_weight == 0:
            return None
            
        return weighted_sum / total_weight