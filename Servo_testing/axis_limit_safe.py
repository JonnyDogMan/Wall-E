from machine import Pin, PWM
import time

# ---------- CHANGE THESE ----------
PIN = 4        # 11 for U/D, 5 for L/R
AXIS = "LR"     # just for printing ("UD" or "LR")
# ----------------------------------

STEP = 10       # safe step size
US_MIN = 500
US_MAX = 2500

Pin(PIN, Pin.OUT).value(0)  # force LOW, no PWM
pwm = None
us = None

def clamp(x):
    if x < US_MIN: return US_MIN
    if x > US_MAX: return US_MAX
    return x

def write_us(x):
    global us
    us = clamp(int(x))
    pwm.duty_u16(int(us * 65535 / 20000))
    print(f"{AXIS} pulse_us:", us)

def stop_pwm():
    global pwm, us
    if pwm:
        try: pwm.duty_u16(0)
        except: pass
        try: pwm.deinit()
        except: pass
    pwm = None
    us = None
    Pin(PIN, Pin.OUT).value(0)

def begin(start_us):
    global pwm
    stop_pwm()
    pwm = PWM(Pin(PIN))
    pwm.freq(50)
    write_us(start_us)

print(f"{AXIS} LIMIT FINDER (GPIO{PIN})")
print("No movement on startup.")
print("Commands:")
print("  b = begin PWM (try 1500 first)")
print("  + = +10us")
print("  - = -10us")
print("  j = -50us")
print("  l = +50us")
print("  m = save MIN")
print("  M = save MAX")
print("  p = print saved limits")
print("  s = stop PWM")
print("  q = quit")
print()

min_safe = None
max_safe = None

try:
    while True:
        cmd = input("> ").strip()

        if cmd == "q":
            break

        if cmd == "b":
            raw = input("Start pulse (try 1500): ")
            try:
                begin(int(raw))
            except:
                print("Invalid number")
            continue

        if cmd == "s":
            stop_pwm()
            print("PWM stopped")
            continue

        if pwm is None:
            print("Type b to begin")
            continue

        if cmd == "+":
            write_us(us + STEP)
        elif cmd == "-":
            write_us(us - STEP)
        elif cmd == "j":
            write_us(us - 50)
        elif cmd == "l":
            write_us(us + 50)
        elif cmd == "m":
            min_safe = us
            print("Saved MIN:", min_safe)
        elif cmd == "M":
            max_safe = us
            print("Saved MAX:", max_safe)
        elif cmd == "p":
            print(f'{AXIS} limits:', min_safe, max_safe)
            if min_safe and max_safe:
                print(f'"{AXIS}": ("{PIN}", {min_safe}, {max_safe})')
        else:
            print("Use + - j l m M p s q")

        time.sleep(0.1)

finally:
    stop_pwm()
    print("Exited. PWM stopped.")
