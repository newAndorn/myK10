import time

class BMSData:
    """Data class to hold parsed BMS information."""
    
    def __init__(self):
        self.voltage = 0.0       # Total voltage in V
        self.current = 0.0       # Current in A (positive = charging, negative = discharging)
        self.power = 0.0         # Power in W
        self.capacity_remain_ah = 0.0   # Remaining capacity in Ah
        self.capacity_percent = 0       # State of charge in %
        self.temp1 = 0.0         # Temperature 1 in °C
        self.temp2 = 0.0         # Temperature 2 in °C
        self.num_cells = 0       # Number of cells
        self.cell_voltages = []  # Individual cell voltages in V
        self.cell_max = 0.0      # Highest cell voltage
        self.cell_min = 0.0      # Lowest cell voltage
        self.cell_diff = 0.0     # Cell voltage difference
        self.balance_status = 0  # Balancing status bits
        self.mosfet_status = 0   # MOSFET status byte
        self.rssi = 0            # Signal strength
        self.raw_data = None     # Raw manufacturer data bytes
        
    def __repr__(self):
        return (f"BMSData(voltage={self.voltage:.2f}V, current={self.current:.2f}A, "
                f"soc={self.capacity_percent}%, temp={self.temp1:.1f}°C)")


class BMS_new:
    """
    Xiaoxiang/JBD BMS watcher over BLE (central mode).
    Provides scanning, start, and stop helpers for console logging.
    Supports both advertisement data parsing and GATT connection.
    """

    # Typical BLE UART characteristic UUID used by many Xiaoxiang/JBD BMS modules.
    UART_UUID_STR = "0000ffe1-0000-1000-8000-00805f9b34fb"

    # Basic status request frame used by many Xiaoxiang/JBD BMS (from open-source tools).
    REQUEST_FRAME = b"\xDD\xA5\x03\x00\xFF\xFD\x77"
    
    # JBD BMS packet markers
    PACKET_START = 0xDD
    PACKET_END = 0x77
    
    # Packet types
    TYPE_BASIC_INFO = 0x03
    TYPE_CELL_INFO = 0x04

    def __init__(self, name=None, addr=None, poll_interval=5, on_data_callback=None):
        """
        Create a BMS watcher.

        Args:
            name: BLE device name to match (bytes or str). Required if addr is not provided.
                  Example: name="0421150164" or name=b"JBD-BMS-1234"
            addr: BLE address (bytes). If provided, takes precedence over name.
                  Example: addr=bytes([0x12, 0x34, 0x56, 0x78, 0x9A, 0xBC])
            poll_interval: Seconds between request frames (default: 5).
            on_data_callback: Optional callback function(bms_data) called when data is received.
        """
        if isinstance(name, str):
            self.name = name.encode()
        else:
            self.name = name
        self.name_str = name if isinstance(name, str) else (name.decode() if name else None)
        self.addr = addr
        self.poll_interval = poll_interval
        self.on_data_callback = on_data_callback
        self._running = False
        self._thread = None
        self.last_data = BMSData()

    @staticmethod
    def parse_advertisement_data(adv_data):
        """
        Parse BLE advertisement data into structured components.
        
        Args:
            adv_data: Raw advertisement data bytes
            
        Returns:
            Dictionary with parsed fields: name, flags, uuids, manufacturer_data, etc.
        """
        if isinstance(adv_data, memoryview):
            adv_data = bytes(adv_data)
            
        result = {
            'name': None,
            'flags': None,
            'uuids': [],
            'manufacturer_data': None,
            'service_data': None,
            'tx_power': None,
            'raw': adv_data
        }
        
        i = 0
        while i < len(adv_data):
            if i >= len(adv_data):
                break
            length = adv_data[i]
            if length == 0 or i + length >= len(adv_data):
                break
                
            ad_type = adv_data[i + 1]
            ad_data = adv_data[i + 2:i + 1 + length]
            if isinstance(ad_data, memoryview):
                ad_data = bytes(ad_data)
            
            # Parse by AD type
            if ad_type == 0x01:  # Flags
                result['flags'] = ad_data[0] if len(ad_data) > 0 else 0
            elif ad_type == 0x02 or ad_type == 0x03:  # 16-bit UUIDs
                for j in range(0, len(ad_data), 2):
                    if j + 1 < len(ad_data):
                        uuid16 = ad_data[j] | (ad_data[j + 1] << 8)
                        result['uuids'].append(f"0x{uuid16:04x}")
            elif ad_type == 0x08 or ad_type == 0x09:  # Short/Complete Local Name
                try:
                    result['name'] = ad_data.decode('utf-8', 'ignore').rstrip('\x00')
                except:
                    result['name'] = ad_data.hex()
            elif ad_type == 0xFF:  # Manufacturer Specific Data
                result['manufacturer_data'] = ad_data
            elif ad_type == 0x16:  # Service Data
                result['service_data'] = ad_data
            elif ad_type == 0x0A:  # TX Power Level
                result['tx_power'] = ad_data[0] if len(ad_data) > 0 else 0
                
            i += 1 + length
            
        return result

    @staticmethod
    def parse_jbd_basic_info(data):
        """
        Parse JBD BMS basic info packet data.
        
        Args:
            data: Data bytes (after header, starting at data portion)
            
        Returns:
            BMSData object with parsed values
        """
        bms = BMSData()
        
        if len(data) < 27:  # Minimum expected length for basic info
            return None
            
        try:
            # Parse according to JBD protocol
            # Voltage: bytes 0-1, unit 10mV
            bms.voltage = ((data[0] << 8) | data[1]) * 0.01
            
            # Current: bytes 2-3, signed, unit 10mA
            current_raw = (data[2] << 8) | data[3]
            if current_raw > 32767:
                current_raw -= 65536
            bms.current = current_raw * 0.01
            
            # Capacity remaining: bytes 4-5, unit 10mAh
            bms.capacity_remain_ah = ((data[4] << 8) | data[5]) * 0.01
            
            # Capacity percent: byte 19
            if len(data) > 19:
                bms.capacity_percent = data[19]
            
            # Temperatures: bytes 23-24 and 25-26, unit 0.1K - 2731 (to get Celsius)
            if len(data) > 24:
                temp1_raw = (data[23] << 8) | data[24]
                bms.temp1 = (temp1_raw - 2731) * 0.1
            if len(data) > 26:
                temp2_raw = (data[25] << 8) | data[26]
                bms.temp2 = (temp2_raw - 2731) * 0.1
                
            # Balance status: bytes 12-13 (low) and 14-15 (high)
            if len(data) > 15:
                bms.balance_status = ((data[12] << 8) | data[13]) | (((data[14] << 8) | data[15]) << 16)
                
            # MOSFET status: byte 20
            if len(data) > 20:
                bms.mosfet_status = data[20]
                
            # Calculate power
            bms.power = bms.voltage * bms.current
            
        except Exception as e:
            print(f"Error parsing JBD basic info: {e}")
            return None
            
        return bms

    @staticmethod
    def parse_jbd_cell_info(data, bms=None):
        """
        Parse JBD BMS cell info packet data.
        
        Args:
            data: Data bytes (after header, starting at data portion)
            bms: Optional BMSData object to update
            
        Returns:
            BMSData object with cell voltages
        """
        if bms is None:
            bms = BMSData()
            
        try:
            # Number of cells = data length / 2 (each cell is 2 bytes)
            bms.num_cells = len(data) // 2
            bms.cell_voltages = []
            
            cell_min = 5.0
            cell_max = 0.0
            
            for i in range(bms.num_cells):
                # Each cell voltage: 2 bytes, unit 1mV
                cell_v = ((data[i * 2] << 8) | data[i * 2 + 1]) * 0.001
                bms.cell_voltages.append(cell_v)
                if cell_v < cell_min:
                    cell_min = cell_v
                if cell_v > cell_max:
                    cell_max = cell_v
                    
            bms.cell_min = cell_min
            bms.cell_max = cell_max
            bms.cell_diff = cell_max - cell_min
            
        except Exception as e:
            print(f"Error parsing JBD cell info: {e}")
            
        return bms

    @staticmethod
    def parse_manufacturer_data(mfr_data):
        """
        Try to parse manufacturer-specific data as BMS data.
        
        Args:
            mfr_data: Manufacturer data bytes from advertisement
            
        Returns:
            BMSData if parseable, None otherwise
        """
        if mfr_data is None or len(mfr_data) < 4:
            return None
            
        bms = BMSData()
        bms.raw_data = mfr_data
        
        # Check if it looks like JBD format (starts with 0xDD)
        if mfr_data[0] == 0xDD:
            # Try to find packet end marker
            end_idx = -1
            for i in range(len(mfr_data) - 1, 0, -1):
                if mfr_data[i] == 0x77:
                    end_idx = i
                    break
                    
            if end_idx > 4:
                pkt_type = mfr_data[1]
                pkt_status = mfr_data[2]
                data_len = mfr_data[3]
                data = mfr_data[4:4 + data_len]
                
                if pkt_type == 0x03:  # Basic info
                    return BMS_new.parse_jbd_basic_info(data)
                elif pkt_type == 0x04:  # Cell info
                    return BMS_new.parse_jbd_cell_info(data)
        
        # Try generic parsing for other BMS formats
        # Some BMS broadcast simple status in manufacturer data
        # Format may vary - try to extract common patterns
        
        if len(mfr_data) >= 8:
            # Try to detect common patterns
            # Many BMS use big-endian 16-bit values for voltage/current
            try:
                # First 2 bytes might be manufacturer ID
                mfr_id = (mfr_data[0] << 8) | mfr_data[1]
                
                # Check for voltage-like value (typical 12-60V range = 1200-6000 in 10mV units)
                possible_voltage = (mfr_data[2] << 8) | mfr_data[3] if len(mfr_data) > 3 else 0
                if 100 < possible_voltage < 7000:  # Looks like 10mV units
                    bms.voltage = possible_voltage * 0.01
                    
                    # Next 2 bytes might be current
                    if len(mfr_data) > 5:
                        current_raw = (mfr_data[4] << 8) | mfr_data[5]
                        if current_raw > 32767:
                            current_raw -= 65536
                        bms.current = current_raw * 0.01
                        bms.power = bms.voltage * bms.current
                        
                    # SOC might be a single byte
                    if len(mfr_data) > 6:
                        if 0 <= mfr_data[6] <= 100:
                            bms.capacity_percent = mfr_data[6]
                            
                    return bms
            except:
                pass
                
        return None

    @staticmethod
    def scan_devices(duration=5):
        """
        Scan for BLE devices to find your BMS name and address.

        Args:
            duration: Scan duration in seconds (default: 5)

        Returns:
            List of tuples (name, addr_type, addr, parsed_adv_data) for discovered devices
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
                
                # Parse advertisement data
                parsed = BMS_new.parse_advertisement_data(adv_data)
                name = parsed.get('name')
                
                print(f"\nDevice found - Addr: {addr_hex}, Type: {adv_type}, RSSI: {rssi}dBm")
                print(f"  Name: {name}")
                print(f"  adv_data hex: {' '.join(f'{b:02x}' for b in adv_data)}")
                
                if parsed.get('manufacturer_data'):
                    mfr = parsed['manufacturer_data']
                    print(f"  Manufacturer Data: {mfr.hex()}")
                    
                    # Try to parse as BMS data
                    bms_data = BMS_new.parse_manufacturer_data(mfr)
                    if bms_data and bms_data.voltage > 0:
                        print(f"  BMS Data: {bms_data}")
                
                if parsed.get('uuids'):
                    print(f"  UUIDs: {parsed['uuids']}")

                addr_bytes = bytes(addr)
                if not any(d[2] == addr_bytes for d in devices):
                    if name and name.strip():
                        print(f"  Added: {name} (RSSI: {rssi})")
                        devices.append((name, addr_type, addr_bytes, parsed))
                    else:
                        devices.append((f"<no name>", addr_type, addr_bytes, parsed))

        ble.irq(_irq)
        print(f"Scanning for BLE devices for {duration} seconds...")
        ble.gap_scan(int(duration * 1000), 30000, 30000)
        time.sleep(duration + 0.5)
        ble.gap_scan(None)  # Stop scanning
        ble.active(False)

        print(f"Scan complete. Found {len(devices)} device(s)")
        return devices

    def watch_advertisements(self, duration=None, continuous=True):
        """
        Watch for BLE advertisements from the target device and parse BMS data.
        
        Args:
            duration: How long to watch in seconds. If None and continuous=True, runs forever.
            continuous: If True, keeps watching until stop() is called.
            
        Returns:
            List of BMSData objects received (if not continuous)
        """
        print(f"BMS watch_advertisements: Starting for device '{self.name_str}'")
        
        try:
            import bluetooth
            from mpython_ble.const import IRQ
        except Exception as e:
            print("BLE watch: modules not available:", e)
            return []

        ble = bluetooth.BLE()
        ble.active(True)
        
        self._running = True
        results = []
        start_time = time.time()

        def _irq(event, data):
            if not self._running:
                return
                
            if event == IRQ.IRQ_SCAN_RESULT:
                addr_type, addr, adv_type, rssi, adv_data = data
                if isinstance(adv_data, memoryview):
                    adv_data = bytes(adv_data)
                
                # Parse advertisement data
                parsed = BMS_new.parse_advertisement_data(adv_data)
                name = parsed.get('name')
                
                # Check if this is our target device
                target_match = False
                if self.name_str and name:
                    target_match = self.name_str in name or name in self.name_str
                if self.addr:
                    addr_bytes = bytes(addr)
                    target_match = target_match or (addr_bytes == self.addr)
                    
                if not target_match:
                    return
                    
                print(f"\n[{name}] RSSI: {rssi}dBm")
                print(f"  Raw: {' '.join(f'{b:02x}' for b in adv_data)}")
                
                # Store RSSI
                self.last_data.rssi = rssi
                
                # Check for manufacturer data
                mfr_data = parsed.get('manufacturer_data')
                if mfr_data:
                    print(f"  Manufacturer: {mfr_data.hex()}")
                    bms_data = self.parse_manufacturer_data(mfr_data)
                    if bms_data:
                        bms_data.rssi = rssi
                        self.last_data = bms_data
                        print(f"  Parsed: {bms_data}")
                        results.append(bms_data)
                        
                        if self.on_data_callback:
                            try:
                                self.on_data_callback(bms_data)
                            except Exception as e:
                                print(f"Callback error: {e}")
                else:
                    # No manufacturer data, just log the advertisement
                    print(f"  No BMS data in advertisement (name only)")

        ble.irq(_irq)
        
        # Start scanning
        print(f"Starting BLE scan for '{self.name_str}'...")
        ble.gap_scan(0, 30000, 30000)  # 0 = continuous scan
        
        try:
            while self._running:
                time.sleep(0.5)
                if duration and (time.time() - start_time) >= duration:
                    break
                if not continuous:
                    break
        except KeyboardInterrupt:
            print("Watch interrupted by user")
        finally:
            ble.gap_scan(None)
            ble.active(False)
            self._running = False
            
        print(f"Watch complete. Received {len(results)} data packet(s)")
        return results

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
            
            # Try to parse as JBD packet
            if len(data) > 4 and data[0] == self.PACKET_START:
                pkt_type = data[1]
                pkt_status = data[2]
                data_len = data[3]
                pkt_data = data[4:4 + data_len]
                
                if pkt_type == self.TYPE_BASIC_INFO:
                    bms = self.parse_jbd_basic_info(pkt_data)
                    if bms:
                        self.last_data = bms
                        print(f"  Parsed: {bms}")
                        if self.on_data_callback:
                            self.on_data_callback(bms)
                elif pkt_type == self.TYPE_CELL_INFO:
                    bms = self.parse_jbd_cell_info(pkt_data, self.last_data)
                    if bms:
                        self.last_data = bms
                        print(f"  Cells: {bms.cell_voltages}")
                        if self.on_data_callback:
                            self.on_data_callback(bms)

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
        Uses GATT connection for detailed BMS data.
        """
        if self._running:
            print("BMS watch is already running")
            return

        self._running = True
        try:
            import _thread
            self._thread = _thread.start_new_thread(self._watch_loop, ())
            print("BMS watch: background thread started")
        except Exception as e:
            print("BMS watch: failed to start thread:", e)
            self._running = False

    def start_advertisement_watch(self):
        """
        Start watching BMS advertisement data in a background thread.
        This is lighter weight than full GATT connection but provides less data.
        """
        if self._running:
            print("BMS watch is already running")
            return

        self._running = True
        try:
            import _thread
            self._thread = _thread.start_new_thread(self.watch_advertisements, (None, True))
            print("BMS advertisement watch: background thread started")
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
