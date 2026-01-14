from machine import Pin, PWM
import time

PINS = [4]

def pulse_on(pin, us):
    pwm = PWM(Pin(pin))
    pwm.freq(50)
    duty = int(us * 65535 / 20000)
    pwm.duty_u16(duty)
    return pwm

for pin in PINS:
    print("Testing pin", pin, "neutral 1500us")
    pwm = pulse_on(pin, 1500)
    time.sleep(2)
    pwm.deinit()
    time.sleep(0.5)
