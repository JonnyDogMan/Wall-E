#!/usr/bin/env python3
"""
Wall-E AI Assistant (PC) + Reliable Face + Hard Error Trapping

Fixes included:
- Blink spam fix: blink only when NOT LISTENING and NOT SPEAKING
- Blink thread safety: stop old thread before starting new one
- Mic fix: never uses device -1; prefers default input, then preferred index
- Silence watchdog: if mic captures nothing 3 times, re-pick device and warn

Face endpoints used (NO LR):
/ping /open /close /blink /wink_left /wink_right /look_up /look_down /center_ud /release
"""

import os, sys, re, time, json, tempfile, threading, subprocess, random, traceback
from typing import List, Dict, Tuple, Optional

import numpy as np
import sounddevice as sd
import soundfile as sf
import requests

# ================= CONFIG =================

DEFAULT_VOSK_PATH = r"C:\Users\SkillsHub-Learner-12\Documents\AI_Robot\vosk-model-en-us-0.22"
PREFERRED_INPUT_INDEX = 8  # RØDE NT-USB Mini

PYTHON_EXE = r"C:\Users\SkillsHub-Learner-12\AppData\Local\Programs\Python\Python312\python.exe"
PIPER_MODEL_PRIMARY = r"C:\Users\SkillsHub-Learner-12\Documents\AI_Robot\voices\en_US-amy-medium.onnx"
PIPER_MODEL_FALLBACK = r""

OLLAMA_BASE = "http://127.0.0.1:11434"
OLLAMA_MODEL = "llama3.1"

PICO_BASE = "http://172.20.10.5"
PICO_ENABLED = True

BLINK_MIN_S = 5.0
BLINK_MAX_S = 10.0

ENGLISH_GAP_MS = 3000
MAX_SEGMENT_MS = 15000

SYSTEM_PROMPT = (
    "You are Wall-E, a friendly and capable AI assistant built to help Jonny. "
    "Speak clearly and concisely, one to three short sentences, no filler."
)

ERROR_LOG = os.path.join(os.path.dirname(__file__), "walle_errors.log")

# Events
SPEAKING = threading.Event()
LISTENING = threading.Event()

# ================= LOGGING =================

def log_err(tag: str, exc: BaseException) -> None:
    """
    Logs an error with timestamp and traceback to both file and console.
    
    @param tag: A string identifier/tag for the error context (e.g., "Record", "TTS")
    @param exc: The exception object to log
    @return: None
    """
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    msg = f"[{ts}] {tag}: {repr(exc)}\n{traceback.format_exc()}\n"
    try:
        with open(ERROR_LOG, "a", encoding="utf-8") as f:
            f.write(msg)
    except Exception:
        pass
    print(f"[ERR] {tag}: {exc}")

# ================= FACE CONTROL (NO LR) =================

BLINK_STOP = threading.Event()
BLINK_THREAD: Optional[threading.Thread] = None

def pico_request(method: str, endpoint: str, timeout: float = 1.2) -> Optional[str]:
    """
    Sends an HTTP request to the Pico face control endpoint.
    
    @param method: HTTP method ("GET" or "POST")
    @param endpoint: The API endpoint path (e.g., "/ping", "/open")
    @param timeout: Request timeout in seconds (default: 1.2)
    @return: Response text if successful, None otherwise
    """
    if not PICO_ENABLED:
        return None
    url = PICO_BASE + endpoint
    try:
        if method == "GET":
            r = requests.get(url, timeout=timeout)
        else:
            r = requests.post(url, timeout=timeout)
        return r.text
    except Exception:
        return None

def pico_ok() -> bool:
    """
    Checks if the Pico face controller is reachable and responding.
    
    @return: True if Pico responds with "pong", False otherwise
    """
    t = pico_request("GET", "/ping", timeout=1.2)
    return (t or "").strip().lower() == "pong"

def pico_post_reliable(endpoint: str, tries: int = 6, delay_s: float = 0.20) -> bool:
    """
    Sends a POST request to Pico with retry logic for reliability.
    
    @param endpoint: The API endpoint path to POST to
    @param tries: Number of retry attempts (default: 6)
    @param delay_s: Delay between retries in seconds (default: 0.20)
    @return: True if request succeeds within retries, False otherwise
    """
    for _ in range(tries):
        t = pico_request("POST", endpoint, timeout=1.2)
        if t is not None:
            return True
        time.sleep(delay_s)
    return False

