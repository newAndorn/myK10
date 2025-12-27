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
from k10_base._k10_base import BMS
from BMS import BMS_new, BMSData

import _thread
import lvgl as lv

from gauge_old import VerticalGauge
from textBox import TextBox

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

bt_a = button(button.a)
bt_b = button(button.b)

_client = None
_last_wifi_check_ms = 0
_last_mqtt_check_ms = 0
_wifi_check_interval_ms = 5000
_mqtt_check_interval_ms = 5000

# Values
hum = None
temp = None
lux = None
count = 0

# GUI Element
gauge = None
gauge_hum = None

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
    
    devices = BMS.scan_devices(duration=5)
    
    
#    global screen_status
    
#    print("button_b_pressed")
#     try:
#         print("begin sys play")
#         speaker.play_sys_music("sound.wav")
#     except Exception as e:
#         print("speaker error:", e)
#     print("end sys play")
    
#    if screen_status == "off":
#        screen_status = "on"
#    else:
#        screen_status = "off"
#        print("clear screen.")
#        screen.clear()

def button_b_released():
    print("button_b_released")


# Global BMS watcher instance
_bms_watcher = None
_bms_last_data = None


def on_bms_data_received(bms_data):
    """
    Callback function called when BMS data is received from advertisement.
    
    Args:
        bms_data: BMSData object containing parsed battery information
    """
    global _bms_last_data
    _bms_last_data = bms_data
    
    print(f"BMS Data Received:")
    print(f"  Voltage: {bms_data.voltage:.2f}V")
    print(f"  Current: {bms_data.current:.2f}A")
    print(f"  Power: {bms_data.power:.2f}W")
    print(f"  SOC: {bms_data.capacity_percent}%")
    print(f"  Temp1: {bms_data.temp1:.1f}°C")
    print(f"  RSSI: {bms_data.rssi}dBm")
    
    if bms_data.raw_data:
        print(f"  Raw: {bms_data.raw_data.hex()}")
    
    # Optionally publish BMS data via MQTT
    if _client is not None:
        try:
            bms_mqtt_data = {
                "bms": {
                    "voltage": bms_data.voltage,
                    "current": bms_data.current,
                    "power": bms_data.power,
                    "soc": bms_data.capacity_percent,
                    "temp1": bms_data.temp1,
                    "temp2": bms_data.temp2,
                    "rssi": bms_data.rssi
                }
            }
            _client.publish(b"unihiker/bms", json.dumps(bms_mqtt_data))
        except Exception as e:
            print(f"Error publishing BMS data: {e}")


def watch_bluetooth_data(device_name="0421150164", poll_interval=5, use_advertisements=True):
    """
    Watch bluetooth data from a BLE device using BMS_new class.
    
    Args:
        device_name: The name of the BLE device to connect to (default: "0421150164")
        poll_interval: Seconds between data requests (default: 5)
        use_advertisements: If True, watch advertisement data (passive scan).
                           If False, connect via GATT for detailed data.
    
    Returns:
        BMS_new instance that is watching the device
    """
    global _bms_watcher
    
    print(f"Starting bluetooth watch for device: {device_name}")
    print(f"  Mode: {'Advertisement scanning' if use_advertisements else 'GATT connection'}")
    
    # Create BMS_new instance with the device name and callback
    _bms_watcher = BMS_new(
        name=device_name,
        poll_interval=poll_interval,
        on_data_callback=on_bms_data_received
    )
    
    # Start watching bluetooth data
    if use_advertisements:
        # Watch advertisement data (passive, no connection needed)
        _bms_watcher.start_advertisement_watch()
    else:
        # Connect via GATT for detailed BMS data
        _bms_watcher.start()
    
    print(f"Bluetooth watcher started for device: {device_name}")
    return _bms_watcher


def stop_bluetooth_watch():
    """
    Stop the bluetooth BMS watcher.
    """
    global _bms_watcher
    if _bms_watcher:
        _bms_watcher.stop()
        print("Bluetooth watcher stopped")
    else:
        print("No bluetooth watcher running")


def get_bms_data():
    """
    Get the last received BMS data.
    
    Returns:
        BMSData object or None if no data received yet
    """
    global _bms_last_data, _bms_watcher
    if _bms_watcher:
        return _bms_watcher.last_data
    return _bms_last_data


def publish_values():
    global hum, temp, count, _client
    
    try:
        success = True
            
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
    
def take_and_send_photo():    
    print("Taking photo...")
    image_header = b"data:image/jpeg;base64,"
    
    try:
        
        # White balance may not work on first capture
        buffer = camera.capture()
        time.sleep(0.1)
        buffer = camera.capture()
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


bt_a.event_pressed = button_a_pressed
bt_a.event_released = button_a_released
bt_b.event_pressed = button_b_pressed
bt_b.event_released = button_b_released

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
    global hum, temp, count, gauge, gauge_hum
    
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

def read_bms_once(device_name="0421150164", timeout=30):
    """
    Read BMS data once (blocking) and disable Bluetooth when done.
    
    Args:
        device_name: Name of the BMS device
        timeout: Maximum time to wait for data
        
    Returns:
        BMSData object or None if failed
    """
    global _bms_last_data
    
    print("=" * 40)
    print("Reading BMS data from device: %s" % device_name)
    print("=" * 40)
    
    # Create BMS instance and read data once
    bms = BMS_new(name=device_name)
    data = bms.read_once(timeout=timeout)
    
    if data:
        _bms_last_data = data
        print("BMS data retrieved successfully:")
        print("  Voltage: %.2fV" % data.voltage)
        print("  Current: %.2fA" % data.current)
        print("  Power: %.2fW" % data.power)
        print("  SOC: %d%%" % data.capacity_percent)
        print("  Temp: %.1f°C" % data.temp1)
    else:
        print("Failed to read BMS data")
    
    # Disable Bluetooth to free resources for WiFi
    print("Disabling Bluetooth...")
    BMS_new.disable_bluetooth()
    time.sleep(0.5)  # Give time for BLE to fully stop
    
    print("=" * 40)
    return data


def main():
    global count, wifi, gauge, gauge_hum, screen_status, _bms_last_data
    
    # ===== PHASE 1: Read BMS data via Bluetooth =====
    # Must do this BEFORE starting WiFi (ESP32 limitation)
    print("Phase 1: Reading BMS data...")
    bms_data = read_bms_once("0421150164", timeout=30)
    
    if bms_data:
        print("BMS: %.2fV, %d%% SOC" % (bms_data.voltage, bms_data.capacity_percent))
    else:
        print("BMS: No data (device not found or timeout)")
    
    # ===== PHASE 2: Start WiFi and normal program =====
    print("\nPhase 2: Starting WiFi and main program...")
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
    
    # show gui elements
    gauge = screen.create_gauge(height=40, width=240, min_val=0, max_val=40)
    gauge_hum = screen.create_gauge(x=0, y= 80, height=40, width=240, min_val=0, max_val=100)
            
    while True:
        try:
            # Background reconnection attempts
            maybe_reconnect_wifi()
            maybe_connect_mqtt()

            # Handle incoming MQTT if connected
            if _client is not None:
                try:
                    rgb.write(num=2, R=255, G=0, B=0)
                    _client.check_msg()
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
