import logging

class _MockPWM:
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency
        self.duty_cycle = 0
        
    def start(self, duty_cycle):
        self.duty_cycle = duty_cycle
        
    def ChangeDutyCycle(self, duty_cycle):
        self.duty_cycle = duty_cycle

class _MockGPIO:
    HIGH = 1
    LOW = 0
    OUT = 0
    IN = 1
    BCM = 11
    BOARD = 10
    
    PUD_OFF = 20
    PUD_DOWN = 21
    PUD_UP = 22

    def __init__(self):
        self._pins = {} # Virtual pin states
        self.PWM = _MockPWM

    def setmode(self, mode):
        pass

    def setup(self, pins, mode, pull_up_down=20):
        if not isinstance(pins, (list, tuple)):
            pins = [pins]
        for pin in pins:
            if pin not in self._pins:
                # If pull-up is specified, default state to HIGH
                if pull_up_down == self.PUD_UP:
                    self._pins[pin] = self.HIGH
                else:
                    self._pins[pin] = self.LOW

    def output(self, pin, state):
        self._pins[pin] = state

    def input(self, pin):
        return self._pins.get(pin, self.LOW)

    def cleanup(self):
        pass    # Nothing to actually clean up

# Instantiate a singleton to be used across the library
GPIO = _MockGPIO()