def pico_wait_ready(max_wait_s: float = 6.0) -> bool:
    """
    Waits for the Pico controller to become ready, polling until it responds.
    
    @param max_wait_s: Maximum time to wait in seconds (default: 6.0)
    @return: True if Pico becomes ready within timeout, False otherwise
    """
    t0 = time.time()
    while (time.time() - t0) < max_wait_s:
        if pico_ok():
            return True
        time.sleep(0.25)
    return False

def eyes_open() -> bool:
    """
    Opens the robot's eyes.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/open")

def eyes_close() -> bool:
    """
    Closes the robot's eyes.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/close")

def eyes_blink() -> bool:
    """
    Performs a single blink animation.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/blink")

def wink_left() -> bool:
    """
    Performs a left eye wink animation.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/wink_left")

def wink_right() -> bool:
    """
    Performs a right eye wink animation.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/wink_right")

def look_up() -> bool:
    """
    Moves the eyes to look upward.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/look_up")

def look_down() -> bool:
    """
    Moves the eyes to look downward.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/look_down")

def center_ud() -> bool:
    """
    Centers the eyes vertically (neutral up/down position).
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/center_ud")

def eyes_release() -> bool:
    """
    Releases/resets the eye servos to their default state.
    
    @return: True if command succeeded, False otherwise
    """
    return pico_post_reliable("/release")

def stop_blinking() -> None:
    """
    Stops the automatic blinking thread safely.
    
    @return: None
    """
    BLINK_STOP.set()
    global BLINK_THREAD
    if BLINK_THREAD and BLINK_THREAD.is_alive():
        BLINK_THREAD.join(timeout=1.0)
    BLINK_THREAD = None

def blink_loop() -> None:
    """
    Main loop for automatic blinking. Blinks at random intervals when not listening or speaking.
    
    @return: None
    """
    while not BLINK_STOP.is_set():
        wait_s = random.uniform(BLINK_MIN_S, BLINK_MAX_S)
        t0 = time.time()
        while (time.time() - t0) < wait_s:
            if BLINK_STOP.is_set():
                return
            time.sleep(0.1)

        # Key rule: do not blink while listening or speaking
        if (not SPEAKING.is_set()) and (not LISTENING.is_set()):
            eyes_blink()

def start_blinking() -> None:
    """
    Starts the automatic blinking thread. Stops any existing blink thread first.
    
    @return: None
    """
    global BLINK_THREAD
    stop_blinking()          # prevent multiple blink threads
    BLINK_STOP.clear()
    BLINK_THREAD = threading.Thread(target=blink_loop, daemon=True)
    BLINK_THREAD.start()

def face_neutral() -> None:
    """
    Sets the face to a neutral expression (centers up/down gaze).
    
    @return: None
    """
    center_ud()

def face_thinking_small() -> None:
    """
    Animates a "thinking" expression with random up/down gaze movements and occasional winks.
    
    @return: None
    """
    # No LR. Small random up/down and occasional wink.
    if random.random() < 0.50:
        (look_up if random.random() < 0.5 else look_down)()
    if random.random() < 0.18:
        (wink_left if random.random() < 0.5 else wink_right)()
    center_ud()

# ================= AUDIO HELPERS =================

def prefer_wasapi() -> None:
    """
    Sets the default audio host API to WASAPI (Windows Audio Session API) if available.
    
    @return: None
    """
    try:
        apis = sd.query_hostapis()
        for idx, api in enumerate(apis):
            if "WASAPI" in (api.get("name", "") or "").upper():
                sd.default.hostapi = idx
                break
    except Exception:
        pass

prefer_wasapi()

class LiveLine:
    """
    Utility class for live-updating console output (used for real-time transcription display).
    
    Uses ANSI escape codes to overwrite the current line in the terminal.
    """
    CSI = "\x1b["

    def __init__(self, prefix: str = "You: ") -> None:
        """
        Initializes a LiveLine instance with a prefix string.
        
        @param prefix: Text to prepend to each line (default: "You: ")
        """
        self.prefix = prefix
        self.buf = ""

    def clear(self) -> None:
        """
        Clears the current terminal line.
        
        @return: None
        """
        sys.stdout.write(self.CSI + "2K\r")
        sys.stdout.flush()

    def print(self, text: str) -> None:
        """
        Updates the current line with new text, overwriting previous content.
        
        @param text: The text to display
        @return: None
        """
        self.buf = text
        self.clear()
        sys.stdout.write(f"{self.prefix}{text}")
        sys.stdout.flush()

    def finalize(self, final: str) -> None:
        """
        Finalizes the line by clearing and printing the final text on a new line.
        
        @param final: The final text to print
        @return: None
        """
        self.clear()
        print(f"{self.prefix}{final}")

