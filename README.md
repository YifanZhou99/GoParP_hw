# Sitting Reminder System / 久坐提醒系统

A pressure-sensor-driven interactive installation that detects prolonged sitting and responds with sound, haptic feedback, and robot arm movement.

基于压力传感器的交互装置，检测久坐行为，通过声音、触觉震动和机械臂动作进行提醒。

---

## Hardware / 硬件

| Component / 组件 | Detail / 说明 |
|---|---|
| Arduino Uno | FSR sensor reader / FSR 传感器读取 |
| FSR sensors × 5 | Seat pressure detection / 座位压力检测 |
| BLE Vibration Motor | JW-aLRA series, address `C8:46:82:00:2F:A9` |
| Robot Arm | ESP8266 web interface at `192.168.1.1` |

---

## Requirements / 环境依赖

```bash
pip install pyserial requests bleak

# Audio playback (supports mp3 / m4a)
sudo apt install ffmpeg
```

---

## Files / 文件说明

| File / 文件 | Description / 说明 |
|---|---|
| `play_demo.py` | **Main demo script** / 主 demo 脚本（三阶段提醒） |
| `monitor_fsr.py` | Legacy two-alert monitor / 旧版双档位监控 |
| `robot_arm_control.py` | Robot arm controller & action library / 机械臂控制与动作库 |
| `motor_ble.py` | BLE vibration motor controller / 蓝牙震动电机控制 |
| `collect_posture_data.py` | Posture data collection tool / 坐姿数据采集工具 |
| `media/` | Audio files / 音频文件 |
| `media/fart_sound/` | Fart SFX & music playlist / 放屁音效及音乐 |
| `data/` | Collected posture CSV data / 采集的坐姿数据 |

---

## Usage / 使用方法

### Main Demo / 主 Demo (`play_demo.py`)

```bash
python3 play_demo.py
```

The script opens the serial port, connects to the BLE motor in the background, then enters the FSR monitoring loop. No manual arm initialization needed — the arm moves to the ready position automatically in Phase 2.

脚本启动后自动打开串口、后台连接蓝牙电机，进入 FSR 监控循环。无需手动初始化机械臂——Phase 2 会自动蓄力。

---

### Legacy Monitor / 旧版监控 (`monitor_fsr.py`)

```bash
python3 monitor_fsr.py
```

---

## Demo Modes / 演示模式

### `play_demo.py` — 3-Phase Sitting Reminder / 三阶段久坐提醒

Triggered by FSR pressure exceeding threshold (`FSR_THRESHOLD = 600`).
由 FSR 压力超过阈值（`FSR_THRESHOLD = 600`）触发。

| Phase / 阶段 | Trigger / 触发时间 | Sound / 声音 | Haptic / 触觉 | Robot Arm / 机械臂 |
|---|---|---|---|---|
| **Phase 1** | Sit down / 坐下瞬间 | Random fart SFX<br>随机放屁音效 | Light buzz<br>轻震 | — |
| **Phase 2** | +5 s still sitting<br>坐满 5 秒 | "您还坐着呢"（北京话）| — | Move to ready position<br>后仰蓄力 |
| **Phase 3** | +10 s still sitting<br>坐满 10 秒 | Random "stand up" voice →<br>随机"站起来"语音 →<br>Random music<br>随机放屁音乐 | Long vibration<br>长震动 | Head hammer × 3<br>头锤 ×3 |

**On standing up / 站起来时：** all audio stops immediately, pending phases are cancelled, hammer aborts between strikes.
所有声音立即停止，未触发的阶段取消，头锤在两击之间中止。

#### Media Files / 音频文件

| Role / 用途 | Files / 文件 |
|---|---|
| Phase 1 SFX | `fart_sound/fart_quick.mp3`, `fart_sound/fart_wet.mp3` |
| Phase 2 voice | `您还坐着呢.m4a` |
| Phase 3 voice | `上海话你站起来.m4a`, `北京话站起来走.m4a` (random) |
| Phase 3 music | `fart_sound/放屁_*.mp3` (random, currently 4 tracks) |

---

### `monitor_fsr.py` — 2-Alert Monitor / 双档位监控

| Alert / 档位 | Trigger / 触发条件 | Sound / 声音 | Haptic / 触觉 | Robot Arm / 机械臂 |
|---|---|---|---|---|
| **Alert 1** | Above threshold for 1 s | `parp_sound.mp3` | Light buzz | Nod + shake head<br>点头摇头 × 2 |
| **Alert 2** | Above threshold for 3 s | `parp_sound_9s.mp3` | — | Head hammer × 1 |

---

## Robot Arm Actions / 机械臂动作库

Defined in `robot_arm_control.py`. Coordinate system: X/Y/Z position, B = base tilt, E = end effector angle.
定义于 `robot_arm_control.py`。坐标系：X/Y/Z 位置，B = 底座倾角，E = 末端角度。

### `head_hammer(repeats=3, speed=200, from_ready=False)`

Quick downward strike. / 快速下击。

| Pose / 姿态 | X | Y | Z | B | E |
|---|---|---|---|---|---|
| Ready / 蓄力位 | 103 | 116 | 37 | 33 | 55 |
| Strike / 击打位 | 103 | 116 | 143 | 32 | 91 |

`from_ready=True` skips the initial move-to-ready if arm is already in position.
`from_ready=True` 跳过归位动作，适合已蓄力后直接触发。

### `nod_and_shake(repeats=1, speed=150, steps=4, step_delay_ms=180)`

Simultaneously nods (B: 28→104) and shakes head (X: 143→45) with linear interpolation, then returns.
同步点头（B: 28→104）与摇头（X: 143→45），线性插值，结束后归位。

---

## Configuration / 可调参数

### `play_demo.py`

| Variable / 变量 | Default / 默认值 | Description / 说明 |
|---|---|---|
| `FSR_THRESHOLD` | `600` | Sitting detection threshold / 坐下检测阈值 |
| `PHASE2_DELAY` | `5.0 s` | Delay before Phase 2 / Phase 2 触发延迟 |
| `PHASE3_DELAY` | `10.0 s` | Delay before Phase 3 / Phase 3 触发延迟 |
| `ARM_SPEED` | `200` | Robot arm movement speed / 机械臂运动速度 |
| `PORT` | `/dev/ttyACM0` | Arduino serial port / 串口 |

---

## Posture Data Collection / 坐姿数据采集

```bash
python3 collect_posture_data.py
```

Collects 30-second FSR recordings for normal and cross-legged sitting postures, with user demographic metadata.
采集正常坐姿和盘腿坐姿各 30 秒的 FSR 数据，附带用户基本信息。

Output files in `data/`:
- `{ID}_normal_{name}.csv` — Normal posture / 正常坐姿
- `{ID}_cross_{name}.csv` — Cross-legged posture / 盘腿坐姿
- `{ID}_{name}_metadata.json` — Demographics & scores / 用户信息与评分
