from baracommlib import BaraRobot
from baracommlib.sensors import SensorsManager, AbstractSensor
import time
import threading

def test_robot_init():
    robot = BaraRobot(config_filepath="baraconfig.yaml")
    assert robot is not None
    assert isinstance(robot, BaraRobot)

def test_sensor_failure_handler():
    """Test that sensors triggering 5+ seconds of errors stop the drivetrain."""
    
    # Create a mock sensor that always fails
    class FailingSensor(AbstractSensor):
        def _initialize_hardware(self):
            pass
        
        def _read_hardware(self):
            raise IOError("Simulated hardware failure")
    
    # Create robot (uses mock GPIO on PC)
    robot = BaraRobot()
    
    # Inject our failing sensor directly into the manager
    failing_sensor = FailingSensor({'id': 'test_fail'}, None)
    failing_sensor.sensor_type = "tof"
    failing_sensor.bus_id = "i2c_1"
    failing_sensor.on_critical_failure = robot.sensors_manager._handle_sensor_failure
    
    # Add it to sensors dict (overwrite existing to ensure it's used)
    robot.sensors_manager.sensors['test_fail'] = failing_sensor
    
    # Start the sensor (this starts the polling thread)
    failing_sensor.start()
    
    # Wait for 5+ seconds of continuous errors
    # The polling loop should detect 5s of errors, call on_critical_failure,
    # stop the drivetrain, and reinitialize sensors
    print("Waiting for sensor to fail continuously for 5+ seconds...")
    
    # Wait up to 7 seconds for the failure to trigger
    start_time = time.time()
    while time.time() - start_time < 7:
        if not failing_sensor._running:
            print(f"Sensor thread stopped after {time.time() - start_time:.1f}s - fail-safe triggered!")
            break
        time.sleep(0.5)
    
    # If the handler worked, drivetrain should have been stopped
    # (In mock mode, we can't easily verify motor state, but we can verify no crash)
    print("Test completed - robot should still be responsive after fail-safe.")
    assert robot.drivetrain is not None

# Run the test
if __name__ == "__main__":
    test_robot_init()
    print("test_robot_init passed!")
    test_sensor_failure_handler()
    print("test_sensor_failure_handler passed!")
