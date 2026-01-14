from machine import Pin, PWM
import time

# ---------------- Servo configuration ----------------
# Update limits if you refine TR / BR later

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
        "closed": 1700,   # adjust if needed
        "open": 700,
    },
    "BR": {
        "pin": 15,
        "closed": 1040,   # adjust if needed
        "open": 1920,
    },
    "UD": {
        "pin": 11,
        "closed": 1260,   # adjust if needed
        "open": 1560,
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

def ramp_all(start_vals, end_vals):
    currents = start_vals.copy()

    steps = {}
    for k in currents:
        steps[k] = STEP_US if end_vals[k] > currents[k] else -STEP_US

    done = False
    while not done:
        done = True
        for k in currents:
            if currents[k] != end_vals[k]:
                currents[k] += steps[k]
                if (steps[k] > 0 and currents[k] > end_vals[k]) or \
                   (steps[k] < 0 and currents[k] < end_vals[k]):
                    currents[k] = end_vals[k]
                done = False

            set_us(pwms[k], currents[k])

        time.sleep_ms(STEP_DELAY_MS)

# ---------------- Blink sequence ----------------

try:
    # Start CLOSED
    closed_vals = {k: v["closed"] for k, v in SERVOS.items()}
    open_vals   = {k: v["open"]   for k, v in SERVOS.items()}

    for k in closed_vals:
        set_us(pwms[k], closed_vals[k])

    time.sleep_ms(HOLD_MS)

    for i in range(CYCLES):
        print("Blink", i + 1, "open")
        ramp_all(closed_vals, open_vals)
        time.sleep_ms(HOLD_MS)

        print("Blink", i + 1, "close")
        ramp_all(open_vals, closed_vals)
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
