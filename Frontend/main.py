import time
import network
import ubinascii
from machine import unique_id
from umqtt.simple import MQTTClient
import ujson as json

from unihiker_k10 import screen
from unihiker_k10 import temp_humi
from unihiker_k10 import light
from unihiker_k10 import rgb
from unihiker_k10 import button
from unihiker_k10 import mic, speaker
from unihiker_k10 import camera
from unihiker_k10 import acce
from k10_base import WiFi

import _thread
import lvgl as lv

import asyncio
import aioble
import bluetooth

from bms_data import BMSData

WIFI_SSID = "andorn12"
WIFI_PASSWORD = "GardenRoute11"

MQTT_HOST = "194.164.50.92"
MQTT_PORT = 1883
MQTT_USER = "andorn"
MQTT_PASSWORD = "gigant"
MQTT_CLIENT_ID = b"hiker-k10-" + ubinascii.hexlify(unique_id())
MQTT_TOPIC_SUB = b"shellyemg3/status/em1:0"
MQTT_TOPIC_PUB = b"unihiker/photo"
MQTT_TOPIC_PUB_DATA = b'unihiker/json'
MQTT_TOPIC_PUB_BMS = b'unihiker/bms'

# BMS Configuration
BMS_DEVICE_NAME = "0421150164"
BMS_SERVICE_UUID = bluetooth.UUID(0xff00)
BMS_CHAR_TX_UUID = bluetooth.UUID(0xff01)  # Write
BMS_CHAR_RX_UUID = bluetooth.UUID(0xff02)  # Notify
BMS_SCAN_INTERVAL_SECONDS = 300  # 5 minutes

# JBD BMS Protocol Commands
CMD_BASIC_INFO = b"\xDD\xA5\x03\x00\xFF\xFD\x77"  # Request basic system info
CMD_CELL_VOLTAGES = b"\xDD\xA5\x04\x00\xFF\xFC\x77"  # Request cell voltages

bt_a = button(button.a)
bt_b = button(button.b)

_client = None
_last_wifi_check_ms = 0
_last_mqtt_check_ms = 0
_last_bms_scan_ms = 0
_wifi_check_interval_ms = 5000
_mqtt_check_interval_ms = 5000

# Values
hum = None
temp = None
lux = None
count = 0
bms_data = None

# GUI Element
gauge = None
gauge_hum = None
gauge_bms_voltage = None
gauge_bms_soc = None

temp_adjustment = 7
hum_adjustment = 20

light_status = "off"
screen_status = "on"

def button_a_pressed():
    print("button_a_pressed")
    toggle_light()

def button_a_released():
    print("button_a_released")

def button_b_pressed():
    print("button_b_pressed")

def button_b_released():
    print("button_b_released")

bt_a.event_pressed = button_a_pressed
bt_a.event_released = button_a_released
bt_b.event_pressed = button_b_pressed
bt_b.event_released = button_b_released

def publish_values():
    global hum, temp, count, _client
    
    try:
        # Create JSON object with all sensor readings
        sensor_data = {
            "environment": {
                "temperature": float(temp),
                "humidity": float(hum),
                #"light": float(lux)
            },
            "system": {
                "count": count
            }
        }
            
        # Convert to JSON string and publish
        json_str = json.dumps(sensor_data)
        #print(f"Publishing JSON: {json_str}")
        _client.publish(MQTT_TOPIC_PUB_DATA, json_str)
        #print("Publishing done.")
                    
    except Exception as e:
        print(f"Error publishing: {e}")
        success = False

