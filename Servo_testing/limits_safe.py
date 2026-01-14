from machine import Pin, PWM
import time

# Your updated mapping (edit if needed)
SERVO_PINS = {
    "LR": 5,
    "UD": 11,
    "TL": 12,
    "BL": 9,
    "TR": 7,
    "BR": 15,
}

TEST_SERVO = "TL"   # change this each time

# Tiny step so it cannot jump much
STEP_US = 5

# Hard clamp to keep you safe (tight at first, expand later)
US_MIN = 0
US_MAX = 1800

pin_num = SERVO_PINS[TEST_SERVO]

# Start with NO PWM, and hold the pin low so nothing random happens
sig = Pin(pin_num, Pin.OUT)
sig.value(0)

pwm = None
current_us = None
min_safe = None
max_safe = None

def clamp(us):
    if us < US_MIN:
        return US_MIN
    if us > US_MAX:
        return US_MAX
    return us

def start_pwm(initial_us):
    global pwm, current_us
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    current_us = clamp(int(initial_us))
    write_us(current_us)

def write_us(us):
    global current_us
    if pwm is None:
        return
    current_us = clamp(int(us))
    duty = int(current_us * 65535 / 20000)
    pwm.duty_u16(duty)
    print(TEST_SERVO, "GPIO", pin_num, "pulse_us", current_us)

def stop_pwm():
    global pwm
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
    # force pin low again
    try:
        sig2 = Pin(pin_num, Pin.OUT)
        sig2.value(0)
    except:
        pass

print("SAFE LIMIT TESTER (microseconds)")
print("Servo:", TEST_SERVO, "GPIO", pin_num)
print("IMPORTANT: This script does NOT move anything on startup.")
print("Commands:")
print("  b = begin PWM (you will type a starting pulse width)")
print("  + = +5us (tiny nudge)")
print("  - = -5us (tiny nudge)")
print("  j = -25us")
print("  l = +25us")
print("  m = save MIN safe")
print("  M = save MAX safe")
print("  p = print saved limits")
print("  s = stop PWM (detach this servo)")
print("  q = quit (also stops PWM)")
print("Clamp:", US_MIN, "to", US_MAX)
print()

try:
    while True:
        cmd = input("> ").strip()

        if cmd == "q":
            break

        if cmd == "b":
            # You choose the safest starting point for this servo
            # Start values to try: 1500, or 1600, or 1400 depending on your manual neutral
            raw = input("Start pulse in us (example 1500): ").strip()
            try:
                start_val = int(raw)
            except:
                print("Not a number.")
                continue
            stop_pwm()
            start_pwm(start_val)
            continue

        if cmd == "s":
            stop_pwm()
            print("PWM stopped for this servo.")
            continue

        if pwm is None:
            print("PWM is not running. Type b to begin.")
            continue

        if cmd == "+":
            write_us(current_us + STEP_US)
        elif cmd == "-":
            write_us(current_us - STEP_US)
        elif cmd == "j":
            write_us(current_us - 25)
        elif cmd == "l":
            write_us(current_us + 25)
        elif cmd == "m":
            min_safe = current_us
            print("Saved MIN safe:", min_safe)
        elif cmd == "M":
            max_safe = current_us
            print("Saved MAX safe:", max_safe)
        elif cmd == "p":
            print("Servo:", TEST_SERVO, "MIN:", min_safe, "MAX:", max_safe)
            if min_safe is not None and max_safe is not None:
                print("Paste this line:")
                print(f'    "{TEST_SERVO}": ({min_safe}, {max_safe}),')
        else:
            print("Use b, +, -, j, l, m, M, p, s, q")

        time.sleep(0.1)

finally:
    stop_pwm()
    print("Exited. PWM stopped.")
