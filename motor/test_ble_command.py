import asyncio
from bleak import BleakClient, BleakScanner


DEVICE_NAME = "JW-aLRA-A4D7"
DEVICE_ADDRESS = "C8:46:82:00:2F:A9"

# DEVICE_NAME = "JW-aLRA-BA03"
# DEVICE_ADDRESS = "C8:46:82:00:2E:FA"

# Single-shot vibration parameters (used in vibrate())
FREQ = 150        # Hz, range: 20-500
AMP1 = 80         # Amplitude effect 1, range: 1-127
SET_ON_TIME = 20  # ON time in units of /10ms → 200ms
SET_OFF_TIME = 10 # OFF time in units of /10ms → 100ms
SET_ONF_CYC = 3   # Number of ON-OFF cycles per GO trigger

# Pre-stored vibration sequence: list of steps played in order.
# Each step: freq (Hz), amp (1-127), on_time (/10ms), off_time (/10ms), cyc (cycles), pause (s after GO)
VIBRATION_SEQUENCE = [
    {"freq": 100, "amp":  50, "on_time": 30, "off_time": 20, "cyc": 2, "pause": 1.5},
    {"freq": 200, "amp":  90, "on_time": 30, "off_time": 20, "cyc": 3, "pause": 2.0},
    {"freq": 300, "amp": 120, "on_time": 30, "off_time": 20, "cyc": 2, "pause": 1.5},
    {"freq": 150, "amp":  60, "on_time": 30, "off_time": 20, "cyc": 4, "pause": 3.0},
]

notification_log = []
notification_queue = asyncio.Queue()

def notification_handler(sender, data):
    msg = data.decode("utf-8", errors="ignore").strip()
    print(f"  ← [{sender}] {msg}")
    notification_log.append(msg)
    try:
        notification_queue.put_nowait(msg)
    except Exception:
        pass

async def wait_for_response(expected: str, timeout=5.0):
    """Wait until a notification containing `expected` is received."""
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            print(f"  ⚠ Timeout waiting for '{expected}'")
            return False
        try:
            msg = await asyncio.wait_for(notification_queue.get(), timeout=remaining)
            if expected.lower() in msg.lower():
                return True
        except asyncio.TimeoutError:
            print(f"  ⚠ Timeout waiting for '{expected}'")
            return False

async def send_cmd(client, char_uuid, cmd: str, delay=0.2):
    """Send a raw text command."""
    print(f"  → {cmd}")
    await client.write_gatt_char(char_uuid, (cmd + "\r\n").encode("utf-8"), response=False)
    await asyncio.sleep(delay)

async def send_set_cmd(client, char_uuid, cmd_name: str, value, wait=True):
    """
    SET protocol:
      1. Send CMD (e.g. SET_FREQ)  → optionally wait for 'ok'
      2. Send value (e.g. 150)
      3. Send ACTION               → optionally wait for 'set finish'
    Set wait=False to fire-and-forget (no response polling).
    """
    await send_cmd(client, char_uuid, cmd_name, delay=0.3 if not wait else 0.2)
    if wait:
        ok = await wait_for_response("ok")
        if not ok:
            print(f"  ⚠ No 'ok' received for {cmd_name}, continuing anyway...")
    else:
        await asyncio.sleep(0.1)  # let device finish processing CMD before sending value

    await send_cmd(client, char_uuid, str(value))

    await send_cmd(client, char_uuid, "ACTION")
    if wait:
        done = await wait_for_response("set finish")
        if not done:
            print(f"  ⚠ No 'set finish' received for {cmd_name}")
        else:
            print(f"  ✓ {cmd_name} set to {value}")
    else:
        print(f"  ✓ {cmd_name} = {value} (no-wait)")

async def find_uart_char(client):
    """
    Find the writable+notify characteristic pair.
    Prefers Nordic UART Service (NUS), falls back to first writable char.
    """
    NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"  # write to this
    NUS_TX = "6e400003-b5a3-f393-e0a9-e50e24dcca9e"  # notifications from this

    write_char = None
    notify_char = None

    for service in client.services:
        for char in service.characteristics:
            uuid = char.uuid.lower()
            if uuid == NUS_RX:
                write_char = char.uuid
            if uuid == NUS_TX:
                notify_char = char.uuid

    # Fallback: scan all characteristics
    if not write_char:
        for service in client.services:
            for char in service.characteristics:
                props = char.properties
                if not write_char and ("write" in props or "write-without-response" in props):
                    write_char = char.uuid
                if not notify_char and "notify" in props:
                    notify_char = char.uuid

    return write_char, notify_char

