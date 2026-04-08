import asyncio
from bleak import BleakScanner

async def scan_bluetooth():
    print("正在扫描附近蓝牙设备...\n")
    devices = await BleakScanner.discover(timeout=8.0)

    if not devices:
        print("没有扫描到蓝牙设备。")
        return

    print(f"共扫描到 {len(devices)} 个设备：\n")
    for i, device in enumerate(devices, 1):
        name = device.name if device.name else "Unknown"
        if device.name == 'JW-aLRA-A4D7':
            print(f"{i}. 名称: {name}")
            print(f"   地址: {device.address}")
            print(f"   RSSI: {getattr(device, 'rssi', 'N/A')}")
            print("-" * 40)

if __name__ == "__main__":
    asyncio.run(scan_bluetooth())