from machine import Pin, PWM
import time

# ---------------- Servo configuration ----------------

SERVOS = {
    "TL": {
        "pin": 12,
        "closed": 1155,
        "open": 2200,
    },
    "BL": {
        "pin": 9,
        "closed": 2360,
        "open": 1560,
    },
    "TR": {
        "pin": 7,
        "closed": 1700,
        "open": 700,
    }    
}

CYCLES = 3

# Motion tuning
STEP_US = 15          # smaller = smoother
STEP_DELAY_MS = 8     # delay between steps
HOLD_MS = 250         # pause at open/closed

# ---------------- Setup PWM ----------------

pwms = {}

for name, cfg in SERVOS.items():
    pwm = PWM(Pin(cfg["pin"]))
    pwm.freq(50)
    pwms[name] = pwm

def set_us(pwm, us):
    pwm.duty_u16(int(us * 65535 / 20000))

def ramp_pair(start_a, end_a, start_b, end_b):
    step_a = STEP_US if end_a > start_a else -STEP_US
    step_b = STEP_US if end_b > start_b else -STEP_US

    a = start_a
    b = start_b

    while (a != end_a) or (b != end_b):
        if a != end_a:
            a += step_a
            if (step_a > 0 and a > end_a) or (step_a < 0 and a < end_a):
                a = end_a

        if b != end_b:
            b += step_b
            if (step_b > 0 and b > end_b) or (step_b < 0 and b < end_b):
                b = end_b

        set_us(pwms["TL"], a)
        set_us(pwms["BL"], b)
        set_us(pwms["TR"], a)
        time.sleep_ms(STEP_DELAY_MS)

# ---------------- Blink sequence ----------------

try:
    # Start from CLOSED
    set_us(pwms["TL"], SERVOS["TL"]["closed"])
    set_us(pwms["BL"], SERVOS["BL"]["closed"])
    set_us(pwms["TR"], SERVOS["TR"]["closed"])
    time.sleep_ms(HOLD_MS)

    for i in range(CYCLES):
        print("Blink", i + 1, "open")
        ramp_pair(
            SERVOS["TL"]["closed"], SERVOS["TL"]["open"],
            SERVOS["BL"]["closed"], SERVOS["BL"]["open"],
            SERVOS["TR"]["closed"], SERVOS["TR"]["open"]
        )
        time.sleep_ms(HOLD_MS)

        print("Blink", i + 1, "close")
        ramp_pair(
            SERVOS["TL"]["open"], SERVOS["TL"]["closed"],
            SERVOS["BL"]["open"], SERVOS["BL"]["closed"],
            SERVOS["TR"]["open"], SERVOS["TR"]["closed"]
        )
        time.sleep_ms(HOLD_MS)

finally:
    # Stop PWM cleanly
    for pwm in pwms.values():
        try:
            pwm.duty_u16(0)
        except:
            pass
        try:
            pwm.deinit()
        except:
            pass

    print("Done. PWM stopped.")
