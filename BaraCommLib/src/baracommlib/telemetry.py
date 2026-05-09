"""
Telemetry and Debug utilities.
"""

import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class TelemetrySnapshot:
    """A single snapshot of robot state."""
    timestamp: float
    sensors: Dict[str, Any]
    motors: Dict[str, Any]
    vision_fps: Optional[float] = None
    imu: Optional[Dict[str, float]] = None
    
class TelemetryLogger:
    """
    Records robot state over time for debugging and analysis.
    Useful for identifying timing issues, sensor glitches, etc.
    """
    
    def __init__(self, enabled: bool = True, max_entries: int = 1000):
        self.enabled = enabled
        self.max_entries = max_entries
        self._entries: List[TelemetrySnapshot] = []
        self._start_time = time.time()
        self._logger = logging.getLogger("Telemetry")
        
    def log(
        self,
        sensor_readings: Dict[str, Any],
        motor_status: Dict[str, Any],
        vision_fps: Optional[float] = None,
        imu_data: Optional[Dict[str, float]] = None
    ):
        """Record a telemetry snapshot."""
        if not self.enabled:
            return
            
        snapshot = TelemetrySnapshot(
            timestamp=time.time() - self._start_time,
            sensors=sensor_readings,
            motors=motor_status,
            vision_fps=vision_fps,
            imu=imu_data
        )
        
        self._entries.append(snapshot)
        
        # Trim if too large
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
            
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics."""
        if not self._entries:
            return {"entries": 0}
            
        return {
            "entries": len(self._entries),
            "duration_sec": self._entries[-1].timestamp,
            "avg_loop_hz": len(self._entries) / self._entries[-1].timestamp if self._entries[-1].timestamp > 0 else 0,
            "last_vision_fps": self._entries[-1].vision_fps
        }
        
    def get_recent(self, n: int = 10) -> List[TelemetrySnapshot]:
        """Get N most recent entries."""
        return self._entries[-n:]
        
    def clear(self):
        """Clear all logged entries."""
        self._entries.clear()
        self._start_time = time.time()
        
    def print_summary(self):
        """Print a human-readable summary."""
        summary = self.get_summary()
        print(f"=== Telemetry Summary ===")
        print(f"Entries: {summary['entries']}")
        print(f"Duration: {summary['duration_sec']:.2f}s")
        print(f"Avg Loop Hz: {summary.get('avg_loop_hz', 0):.1f}")
        print(f"Last Vision FPS: {summary.get('last_vision_fps', 'N/A')}")


class DebugPrinter:
    """Helper to print formatted debug info."""
    
    @staticmethod
    def sensors(sensor_data: Dict[str, Any], prefix: str = ""):
        """Print sensor data in a readable format."""
        lines = [f"{prefix}Sensors:"]
        for sid, val in sensor_data.items():
            if isinstance(val, dict):
                lines.append(f"  {sid}: {val}")
            else:
                lines.append(f"  {sid}: {val}")
        print("\n".join(lines))
        
    @staticmethod
    def motors(motor_data: Dict[str, Any], prefix: str = ""):
        """Print motor status in a readable format."""
        print(f"{prefix}Motors: action={motor_data.get('action')}, speed={motor_data.get('speed')}")
        if motor_data.get("encoders"):
            enc = motor_data["encoders"]
            print(f"{prefix}  L: {enc.get('left', 0)} ticks, R: {enc.get('right', 0)} ticks")
            
    @staticmethod
    def loop_timing(prefix: str, loop_time: float, target_hz: float):
        """Print loop timing info."""
        actual_hz = 1.0 / loop_time if loop_time > 0 else 0
        status = "OK" if abs(actual_hz - target_hz) < target_hz * 0.1 else "SLOW"
        print(f"{prefix}Loop: {actual_hz:.1f}Hz (target: {target_hz}Hz) [{status}]")


# Global telemetry instance
_telemetry = TelemetryLogger()

def get_telemetry() -> TelemetryLogger:
    """Get the global telemetry instance."""
    return _telemetry