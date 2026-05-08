# PC Development (The Mocking System)

Developing software for the Raspberry Pi on a Windows PC or a Mac (which have neither physical GPIO pins nor hardware I2C buses) often leads to annoying `ImportError: No module named RPi` or `NotImplementedError` crashes.

The BaraCommLib library fundamentally solves this problem by implementing **transparent Mocking patterns** for both the GPIO system and the I2C framework (`Adafruit Blinka`).

## `mock_gpio.py`

When you execute `from baracommlib.Motors import Motors`, the library secretly does this:

```python
try:
    import RPi.GPIO as GPIO
except (ImportError, RuntimeError):
    import logging
    logging.warning("RPi.GPIO not found or not running on Raspberry Pi. Using Mock GPIO for development.")
    from .mock_gpio import GPIO
```

### How GPIO Mock Works

The `_MockGPIO` class (which masks the real `RPi.GPIO`) maintains an internal dictionary `self._pins = {}` instead of actual silicon memory.

When your program does:
`GPIO.output(12, GPIO.HIGH)`

The mock silently registers:
`self._pins[12] = 1`

When your function (e.g., `health_check`) does:
`GPIO.input(12)`

The mock returns `1`. This allows all your logic code (PID, safety checks, health checks) to work **exactly as it would on the board**, without requiring any changes on your end.

## I2C Mocking (Blinka)

Similarly, in the `sensors.py` file, heavy and device-specific libraries like `board`, `busio`, and `digitalio` are mocked with stub classes (`_MockBoard`, `_MockBusIO`, etc.).
This way, the I2C sensors in the config are initialized, and the background thread polling simply returns a harmless fallback (like `0.0`) without crashing or freezing the main loop.

> [!NOTE]
> The output "Using Mock GPIO for development." is intentionally injected into `logging.warning` so it's always visible in the standard output, preventing you from forgetting to install the real libraries once you deploy the code to the final Raspberry Pi!
