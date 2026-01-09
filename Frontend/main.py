import time
import network
import ubinascii
from machine import unique_id
from umqtt.simple import MQTTClient
import ujson as json
import gc

from unihiker_k10 import screen
from unihiker_k10 import temp_humi
from unihiker_k10 import light
from unihiker_k10 import rgb
from unihiker_k10 import button
from unihiker_k10 import mic, speaker
#from unihiker_k10 import camera
import camera
from unihiker_k10 import acce

import asyncio
import aioble
import bluetooth

import lvgl as lv

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
_bms_data_published = True  # Flag to track if current BMS data has been published

# Values
hum = None
temp = None
lux = None
count = 0
bms_count = 0
bms_data = None

# GUI Element
gauge_temp = None
gauge_hum = None
gauge_bms_voltage = None
gauge_bms_soc = None
arc_ampere = None

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
    camera.init(0, framesize=camera.FRAME_QVGA, format=camera.RGB565, fb_location=camera.PSRAM)

def button_b_released():
    print("button_b_released")

bt_a.event_pressed = button_a_pressed
bt_a.event_released = button_a_released
bt_b.event_pressed = button_b_pressed
bt_b.event_released = button_b_released

def get_ampere_color(ampere):
    """
    Calculate color based on ampere value for arc display.
    Red for negative values (left side), green for positive values (right side).

    Args:
        ampere: Current in amperes

    Returns:
        Color value in hex format (0xRRGGBB)
    """
    if ampere < 0:
        # Red for negative values (left side)
        return 0xFF0000  # Pure red
    else:
        # Green for positive values (right side)
        return 0x00FF00  # Pure green

def create_ampere_arc(x=60, y=100, radius=80, min_val=-10, max_val=10):
    """
    Create and display an LVGL arc widget for ampere measurement.
    Center at 0A, negative values (red) on left, positive values (green) on right.

    Args:
        x: X position of arc center on screen
        y: Y position of arc center on screen
        radius: Radius of the arc
        min_val: Minimum ampere value (default: -10)
        max_val: Maximum ampere value (default: 10)

    Returns:
        Dictionary containing the arc widget and range values
        {'arc': lv.arc, 'label': lv.label, 'min_val': int, 'max_val': int}
    """
    # Create an arc widget
    arc = lv.arc(lv.screen_active())

    # Set position and size (arc is positioned by its center)
    arc.set_pos(x - radius, y - radius)
    arc.set_size(radius * 2, radius * 2)

    # Set the value range (min and max ampere values)
    arc.set_range(min_val, max_val)

    # Set initial value to 0 (center)
    arc.set_value(0)

    # Configure arc angles for a semicircle (180 degrees)
    # LVGL angles are in degrees, 0° is at 3 o'clock, increasing clockwise
    # For a semicircle centered at bottom, we want 0° to 180°
    arc.set_bg_angles(0, 180)  # Background arc from 0° to 180°

    # Set the arc to show the value range from min to current value
    arc.set_angles(0, 180)  # Initially show full range

    # Create a label to display the current ampere value
    label = lv.label(lv.screen_active())
    label.set_text("0.0 A")
    label.set_style_text_color(lv.color_white(), 0)

    label.set_style_text_font(lv.font_montserrat_16, 0)
    font_height = 16

    # Position label at the center bottom of the arc
    label.set_pos(x - 20, y + radius - font_height - 40)

    return {'arc': arc, 'label': label, 'min_val': min_val, 'max_val': max_val}

def set_ampere_arc_value(arc_dict, value, animated=True):
    """
    Set the current ampere value of an arc and update the display.

    Args:
        arc_dict: The dictionary returned by create_ampere_arc containing 'arc', 'label', 'min_val', 'max_val'
        value: The numerical ampere value to set
        animated: Whether to animate the value change (default: True)
    """
    arc = arc_dict['arc']
    label = arc_dict['label']
    min_val = arc_dict['min_val']
    max_val = arc_dict['max_val']

    # Ensure value is within range
    value = max(min_val, min(max_val, value))

    # Update arc value
    anim_enable = lv.ANIM.ON if animated else lv.ANIM.OFF
    arc.set_value(value)

    # Set arc color based on value (red for negative, green for positive)
    color = get_ampere_color(value)
    arc.set_style_arc_color(lv.color_hex(color), lv.PART.INDICATOR)

    # Update label text with formatted ampere value
    if abs(value) < 10:
        label_text = f"{value:.1f} A"
    else:
        label_text = f"{value:.0f} A"
    label.set_text(label_text)

    # Set label color to match arc color
    label.set_style_text_color(lv.color_hex(color), 0)


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
        write_status_line("Publishing done.")

    except Exception as e:
        print(f"Error publishing: {e}")
        success = False

