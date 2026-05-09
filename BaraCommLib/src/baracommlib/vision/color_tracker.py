import cv2
import numpy as np

# Presets for 10 common colors. 
# HSV is generally recommended for computer vision as it handles shadows/lighting better.
# BGR (OpenCV's default RGB) bounds are also provided as requested.
COLOR_PRESETS = {
    'red': {
        'hsv': {'lower': (0, 120, 70), 'upper': (10, 255, 255)},
        'bgr': {'lower': (0, 0, 150), 'upper': (100, 100, 255)} # OpenCV uses BGR!
    },
    'green': {
        'hsv': {'lower': (40, 50, 50), 'upper': (90, 255, 255)},
        'bgr': {'lower': (0, 150, 0), 'upper': (100, 255, 100)}
    },
    'blue': {
        'hsv': {'lower': (100, 150, 0), 'upper': (140, 255, 255)},
        'bgr': {'lower': (150, 0, 0), 'upper': (255, 100, 100)}
    },
    'yellow': {
        'hsv': {'lower': (20, 100, 100), 'upper': (40, 255, 255)},
        'bgr': {'lower': (0, 150, 150), 'upper': (100, 255, 255)}
    },
    'orange': {
        'hsv': {'lower': (10, 100, 100), 'upper': (25, 255, 255)},
        'bgr': {'lower': (0, 100, 200), 'upper': (100, 180, 255)}
    },
    'purple': {
        'hsv': {'lower': (130, 50, 50), 'upper': (160, 255, 255)},
        'bgr': {'lower': (100, 0, 100), 'upper': (255, 100, 255)}
    },
    'cyan': {
        'hsv': {'lower': (80, 100, 100), 'upper': (100, 255, 255)},
        'bgr': {'lower': (150, 150, 0), 'upper': (255, 255, 100)}
    },
    'magenta': {
        'hsv': {'lower': (140, 100, 100), 'upper': (170, 255, 255)},
        'bgr': {'lower': (150, 0, 150), 'upper': (255, 100, 255)}
    },
    'white': {
        'hsv': {'lower': (0, 0, 200), 'upper': (180, 30, 255)},
        'bgr': {'lower': (200, 200, 200), 'upper': (255, 255, 255)}
    },
    'black': {
        'hsv': {'lower': (0, 0, 0), 'upper': (180, 255, 50)},
        'bgr': {'lower': (0, 0, 0), 'upper': (50, 50, 50)}
    }
}

class ColorTracker:
    def __init__(self, custom_bounds=None):
        """
        Initializes the tracker. 
        custom_bounds: optional dict of color_name -> {'hsv': {'lower': (), 'upper': ()}}
        to override or add new colors.
        """
        self.colors = COLOR_PRESETS.copy()
        if custom_bounds:
            for color, spaces in custom_bounds.items():
                if color not in self.colors:
                    self.colors[color] = {}
                # Update with custom HSV or RGB/BGR spaces
                for space, bounds in spaces.items():
                    self.colors[color][space] = bounds

    def check_region_color(self, frame, x, y, w, h, target_color, color_space='hsv', threshold=0.2):
        """
        Extracts a region of interest (ROI) and checks if a color covers more than 'threshold' 
        percentage of that area.
        
        frame: OpenCV BGR frame (numpy array)
        x, y, w, h: ROI coordinates and dimensions
        target_color: string name of the color (e.g. 'red', 'blue')
        color_space: 'hsv' (recommended) or 'bgr'/'rgb'
        threshold: float 0.0 to 1.0 (e.g. 0.2 means 20% of the area)
        """
        if target_color not in self.colors:
            raise ValueError(f"Color '{target_color}' not configured.")
        
        # 'rgb' in opencv usually means we just process it as BGR values if we mapped them to BGR.
        # But if the user really passed RGB bounds explicitly for custom, we can handle it.
        lookup_space = 'bgr' if color_space.lower() == 'rgb' else color_space.lower()
        
        if lookup_space not in self.colors[target_color]:
            raise ValueError(f"Color '{target_color}' does not have bounds defined for space '{color_space}'.")
            
        roi = frame[y:y+h, x:x+w]
        if roi.size == 0:
            return False
            
        bounds = self.colors[target_color][lookup_space]
        lower = np.array(bounds['lower'])
        upper = np.array(bounds['upper'])
        
        if lookup_space == 'hsv':
            process_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        else:
            process_roi = roi # Keep as BGR for 'bgr' or 'rgb' (assuming bounds match opencv's BGR order)
            
        mask = cv2.inRange(process_roi, lower, upper)
        
        # Check if color is present in more than the threshold ratio of the ROI
        color_ratio = cv2.countNonZero(mask) / (w * h)
        return color_ratio > threshold
        
    def get_available_colors(self):
        return list(self.colors.keys())
