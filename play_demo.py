"""
play_demo.py — FSR-triggered 3-phase sitting demo.

Phase 1 (t = 0s)  Sitting detected
  · Soft fart sound
  · Light haptic buzz

Phase 2 (t = 5s)  Still sitting
  · Voice: "您还坐着呢" (Beijing)
  · Robot arm: move to ready position (蓄力)

Phase 3 (t = 10s) Still sitting
  · Music: random from playlist
  · Haptic: long vibration
  · Robot arm: head hammer × 3
  · Voice: random "stand up" (Shanghai / Beijing), 2 s after music starts

Reset: person stands up → cancel pending timers, reset state.
"""

import asyncio
import glob
import random
import serial
import subprocess
import sys
import threading
import time

from robot_arm_control import RobotArmController
from motor_ble import MotorController

# ── Hardware ───────────────────────────────────────────────────────────────────
PORT = "/dev/ttyACM0"
BAUD = 9600

# ── Robot arm ─────────────────────────────────────────────────────────────────
ARM_HOST    = "192.168.1.1"
ARM_PORT    = 80
ARM_SESSION = "JfLiwMiyU6zz802mJi48Ylw1N7MfGV1n4t8lEfa0XignprdBtBNK4KIgM4PG449tCx90icNy8dzppew0f9AFxquIq80hSFdD0bylfK400XC80NmdYoOnONbugA0QwSH"
ARM_READY   = {"x": "103", "y": "116", "z": "37", "b": "33", "e": "55"}
ARM_SPEED   = 200

# ── Media ─────────────────────────────────────────────────────────────────────
MEDIA       = "/home/yifzhou/Arduino/media"
FART_SOUNDS = "/home/yifzhou/Arduino/media/fart_sound"
SOUNDS_FART_SHORT = [
    f"{FART_SOUNDS}/fart_quick.mp3",
    f"{FART_SOUNDS}/fart_wet.mp3",
]
VOICE_SITTING    = f"{MEDIA}/audio/您还坐着呢.m4a"
MUSIC_PLAYLIST   = glob.glob(f"{FART_SOUNDS}/放屁_*.mp3")
VOICES_STANDUP   = [
    f"{MEDIA}/audio/上海话你站起来.m4a",
    f"{MEDIA}/audio/北京话站起来走.m4a",
]

# ── FSR ───────────────────────────────────────────────────────────────────────
NUM_SENSORS   = 5
FSR_THRESHOLD = 600
PHASE2_DELAY  = 5.0    # seconds after sitting
PHASE3_DELAY  = 10.0   # seconds after sitting

# ── Globals ───────────────────────────────────────────────────────────────────
arm    = RobotArmController(host=ARM_HOST, port=ARM_PORT, session_id=ARM_SESSION)
_motor = MotorController()
_motor_loop = asyncio.new_event_loop()
threading.Thread(target=_motor_loop.run_forever, daemon=True).start()

_phase2_timer: threading.Timer | None = None
_phase3_timer: threading.Timer | None = None
_arm_ready    = False   # set True after phase-2 arm init succeeds
_is_hammering = False
_hammer_lock  = threading.Lock()
_stop_flag    = False   # set True on stood-up to abort ongoing actions

_active_procs: list[subprocess.Popen] = []
_procs_lock   = threading.Lock()


# ── Helpers: sound ─────────────────────────────────────────────────────────────