def publish_bms_data():
    global bms_data, _client, _bms_data_published

    if bms_data is None or _client is None:
        return False

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
        _bms_data_published = True
        write_status_line("BMS publishing done.")
        return True

    except Exception as e:
        print(f"Error publishing BMS data: {e}")
        return False

def take_and_send_photo():
    print("Taking photo...")
    write_status_line("Taking photo...")
    image_header = b"data:image/jpeg;base64,"

    try:
        # White balance may not work on first capture
        camera.capture()
        time.sleep(0.1)
        camera.capture()
        time.sleep(0.1)
        buffer = camera.capture()

        jpeg_buf = camera.encode_jpeg(buffer, quality=50)

        base64_picture = ubinascii.b2a_base64(jpeg_buf)

        if _client is not None:
            try:
                print("Sending Photo...")
                write_status_line("Sending Photo...")
                _client.publish(MQTT_TOPIC_PUB, image_header + base64_picture)
                print("Photo sent. Size =", len(base64_picture))
            except Exception as e:
                print("MQTT publish failed:", e)
        else:
            print("No MQTT client; photo not sent.")
    except Exception as e:
        print("Camera error:", e)

def wifi_connect_non_blocking(wlan, ssid, password, timeout_s=20):
    """Connect to WiFi using standard MicroPython network module"""
    print("Connecting to:", ssid)

    if not wlan.active():
        wlan.active(True)

    wlan.connect(ssid, password)

    # Wait for connection with timeout
    start_time = time.time()
    while not wlan.isconnected() and (time.time() - start_time) < timeout_s:
        time.sleep(0.5)

    if wlan.isconnected():
        return wlan.ifconfig()
    else:
        return None

def on_mqtt_message(topic, msg):
    rgb.write(num=1, R=0, G=0, B=255)
    try:
        print(
            "MQTT message on topic:",
            topic.decode() if isinstance(topic, bytes) else topic,
        )

        write_status_line("MQTT message")

        if topic.decode() == "unihiker/takephoto":
            take_and_send_photo()
        else:
            data = json.loads(msg.decode() if isinstance(msg, bytes) else msg)
            act_power = data.get("act_power", 0)
            print(act_power)

            # cast to INT ?
            set_ampere_arc_value(arc_ampere, act_power)

    # gauge = VerticalGauge(
            #     x=0, y=100, width=70, height=200, min_value=-200, max_value=200
            # )
            # gauge.set_value(act_power)
            # gauge.draw()
            # screen.show_draw()
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
        # Subscribe to multiple topics
        topics = ["unihiker/takephoto", MQTT_TOPIC_SUB]
        client.subscribe(topics)
        print("Connected to MQTT and subscribed to:", topics)
        return client
    except Exception as e:
        print("MQTT connect/subscribe failed:", e)
        return None

def toggle_light():
    global light_status
    write_status_line("Toggle light")
    try:
        if light_status == "off":
            light_status = "on"
        else:
            light_status = "off"

        _client.publish("shellyplug/command/switch:0", light_status)

    except Exception as e:
        print(f"Error publishing: {e}")

