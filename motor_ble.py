"""BLE vibration motor controller (JW-aLRA series) — mode 1 single-shot."""

import asyncio
from bleak import BleakClient, BleakScanner

DEVICE_ADDRESS = "C8:46:82:00:2F:A9"

# Mode 1 vibration parameters
FREQ     = 150  # Hz, range: 20-500
AMP1     = 80   # amplitude, 1-127
ON_TIME  = 20   # /10ms → 200ms on
OFF_TIME = 10   # /10ms → 100ms off
ONF_CYC  = 3    # ON-OFF cycles per GO

NUS_RX = "6e400002-b5a3-f393-e0a9-e50e24dcca9e"


async def _write(client, char, cmd, delay=0.2):
    await client.write_gatt_char(char, (cmd + "\r\n").encode(), response=False)
    await asyncio.sleep(delay)


async def _set_param(client, char, name, value):
    """Send CMD → value → ACTION with settle delays (no response polling)."""
    await _write(client, char, name, delay=0.3)
    await asyncio.sleep(0.1)
    await _write(client, char, str(value))
    await _write(client, char, "ACTION")


async def _find_write_char(client):
    for service in client.services:
        for ch in service.characteristics:
            if ch.uuid.lower() == NUS_RX:
                return ch.uuid
    for service in client.services:
        for ch in service.characteristics:
            if "write" in ch.properties or "write-without-response" in ch.properties:
                return ch.uuid
    return None


class MotorController:
    def __init__(self, address=DEVICE_ADDRESS):
        self._address = address
        self._client = None
        self._write_char = None

    async def connect(self):
        """Scan, connect, and configure vibration parameters."""
        devices = await BleakScanner.discover(timeout=10.0)
        found = any(d.address.upper() == self._address.upper() for d in devices)
        if not found:
            raise RuntimeError(f"Motor device not found: {self._address}")

        self._client = BleakClient(self._address)
        await self._client.connect()
        if not self._client.is_connected:
            raise RuntimeError("Motor connection failed")

        self._write_char = await _find_write_char(self._client)
        if not self._write_char:
            raise RuntimeError("No writable characteristic found on motor")

        await _write(self._client, self._write_char, "WAKE_UP", delay=1.0)
        await _write(self._client, self._write_char, "MCU_MODE", delay=0.5)
        await _set_param(self._client, self._write_char, "SET_FREQ",     FREQ)
        await _set_param(self._client, self._write_char, "SET_AMP1",     AMP1)
        await _set_param(self._client, self._write_char, "SET_ON_TIME",  ON_TIME)
        await _set_param(self._client, self._write_char, "SET_OFF_TIME", OFF_TIME)
        await _set_param(self._client, self._write_char, "SET_ONF_CYC",  ONF_CYC)
        print("[motor] Connected and configured.")

    async def trigger(self, cycles=None):
        """Fire one vibration burst. Reconnects automatically if dropped.

        Args:
            cycles: Override ONF_CYC for this burst (None = use configured default).
                    E.g. cycles=20 for a ~6-second long vibration.
        """
        if self._client is None or not self._client.is_connected:
            print("[motor] Reconnecting...")
            await self.connect()
        if cycles is not None:
            await _set_param(self._client, self._write_char, "SET_ONF_CYC", cycles)
        await _write(self._client, self._write_char, "WAKE_UP", delay=0.5)
        await _write(self._client, self._write_char, "GO", delay=1.0)
        if cycles is not None:
            await _set_param(self._client, self._write_char, "SET_ONF_CYC", ONF_CYC)

    async def disconnect(self):
        if self._client and self._client.is_connected:
            await _write(self._client, self._write_char, "SLEEP")
            await self._client.disconnect()
