from machine import Pin
import time

led = Pin("LED", Pin.OUT)
print("LED blink running")

while True:
    led.toggle()
    time.sleep(0.25)