def print_sensor_values():
    global hum, temp, count, gauge_temp, gauge_hum, gauge_bms_voltage, gauge_bms_soc, bms_data

    write_status_line("Getting sensor data.")

    try:
        temp = temp_humi.read_temp() - temp_adjustment
    except Exception:
        temp = None
    try:
        hum = temp_humi.read_humi() + hum_adjustment
    except Exception:
        hum = None

    screen.set_gauge_value(gauge_temp, int(temp), text=f"{temp:.2f} C")
    screen.set_gauge_value(gauge_hum, int(hum ), text=f"{hum:.2f} %", gauge_type="humidity")

    # Update BMS gauges if data is available
    if bms_data is not None:
        voltage = bms_data.voltage if bms_data.voltage > 0 else bms_data.calculated_voltage
        soc = bms_data.calculated_soc_voltage if bms_data.calculated_soc_voltage > 0 else bms_data.soc

        screen.set_gauge_value(gauge_bms_voltage, int(voltage), text=f"{voltage:.1f} V")
        screen.set_gauge_value(gauge_bms_soc, int(soc), text=f"{soc:.0f} %", gauge_type="soc")

    screen.show_draw()

def maybe_reconnect_wifi():
    global _last_wifi_check_ms, wlan
    now = time.ticks_ms()
    if time.ticks_diff(now, _last_wifi_check_ms) < _wifi_check_interval_ms:
        return

    _last_wifi_check_ms = now

    if wlan.isconnected():
        return

    print("WiFi not connected. Attempting reconnect...")
    ipcfg = wifi_connect_non_blocking(wlan, WIFI_SSID, WIFI_PASSWORD, timeout_s=5)
    if ipcfg:
        print("WiFi connected. IF config:", ipcfg)
    else:
        print("Still offline (WiFi).")

def maybe_connect_mqtt():
    global _client, _last_mqtt_check_ms, wlan
    if _client is not None:
        return

    now = time.ticks_ms()
    if time.ticks_diff(now, _last_mqtt_check_ms) < _mqtt_check_interval_ms:
        return
    _last_mqtt_check_ms = now

    if not wlan.isconnected():
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
    global bms_data, _bms_data_published
    write_status_line("Read BMS data.")

    new_bms_data = BMSData()

    # Find BMS device
    device = await find_bms_device(BMS_DEVICE_NAME, timeout_ms=50000)
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
            write_status_line("Discovering services...")

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
                write_status_line("Getting Cell Voltages.")
                await rx_char.write(CMD_CELL_VOLTAGES, response=False)
                try:
                    data = await asyncio.wait_for(tx_char.notified(), timeout=5.0)
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
                write_status_line("Getting Basic Info.")
                await rx_char.write(CMD_BASIC_INFO, response=False)

                try:
                    # Get first notification
                    data = await asyncio.wait_for(tx_char.notified(), timeout=2.0)
                    print(f"Received {len(data)} bytes")

                    # Check for expected DD 03 header
                    if data[0] == 0xDD and data[1] == 0x03:
                        print("Header matches DD 03, attempting to parse...")
                        new_bms_data.parse_basic_info(data)
                        break
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

            # Update global BMS data and mark as not published yet
            bms_data = new_bms_data
            _bms_data_published = False  # Reset flag - new data needs to be published
            print("New BMS data ready for publishing")

            return True

    except Exception as e:
        print(f"Error reading BMS data: {e}")
        write_status_line("Error BMS data.")
        import sys
        sys.print_exception(e)
        return False


