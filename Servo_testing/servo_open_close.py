from machine import Pin, PWM
import time

PIN = 5          # TL pin
US_CLOSED = 1500  # your found closed value
US_OPEN = 1260  # your found opened value

STEP = 20         # change to 5 for finer, 25 for faster
US_MIN = 500      # safety clamp
US_MAX = 2500     # safety clamp

pwm = PWM(Pin(PIN))
pwm.freq(50)

us = US_CLOSED

def clamp(x):
    if x < US_MIN: return US_MIN
    if x > US_MAX: return US_MAX
    return x

def write_us(x):
    global us
    us = clamp(int(x))
    pwm.duty_u16(int(us * 65535 / 20000))
    print("TL pulse_us:", us)

print("TL open/close finder")
print("o = open (increase us)")
print("c = close (decrease us)")
print("p = print current us")
print("q = quit")
print("Starting at CLOSED =", US_CLOSED)

write_us(US_CLOSED)
time.sleep(0.2)

try:
    while True:
        cmd = input("> ").strip().lower()
        if cmd == "q":
            break
        if cmd == "o":
            write_us(us + STEP)
        elif cmd == "c":
            write_us(us - STEP)
        elif cmd == "p":
            print("TL current:", us)
        else:
            print("Use o/c/p/q")
        time.sleep(0.1)

finally:
    try:
        pwm.duty_u16(0)
    except:
        pass
    try:
        pwm.deinit()
    except:
        pass
    print("Stopped PWM")
