import time
import sys
import os

# Temporarily add the library to PYTHONPATH so we can import it
# without installing it globally first
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from baracommlib.BaraRobot import BaraRobot

def main():
    print("Initializing Robot...")
    # The robot is created using the baraconfig.yaml file in this same folder
    robot = BaraRobot(config_filepath="baraconfig.yaml")
    
    # 1. BUTTON EXAMPLE: We use the decorator to react to the "start" button configured in the YAML
    @robot.on_button_pressed("start")
    def on_start_button():
        print("\n[!] 'start' button pressed! Executing a 90-degree right turn...")
        try:
            # Uses the gyroscope to turn exactly 90 degrees with a 2-degree tolerance
            robot.turn(angle=90.0, speed=50, tolerance=2.0)
            print("[!] Turn completed.")
        except RuntimeError as e:
            print(f"[!] Unable to turn: {e}")

    print("Robot initialized successfully.")
    print("Press CTRL+C to stop the program.")
    print("Waiting for command... (press the 'start' button to turn or place an obstacle in front)\n")

    # Flag to avoid console spam
    was_obstructed = False

    try:
        # Main Loop (Application Loop)
        while True:
            # 2. SENSOR READING: Values are read in O(1) from the background threads cache
            front_distance = robot.sensor.get("front") # The front ToF sensor from YAML
            gyro_data = robot.sensor.get("main_gyro")
            
            # Safe formatting for print
            dist_str = f"{front_distance} mm" if front_distance is not None else "N/A"
            yaw_str = f"{gyro_data['yaw']:.1f}°" if (gyro_data and isinstance(gyro_data, dict)) else "N/A"
            
            # 3. MOVEMENT LOGIC: Simple Obstacle Avoidance
            if front_distance is not None and front_distance < 150.0:
                if not was_obstructed:
                    print(f"\n[WARNING] Obstacle detected at {dist_str}! Braking immediately.")
                    was_obstructed = True
                
                # Brake the motors
                robot.drivetrain.coast()
            else:
                if was_obstructed:
                    print("\n[WARNING] Path clear. Resuming movement.")
                    was_obstructed = False
                
                # Move motors forward
                robot.drivetrain.move_forward_action(speed=30)
                
                # Print state compactly (overwriting the line)
                print(f"\rMoving - Distance: {dist_str} | Heading Gyro: {yaw_str}    ", end="", flush=True)

            # The loop can run very fast, let's add a sleep to avoid saturating the CPU
            time.sleep(0.05)

    except KeyboardInterrupt:
        # This catches CTRL+C
        print("\n\nShutdown requested by the user...")
        
    finally:
        # 4. CRITICAL CLEANUP: Must ALWAYS be placed in the "finally" block
        # Ensures GPIO pins are released, threads are stopped, and motors are turned off.
        print("Executing hardware cleanup...")
        robot.cleanup()
        print("Cleanup completed. Goodbye!")

if __name__ == "__main__":
    main()