def publish_bms_data():
    global bms_data, _client
    
    if bms_data is None or _client is None:
        return
    
    try:
        # Create JSON object with BMS data
        bms_json = {
            "battery": {
                "voltage": float(bms_data.voltage),
                "current": float(bms_data.current),
                "soc": int(bms_data.soc),
                "soc_calculated": float(bms_data.calculated_soc_voltage),
                "capacity": float(bms_data.balance_capacity),
                "power": float(bms_data.voltage * bms_data.current),
                "cycle_count": int(bms_data.cycle_count)
            }
        }
        
        if bms_data.temps:
            bms_json["battery"]["temperature"] = float(bms_data.temps[0])
        
        if bms_data.cell_voltages:
            bms_json["battery"]["cells"] = {
                "voltages": [float(v) for v in bms_data.cell_voltages],
                "min": float(min(bms_data.cell_voltages)),
                "max": float(max(bms_data.cell_voltages))
            }
        
        json_str = json.dumps(bms_json)
        _client.publish(MQTT_TOPIC_PUB_BMS, json_str)
        print("BMS data published to MQTT")
        
    except Exception as e:
        print(f"Error publishing BMS data: {e}")
    
def take_and_send_photo():    
    print("Taking photo...")
    image_header = b"data:image/jpeg;base64,"
    
    try:
        
        # White balance may not work on first capture
        camera.capture()
        time.sleep(0.1)
        camera.capture()
        time.sleep(0.1)
        buffer = camera.capture()
            
        jpeg_buf = camera.encode_jpeg(buffer, quality=70)
                
        base64_picture = ubinascii.b2a_base64(jpeg_buf)

        if _client is not None:
            try:
                print("Sending Photo...")
                _client.publish(MQTT_TOPIC_PUB, image_header + base64_picture)
                print("Photo sent. Size =", len(base64_picture))
            except Exception as e:
                print("MQTT publish failed:", e)
        else:
            print("No MQTT client; photo not sent.")
    except Exception as e:
        print("Camera error:", e)

def wifi_connect_non_blocking(ssid, password, timeout_s=20):
    
    print("Connecting to:", ssid)
    
    wifi.connect(ssid=ssid,psd=password,timeout=50000)
    wifi.status()
    wifi.info()
    
    return wifi.info()

def on_mqtt_message(topic, msg):
    rgb.write(num=1, R=0, G=0, B=255)
    try:
        print(
            "MQTT message on topic:",
            topic.decode() if isinstance(topic, bytes) else topic,
        )
        
        if topic.decode() == "unihiker/takephoto":
            take_and_send_photo()
        else:
            data = json.loads(msg.decode() if isinstance(msg, bytes) else msg)
            act_power = data.get("act_power", 0)
            print(act_power)

            gauge = VerticalGauge(
                x=0, y=100, width=70, height=200, min_value=-200, max_value=200
            )
            gauge.set_value(act_power)
            gauge.draw()
            screen.show_draw()
    except Exception as e:
        print("MQTT payload error:", e)
        print("Payload (raw bytes):", msg)
    finally:
        rgb.write(num=1, R=0, G=0, B=0)


def mqtt_connect_and_subscribe():
    try:
        client = MQTTClient(
            client_id=MQTT_CLIENT_ID,
            server=MQTT_HOST,
            port=MQTT_PORT,
            user=MQTT_USER,
            password=MQTT_PASSWORD,
            keepalive=30,
            ssl=False,
        )
        client.set_callback(on_mqtt_message)
        client.connect()
        # TODO: subscribe to multiple topics
        #client.subscribe([MQTT_TOPIC_SUB, "unihiker/takephoto"])
        client.subscribe("unihiker/takephoto")
        print("Connected to MQTT and subscribed to:", MQTT_TOPIC_SUB.decode())
        return client
    except Exception as e:
        print("MQTT connect/subscribe failed:", e)
        return None

def toggle_light():
    global light_status
    try:        
        if light_status == "off":
            light_status = "on"
        else:
            light_status = "off"
            
        _client.publish("shellyplug/command/switch:0", light_status)
                    
    except Exception as e:
        print(f"Error publishing: {e}")

