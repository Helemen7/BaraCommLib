# Path configured in tests/conftest.py
from baracomllib.telemetry import TelemetryLogger, DebugPrinter
import pytest

def test_logger_trims_entries():
    logger = TelemetryLogger(max_entries=5)
    for i in range(7):
        logger.log(sensor_readings={'sensor':i}, motor_status={})
    # Should keep only last 5 entries (indices 2-6)
    assert len(logger._entries) == 5
    assert logger._entries[0].sensors['sensor'] >= 2

def test_summary_output(capsys):
    logger = TelemetryLogger(max_entries=3)
    for i in range(4):
        logger.log(sensor_readings={'val':i}, motor_status={})
    # Capture printed summary
    logger.print_summary()
    captured = capsys.readouterr().out
    assert "Entries:" in captured
    assert str(len(logger._entries)) in captured