def scan_bms_with_wifi_management():
    """Scan BMS with WiFi disabled, then re-enable WiFi"""
    global wlan, _client, _last_bms_scan_ms, bms_count

    print("\n" + "="*50)
    print("Starting BMS scan cycle")
    print("="*50)
    write_status_line("Starting BMS scan cycle")

    # free memory if possible
    gc.collect()

    # # Disconnect MQTT if connected
    # if _client is not None:
    #     try:
    #         print("Disconnecting MQTT...")
    #         _client.disconnect()
    #         print("done")
    #     except Exception as e:
    #         print(f"Error disconnecting MQTT: {e}")
    #     finally:
    #         _client = None
    #
    # # Enhanced WiFi shutdown for ESP32 Bluetooth/WiFi coexistence
    # print("Performing thorough WiFi shutdown for Bluetooth...")
    # try:
    #     # Multiple disconnection attempts to ensure WiFi is fully off
    #     for attempt in range(3):
    #         try:
    #             if wlan.isconnected():
    #                 print(f"  Disconnect attempt {attempt + 1}/3...")
    #                 wlan.disconnect()
    #                 time.sleep(0.5)
    #             else:
    #                 print("  WiFi already disconnected")
    #                 break
    #         except Exception as e:
    #             print(f"  Disconnect attempt {attempt + 1} error: {e}")
    #             time.sleep(0.3)
    #
    #     # Deactivate WiFi radio
    #     print("  Deactivating WiFi radio...")
    #     wlan.active(False)
    #
    #     # Extended cooldown period for ESP32 radio stabilization
    #     # This is critical for Bluetooth to work after WiFi was active
    #     print("  Waiting for radio stabilization (3 seconds)...")
    #     time.sleep(3)
    #
    #     print(f"Final WiFi result {wlan.active}")
    #
    #     print("WiFi shutdown complete - radio ready for Bluetooth")
    # except Exception as e:
    #     print(f"Error during WiFi shutdown: {e}")
    #     # Still try to proceed with Bluetooth
    #     time.sleep(3)

    # Perform BMS scan using asyncio
    try:
        rgb.write(num=1, R=255, G=255, B=0)  # Yellow LED for BMS scanning
        print("Starting Bluetooth scan...")
        write_status_line("Starting Bluetooth scan.")

        success = asyncio.run(read_bms_data_async())
        if success:
            print("BMS scan completed successfully")
            # Publish BMS data when WiFi comes back up
        else:
            print("BMS scan failed - will retry on next cycle")
    except Exception as e:
        print(f"Error during BMS scan: {e}")
        import sys
        sys.print_exception(e)
    finally:
        bms_count = bms_count + 1
        rgb.write(num=1, R=0, G=0, B=0)

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

def write_status_line(text):
    global count, bms_count
    global status_label
    status_label.set_text(f"{text} {count}-{bms_count}")

def create_gui_elements():
    global status_label, gauge_temp, gauge_hum, gauge_bms_voltage, gauge_bms_soc, arc_ampere

    # Initialize screen regardless of connectivity
    screen.init(dir=2)
    screen.show_bg(color=0x000000)
    screen.set_width(width=2)

    # Show GUI elements - 4 gauges
    gauge_temp = screen.create_gauge(x=40, y=0, height=35, width=200, min_val=0, max_val=40)
    gauge_hum = screen.create_gauge(x=40, y=50, height=35, width=200, min_val=0, max_val=100)
    gauge_bms_voltage = screen.create_gauge(x=40, y=100, height=35, width=200, min_val=0, max_val=15)
    gauge_bms_soc = screen.create_gauge(x=40, y=150, height=35, width=200, min_val=0, max_val=100)

    # Ampere meter
    arc_ampere = create_ampere_arc(x=120, y=210, radius=70, min_val=-10, max_val=10)

    scr = lv.screen_active()

    # Create a label
    status_label = lv.label(scr)
    # Set long text display mode. For more parameters, see the "class LONG_MODE" section in api.py
    #label.set_long_mode(label.LONG_MODE.SCROLL_CIRCULAR)
    # Set the display width and height of the label
    status_label.set_size(240, 20)
    # Set the label content
    #status_label.set_text('HELLO MicroPython LVGL')
    # Align the label to the center of the container and offset upward by 50. For more parameters, see the "class ALIGN" section in api.py
    status_label.align(lv.ALIGN.CENTER, 0, 150)

    style_label = lv.style_t()
    # Text color
    #style_label.set_text_color(lv.color_hex(0xFF0000))
    # Set font (supports 12, 14, 16)
    style_label.set_text_font(lv.font_montserrat_12)
    # Apply as the default state style. For more states, see the "class STATE" section in api.py
    status_label.add_style(style_label, lv.STATE.DEFAULT)

    label_gauge_temp = lv.label(scr)
    label_gauge_temp.set_size(40, 20)
    label_gauge_temp.set_text('Tmp:')
    label_gauge_temp.align(lv.ALIGN.LEFT_MID, 0, -140)

    style_label = lv.style_t()
    #style_label.set_text_color(lv.color_hex(0xFF0000))
    # Set font (supports 12, 14, 16)
    style_label.set_text_font(lv.font_montserrat_12)
    label_gauge_temp.add_style(style_label, lv.STATE.DEFAULT)

    label_gauge_hum = lv.label(scr)
    label_gauge_hum.set_size(40, 20)
    label_gauge_hum.set_text('Hum:')
    label_gauge_hum.align(lv.ALIGN.LEFT_MID, 0, -90)
    label_gauge_hum.add_style(style_label, lv.STATE.DEFAULT)

    label_gauge_voltage = lv.label(scr)
    label_gauge_voltage.set_size(40, 20)
    label_gauge_voltage.set_text('Bat:')
    label_gauge_voltage.align(lv.ALIGN.LEFT_MID, 0, -40)
    label_gauge_voltage.add_style(style_label, lv.STATE.DEFAULT)

    label_gauge_soc = lv.label(scr)
    label_gauge_soc.set_size(40, 20)
    label_gauge_soc.set_text('Soc:')
    label_gauge_soc.align(lv.ALIGN.LEFT_MID, 0, 10)
    label_gauge_soc.add_style(style_label, lv.STATE.DEFAULT)

