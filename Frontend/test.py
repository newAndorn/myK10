import asyncio
import aioble
import bluetooth

_TARGET_NAME = "0421150164"
_SERVICE_UUID = bluetooth.UUID(0xFF00)

#static BLEUUID serviceUUID("0000ff00-0000-1000-8000-00805f9b34fb"); //xiaoxiang bms service
#static BLEUUID charUUID_rx("0000ff01-0000-1000-8000-00805f9b34fb"); //xiaoxiang bms rx id
#static BLEUUID charUUID_tx("0000ff02-0000-1000-8000-00805f9b34fb"); //xiaoxiang bms tx id

async def discover_device(target_name):
    # Scan for 20 seconds, in active mode, with very low interval/window (to maximise detection rate).
    async with aioble.scan(duration_ms=20_000, interval_us=30000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            # See if it matches target_name.
            if (name := result.name()) is not None and target_name in name:
                print(f"Found target device: {name} - {result.device}")
                return result.device

        print(f"Device with name {target_name} not found.")
        return None

async def run():
    print("Start...")
    device = await discover_device(_TARGET_NAME)
    if not device:
        return

    connection = await device.connect(
        timeout_ms=60_000,
        scan_duration_ms=5_000, min_conn_interval_us=7_500, max_conn_interval_us=7_500)

    async with connection:
        print(f"Connected to {device}")

        found = False
        async for service in connection.services():
            print(f"Found Service {service.uuid}")
            print(f"Service attributes: {dir(service)}")
            
            for attr in dir(service):
                if not attr.startswith('_'):  # Skip private attributes
                    try:
                        value = getattr(service, attr)
                        print(f"{attr}: {value}")
                    except:
                        print(f"{attr}: <error getting value>")
            
            if service.uuid == _SERVICE_UUID:
                print("Found target Service")
                found = True

        # After the loop completion.
        if found:
            service = await connection.service(_SERVICE_UUID)
            print(f"Connected to Service {service.uuid}")

            async for char in service.characteristics():
                print(f"characteristic {char}")

asyncio.run(run())