def model_config_exists(onnx_path: str) -> bool:
    """
    Checks if a JSON configuration file exists for the given ONNX model path.
    
    @param onnx_path: Path to the ONNX model file
    @return: True if a corresponding JSON config file exists, False otherwise
    """
    if not onnx_path:
        return False
    a = onnx_path + ".json"
    b = os.path.splitext(onnx_path)[0] + ".json"
    return os.path.isfile(a) or os.path.isfile(b)

def speak_text_blocking(text: str) -> None:
    """
    Converts text to speech using Piper TTS and plays it synchronously.
    
    Uses primary model first, falls back to fallback model if available.
    Sets SPEAKING event flag during playback.
    
    @param text: The text to synthesize and speak
    @return: None
    """
    text = (text or "").strip()
    if not text:
        return

    SPEAKING.set()
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            out_wav = tmp.name

        ok = False
        try:
            if os.path.isfile(PIPER_MODEL_PRIMARY) and model_config_exists(PIPER_MODEL_PRIMARY):
                subprocess.run(
                    [PYTHON_EXE, "-m", "piper", "-m", PIPER_MODEL_PRIMARY, "-f", out_wav],
                    input=text.encode("utf-8"),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True,
                )
                ok = True
        except Exception as e:
            log_err("TTS primary", e)
            ok = False

        if (not ok) and PIPER_MODEL_FALLBACK:
            try:
                if os.path.isfile(PIPER_MODEL_FALLBACK) and model_config_exists(PIPER_MODEL_FALLBACK):
                    subprocess.run(
                        [PYTHON_EXE, "-m", "piper", "-m", PIPER_MODEL_FALLBACK, "-f", out_wav],
                        input=text.encode("utf-8"),
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        check=True,
                    )
                    ok = True
            except Exception as e:
                log_err("TTS fallback", e)
                ok = False

        if not ok:
            return

        data, sr = sf.read(out_wav, dtype="float32")
        try:
            sd.stop()
        except Exception:
            pass
        sd.play(data, sr)
        sd.wait()
    finally:
        SPEAKING.clear()

# ================= WHISPER =================

def load_whisper():
    """
    Loads a Whisper speech recognition model (prefers faster-whisper, falls back to openai-whisper).
    
    @return: A transcription function that takes a WAV file path and returns transcribed text
    """
    try:
        from faster_whisper import WhisperModel
        model = WhisperModel("small", device="auto", compute_type="auto")

        def tx(path: str) -> str:
            segs, _ = model.transcribe(path, beam_size=1, vad_filter=True)
            return "".join(s.text for s in segs).strip()

        return tx
    except Exception:
        import whisper
        w = whisper.load_model("small")

        def tx(path: str) -> str:
            res = w.transcribe(path, fp16=False)
            return (res.get("text") or "").strip()

        return tx

# ================= OLLAMA =================

def ollama_healthy() -> bool:
    """
    Checks if the Ollama LLM service is running and accessible.
    
    @return: True if Ollama responds successfully, False otherwise
    """
    try:
        return requests.get(f"{OLLAMA_BASE}/api/version", timeout=3).ok
    except Exception:
        return False

def ollama_chat_once(messages: List[Dict]) -> str:
    """
    Sends a chat request to Ollama and returns the assistant's response.
    
    @param messages: List of message dictionaries with "role" and "content" keys
    @return: The assistant's reply text from Ollama
    """
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.6,
            "top_p": 0.85,
            "num_predict": 200,
            "repeat_penalty": 1.12,
        },
    }
    r = requests.post(f"{OLLAMA_BASE}/api/chat", json=payload, timeout=60)
    r.raise_for_status()
    return r.json().get("message", {}).get("content", "") or ""

# ================= MIC PICKER =================

