import time
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from baracommlib.BaraRobot import BaraRobot

def main():
    print("--- Vision Module: Real-time Classification Example ---")
    
    # We load the BaraRobot instance. Ensure vision is enabled in baraconfig.yaml
    # and model_path is set to "robot_brain.tflite"
    try:
        robot = BaraRobot("baraconfig.yaml")
    except Exception as e:
        print(f"Failed to initialize BaraRobot: {e}")
        return

    if not robot.vision:
        print("Error: Vision subsystem is not enabled.")
        print("Please set 'vision: enabled: true' and provide a valid 'model_path' in baraconfig.yaml.")
        return

    print("Vision system initialized. Starting classification loop...")
    print("Press CTRL+C to stop.")
    
    try:
        while True:
            # We fetch the inference result from the 'main_cam' defined in YAML
            result = robot.vision.classify("main_cam")
            
            if "error" in result:
                print(f"\rWaiting for camera frame: {result['error']}    ", end="", flush=True)
            else:
                label = result["label"]
                confidence = result["confidence"] * 100
                inf_time = result["inference_time_ms"]
                
                print(f"\rDetected: {label:15} | Confidence: {confidence:5.1f}% | Time: {inf_time:5.1f}ms    ", end="", flush=True)
                
                # Simple logic example
                if label == "red_ball" and confidence > 85.0:
                    # e.g., move towards the ball
                    pass
                elif label == "soda_can" and confidence > 85.0:
                    # e.g., avoid the can
                    pass
                    
            time.sleep(0.1) # Check 10 times a second
            
    except KeyboardInterrupt:
        print("\nStopping classification...")
    finally:
        robot.cleanup()
        print("Cleanup done. Goodbye!")

if __name__ == "__main__":
    main()
