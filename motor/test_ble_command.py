import asyncio
from bleak import BleakClient, BleakScanner

 
DEVICE_NAME = "JW-aLRA-A4D7"
DEVICE_ADDRESS = "C8:46:82:00:2F:A9"

# DEVICE_NAME = "JW-aLRA-BA03"
# DEVICE_ADDRESS = "C8:46:82:00:2E:FA"

# Vibration parameters (adjust as needed)
FREQ = 150        # Hz, range: 20-500
AMP1 = 80         # Amplitude effect 1, range: 1-127
SET_ON_TIME = 20  # ON time in units of /10ms → 200ms
SET_OFF_TIME = 10 # OFF time in units of /10ms → 100ms
SET_ONE_CYC = 3   # Number of ON-OFF cycles per GO trigger

notification_log = []

def notification_handler(sender, data):
    msg = data.decode("utf-8", errors="ignore").strip()
    print(f"  ← [{sender}] {msg}")
    notification_log.append(msg)

async def send_cmd(client, char_uuid, cmd: str, delay=0.4):
    """Send a text command and wait briefly for response."""
    print(f"  → {cmd}")
    await client.write_gatt_char(char_uuid, (cmd + "\r\n").encode("utf-8"), response=False)
    await asyncio.sleep(delay)

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
        await send_cmd(client, write_char, "WAKE_UP")

        # ── 2. Switch to MCU_MODE for clean responses ───────────
        print("[2] Setting MCU_MODE (terse output)...")
        await send_cmd(client, write_char, "MCU_MODE")

        # ── 3. Configure vibration parameters ───────────────────
        print("[3] Setting frequency...")
        await send_cmd(client, write_char, f"SET_FREQ {FREQ}")

        print("[4] Setting amplitude (effect 1)...")
        await send_cmd(client, write_char, f"SET_AMP1 {AMP1}")

        print("[5] Setting ON time...")
        await send_cmd(client, write_char, f"SET_ON_TIME {SET_ON_TIME}")

        print("[6] Setting OFF time...")
        await send_cmd(client, write_char, f"SET_OFF_TIME {SET_OFF_TIME}")

        print("[7] Setting cycle count...")
        await send_cmd(client, write_char, f"SET_ONE_CYC {SET_ONE_CYC}")

        # ── 4. Verify settings ───────────────────────────────────
        print("[8] Querying settings...")
        await send_cmd(client, write_char, "ASK_FREQ")
        await send_cmd(client, write_char, "ASK_AMP")
        await send_cmd(client, write_char, "ASK_ON_TIME")
        await send_cmd(client, write_char, "ASK_OFF_TIME")
        await send_cmd(client, write_char, "ASK_ONE_CYC")

        # ── 5. Trigger vibration ─────────────────────────────────
        print("\n[9] Triggering vibration (GO)...")
        await send_cmd(client, write_char, "GO", delay=1.0)
        print("✓ Vibration triggered!\n")

        # Optional: trigger again after a pause
        await asyncio.sleep(1.0)
        print("[10] Second vibration burst...")
        await send_cmd(client, write_char, "GO", delay=1.0)

        # ── 6. Sleep when done ───────────────────────────────────
        print("[11] Sending SLEEP...")
        await send_cmd(client, write_char, "SLEEP")

        if notify_char:
            await client.stop_notify(notify_char)

        print("\n✓ Done.")

if __name__ == "__main__":
    print("=" * 50)
    print("JW-BLE-DL500 Vibration Test")
    print("=" * 50 + "\n")
    asyncio.run(vibrate())