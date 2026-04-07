import serial
import subprocess
import sys

PORT = "/dev/ttyACM0"
BAUD = 9600
SOUND_1 = "/home/yifzhou/Arduino/parp_sound.mp3"
SOUND_2 = "/home/yifzhou/Arduino/parp_sound_9s.mp3"


def play(sound):
    subprocess.Popen(["mpg123", "-q", sound], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    try:
        ser = serial.Serial(PORT, BAUD, timeout=1)
    except serial.SerialException as e:
        print(f"Could not open port {PORT}: {e}")
        sys.exit(1)

    print(f"Monitoring on {PORT}...")

    while True:
        line = ser.readline().decode("utf-8", errors="ignore").strip()
        if not line:
            continue
        print(line)
        if line == "ALERT1":
            print("  --> 1s hold: playing parp_sound.mp3")
            play(SOUND_1)
        elif line == "ALERT2":
            print("  --> 3s hold: playing parp_sound_9s.mp3")
            play(SOUND_2)


if __name__ == "__main__":
    main()
