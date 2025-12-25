class BMS:
    """
    Xiaoxiang/JBD BMS watcher over BLE (central mode).
    Provides scanning, start, and stop helpers for console logging.
    """

    # Typical BLE UART characteristic UUID used by many Xiaoxiang/JBD BMS modules.
    # Adjust if your module uses a different UUID.
    UART_UUID_STR = "0000ffe1-0000-1000-8000-00805f9b34fb"

    # Basic status request frame used by many Xiaoxiang/JBD BMS (from open-source tools).
    REQUEST_FRAME = b"\xDD\xA5\x03\x00\xFF\xFD\x77"

    def __init__(self, name=None, addr=None, poll_interval=5):
        """
        Create a BMS watcher.

        Args:
            name: BLE device name to match (bytes). Required if addr is not provided.
                  Example: name=b"JBD-BMS-1234"
            addr: BLE address (bytes). If provided, takes precedence over name.
                  Example: addr=bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
            poll_interval: Seconds between request frames (default: 5).
        """
        self.name = name
        self.addr = addr
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None

    @staticmethod
    def scan_devices(duration=5):
        """
        Scan for BLE devices to find your BMS name and address.

        Args:
            duration: Scan duration in seconds (default: 5)

        Returns:
            List of tuples (name, addr_type, addr) for discovered devices
        """
        print("BMS scan_devices called")
        try:
            import bluetooth
            from mpython_ble.advertising import decode_name
            from mpython_ble.const import IRQ
        except Exception as e:
            print("BLE scan: modules not available:", e)
            return []

        ble = bluetooth.BLE()
        ble.active(True)

        devices = []

        def _irq(event, data):
            if event == IRQ.IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                if isinstance(adv_data, memoryview):
                    adv_data = bytes(adv_data)
                addr_hex = bytes(addr).hex()
                print(f"\nDevice found - Addr: {addr_hex}, Type: {adv_type}, RSSI: {rssi}dBm")
                print(f"Raw adv_data: {adv_data}")
                
                # Print adv_data in hex for inspection
                print("adv_data hex:", " ".join(f"{b:02x}" for b in adv_data))
                
                # Try to parse the advertising data
                i = 0
                while i < len(adv_data):
                    length = adv_data[i]
                    if length == 0 or i + length > len(adv_data):
                        break
                        
                    adv_type = adv_data[i + 1]
                    adv_data_start = i + 2
                    adv_data_end = i + 1 + length
                    adv_data_bytes = adv_data[adv_data_start:adv_data_end]
                    if isinstance(adv_data_bytes, memoryview):
                        adv_data_bytes = bytes(adv_data_bytes)
                    
                    print(f"  AD Type: 0x{adv_type:02x}, Length: {length-1}, Data: {adv_data_bytes.hex()}")
                    
                    # Common AD Types
                    if adv_type == 0x01:  # Flags
                        print("    - Flags:", " ".join(f"{b:08b}" for b in adv_data_bytes))
                    elif adv_type == 0x08:  # Shortened Local Name
                        try:
                            print(f"    - Short Name: {adv_data_bytes.decode('ascii', errors='replace')}")
                        except Exception as e:
                            print(f"    - Short Name (decode error): {e}")
                    elif adv_type == 0x09:  # Complete Local Name
                        try:
                            print(f"    - Complete Name: {adv_data_bytes.decode('ascii', errors='replace')}")
                        except Exception as e:
                            print(f"    - Complete Name (decode error): {e}")
                    elif adv_type == 0xFF:  # Manufacturer Specific Data
                        print(f"    - Manufacturer Data: {adv_data_bytes.hex()}")
                    
                    i += 1 + length  # Move to next AD structure
                
                # Original name decoding for compatibility
                name = decode_name(adv_data)
                if isinstance(name, (memoryview, bytes)):
                    try:
                        if isinstance(name, memoryview):
                            name = bytes(name)
                        name = name.decode('utf-8', errors='ignore').rstrip('\x00')
                    except Exception as e:
                        print(f"Name decode error: {e}")
                        name = None
                
                addr_bytes = bytes(addr)
                if not any(d[2] == addr_bytes for d in devices):
                    if name and name.strip():
                        print(f"  Found: {name} (RSSI: {rssi})")
                        devices.append((name, addr_type, addr_bytes))
                    else:
                        print(f"  Found: <no name> (RSSI: {rssi}) at {addr_hex}")
                        devices.append((f"<no name>", addr_type, addr_bytes))

        ble.irq(_irq)
        print(f"Scanning for BLE devices for {duration} seconds...")
        ble.gap_scan(int(duration * 1000), 30000, 30000)
        time.sleep(duration + 0.5)
        ble.gap_scan(None)  # Stop scanning
        ble.active(False)

        print(f"Scan complete. Found {len(devices)} device(s)")
        return devices

    def _watch_loop(self):
        """
        Internal background loop: connects to the BMS over BLE and periodically
        sends a request frame, printing any responses to the console.
        """
        try:
            from mpython_ble.application.centeral import Centeral
            from bluetooth import UUID
        except Exception as e:
            print("BMS watch: BLE modules not available:", e)
            self._running = False
            return

        if self.name is None and self.addr is None:
            print("BMS watch: ERROR - provide either 'name' or 'addr'")
            self._running = False
            return

        center = Centeral()

        print("BMS watch: scanning for device...")
        if self.name:
            print("  Name:", self.name)
        if self.addr:
            if isinstance(self.addr, (bytes, bytearray)):
                print("  Address:", self.addr.hex())
            else:
                print("  Address:", self.addr)

        profile = center.connect(name=self.name, addr=self.addr)
        if profile is None:
            print("BMS watch: failed to find or connect to BMS")
            self._running = False
            return

        print("BMS watch: connected, discovering UART characteristic...")

        uart_char = None
        uart_uuid = UUID(self.UART_UUID_STR)

        for service in profile.services:
            for ch in service.characteristics:
                try:
                    if ch.uuid == uart_uuid:
                        uart_char = ch
                        break
                except Exception:
                    if str(ch.uuid).lower() == self.UART_UUID_STR:
                        uart_char = ch
                        break
            if uart_char:
                break

        if uart_char is None:
            print("BMS watch: UART characteristic not found (UUID", self.UART_UUID_STR, ")")
            self._running = False
            center.disconnect()
            return

        print("BMS watch: using characteristic handle", uart_char.value_handle)

        def _notify_cb(value_handle, data):
            print("BMS notify (handle", value_handle, "):", data.hex())

        center.notify_callback(_notify_cb)

        print("BMS watch: starting polling loop (interval:", self.poll_interval, "s)")

        while self._running and center.is_connected():
            try:
                center.characteristic_write(uart_char.value_handle, self.REQUEST_FRAME)
            except Exception as e:
                print("BMS watch: write failed:", e)
                break
            time.sleep(self.poll_interval)

        print("BMS watch: stopping, disconnecting...")
        try:
            center.disconnect()
        except Exception:
            pass
        self._running = False

    def start(self):
        """
        Start watching BMS data over BLE and log it to the console.
        """
        if self._running:
            print("BMS watch is already running")
            return

        self._running = True
        try:
            self._thread = _thread.start_new_thread(self._watch_loop, ())
            print("BMS watch: background thread started")
        except Exception as e:
            print("BMS watch: failed to start thread:", e)
            self._running = False

    def stop(self):
        """
        Stop the BMS watch loop. The background thread will exit after the next poll.
        """
        if not self._running:
            print("BMS watch is not running")
            return
        self._running = False
        print("BMS watch: stop requested")