from servo import Servo

PIN_LR = 10
STEP = 5

# Tight clamp to prevent jams. Adjust these tighter if needed.
MIN_ANGLE = 88
MAX_ANGLE = 92

lr = Servo(PIN_LR, start_angle=90)  # safe startup

angle = 90
print("LR nudge tester")
print("Commands:")
print("  l = -5 degrees")
print("  r = +5 degrees")
print("  q = quit")
print("Clamp:", MIN_ANGLE, "to", MAX_ANGLE)

def clamp(a):
    if a < MIN_ANGLE:
        return MIN_ANGLE
    if a > MAX_ANGLE:
        return MAX_ANGLE
    return a

while True:
    cmd = input("> ").strip().lower()
    if cmd == "q":
        break
    if cmd not in ("l", "r"):
        print("Use l, r, or q")
        continue

    if cmd == "l":
        angle -= STEP
    else:
        angle += STEP

    angle = clamp(angle)
    lr.write(angle)
    print("LR angle:", angle)

print("Done.")
