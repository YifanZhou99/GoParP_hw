import json
import serial
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from robot_arm_control import RobotArmController

controller = RobotArmController(
        host="192.168.1.1",
        port=80,
        session_id="JfLiwMiyU6zz802mJi48Ylw1N7MfGV1n4t8lEfa0XignprdBtBNK4KIgM4PG449tCx90icNy8dzppew0f9AFxquIq80hSFdD0bylfK400XC80NmdYoOnONbugA0QwSH"
    )

PORT = "/dev/ttyACM0"
BAUD = 9600
SOUND_1 = "/home/yifzhou/Arduino/media/parp_sound.mp3"
SOUND_2 = "/home/yifzhou/Arduino/media/parp_sound.mp3"

NUM_SENSORS = 5
SENSORS = [f"SENSOR{i+1}" for i in range(NUM_SENSORS)]

FSR_THRESHOLD = 500
HOLD_1 = 1.0
HOLD_2 = 3.0

EVENT_REPORT_URL = "https://butt-agent-server-production.up.railway.app/events/report"
EVENT_REPORT_TIMEOUT_SECONDS = 2



#todo: 只需要在某个触发点加一行：report_event_async()
def _post_event_report(count=1):
    payload = {
        "userId": "cmnn6ovkf0000ma3w8zsp5mgz",
        "event": "fart",
        "count": count,
    }
    request = urllib.request.Request(
        EVENT_REPORT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=EVENT_REPORT_TIMEOUT_SECONDS) as response:
            response_text = response.read().decode("utf-8", errors="ignore")
            print(f"[event-report] ok payload={payload} response={response_text}")
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        print(f"[event-report] failed payload={payload} error={error}")


def report_event_async(count=1):
    threading.Thread(target=_post_event_report, args=(count,), daemon=True).start()


def play(sound):
    """Play sound file"""
    subprocess.run(["mpg123", "-q", sound],
                  stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL,
                  timeout=15)


def parse_fsr_reading(line):
    """Parse FSR reading line"""
    fsr_values = {}
    try:
        parts = line.split()
        for i in range(1, NUM_SENSORS + 1):
            fsr_key = f"FSR{i}:"
            if fsr_key in parts:
                idx = parts.index(fsr_key)
                if idx + 1 < len(parts):
                    fsr_values[i] = int(parts[idx + 1])

        return fsr_values if len(fsr_values) == NUM_SENSORS else None
    except (ValueError, IndexError):
        return None


def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"Could not open port {PORT}: {e}")
        sys.exit(1)

    print(f"Monitoring on {PORT}...")

    above_threshold_since = None
    current_max_sensor = None
    alerted1 = False
    alerted2 = False

    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue

        fsr_reading = parse_fsr_reading(line)
        if fsr_reading:
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
                    print(f"  --> ALERT2 from {SENSORS[current_max_sensor-1]}")
                    controller.head_hammer(repeats=1, speed=100)
                    print(f"  Head hammer complete!")
                    play(SOUND_2)
                    alerted2 = True

                elif elapsed >= HOLD_1 and not alerted1:
                    print(f"  --> ALERT1 from {SENSORS[current_max_sensor-1]}")
                    play(SOUND_1)
                    alerted1 = True
            else:
                if above_threshold_since is not None:
                    above_threshold_since = None
                    current_max_sensor = None
                    alerted1 = False
                    alerted2 = False


if __name__ == "__main__":
    main()
