from machine import Pin, PWM
import time

PIN = 9  # BL signal pin

STEP = 20          # bump to 25 once you are in a safe zone
US_MIN = 500
US_MAX = 3500

# Start with no PWM and force signal low
Pin(PIN, Pin.OUT).value(0)
pwm = None
us = None

# Direction mapping (BL is often mirrored)
# If "o" closes the lid, type "swap" to flip directions.
open_sign = +1
close_sign = -1

def clamp(x):
    if x < US_MIN: return US_MIN
    if x > US_MAX: return US_MAX
    return x

def write_us(x):
    global us
    us = clamp(int(x))
    pwm.duty_u16(int(us * 65535 / 20000))
    print("BL pulse_us:", us)

def stop_pwm():
    global pwm, us
    if pwm is not None:
        try:
            pwm.duty_u16(0)
        except:
            pass
        try:
            pwm.deinit()
        except:
            pass
    pwm = None
    us = None
    try:
        Pin(PIN, Pin.OUT).value(0)
    except:
        pass

def begin(start_us):
    global pwm
    stop_pwm()
    pwm = PWM(Pin(PIN))
    pwm.freq(50)
    write_us(start_us)

print("BL limit finder (GPIO9)")
print("This script will NOT move the servo on startup.")
print("Commands:")
print("  b = begin PWM at a pulse you choose")
print("  o = open (step)")
print("  c = close (step)")
print("  swap = flip open/close direction")
print("  p = print current pulse")
print("  s = stop PWM")
print("  q = quit")
print("Valid range:", US_MIN, "to", US_MAX)
print()

try:
    while True:
        cmd = input("> ").strip().lower()

        if cmd == "q":
            break

        if cmd == "b":
            raw = input("Start pulse (try 1700, 1500, 1300): ").strip()
            try:
                start_val = int(raw)
            except:
                print("Not a number.")
                continue
            begin(start_val)
            continue

        if cmd == "swap":
            open_sign *= -1
            close_sign *= -1
            print("Swapped directions.")
            continue

        if cmd == "s":
            stop_pwm()
            print("PWM stopped.")
            continue

        if pwm is None:
            print("PWM not running. Type b to begin.")
            continue

        if cmd == "o":
            write_us(us + open_sign * STEP)
        elif cmd == "c":
            write_us(us + close_sign * STEP)
        elif cmd == "p":
            print("BL current:", us)
        else:
            print("Use b, o, c, swap, p, s, q")

        time.sleep(0.1)

finally:
    stop_pwm()
    print("Exited. PWM stopped.")