async def play_sequence(client, write_char, notify_char):
    """Play the pre-stored VIBRATION_SEQUENCE step by step."""
    if notify_char:
        print(f"[notify] Subscribing to {notify_char}")
        await client.start_notify(notify_char, notification_handler)
    else:
        print("⚠ notify_char is None — responses will not be received!")

    print("[1] Waking up device...")
    await send_cmd(client, write_char, "WAKE_UP", delay=1.5)
    print("[2] Setting MCU_MODE...")
    await send_cmd(client, write_char, "MCU_MODE", delay=1.5)  # give device time to settle

    for i, step in enumerate(VIBRATION_SEQUENCE, start=1):
        print(f"\n── Step {i}/{len(VIBRATION_SEQUENCE)} "
              f"freq={step['freq']}Hz amp={step['amp']} "
              f"on={step['on_time']} off={step['off_time']} cyc={step['cyc']} ──")
        await send_cmd(client, write_char, "WAKE_UP", delay=0.8)
        await send_set_cmd(client, write_char, "SET_FREQ",     step["freq"],     wait=False)
        await send_set_cmd(client, write_char, "SET_AMP1",     step["amp"],      wait=False)
        await send_set_cmd(client, write_char, "SET_ON_TIME",  step["on_time"],  wait=False)
        await send_set_cmd(client, write_char, "SET_OFF_TIME", step["off_time"], wait=False)
        await send_set_cmd(client, write_char, "SET_ONF_CYC",  step["cyc"],      wait=False)
        vibe_duration = step["cyc"] * (step["on_time"] + step["off_time"]) * 0.01  # seconds
        await send_cmd(client, write_char, "LONG_Vibe", delay=0.2)
        await asyncio.sleep(vibe_duration + 1.0)  # wait for full vibration + settle buffer

    print("\n[done] Sending SLEEP...")
    await send_cmd(client, write_char, "SLEEP")
    if notify_char:
        await client.stop_notify(notify_char)
    print("✓ Sequence finished.")


async def vibrate():
    print(f"Scanning for {DEVICE_NAME} ({DEVICE_ADDRESS})...")
    devices = await BleakScanner.discover(timeout=10.0)
    found = any(d.address.upper() == DEVICE_ADDRESS.upper() for d in devices)
    if not found:
        print("✗ Device not found. Nearby devices:")
        for d in devices:
            if d.name:
                print(f"  {d.name}: {d.address}")
        return

    print(f"✓ Device found. Connecting...\n")

    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("✗ Connection failed.")
            return

        print("✓ Connected!\n")

        write_char, notify_char = await find_uart_char(client)

        if not write_char:
            print("✗ No writable characteristic found.")
            return

        print(f"Write char : {write_char}")
        print(f"Notify char: {notify_char}\n")

        # Subscribe to notifications
        if notify_char:
            await client.start_notify(notify_char, notification_handler)

        # ── 1. Wake up ──────────────────────────────────────────
        print("[1] Waking up device...")
        await send_cmd(client, write_char, "WAKE_UP", delay=1.0)

        # ── 2. Switch to MCU_MODE for clean responses ───────────
        print("[2] Setting MCU_MODE (terse output)...")
        await send_cmd(client, write_char, "MCU_MODE", delay=0.5)

        # ── 3. Configure vibration parameters ───────────────────
        print("[3] Setting frequency...")
        await send_set_cmd(client, write_char, "SET_FREQ", FREQ)

        print("[4] Setting amplitude (effect 1)...")
        await send_set_cmd(client, write_char, "SET_AMP1", AMP1)

        print("[5] Setting ON time...")
        await send_set_cmd(client, write_char, "SET_ON_TIME", SET_ON_TIME)

        print("[6] Setting OFF time...")
        await send_set_cmd(client, write_char, "SET_OFF_TIME", SET_OFF_TIME)

        print("[7] Setting cycle count...")
        await send_set_cmd(client, write_char, "SET_ONF_CYC", SET_ONF_CYC)

        # ── 4. Trigger vibration ─────────────────────────────────
        print("\n[8] Triggering vibration (GO)...")
        await send_cmd(client, write_char, "GO", delay=1.0)
        print("✓ Vibration triggered!\n")

        # Optional: trigger again after a pause
        await asyncio.sleep(1.0)
        print("[9] Second vibration burst...")
        await send_cmd(client, write_char, "GO", delay=1.0)

        # ── 5. Sleep when done ───────────────────────────────────
        print("[10] Sending SLEEP...")
        await send_cmd(client, write_char, "SLEEP")

        if notify_char:
            await client.stop_notify(notify_char)

        print("\n✓ Done.")

async def run_sequence_mode():
    print(f"Scanning for {DEVICE_NAME} ({DEVICE_ADDRESS})...")
    devices = await BleakScanner.discover(timeout=10.0)
    found = any(d.address.upper() == DEVICE_ADDRESS.upper() for d in devices)
    if not found:
        print("✗ Device not found.")
        return
    print("✓ Device found. Connecting...\n")
    async with BleakClient(DEVICE_ADDRESS) as client:
        if not client.is_connected:
            print("✗ Connection failed.")
            return
        print("✓ Connected!\n")
        write_char, notify_char = await find_uart_char(client)
        if not write_char:
            print("✗ No writable characteristic found.")
            return
        await play_sequence(client, write_char, notify_char)


if __name__ == "__main__":
    import sys
    print("=" * 50)
    print("JW-BLE-DL500 Vibration Test")
    print("=" * 50 + "\n")
    mode = sys.argv[1] if len(sys.argv) > 1 else "single"
    if mode == "seq":
        asyncio.run(run_sequence_mode())
    else:
        asyncio.run(vibrate())