def print_sensor_values(): 
    global hum, temp, count, gauge, gauge_hum, gauge_bms_voltage, gauge_bms_soc, bms_data
    
    try:
        temp = temp_humi.read_temp() - temp_adjustment
    except Exception:
        temp = None
    try:
        hum = temp_humi.read_humi() + hum_adjustment
    except Exception:
        hum = None
        
    screen.set_gauge_value(gauge, int(temp), text=f"{temp:.2f} C")
    screen.set_gauge_value(gauge_hum, int(hum ), text=f"{hum:.2f} %", gauge_type="humidity")

    # Update BMS gauges if data is available
    if bms_data is not None:
        voltage = bms_data.voltage if bms_data.voltage > 0 else bms_data.calculated_voltage
        soc = bms_data.calculated_soc_voltage if bms_data.calculated_soc_voltage > 0 else bms_data.soc
        
        screen.set_gauge_value(gauge_bms_voltage, int(voltage), text=f"{voltage:.1f} V")
        screen.set_gauge_value(gauge_bms_soc, int(soc), text=f"{soc:.0f} %")

    screen.show_draw()

def maybe_reconnect_wifi():
    global _last_wifi_check_ms
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_wifi_check_ms) < _wifi_check_interval_ms:
        return

    _last_wifi_check_ms = now

    if wifi.status():
        return

    print("WiFi not connected. Attempting reconnect...")
    ipcfg = wifi_connect_non_blocking(WIFI_SSID, WIFI_PASSWORD, timeout_s=5)
    if ipcfg:
        print("WiFi connected. IF config:", ipcfg)
    else:
        print("Still offline (WiFi).")

def maybe_connect_mqtt():
    global _client, _last_mqtt_check_ms
    if _client is not None:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_mqtt_check_ms) < _mqtt_check_interval_ms:
        return
    _last_mqtt_check_ms = now

    if not wifi.status():
        print("Skipping MQTT connect; WiFi offline.")
        return

    print("Attempting MQTT connect...")
    _client = mqtt_connect_and_subscribe()
    if _client is None:
        print("MQTT still offline.")