def pick_input_device(preferred_index: int) -> int:
    """
    Selects a valid audio input device index, prioritizing default, then preferred, then first available.
    
    Always returns a real device index (never -1).
    Priority: 1) sounddevice default input (if valid), 2) preferred index (if valid), 3) first device with input channels
    
    @param preferred_index: The preferred microphone device index
    @return: A valid input device index
    @raises RuntimeError: If no input devices are found
    """
    devs = sd.query_devices()

    def ok(idx: int) -> bool:
        return 0 <= idx < len(devs) and devs[idx].get("max_input_channels", 0) > 0

    try:
        d = sd.default.device
        default_in = d[0] if isinstance(d, (list, tuple)) else d
    except Exception:
        default_in = None

    if isinstance(default_in, int) and ok(default_in):
        return default_in

    if ok(preferred_index):
        return preferred_index

    for i in range(len(devs)):
        if ok(i):
            return i

    raise RuntimeError("No input microphone devices found.")

# ================= VOSK + RECORD =================

def load_vosk_model(path: str):
    """
    Loads a Vosk speech recognition model from the specified directory.
    
    @param path: Path to the Vosk model directory
    @return: A Vosk Model instance
    @raises RuntimeError: If the model directory does not exist
    """
    from vosk import Model
    if not os.path.isdir(path):
        raise RuntimeError(f"Vosk model missing at: {path}")
    return Model(path)

def record_utterance(vosk_model, input_device: int) -> Tuple[str, str]:
    """
    Records audio from the microphone and performs real-time speech recognition using Vosk.
    
    Records until silence is detected or maximum segment time is reached.
    Sets LISTENING event flag during recording.
    
    @param vosk_model: The loaded Vosk Model instance
    @param input_device: The audio input device index to use
    @return: A tuple containing (WAV file path, rough transcription text)
    """
    from vosk import KaldiRecognizer

    LISTENING.set()
    try:
        # Safety: never query -1
        if input_device == -1:
            input_device = pick_input_device(PREFERRED_INPUT_INDEX)

        info = sd.query_devices(input_device, "input")
        sr = int(info["default_samplerate"])

        rec = KaldiRecognizer(vosk_model, sr)
        rec.SetWords(True)

        chunks: List[np.ndarray] = []
        live = LiveLine()
        last_eng = time.time()

        def cb(indata, frames, t, status):
            nonlocal last_eng
            if SPEAKING.is_set():
                return

            x = indata[:, 0].astype(np.float32)
            chunks.append(x)

            pcm = (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()

            if rec.AcceptWaveform(pcm):
                tx = json.loads(rec.Result()).get("text", "")
                if tx:
                    live.print(tx)
                    last_eng = time.time()
            else:
                part = json.loads(rec.PartialResult() or "{}").get("partial", "")
                if part:
                    live.print(part)
                    if re.search(r"[A-Za-z]", part):
                        last_eng = time.time()

        print("\n------------------------------------------")
        print("Listening (auto-stop after silence)")

        start = time.time()
        with sd.InputStream(
            device=input_device,
            channels=1,
            samplerate=sr,
            dtype="float32",
            blocksize=int(sr * 0.01),
            callback=cb
        ):
            while True:
                time.sleep(0.1)
                if (time.time() - last_eng) * 1000 >= ENGLISH_GAP_MS:
                    break
                if (time.time() - start) * 1000 >= MAX_SEGMENT_MS:
                    break

        live.finalize(live.buf)

        audio = np.concatenate(chunks, axis=0) if chunks else np.zeros(0, dtype=np.float32)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp.close()
        sf.write(tmp.name, audio.reshape(-1, 1), sr)
        return tmp.name, live.buf
    finally:
        LISTENING.clear()

# ================= TIDY =================

def tidy_reply(text: str) -> str:
    """
    Cleans and formats assistant replies by normalizing whitespace, limiting sentences, and truncating if needed.
    
    Limits to first 3 sentences, truncates to ~380 chars if longer, adds prompt if response is short.
    
    @param text: The raw reply text to process
    @return: Formatted and cleaned reply text
    """
    text = re.sub(r"\s+", " ", (text or "")).strip()
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s.strip() for s in sents if s.strip()][:3]
    out = " ".join(sents)
    if len(out) > 400:
        out = out[:380].rsplit(" ", 1)[0] + "..."
    if "?" not in out and len(out) < 200:
        out += " Anything else?"
    return out