def _ffplay(path, timeout=60):
    """Run ffplay, register process so it can be killed on stood-up."""
    proc = subprocess.Popen(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    with _procs_lock:
        _active_procs.append(proc)
    try:
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.terminate()
    finally:
        with _procs_lock:
            _active_procs.discard(proc) if hasattr(_active_procs, "discard") else None
            if proc in _active_procs:
                _active_procs.remove(proc)


def play_async(path):
    threading.Thread(target=_ffplay, args=(path,), daemon=True).start()


def stop_all_audio():
    with _procs_lock:
        for proc in list(_active_procs):
            proc.terminate()
        _active_procs.clear()


# ── Helpers: motor ─────────────────────────────────────────────────────────────

def _motor_call(coro):
    """Schedule a motor coroutine and return (ignores result)."""
    asyncio.run_coroutine_threadsafe(coro, _motor_loop)


def vibrate_short():
    """Light single buzz (default ONF_CYC = 3)."""
    _motor_call(_motor.trigger())


def vibrate_long():
    """Long continuous vibration (ONF_CYC = 20 → ~6 s)."""
    _motor_call(_motor.trigger(cycles=20))


# ── Helpers: arm ──────────────────────────────────────────────────────────────

def _arm_goto_ready():
    global _arm_ready
    try:
        arm.move_xyz(
            x=ARM_READY["x"], y=ARM_READY["y"], z=ARM_READY["z"],
            b=ARM_READY["b"], e=ARM_READY["e"],
            speed=ARM_SPEED, delay_ms=0,
        )
        time.sleep(0.3)
        _arm_ready = True
        print("[arm] Ready.")
    except Exception as e:
        print(f"[arm] Move to ready failed: {e}")


def hammer_async():
    global _is_hammering
    if _is_hammering:
        print("[arm] Already hammering, skipping.")
        return

    def _run():
        global _is_hammering
        with _hammer_lock:
            _is_hammering = True
            try:
                for i in range(3):
                    if _stop_flag:
                        print("[arm] Hammer aborted.")
                        break
                    arm.head_hammer(
                        repeats=1, speed=ARM_SPEED,
                        from_ready=(_arm_ready and i == 0),
                    )
                else:
                    print("[arm] Hammer complete.")
            except Exception as e:
                print(f"[arm] Hammer failed: {e}")
            finally:
                _is_hammering = False

    threading.Thread(target=_run, daemon=True).start()


# ── Demo phases ────────────────────────────────────────────────────────────────

def _phase1():
    """Sitting detected — immediate response."""
    print("\n[PHASE 1] Sitting detected")
    play_async(random.choice(SOUNDS_FART_SHORT))
    vibrate_short()


def _phase2():
    """5 s elapsed — still sitting."""
    print("\n[PHASE 2] 5 s — still sitting")
    play_async(VOICE_SITTING)
    threading.Thread(target=_arm_goto_ready, daemon=True).start()


def _phase3():
    """10 s elapsed — escalate."""
    print("\n[PHASE 3] 10 s — escalating")

    voice = random.choice(VOICES_STANDUP)
    music = random.choice(MUSIC_PLAYLIST)

    def _sequence():
        _ffplay(voice, timeout=15)          # 1. Voice first
        if not _stop_flag:
            _ffplay(music, timeout=60)      # 2. Music after voice, if not stopped

    threading.Thread(target=_sequence, daemon=True).start()
    vibrate_long()
    hammer_async()


# ── State machine ──────────────────────────────────────────────────────────────

def _cancel_timers():
    global _phase2_timer, _phase3_timer
    for t in (_phase2_timer, _phase3_timer):
        if t is not None:
            t.cancel()
    _phase2_timer = None
    _phase3_timer = None


def on_sitting():
    global _phase2_timer, _phase3_timer, _arm_ready, _stop_flag
    _stop_flag = False
    _arm_ready = False
    _cancel_timers()
    _phase1()
    _phase2_timer = threading.Timer(PHASE2_DELAY, _phase2)
    _phase3_timer = threading.Timer(PHASE3_DELAY, _phase3)
    _phase2_timer.start()
    _phase3_timer.start()


def on_stood_up():
    global _stop_flag
    print("\n[RESET] Person stood up — stopping all actions.")
    _stop_flag = True
    _cancel_timers()
    stop_all_audio()


# ── FSR parsing ────────────────────────────────────────────────────────────────

def parse_fsr(line):
    values = {}
    try:
        parts = line.split()
        for i in range(1, NUM_SENSORS + 1):
            key = f"FSR{i}:"
            if key in parts:
                idx = parts.index(key)
                if idx + 1 < len(parts):
                    values[i] = int(parts[idx + 1])
        return values if len(values) == NUM_SENSORS else None
    except (ValueError, IndexError):
        return None


# ── Startup ────────────────────────────────────────────────────────────────────

def init_motor():
    print("[motor] Connecting via BLE...")
    try:
        future = asyncio.run_coroutine_threadsafe(_motor.connect(), _motor_loop)
        future.result(timeout=20)
    except Exception as e:
        print(f"[motor] INIT FAILED (continuing without motor): {e}")


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    # 1. Serial
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
        print(f"[serial] Opened {PORT} at {BAUD} baud.")
    except serial.SerialException as e:
        print(f"[serial] Could not open {PORT}: {e}")
        sys.exit(1)

    # 2. BLE motor (background, non-blocking for rest of startup)
    threading.Thread(target=init_motor, daemon=True).start()

    print("[demo] Ready — waiting for FSR trigger.\n")

    sitting = False

    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        reading = parse_fsr(line)
        if not reading:
            continue

        reading_str = "  |  ".join(f"S{i}: {reading[i]:4d}" for i in range(1, NUM_SENSORS + 1))
        print(f"[FSR] {reading_str}")

        max_val = max(reading.values())

        if max_val > FSR_THRESHOLD and not sitting:
            sitting = True
            on_sitting()

        elif max_val <= FSR_THRESHOLD and sitting:
            sitting = False
            on_stood_up()


if __name__ == "__main__":
    main()