async def find_bms_device(device_name, timeout_ms=10000):
    """Scan for BMS device by name"""
    print(f"Scanning for BMS device: {device_name}")
    
    try:
        async with aioble.scan(duration_ms=timeout_ms, interval_us=30000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                name = result.name()
                if name and device_name in name:
                    print(f"Found BMS device: {name} (RSSI: {result.rssi} dBm)")
                    return result.device
    except Exception as e:
        print(f"Scan error: {e}")
    
    return None


async def connect_to_bms(device):
    """Connect to BMS device"""
    print("Connecting to BMS...")
    try:
        connection = await device.connect(timeout_ms=10000)
        print("Connected successfully!")
        return connection
    except Exception as e:
        print(f"Connection failed: {e}")
        return None


async def read_bms_data_async():
    """Read BMS data via Bluetooth"""
    global bms_data
    
    new_bms_data = BMSData()
    
    # Find BMS device
    device = await find_bms_device(BMS_DEVICE_NAME, timeout_ms=15000)
    if not device:
        print("BMS device not found!")
        return False
    
    # Connect to device
    connection = await connect_to_bms(device)
    if not connection:
        print("Failed to connect to BMS!")
        return False
    
    try:
        async with connection:
            print("Discovering services...")
            
            # Get BMS service
            try:
                service = await connection.service(BMS_SERVICE_UUID)
                print(f"Found service: {service.uuid}")
            except Exception as e:
                print(f"Service not found: {e}")
                return False
            
            # Get RX (write) and TX (notify) characteristics
            try:
                rx_char = await service.characteristic(BMS_CHAR_RX_UUID)
                tx_char = await service.characteristic(BMS_CHAR_TX_UUID)
                print("Found characteristics")
            except Exception as e:
                print(f"Characteristics not found: {e}")
                return False
            
            # Subscribe to notifications
            print("Subscribing to notifications...")
            await tx_char.subscribe(notify=True)
            
            # Wait for BMS to be ready for commands (important!)
            print("Waiting for BMS to be ready...")
            await asyncio.sleep(2)
            
            # Request cell voltages FIRST (helps wake up the BMS)
            print("\nRequesting cell voltages...")
            for attempt in range(3):
                await rx_char.write(CMD_CELL_VOLTAGES, response=False)
                try:
                    data = await asyncio.wait_for(tx_char.notified(), timeout=10.0)
                    print(f"Received {len(data)} bytes")
                    if data[0] == 0xDD and data[1] == 0x04:
                        new_bms_data.parse_cell_voltages(data)
                        break
                except asyncio.TimeoutError:
                    if attempt < 2:
                        print(f"Timeout, retry {attempt + 2}/3...")
                        await asyncio.sleep(1)
                    else:
                        print("Timeout waiting for cell voltages")
            
            # Delay between commands
            await asyncio.sleep(1)
            
            # Request basic info with retry logic
            print("\nRequesting basic info...")
            for attempt in range(3):
                await rx_char.write(CMD_BASIC_INFO, response=False)

                try:
                    # Get first notification
                    data = await asyncio.wait_for(tx_char.notified(), timeout=10.0)
                    print(f"Received {len(data)} bytes")
                    
                    # Check for expected DD 03 header
                    if data[0] == 0xDD and data[1] == 0x03:
                        print("Header matches DD 03, attempting to parse...")
                        new_bms_data.parse_basic_info(data)
                        break
                    # Check if data starts with 0x00 0x00 (might be padding or fragment)
                    elif data[0] == 0x00 and data[1] == 0x00:
                        print("Found 0x00 0x00 header - trying to find DD 03...")
                        # Try to find DD 03 in the data
                        for i in range(len(data) - 1):
                            if data[i] == 0xDD and data[i+1] == 0x03:
                                print(f"Found DD 03 at offset {i}")
                                new_bms_data.parse_basic_info(data[i:])
                                break
                        else:
                            # Try waiting for another notification
                            print("Trying to get next notification...")
                            for retry in range(15):
                                try:
                                    data2 = await asyncio.wait_for(tx_char.notified(), timeout=1.0)
                                    print(f"Got second notification: {len(data2)} bytes")
                                    if data2[0] == 0xDD and data2[1] == 0x03:
                                        new_bms_data.parse_basic_info(data2)
                                        break
                                except asyncio.TimeoutError:
                                    if retry < 14:
                                        print(f"Waiting... ({retry + 1}/15)")
                    else:
                        print(f"Unexpected header: 0x{data[0]:02x} 0x{data[1]:02x}")
                        
                except asyncio.TimeoutError:
                    if attempt < 2:
                        print(f"Timeout, retry {attempt + 2}/3...")
                        await asyncio.sleep(1)
                    else:
                        print("Timeout waiting for basic info after all retries")
            
            # Display results
            print("\n")
            new_bms_data.display()
            
            # Update global BMS data
            bms_data = new_bms_data
            
            return True
            
    except Exception as e:
        print(f"Error reading BMS data: {e}")
        import sys
        sys.print_exception(e)
        return False


def scan_bms_with_wifi_management():
    """Scan BMS with WiFi disabled, then re-enable WiFi"""
    global wifi, _client, _last_bms_scan_ms
    
    print("\n" + "="*50)
    print("Starting BMS scan cycle")
    print("="*50)
    
    # Disconnect MQTT if connected
    if _client is not None:
        try:
            print("Disconnecting MQTT...")
            _client.disconnect()
        except Exception as e:
            print(f"Error disconnecting MQTT: {e}")
        finally:
            _client = None
    
    # Disconnect WiFi to free up resources for Bluetooth
    print("Disabling WiFi for Bluetooth scan...")
    try:
        wifi.disconnect()
        time.sleep(0.5)
    except Exception as e:
        print(f"Error disconnecting WiFi: {e}")
    
    # Perform BMS scan using asyncio
    try:
        rgb.write(num=1, R=255, G=255, B=0)  # Yellow LED for BMS scanning
        success = asyncio.run(read_bms_data_async())
        if success:
            print("BMS scan completed successfully")
            # Publish BMS data when WiFi comes back up
        else:
            print("BMS scan failed")
    except Exception as e:
        print(f"Error during BMS scan: {e}")
        import sys
        sys.print_exception(e)
    finally:
        rgb.write(num=1, R=0, G=0, B=0)
    
    # Re-enable WiFi
    print("Re-enabling WiFi...")
    time.sleep(1)  # Give Bluetooth time to fully shutdown
    try:
        ipcfg = wifi_connect_non_blocking(WIFI_SSID, WIFI_PASSWORD, timeout_s=10)
        if ipcfg:
            print("WiFi reconnected after BMS scan")
        else:
            print("WiFi reconnection failed, will retry later")
    except Exception as e:
        print(f"Error reconnecting WiFi: {e}")
    
    # Update last scan time
    _last_bms_scan_ms = time.ticks_ms()
    
    print("BMS scan cycle completed")
    print("="*50 + "\n")


def maybe_scan_bms():
    """Check if it's time to scan BMS (every 5 minutes)"""
    global _last_bms_scan_ms
    
    now = time.ticks_ms()
    interval_ms = BMS_SCAN_INTERVAL_SECONDS * 1000
    
    # Check if enough time has passed
    if time.ticks_diff(now, _last_bms_scan_ms) < interval_ms:
        return
    
    # Time to scan BMS
    scan_bms_with_wifi_management()


def main():
    global count, wifi, gauge, gauge_hum, gauge_bms_voltage, gauge_bms_soc, screen_status, _last_bms_scan_ms
    
    wifi = WiFi()
    
    # Initialize screen regardless of connectivity
    screen.init(dir=2)
    screen.show_bg(color=0x000000)
    screen.set_width(width=2)
            
    version = screen.print_lvgl_version()
    screen.draw_text(text=f"Starting. {version}", x=1, y=1, font_size=16, color=0x008000)
    screen.show_draw()

    # Try initial WiFi (non-fatal if it fails)
    ipcfg = wifi_connect_non_blocking(WIFI_SSID, WIFI_PASSWORD, timeout_s=8)
    if ipcfg:
        print("WiFi connected. IF config:", ipcfg)
        screen.draw_text(text="WiFi connected.", x=1, y=80, font_size=16, color=0x008000)
        screen.show_draw()
    else:
        print("Starting offline; will retry WiFi in background.")

    # Try initial MQTT if WiFi is up (non-fatal)
    global _client
    if wifi.status():
        _client = mqtt_connect_and_subscribe()
        if _client is None:
            print("MQTT not available now; running offline.")
        else:
            screen.draw_text(text="MQTT connected.", x=1, y=120, font_size=16, color=0x008000)
            screen.show_draw()
            
    # Init Camera
    camera.init()

    screen.draw_text(text="Camera init done", x=1, y=160, font_size=16, color=0x008000)
    screen.show_draw()
            
    screen.clear()
    
    # Show GUI elements - 4 gauges
    gauge = screen.create_gauge(x=0, y=0, height=40, width=120, min_val=0, max_val=40)
    gauge_hum = screen.create_gauge(x=120, y=0, height=40, width=120, min_val=0, max_val=100)
    gauge_bms_voltage = screen.create_gauge(x=0, y=80, height=40, width=120, min_val=0, max_val=60)
    gauge_bms_soc = screen.create_gauge(x=120, y=80, height=40, width=120, min_val=0, max_val=100)
    
    # Initialize BMS scan timer
    _last_bms_scan_ms = time.ticks_ms() - (BMS_SCAN_INTERVAL_SECONDS * 1000) + 10000  # Scan after 10 seconds
    
    while True:
        try:
            # Background reconnection attempts
            maybe_reconnect_wifi()
            maybe_connect_mqtt()
            
            # Check if it's time to scan BMS (every 5 minutes)
            maybe_scan_bms()

            # Handle incoming MQTT if connected
            if _client is not None:
                try:
                    rgb.write(num=2, R=255, G=0, B=0)
                    _client.check_msg()
                    
                    # Publish BMS data if available and not published yet
                    if bms_data is not None:
                        publish_bms_data()
                        
                except Exception as e:
                    print("MQTT check_msg error:", e)
                    try:
                        _client.disconnect()
                    except Exception:
                        pass
                    _client = None
                finally:
                    rgb.write(num=2, R=0, G=0, B=0)

            # Always update UI/sensors
            if screen_status == "on":
                print_sensor_values()
            else:
                print("Screen is off.")
                
            publish_values()
            time.sleep(5)
            count += 1
        except Exception as e:
            print("Main loop error:", e)
            time.sleep(1)
            
        
if __name__ == "__main__":
    main()
