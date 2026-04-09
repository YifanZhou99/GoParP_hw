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
MEDIA = "/home/yifzhou/Arduino/media"
SOUND_FART       = f"{MEDIA}/parp_sound.mp3"
VOICE_SITTING    = f"{MEDIA}/您还坐着呢.m4a"
MUSIC_PLAYLIST   = [
    f"{MEDIA}/parp_sound_9s.mp3",
    f"{MEDIA}/parp_32s.mp3",
]
VOICES_STANDUP   = [
    f"{MEDIA}/上海话你站起来.m4a",
    f"{MEDIA}/北京话站起来走.m4a",
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


# ── Helpers: sound ─────────────────────────────────────────────────────────────

def play_async(path):
    def _play():
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
    threading.Thread(target=_play, daemon=True).start()


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
                arm.head_hammer(repeats=3, speed=ARM_SPEED, from_ready=_arm_ready)
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
    play_async(SOUND_FART)
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
        # 1. Voice first
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", voice],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15,
        )
        # 2. Music after voice finishes
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", music],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )

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
    global _phase2_timer, _phase3_timer, _arm_ready
    _arm_ready = False
    _cancel_timers()
    _phase1()
    _phase2_timer = threading.Timer(PHASE2_DELAY, _phase2)
    _phase3_timer = threading.Timer(PHASE3_DELAY, _phase3)
    _phase2_timer.start()
    _phase3_timer.start()


def on_stood_up():
    print("\n[RESET] Person stood up — cancelling pending phases.")
    _cancel_timers()


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
