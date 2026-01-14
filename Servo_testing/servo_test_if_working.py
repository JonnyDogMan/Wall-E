from machine import Pin, PWM
import time

PIN = 5  # LR pin

pwm = PWM(Pin(PIN))
pwm.freq(50)

def pulse(us):
    pwm.duty_u16(int(us * 65535 / 20000))
    print("pulse:", us)

print("1500")
pulse(1500)
time.sleep(2)

print("1200")
pulse(1200)
time.sleep(2)

print("1800")
pulse(1800)
time.sleep(2)

print("1500")
pulse(1500)
time.sleep(2)

pwm.deinit()
print("done")
