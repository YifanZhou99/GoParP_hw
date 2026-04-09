import asyncio
import json
import serial
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from robot_arm_control import RobotArmController
from motor_ble import MotorController

# ── Hardware config ────────────────────────────────────────────────────────────
PORT = "/dev/ttyACM0"
BAUD = 9600

# ── Robot arm ─────────────────────────────────────────────────────────────────
ARM_HOST = "192.168.1.1"
ARM_PORT = 80
ARM_SESSION = "JfLiwMiyU6zz802mJi48Ylw1N7MfGV1n4t8lEfa0XignprdBtBNK4KIgM4PG449tCx90icNy8dzppew0f9AFxquIq80hSFdD0bylfK400XC80NmdYoOnONbugA0QwSH"
ARM_READY_POS = {"x": "103", "y": "116", "z": "37", "b": "33", "e": "55"}
ARM_SPEED = 200

# ── Sound ──────────────────────────────────────────────────────────────────────
SOUND_1 = "/home/yifzhou/Arduino/media/parp_sound.mp3"
SOUND_2 = "/home/yifzhou/Arduino/media/parp_sound_9s.mp3"

# ── FSR ───────────────────────────────────────────────────────────────────────
NUM_SENSORS = 5
SENSORS = [f"SENSOR{i+1}" for i in range(NUM_SENSORS)]
FSR_THRESHOLD = 600
HOLD_1 = 1.0   # seconds before ALERT1
HOLD_2 = 3.0   # seconds before ALERT2

# ── Event reporting ────────────────────────────────────────────────────────────
EVENT_REPORT_URL = "https://butt-agent-server-production.up.railway.app/events/report"
EVENT_REPORT_TIMEOUT_SECONDS = 2

# ── Globals ────────────────────────────────────────────────────────────────────
controller = RobotArmController(host=ARM_HOST, port=ARM_PORT, session_id=ARM_SESSION)
_hammer_lock = threading.Lock()
_is_hammering = False

# Motor BLE — persistent asyncio loop in daemon thread
_motor = MotorController()
_motor_loop = asyncio.new_event_loop()
threading.Thread(target=_motor_loop.run_forever, daemon=True).start()


# ── Event reporting ────────────────────────────────────────────────────────────

def _post_event_report(count=1):
    payload = {"userId": "cmnn6ovkf0000ma3w8zsp5mgz", "event": "fart", "count": count}
    request = urllib.request.Request(
        EVENT_REPORT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=EVENT_REPORT_TIMEOUT_SECONDS) as resp:
            print(f"[event-report] ok response={resp.read().decode('utf-8', errors='ignore')}")
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[event-report] failed: {e}")


def report_event_async(count=1):
    threading.Thread(target=_post_event_report, args=(count,), daemon=True).start()


# ── Sound ──────────────────────────────────────────────────────────────────────

def play_async(sound):
    def _play():
        subprocess.run(["mpg123", "-q", sound],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
    threading.Thread(target=_play, daemon=True).start()


# ── Robot arm ─────────────────────────────────────────────────────────────────

def arm_goto_ready(speed=150, delay_ms=0):
    """Move arm to ready (start) position and wait for it to arrive."""
    controller.move_xyz(
        x=ARM_READY_POS["x"], y=ARM_READY_POS["y"], z=ARM_READY_POS["z"],
        b=ARM_READY_POS["b"], e=ARM_READY_POS["e"],
        speed=speed, delay_ms=delay_ms,
    )
    time.sleep(delay_ms / 1000 + 0.1)


def init_arm():
    """Move arm to ready position at startup. Continues if unreachable."""
    print("[arm] Initializing — moving to ready position...")
    try:
        arm_goto_ready(speed=200, delay_ms=0)
        print("[arm] Ready.")
    except Exception as e:
        print(f"[arm] INIT FAILED (continuing without arm): {e}")


def init_motor():
    """Connect and configure BLE motor at startup. Continues if unreachable."""
    print("[motor] Initializing BLE connection...")
    try:
        future = asyncio.run_coroutine_threadsafe(_motor.connect(), _motor_loop)
        future.result(timeout=20)
    except Exception as e:
        print(f"[motor] INIT FAILED (continuing without motor): {e}")


def vibrate_async():
    """Trigger one vibration burst in the background (non-blocking)."""
    asyncio.run_coroutine_threadsafe(_motor.trigger(), _motor_loop)


def hammer_async():
    """Run head_hammer in background; skips if already running. Returns to ready after."""
    global _is_hammering

    if _is_hammering:
        print("[arm] Already hammering, skipping.")
        return

    def _run():
        global _is_hammering
        with _hammer_lock:
            _is_hammering = True
            try:
                controller.head_hammer(repeats=3, speed=ARM_SPEED, from_ready=True)
                print("[arm] Hammer complete.")
            except Exception as e:
                print(f"[arm] Hammer failed: {e}")
            finally:
                _is_hammering = False

    threading.Thread(target=_run, daemon=True).start()


# ── FSR parsing ────────────────────────────────────────────────────────────────

def parse_fsr_reading(line):
    fsr_values = {}
    try:
        parts = line.split()
        for i in range(1, NUM_SENSORS + 1):
            key = f"FSR{i}:"
            if key in parts:
                idx = parts.index(key)
                if idx + 1 < len(parts):
                    fsr_values[i] = int(parts[idx + 1])
        return fsr_values if len(fsr_values) == NUM_SENSORS else None
    except (ValueError, IndexError):
        return None


# ── Main loop ──────────────────────────────────────────────────────────────────

def main():
    # 1. Open serial port
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print(f"[serial] Opened {PORT} at {BAUD} baud.")
    except serial.SerialException as e:
        print(f"[serial] Could not open {PORT}: {e}")
        sys.exit(1)

    # 2. Initialize robot arm
    init_arm()

    # 3. Initialize vibration motor
    init_motor()

    # 4. Monitor FSR
    print("[fsr] Monitoring started.\n")

    above_threshold_since = None
    current_max_sensor = None
    alerted1 = False
    alerted2 = False

    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        fsr_reading = parse_fsr_reading(line)
        if not fsr_reading:
            continue

        reading_str = "  |  ".join([f"S{i}: {fsr_reading[i]:4d}" for i in range(1, NUM_SENSORS + 1)])
        print(f"[FSR] {reading_str}")

        max_reading = max(fsr_reading.values())
        max_sensor = max(range(1, NUM_SENSORS + 1), key=lambda i: fsr_reading[i])
        now = time.time()

        if max_reading > FSR_THRESHOLD:
            if above_threshold_since is None:
                above_threshold_since = now
                current_max_sensor = max_sensor
                alerted1 = False
                alerted2 = False

            current_max_sensor = max_sensor
            elapsed = now - above_threshold_since

            if elapsed >= HOLD_2 and not alerted2:
                print(f"  --> ALERT2 from {SENSORS[current_max_sensor - 1]}")
                hammer_async()
                play_async(SOUND_2)
                report_event_async()
                alerted2 = True

            elif elapsed >= HOLD_1 and not alerted1:
                print(f"  --> ALERT1 from {SENSORS[current_max_sensor - 1]}")
                play_async(SOUND_1)
                vibrate_async()
                threading.Thread(
                    target=controller.nod_and_shake,
                    kwargs={"repeats": 2, "speed": 150},
                    daemon=True,
                ).start()
                alerted1 = True

        else:
            if above_threshold_since is not None:
                above_threshold_since = None
                current_max_sensor = None
                alerted1 = False
                alerted2 = False


if __name__ == "__main__":
    main()
