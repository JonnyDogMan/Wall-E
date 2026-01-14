from machine import Pin, PWM
import time

SERVO_PINS = {
    "LR": 5,
    "UD": 11,
    "TL": 12,
    "BL": 9,
    "TR": 7,
    "BR": 15,
}

TEST_SERVO = "TL"   # change this

STEP_US = 5

# DO NOT set these below 500 or above 2500
US_MIN = 500
US_MAX = 2500

pin_num = SERVO_PINS[TEST_SERVO]

# Start with no PWM and pin low
Pin(pin_num, Pin.OUT).value(0)
pwm = None
current_us = None

def clamp(us):
    if us < US_MIN:
        return US_MIN
    if us > US_MAX:
        return US_MAX
    return us

def write_us(us):
    global current_us
    us = clamp(int(us))
    current_us = us
    duty = int(us * 65535 / 20000)
    pwm.duty_u16(duty)
    print(TEST_SERVO, "GPIO", pin_num, "pulse_us", us)

def begin(us):
    global pwm, current_us
    stop()
    pwm = PWM(Pin(pin_num))
    pwm.freq(50)
    write_us(us)
    time.sleep(0.1)

def stop():
    global pwm, current_us
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
    current_us = None
    # keep signal low when stopped
    try:
        Pin(pin_num, Pin.OUT).value(0)
    except:
        pass

print("SAFE SERVO US TESTER v2")
print("Servo:", TEST_SERVO, "GPIO", pin_num)
print("Commands:")
print("  b = begin at a pulse (try 1500)")
print("  + = +5us, - = -5us")
print("  j = -25us, l = +25us")
print("  s = stop PWM")
print("  q = quit")
print("Valid range:", US_MIN, "to", US_MAX)
print()

try:
    while True:
        cmd = input("> ").strip()

        if cmd == "q":
            break

        if cmd == "b":
            raw = input("Start pulse in microseconds (500-2500), try 1500: ").strip()
            try:
                start_val = int(raw)
            except:
                print("Not a number.")
                continue
            begin(start_val)
            continue

        if cmd == "s":
            stop()
            print("PWM stopped.")
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
        else:
            print("Use b, +, -, j, l, s, q")

        time.sleep(0.1)

finally:
    stop()
    print("Exited. PWM stopped.")
