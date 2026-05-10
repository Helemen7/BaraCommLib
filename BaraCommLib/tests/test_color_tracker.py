import numpy as np
from baracomllib.vision.color_tracker import ColorTracker

def test_get_available_colors():
    tracker = ColorTracker()
    colors = tracker.get_available_colors()
    assert 'red' in colors and isinstance(colors, list)

# Verify that providing an unknown color raises ValueError
import pytest

def test_unknown_color_raises_error():
    tracker = ColorTracker()
    dummy_frame = np.zeros((10, 10, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        # passing a non-existing target color should raise
        tracker.check_region_color(dummy_frame, x=0, y=0, w=5, h=5, target_color="nonexistent")