# ================= SUPERVISOR =================

def cleanup_face():
    """
    Performs cleanup of face control resources (stops blinking, closes eyes, releases servos).
    
    @return: None
    """
    try:
        stop_blinking()
    except Exception:
        pass
    if PICO_ENABLED:
        try:
            eyes_close()
            eyes_release()
        except Exception:
            pass

def run_once():
    """
    Main execution loop for a single Wall-E session.
    
    Initializes models, waits for Pico, then enters conversation loop:
    records speech -> transcribes -> gets LLM response -> speaks reply.
    Handles microphone silence detection and device re-selection.
    
    @return: None
    @raises RuntimeError: If Ollama is not responding
    """
    pico_ready = False
    if PICO_ENABLED:
        pico_ready = pico_wait_ready(max_wait_s=6.0)
        if pico_ready:
            eyes_close()
        else:
            print("[WARN] Pico not reachable. Face actions disabled for this run.")

    print("[INFO] Initializing Wall-E...")

    if not ollama_healthy():
        raise RuntimeError("Ollama not responding. Run: ollama serve")

    vosk_model = load_vosk_model(DEFAULT_VOSK_PATH)
    whisper_tx = load_whisper()

    input_device = pick_input_device(PREFERRED_INPUT_INDEX)
    try:
        mic_name = sd.query_devices(input_device)["name"]
    except Exception:
        mic_name = "unknown"
    print(f"[MIC] Using input device {input_device}: {mic_name}")

    print("[OK ] Wall-E is ready and listening.")

    if PICO_ENABLED and pico_ready:
        if not eyes_open():
            print("[WARN] Failed to open eyes (network). Retrying...")
            eyes_open()
        center_ud()
        start_blinking()

    messages: List[Dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    silent_runs = 0

    while True:
        try:
            while SPEAKING.is_set():
                time.sleep(0.05)
            wav_path, rough = record_utterance(vosk_model, input_device)
        except KeyboardInterrupt:
            raise
        except Exception as e:
            log_err("Record", e)
            time.sleep(0.5)
            continue

        if not (rough or "").strip():
            silent_runs += 1
            if silent_runs >= 3:
                print("[WARN] Mic captured no speech 3 times. Re-selecting input device.")
                try:
                    input_device = pick_input_device(PREFERRED_INPUT_INDEX)
                    mic_name = sd.query_devices(input_device)["name"]
                    print(f"[MIC] Now using input device {input_device}: {mic_name}")
                except Exception as e:
                    log_err("Mic re-pick", e)
                silent_runs = 0
            continue

        silent_runs = 0

        try:
            final_text = whisper_tx(wav_path).strip() or rough.strip()
        except Exception as e:
            log_err("Whisper", e)
            final_text = rough.strip()

        print(f"You: {final_text}")
        messages.append({"role": "user", "content": final_text})

        if PICO_ENABLED and pico_ready:
            try:
                face_thinking_small()
            except Exception as e:
                log_err("Face thinking", e)

        try:
            raw = ollama_chat_once(messages)
        except Exception as e:
            log_err("Ollama", e)
            raw = "Sorry, I had a brain glitch. Try again."

        reply = tidy_reply(raw)
        print(f"Wall-E: {reply}")
        messages.append({"role": "assistant", "content": reply})

        if PICO_ENABLED and pico_ready:
            try:
                face_neutral()
            except Exception as e:
                log_err("Face neutral", e)

        try:
            speak_text_blocking(reply)
        except Exception as e:
            log_err("TTS", e)

def main():
    """
    Main entry point with supervisor loop that restarts run_once() on crashes.
    
    Implements exponential backoff for error recovery, with cleanup on shutdown.
    
    @return: None
    """
    restart_count = 0
    backoff = 0.6

    try:
        while True:
            try:
                run_once()
            except KeyboardInterrupt:
                print("\nShutting down Wall-E.")
                return
            except Exception as e:
                restart_count += 1
                log_err("Supervisor crash", e)
                cleanup_face()
                time.sleep(backoff)
                backoff = min(5.0, backoff * 1.6)
                if restart_count % 5 == 0:
                    backoff = 0.8
    finally:
        cleanup_face()

if __name__ == "__main__":
    main()
