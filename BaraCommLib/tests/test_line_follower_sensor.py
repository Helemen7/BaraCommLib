# Path configured in tests/conftest.py
import pytest
from baracomllib.line_follower import MultiLineSensor

@pytest.fixture()
def mls():
    config = {'sensors':{'buses':[]}}
    sensor_manager = MultiLineSensor(config)
    # Override get_reading to return deterministic values < 500 (line detected) for two sensors.
    def dummy_get(sid):
        if sid in ['lf1','lf2']:
            return 400
        return None
    sensor_manager.get_reading = lambda sid: dummy_get(sid)
    return sensor_manager

def test_line_position(mls):
    pos = mls.get_line_position(['lf1', 'lf2'])
    assert pos == "center"

def test_line_center_offset(mls):
    offset = mls.get_line_center_offset(['lf1','lf2'],[-10, 10])
    # With equal weights the weighted sum should be zero.
    assert abs(offset) < 0.01
