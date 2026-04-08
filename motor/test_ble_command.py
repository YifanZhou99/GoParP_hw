import asyncio
from bleak import BleakClient

# Device details
DEVICE_NAME = "JW-aLRA-BA03"
DEVICE_ADDRESS = "C8:46:82:00:2E:FA"

# Common BLE UUIDs (you may need to adjust these based on your device)
# These are standard for many serial-over-BLE devices
SERVICE_UUID = "00001101-0000-1000-8000-00805f9b34fb"  # Serial Port Service
CHAR_UUID_TX = "00002a37-0000-1000-8000-00805f9b34fb"  # TX Characteristic
CHAR_UUID_RX = "00002a37-0000-1000-8000-00805f9b34fb"  # RX Characteristic


async def connect_and_send_command():
    """Connect to Bluetooth device and send a test command"""
    
    try:
        print(f"尝试连接到设备: {DEVICE_NAME} ({DEVICE_ADDRESS})")
        
        async with BleakClient(DEVICE_ADDRESS) as client:
            if client.is_connected:
                print(f"✓ 已连接到 {DEVICE_NAME}\n")
                
                # Get all services and characteristics
                print("设备的服务和特征值:")
                print("-" * 50)
                for service in client.services:
                    print(f"服务: {service.uuid}")
                    for char in service.characteristics:
                        props = ", ".join(char.properties)
                        print(f"  特征: {char.uuid}")
                        print(f"    属性: {props}")
                        print(f"    是否可读: {'read' in char.properties}")
                        print(f"    是否可写: {'write' in char.properties}")
                        print(f"    是否可通知: {'notify' in char.properties}")
                
                print("\n" + "-" * 50)
                print("\n发送命令...")
                
                # Try to find a writable characteristic
                writable_char = None
                for service in client.services:
                    for char in service.characteristics:
                        if "write" in char.properties or "write-without-response" in char.properties:
                            writable_char = char
                            break
                    if writable_char:
                        break
                
                if writable_char:
                    command = "WAKE_UP"
                    print(f"发送命令: {command}")
                    print(f"写入到特征: {writable_char.uuid}")
                    
                    # Send command as bytes
                    await client.write_gatt_char(writable_char.uuid, command.encode('utf-8'))
                    print("✓ 命令已发送\n")
                    
                    # Try to read response if there's a readable characteristic
                    readable_char = None
                    for service in client.services:
                        for char in service.characteristics:
                            if "read" in char.properties:
                                readable_char = char
                                break
                        if readable_char:
                            break
                    
                    if readable_char:
                        print(f"尝试读取响应从特征: {readable_char.uuid}")
                        try:
                            await asyncio.sleep(0.5)  # Wait for response
                            response = await client.read_gatt_char(readable_char.uuid)
                            print(f"✓ 收到响应: {response}")
                            print(f"  文本: {response.decode('utf-8', errors='ignore')}")
                        except Exception as e:
                            print(f"✗ 读取失败: {e}")
                    else:
                        print("没有找到可读的特征值")
                
                else:
                    print("✗ 没有找到可写入的特征值")
                    print("请检查设备支持的特征值")
            
            else:
                print(f"✗ 无法连接到设备")
    
    except Exception as e:
        print(f"✗ 错误: {e}")
        print(f"\n排查建议:")
        print(f"1. 检查设备地址是否正确: {DEVICE_ADDRESS}")
        print(f"2. 确保设备已打开且处于配对模式")
        print(f"3. 运行 ble.py 扫描附近设备")


async def scan_and_test():
    """Scan for device first, then connect"""
    from bleak import BleakScanner
    
    print(f"正在扫描设备: {DEVICE_NAME} ({DEVICE_ADDRESS})\n")
    
    devices = await BleakScanner.discover(timeout=10.0)
    
    device_found = False
    for device in devices:
        if device.address.upper() == DEVICE_ADDRESS.upper():
            print(f"✓ 找到设备: {device.name} ({device.address})\n")
            device_found = True
            break
    
    if not device_found:
        print(f"✗ 未找到设备 {DEVICE_ADDRESS}")
        print(f"找到的设备:")
        for device in devices:
            if device.name:
                print(f"  - {device.name}: {device.address}")
        return
    
    # Connect and send command
    await connect_and_send_command()


if __name__ == "__main__":
    print("=" * 50)
    print("Bluetooth 设备通信测试")
    print("=" * 50 + "\n")
    
    asyncio.run(scan_and_test())