def printFreeMem():
    free_mem = gc.mem_free()
    free_mem_kb = free_mem // 1024
    print(f"{free_mem_kb}KB")

def main():
    global count, wlan, screen_status, _last_bms_scan_ms

    printFreeMem()

    create_gui_elements()

    gc.enable()

    # Init Camera
    #camera.init()

    version = screen.print_lvgl_version()
    write_status_line(f"Starting. {version}")

    # Initialize WiFi using standard MicroPython network module
    wlan = network.WLAN(network.STA_IF)

    # Try initial WiFi (non-fatal if it fails)
    # ipcfg = wifi_connect_non_blocking(wlan, WIFI_SSID, WIFI_PASSWORD, timeout_s=8)
    # if ipcfg:
    #     print("WiFi connected. IF config:", ipcfg)
    #     screen.draw_text(text="WiFi connected.", x=1, y=80, font_size=16, color=0x008000)
    #     screen.show_draw()
    # else:
    #     print("Starting offline; will retry WiFi in background.")
    #
    # # Try initial MQTT if WiFi is up (non-fatal)
    global _client
    # if wlan.isconnected():
    #     _client = mqtt_connect_and_subscribe()
    #     if _client is None:
    #         print("MQTT not available now; running offline.")
    #     else:
    #         screen.draw_text(text="MQTT connected.", x=1, y=120, font_size=16, color=0x008000)
    #         screen.show_draw()

    # Initialize BMS scan timer
    _last_bms_scan_ms = time.ticks_ms() - (BMS_SCAN_INTERVAL_SECONDS * 1000) + 10000  # Scan after 10 seconds

    while True:
        try:
            printFreeMem()
            # Check if it's time to scan BMS (every 5 minutes)
            maybe_scan_bms()

            # Background reconnection attempts
            maybe_reconnect_wifi()
            maybe_connect_mqtt()

            # Handle incoming MQTT if connected
            if _client is not None:
                try:
                    rgb.write(num=2, R=255, G=0, B=0)
                    _client.check_msg()

                    # Publish BMS data if available and not published yet
                    if bms_data is not None and not _bms_data_published:
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

            #if screen_status == "on":
            print_sensor_values()
            #else:
            #    print("Screen is off.")
            publish_values()

            # Display free memory at the end of the main loop
            # try:
            #     free_mem = gc.mem_free()
            #     free_mem_kb = free_mem // 1024
            #     # Clear the area before drawing new text
            #     screen.draw_rect(x=1, y=295, w=240, h=27, fcolor=0x000000)
            #     screen.draw_text(text=f"{free_mem_kb}KB, {count}", x=1, y=295, font_size=12, color=0xFFFF00)
            # except Exception as e:
            #     screen.draw_rect(x=1, y=295, w=240, h=27, fcolor=0x000000)
            #     screen.draw_text(text="Free Mem: N/A", x=1, y=295, font_size=12, color=0xFFFF00)

            screen.show_draw()
            time.sleep(5)
            count += 1
        except Exception as e:
            print("Main loop error:", e)
            time.sleep(1)


if __name__ == "__main__":
    main()
