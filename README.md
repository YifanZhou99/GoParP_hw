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
| `collect_posture_data.py` | **Posture data collection system** (see below) |
| `media/` | Audio files (parp_sound.mp3, etc.) |
| `data/` | Output directory for collected data (CSV + JSON metadata) |

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

---

## Posture Data Collection System

### Overview
`collect_posture_data.py` is a comprehensive data collection tool that records FSR sensor data for two different sitting postures (normal and cross-legged) along with user demographic information.

### Quick Start

1. **Ensure Arduino is running the correct firmware:**
   ```bash
   # Upload read_fsr.ino or haptic_sound.ino to Arduino
   ```

2. **Run the collection script:**
   ```bash
   python3 collect_posture_data.py
   ```

3. **Follow the interactive prompts:**
   - Enter user name
   - Sit in comfortable position for 30 seconds (Phase 2)
   - Stand up and sit in cross-legged position for 30 seconds (Phase 3)
   - Enter demographic information (Phase 4)

### Output Files

Each user generates three files in the `data/` directory:

| File | Description |
|---|---|
| `{ID}_normal_{name}.csv` | 30-second normal posture data (timestamp, fsr1-5) |
| `{ID}_cross_{name}.csv` | 30-second cross-legged posture data (timestamp, fsr1-5) |
| `{ID}_{name}_metadata.json` | User info, collection timestamp, scores |

**Example CSV format:**
```
timestamp,fsr1,fsr2,fsr3,fsr4,fsr5
0.000,234,567,123,456,789
0.010,235,568,124,457,790
...
```

**Example metadata JSON:**
```json
{
  "id": "001",
  "name": "张三",
  "gender": "M",
  "height_cm": 175,
  "weight_kg": 70,
  "age": 28,
  "posture_score": 4,
  "normal_file": "001_normal_张三.csv",
  "cross_file": "001_cross_张三.csv",
  "collection_date": "2026-04-08",
  "collection_time": "14:30:45",
  "normal_samples": 245,
  "cross_samples": 242
}
```

### Features

- ✅ Automatic user ID generation (001, 002, ...)
- ✅ Real-time data collection at ~100Hz
- ✅ Audio cues for collection phase transitions
- ✅ Data statistics display upon completion
- ✅ Comprehensive user demographic collection
- ✅ JSON metadata for easy data analysis
- ✅ Graceful error handling and Ctrl+C support

---## Progress

- [x] Read FSR values over serial
- [x] Python script monitors serial and plays sound on threshold
- [x] Sound triggers only after holding above threshold for 1s or 3s
- [x] Coin vibration motors connected via transistor driver
- [x] Motor intensity mapped to hold duration (idle / medium / full)
- [x] Default idle vibration
