# FSR Haptic Sound Monitor

Two FSR sensors drive haptic (vibration) feedback and audio alerts based on pressure hold duration.

## Hardware

- Arduino Uno
- 2x FSR sensors on A0, A1
- 2x Shenzhen Huayuanxin 1027 coin vibration motors
  - Each driven via NPN transistor (e.g. S8050) + 1kΩ resistor + 1N4148 flyback diode
  - Motor pin: **9** (PWM)

## Requirements

```bash
pip install pyserial
sudo apt install mpg123
```

## Files

| File | Description |
|---|---|
| `read_fsr/read_fsr.ino` | Basic FSR serial reader |
| `haptic_sound/haptic_sound.ino` | Main sketch: FSR + motor + serial alerts |
| `monitor_fsr.py` | Python: reads serial, plays sound on alerts |
| `parp_sound.mp3` | Sound for 1s hold |
| `parp_sound_9s.mp3` | Sound for 3s hold |

## Usage

1. Upload `haptic_sound/haptic_sound.ino` to Arduino
2. Close Arduino Serial Monitor
3. Run:

```bash
python3 monitor_fsr.py
```

## Behavior

| Hold duration | Motor | Sound |
|---|---|---|
| idle (no press) | vibrates at default (PWM 60) | — |
| 1s | medium (PWM 120) | `parp_sound.mp3` |
| 3s | full (PWM 255) | `parp_sound_9s.mp3` |

## Config

**`haptic_sound.ino`**

| Constant | Default | Description |
|---|---|---|
| `FSR_THRESHOLD` | `500` | Pressure level to start timing |
| `MOTOR_DEFAULT` | `60` | Idle vibration intensity |
| `HOLD_1` | `1000ms` | First alert hold time |
| `HOLD_2` | `3000ms` | Second alert hold time |

**`monitor_fsr.py`**

| Variable | Default | Description |
|---|---|---|
| `PORT` | `/dev/ttyACM0` | Arduino serial port |
| `BAUD` | `9600` | Serial baud rate |

## Progress

- [x] Read FSR values over serial
- [x] Python script monitors serial and plays sound on threshold
- [x] Sound triggers only after holding above threshold for 1s or 3s
- [x] Coin vibration motors connected via transistor driver
- [x] Motor intensity mapped to hold duration (idle / medium / full)
- [x] Default idle vibration
