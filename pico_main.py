import socket
import network
import time
from machine import Pin, PWM
from secrets import WIFI_SSID, WIFI_PASS

# ======================================================
# WiFi
# ======================================================
def connect_wifi():
    """
    Connects to WiFi network using credentials from secrets module.
    
    @return: IP address assigned to the device
    @raises RuntimeError: If WiFi connection fails after 15 seconds
    """
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)

    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASS)

        start = time.time()
        while not wlan.isconnected():
            if time.time() - start > 15:
                raise RuntimeError("WiFi failed")
            time.sleep(0.2)

    ip = wlan.ifconfig()[0]
    print("WiFi connected:", ip)
    return ip

# ======================================================
# Servo core (pulse width in microseconds)
# ======================================================
SERVO_FREQ = 50
PERIOD_US = 20_000

def us_to_duty(us: int) -> int:
    """
    Converts pulse width in microseconds to PWM duty cycle value (0-65535).
    
    @param us: Pulse width in microseconds
    @return: PWM duty cycle value (16-bit integer)
    """
    return int(int(us) * 65535 // PERIOD_US)

class ServoLazy:
    """
    Lazy PWM servo controller with on-demand PWM activation.
    PWM is only enabled when movement is required and released after use.
    This conserves power and prevents servo buzzing when idle.
    """
    def __init__(self, pin: int, start_us: int):
        """
        Initializes a ServoLazy instance.
        
        @param pin: GPIO pin number for the servo PWM signal
        @param start_us: Initial pulse width in microseconds (neutral position)
        @return: None
        """
        self.pin = int(pin)
        self.current_us = int(start_us)
        self.pwm = None

    def enable(self):
        """
        Enables PWM on the servo pin if not already enabled.
        Sets frequency and initial duty cycle to current position.
        
        @return: None
        """
        if self.pwm is None:
            self.pwm = PWM(Pin(self.pin))
            self.pwm.freq(SERVO_FREQ)
            self.pwm.duty_u16(us_to_duty(self.current_us))

    def write(self, us: int):
        """
        Immediately sets servo position to specified pulse width.
        Requires PWM to be enabled (call enable() first or use move()).
        
        @param us: Pulse width in microseconds
        @return: None
        """
        self.current_us = int(us)
        if self.pwm:
            self.pwm.duty_u16(us_to_duty(self.current_us))

    def move(self, target_us: int, step: int = 20, delay_ms: int = 6):
        """
        Smoothly moves servo from current position to target position.
        Automatically enables PWM, moves in steps, then updates position.
        
        @param target_us: Target pulse width in microseconds
        @param step: Step size in microseconds per iteration (default: 20)
        @param delay_ms: Delay between steps in milliseconds (default: 6)
        @return: None
        """
        self.enable()
        target_us = int(target_us)
        cur = int(self.current_us)

        if cur == target_us:
            return

        direction = 1 if target_us > cur else -1
        step = abs(step) * direction

        while cur != target_us:
            cur += step
            if (direction == 1 and cur > target_us) or (direction == -1 and cur < target_us):
                cur = target_us
            self.write(cur)
            time.sleep_ms(delay_ms)

    def release(self):
        """
        Releases PWM resources by deinitializing the PWM object.
        Servo will no longer receive control signals.
        
        @return: None
        """
        if self.pwm:
            try:
                self.pwm.deinit()
            except:
                pass
            self.pwm = None

# ======================================================
# Eyelids calibration
# ======================================================
SERVOS = {
    "TL": {"pin": 12, "open": 2200, "closed": 1155},
    "BL": {"pin": 9,  "open": 1560, "closed": 2360},
    "TR": {"pin": 7,  "open": 700,  "closed": 1700},
    "BR": {"pin": 15, "open": 1920, "closed": 1040},
}

LEFT_EYE  = ("TL", "BL")
RIGHT_EYE = ("TR", "BR")
ALL_LIDS  = ("TL", "TR", "BL", "BR")

eyelids = {k: ServoLazy(v["pin"], v["open"]) for k, v in SERVOS.items()}

# ======================================================
# Look servos calibration
# ======================================================
UD_LIMITS = {"down": 1260, "up": 1560}
LR_LIMITS = {"left": 820, "right": 1920}

UD_MID = 1410
LR_MID = 1370

UD = ServoLazy(11, UD_MID)
LR = ServoLazy(5, LR_MID)

# ======================================================
# Movement helpers
# ======================================================
def enable_all_lids():
    """
    Enables PWM for all eyelid servos with staggered timing to reduce power surge.
    
    @return: None
    """
    for k in ALL_LIDS:
        eyelids[k].enable()
        time.sleep_ms(50)

def release_all():
    """
    Releases PWM resources for all servos (eyelids, up/down, left/right).
    Stops all servo control signals to conserve power.
    
    @return: None
    """
    for s in eyelids.values():
        s.release()
    UD.release()
    LR.release()

def move_group(names, state: str):
    """
    Synchronously moves a group of eyelid servos to the specified state.
    All servos in the group move together in synchronized steps.
    
    @param names: Tuple or list of servo names (e.g., LEFT_EYE, RIGHT_EYE, ALL_LIDS)
    @param state: Target state string ("open" or "closed")
    @return: None
    """
    enable_all_lids()
    cur = {n: eyelids[n].current_us for n in names}
    tgt = {n: SERVOS[n][state] for n in names}

    while True:
        done = True
        for n in names:
            c = cur[n]
            t = tgt[n]
            if c == t:
                continue
            done = False
            d = 1 if t > c else -1
            nxt = c + d * 20
            if (d == 1 and nxt > t) or (d == -1 and nxt < t):
                nxt = t
            cur[n] = nxt
            eyelids[n].write(nxt)
        if done:
            break
        time.sleep_ms(6)

def lids_open():
    """
    Opens all eyelids to the open position and releases PWM resources.
    
    @return: None
    """
    move_group(ALL_LIDS, "open")
    release_all()

def lids_close():
    """
    Closes all eyelids to the closed position and releases PWM resources.
    
    @return: None
    """
    move_group(ALL_LIDS, "closed")
    release_all()

def blink():
    """
    Performs a complete blink animation: close all lids, wait, then open.
    
    @return: None
    """
    lids_close()
    time.sleep_ms(90)
    lids_open()

def wink_left():
    """
    Performs a left eye wink: close left eye lids, wait, then open.
    
    @return: None
    """
    move_group(LEFT_EYE, "closed")
    time.sleep_ms(110)
    move_group(LEFT_EYE, "open")
    release_all()

def wink_right():
    """
    Performs a right eye wink: close right eye lids, wait, then open.
    
    @return: None
    """
    move_group(RIGHT_EYE, "closed")
    time.sleep_ms(110)
    move_group(RIGHT_EYE, "open")
    release_all()

def look_up():
    """
    Moves eyes to look up position and releases PWM resources.
    
    @return: None
    """
    UD.move(UD_LIMITS["up"])
    UD.release()

def look_down():
    """
    Moves eyes to look down position and releases PWM resources.
    
    @return: None
    """
    UD.move(UD_LIMITS["down"])
    UD.release()

def center_ud():
    """
    Centers the up/down eye position to neutral and releases PWM resources.
    
    @return: None
    """
    UD.move(UD_MID)
    UD.release()

def look_left():
    """
    Moves eyes to look left (centers first, then moves to left limit).
    
    @return: None
    """
    LR.move(LR_MID)
    time.sleep_ms(120)
    LR.move(LR_LIMITS["left"])
    LR.release()

def look_right():
    """
    Moves eyes to look right (centers first, then moves to right limit).
    
    @return: None
    """
    LR.move(LR_MID)
    time.sleep_ms(120)
    LR.move(LR_LIMITS["right"])
    LR.release()

# ======================================================
# Web UI (Wall-E)
# ======================================================
def homepage():
    """
    Returns HTML content for the Wall-E control panel web interface.
    
    @return: HTML string containing the control panel page
    """
    return """<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wall-E Control Panel</title>
<style>
body{
  background:#f4c542;
  font-family:Arial,sans-serif;
  color:#4a321d;
}
button{
  width:100%;
  padding:12px;
  margin:6px 0;
  font-size:16px;
  border-radius:12px;
}
</style>
</head>
<body>
<h2>Wall-E Control Panel</h2>
<button onclick="cmd('/open')">Open</button>
<button onclick="cmd('/close')">Close</button>
<button onclick="cmd('/blink')">Blink</button>
<button onclick="cmd('/wink_left')">Wink Left</button>
<button onclick="cmd('/wink_right')">Wink Right</button>
<button onclick="cmd('/look_up')">Look Up</button>
<button onclick="cmd('/look_down')">Look Down</button>
<button onclick="cmd('/look_left')">Look Left</button>
<button onclick="cmd('/look_right')">Look Right</button>
<button onclick="cmd('/center_ud')">Center Up/Down</button>
<button onclick="cmd('/release')">Release</button>

<pre id="out">Ready.</pre>

<script>
function cmd(p){
  fetch(p,{method:'POST'})
    .then(r=>r.text())
    .then(t=>out.textContent=p+"\\n"+t)
}
</script>
</body>
</html>"""

# ======================================================
# HTTP server
# ======================================================
def reply(c, body, ctype="text/plain", code="200 OK"):
    """
    Sends an HTTP response to a client socket connection.
    
    @param c: Client socket object
    @param body: Response body content (string)
    @param ctype: Content-Type header value (default: "text/plain")
    @param code: HTTP status code and message (default: "200 OK")
    @return: None
    """
    c.send(
        "HTTP/1.1 " + code + "\r\n"
        "Content-Type: " + ctype + "\r\n"
        "Connection: close\r\n\r\n" + body
    )

def server(ip):
    """
    Starts HTTP server on port 80 and handles incoming requests.
    Routes requests to appropriate face control functions.
    Runs indefinitely until program termination.
    
    @param ip: IP address to bind the server socket to
    @return: None (runs indefinitely)
    """
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((ip, 80))
    s.listen(1)
    print("Server ready on http://%s/" % ip)

    while True:
        c, _ = s.accept()
        req = c.recv(1024).decode()
        path = req.split(" ")[1]

        if path == "/": reply(c, homepage(), "text/html")
        elif path == "/ping": reply(c, "pong")
        elif path == "/open": lids_open(); reply(c,"open")
        elif path == "/close": lids_close(); reply(c,"close")
        elif path == "/blink": blink(); reply(c,"blink")
        elif path == "/wink_left": wink_left(); reply(c,"wink_left")
        elif path == "/wink_right": wink_right(); reply(c,"wink_right")
        elif path == "/look_up": look_up(); reply(c,"look_up")
        elif path == "/look_down": look_down(); reply(c,"look_down")
        elif path == "/look_left": look_left(); reply(c,"look_left")
        elif path == "/look_right": look_right(); reply(c,"look_right")
        elif path == "/center_ud": center_ud(); reply(c,"center_ud")
        elif path == "/release": release_all(); reply(c,"released")
        else: reply(c,"404",code="404 Not Found")

        c.close()

# ======================================================
# Main
# ======================================================
print("Boot OK. No servo movement.")
ip = connect_wifi()
server(ip)
