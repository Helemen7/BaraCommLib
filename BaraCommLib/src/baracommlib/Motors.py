import RPi.GPIO as GPIO


class Motors:
    def __init__(self, config: dict):
        self.config = config
        motors = self.config.get("drivetrain").get("motors")
        leftA = motors.get("left")
        rightB = motors.get("right")

        self.AIN1 = leftA.get("in1")
        self.AIN2 = leftA.get("in2")
        self.BIN1 = rightB.get("in1")
        self.BIN2 = rightB.get("in2")

        self.PWMA = leftA.get("pwm")
        self.PWMB = rightB.get("pwm")

        GPIO.setmode(GPIO.BCM)
        GPIO.setup([self.AIN1, self.AIN2, self.BIN1, self.BIN2], GPIO.OUT)
        GPIO.setup([self.PWMA, self.PWMB], GPIO.OUT)

        self.pwm_a = GPIO.PWM(self.PWMA, 1000)
        self.pwm_b = GPIO.PWM(self.PWMB, 1000)
        self.pwm_a.start(0)
        self.pwm_b.start(0)

    def move_forward_action(self, speed: int):
        GPIO.output(self.AIN1, GPIO.HIGH)
        GPIO.output(self.AIN2, GPIO.LOW)
        GPIO.output(self.BIN1, GPIO.HIGH)
        GPIO.output(self.BIN2, GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def turn_left_action(self, speed: int):
        GPIO.output(self.AIN1, GPIO.LOW)
        GPIO.output(self.AIN2, GPIO.HIGH)
        GPIO.output(self.BIN1, GPIO.HIGH)
        GPIO.output(self.BIN2, GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def turn_right_action(self, speed: int):
        GPIO.output(self.AIN1, GPIO.HIGH)
        GPIO.output(self.AIN2, GPIO.LOW)
        GPIO.output(self.BIN1, GPIO.LOW)
        GPIO.output(self.BIN2, GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(speed)
        self.pwm_b.ChangeDutyCycle(speed)

    def coast(self):
        GPIO.output([self.AIN1, self.AIN2, self.BIN1, self.BIN2], GPIO.LOW)
        self.pwm_a.ChangeDutyCycle(0)
        self.pwm_b.ChangeDutyCycle(0)

    def force_brake(self, max_pwm_value: int):
        # This shouldn't be kept on for more then a few seconds because it puts strains on components
        GPIO.output([self.AIN1, self.AIN2, self.BIN1, self.BIN2], GPIO.HIGH)
        self.pwm_a.ChangeDutyCycle(max_pwm_value)
    
        
        