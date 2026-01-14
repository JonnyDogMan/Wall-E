from machine import Pin, PWM
import time

# Edit pins to match your wiring
SERVO_PINS = {
    "LR": 5,
    "UD": 11,
    "TL": 12,
    "BL": 9,
    "TR": 7,
    "BR": 15,
}

TEST_SERVO = "LR"  # change this each time

# Start safe. Tight range prevents sudden jams.
US_START = 1500
US_STEP = 10

# Hard safety clamp (adjust later if needed)
US_MIN = 1000
US_MAX = 2000

pin = SERVO_PINS[TEST_SERVO]
pwm = PWM(Pin(pin))
pwm.freq(50)

current_us = US_START
min_safe = None
max_safe = None

def clamp(us):
    if us < US_MIN:
        return US_MIN
    if us > US_MAX:
        return US_MAX
    return us

def write_us(us):
    global current_us
    current_us = clamp(int(us))
    duty = int(current_us * 65535 / 20000)
    pwm.duty_u16(duty)
    print(TEST_SERVO, "GPIO", pin, "pulse_us", current_us)

print("Testing", TEST_SERVO, "on GPIO", pin)
print("Commands:")
print("  a = -10us, d = +10us")
print("  j = -50us, l = +50us")
print("  m = save MIN safe, M = save MAX safe")
print("  p = print saved limits")
print("  q = quit (stops PWM)")
print("Safety clamp:", US_MIN, "to", US_MAX)
print()

write_us(US_START)
time.sleep(0.2)

try:
    while True:
        cmd = input("> ").strip()

        if cmd == "q":
            break
        elif cmd == "a":
            write_us(current_us - US_STEP)
        elif cmd == "d":
            write_us(current_us + US_STEP)
        elif cmd == "j":
            write_us(current_us - 50)
        elif cmd == "l":
            write_us(current_us + 50)
        elif cmd == "m":
            min_safe = current_us
            print("Saved MIN safe:", min_safe)
        elif cmd == "M":
            max_safe = current_us
            print("Saved MAX safe:", max_safe)
        elif cmd == "p":
            print("Servo:", TEST_SERVO, "MIN:", min_safe, "MAX:", max_safe)
            if min_safe is not None and max_safe is not None:
                print("Paste this:")
                print(f'    "{TEST_SERVO}": ({min_safe}, {max_safe}),')
        else:
            print("Use a/d/j/l/m/M/p/q")

        time.sleep(0.15)

finally:
    # Hard stop PWM so it doesn't keep driving after stop
    try:
        pwm.duty_u16(0)
    except:
        pass
    try:
        pwm.deinit()
    except:
        pass
    print("PWM stopped.")
