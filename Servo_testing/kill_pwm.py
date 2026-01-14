from machine import Pin, PWM
import time

SERVO_PINS = [10, 11, 12, 13, 14, 15]

print("Stopping PWM on servo pins:", SERVO_PINS)

pwms = []
for p in SERVO_PINS:
    try:
        pwm = PWM(Pin(p))
        pwm.freq(50)
        pwm.duty_u16(0)   # stop pulses
        pwms.append(pwm)
    except Exception as e:
        print("Pin", p, "error:", e)

time.sleep_ms(100)

for pwm in pwms:
    try:
        pwm.deinit()
    except:
        pass

print("Done. PWM deinitialized.")
