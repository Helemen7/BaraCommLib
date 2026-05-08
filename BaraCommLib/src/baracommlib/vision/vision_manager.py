import threading
import time
import json
import logging
import os
from typing import Dict, Any, Tuple

try:
    import cv2
    import numpy as np
except ImportError:
    logging.warning("OpenCV or Numpy not found. pip install opencv-python numpy")

# Try to use lightweight tflite_runtime if available (standard on RPi), otherwise fallback to full TF
try:
    from tflite_runtime.interpreter import Interpreter
except ImportError:
    try:
        from tensorflow.lite import Interpreter
    except ImportError:
        logging.warning("No TFLite interpreter found. pip install tflite-runtime OR tensorflow")


class VisionManager:
    """
    Manages background camera polling and O(1) TFLite inference.
    Prevents the main robot loop from stalling while waiting for a camera frame.
    """
    def __init__(self):
        self._cameras = {}
        self._frames = {}
        self._locks = {}
        self._running = False
        
        self.interpreter = None
        self.input_details = None
        self.output_details = None
        self.labels = []
        self.image_size = (224, 224)

    def load_model(self, model_path: str):
        """
        Loads the TFLite model and its associated labels.json file.
        
        Args:
            model_path: Path to the .tflite file (e.g. "robot_brain.tflite")
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model file {model_path} not found.")
            
        base_path = os.path.splitext(model_path)[0]
        labels_path = f"{base_path}_labels.json"
        
        if not os.path.exists(labels_path):
            raise FileNotFoundError(f"Labels file {labels_path} not found. Must be alongside the model.")
            
        with open(labels_path, "r") as f:
            self.labels = json.load(f)
            
        self.interpreter = Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        
        self.input_details = self.interpreter.get_input_details()
        self.output_details = self.interpreter.get_output_details()
        
        # Extract expected input size from the model (e.g. [1, 224, 224, 3])
        shape = self.input_details[0]['shape']
        self.image_size = (shape[2], shape[1]) # Width, Height for OpenCV
        
        logging.info(f"Vision model loaded successfully. Classes: {self.labels}")

    def start_camera(self, cam_id: str, source: int = 0, resolution: Tuple[int, int] = (640, 480)):
        """
        Starts a background thread that continuously grabs frames from the camera.
        """
        if cam_id in self._cameras:
            logging.warning(f"Camera {cam_id} is already running.")
            return

        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logging.error(f"Failed to open camera source {source}")
            return
            
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, resolution[0])
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, resolution[1])

        self._cameras[cam_id] = cap
        self._frames[cam_id] = None
        self._locks[cam_id] = threading.Lock()
        
        if not self._running:
            self._running = True
            
        thread = threading.Thread(
            target=self._camera_loop, 
            args=(cam_id, cap), 
            daemon=True, 
            name=f"CameraPoll_{cam_id}"
        )
        thread.start()

    def _camera_loop(self, cam_id: str, cap):
        """Infinite loop grabbing frames as fast as possible in the background."""
        while self._running and cap.isOpened():
            ret, frame = cap.read()
            if ret:
                with self._locks[cam_id]:
                    self._frames[cam_id] = frame
            time.sleep(0.01) # Small sleep to prevent 100% CPU lock on some systems
            
    def get_latest_frame(self, cam_id: str):
        """Returns the latest OpenCV frame instantly without blocking."""
        if cam_id not in self._locks:
            return None
            
        with self._locks[cam_id]:
            frame = self._frames[cam_id]
            if frame is not None:
                return frame.copy()
        return None

    def classify(self, cam_id: str) -> Dict[str, Any]:
        """
        Takes the latest camera frame and runs TFLite inference.
        Returns a dictionary with the top prediction.
        Execution time: O(1) for frame fetch + Inference time (typically 20-50ms on RPi 5).
        """
        if not self.interpreter:
            raise RuntimeError("Model not loaded. Call load_model() first.")
            
        frame = self.get_latest_frame(cam_id)
        if frame is None:
            return {"error": f"No frame available from camera '{cam_id}'."}

        start_time = time.time()
        
        # Preprocessing: resize to what the model expects and convert BGR to RGB
        img = cv2.resize(frame, self.image_size)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        
        # Expand dimensions to create a batch of 1
        input_data = np.expand_dims(img, axis=0).astype(self.input_details[0]['dtype'])
        
        # Run Inference
        self.interpreter.set_tensor(self.input_details[0]['index'], input_data)
        self.interpreter.invoke()
        
        # Get Results
        output_data = self.interpreter.get_tensor(self.output_details[0]['index'])[0]
        
        # Find highest confidence class
        top_idx = np.argmax(output_data)
        confidence = float(output_data[top_idx])
        label = self.labels[top_idx]
        
        inference_time_ms = (time.time() - start_time) * 1000.0
        
        return {
            "label": label,
            "confidence": confidence,
            "inference_time_ms": round(inference_time_ms, 2)
        }

    def stop_all(self):
        """Safely stops camera threads and releases hardware."""
        self._running = False
        for cam_id, cap in self._cameras.items():
            cap.release()
        self._cameras.clear()
