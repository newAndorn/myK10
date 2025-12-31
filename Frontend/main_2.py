"""
ESP32 BMS Battery Monitor using aioble
Connects to BMS device "0421150164" and displays battery data
"""

import asyncio
import aioble
import bluetooth
import struct
import time

# BMS Device Configuration
BMS_DEVICE_NAME = "0421150164"
BMS_SERVICE_UUID = bluetooth.UUID(0xff00)
BMS_CHAR_TX_UUID = bluetooth.UUID(0xff01)  # Write
BMS_CHAR_RX_UUID = bluetooth.UUID(0xff02)  # Notify

# JBD BMS Protocol Commands
CMD_BASIC_INFO = b"\xDD\xA5\x03\x00\xFF\xFD\x77"  # Request basic system info
CMD_CELL_VOLTAGES = b"\xDD\xA5\x04\x00\xFF\xFC\x77"  # Request cell voltages

class BMSData:
    """Battery Management System data container"""
    def __init__(self):
        self.voltage = 0.0
        self.current = 0.0
        self.balance_capacity = 0.0
        self.rate_capacity = 0.0
        self.cycle_count = 0
        self.production_date = ""
        self.balance_status = 0
        self.protection_status = 0
        self.software_version = 0
        self.soc = 0
        self.fet_status = 0
        self.cell_count = 0
        self.ntc_count = 0
        self.temps = []
        self.cell_voltages = []
        self.calculated_voltage = 0.0
        
    def parse_basic_info(self, data):
        """Parse basic info response from BMS"""
        # Packet format: DD 03 [length_high] [length_low] [data...]
        # Your BMS sends 20 bytes total (16 bytes of actual data after 4-byte header)
        if len(data) < 20:
            print(f"Invalid basic info packet length: {len(data)} bytes (need 20+)")
            return False
            
        try:
            # Skip first 4 bytes (DD 03 + 2 length bytes), data starts at byte 4
            # Voltage (0.01V units) - bytes 4-5
            self.voltage = struct.unpack('>H', data[4:6])[0] / 100.0
            
            # Current (0.01A units, signed) - bytes 6-7
            current_raw = struct.unpack('>h', data[6:8])[0]
            self.current = current_raw / 100.0
            
            # Balance capacity (0.01Ah units) - bytes 8-9
            self.balance_capacity = struct.unpack('>H', data[8:10])[0] / 100.0
            
            # Rate capacity (0.01Ah units) - bytes 10-11
            self.rate_capacity = struct.unpack('>H', data[10:12])[0] / 100.0
            
            # Cycle count - bytes 12-13
            self.cycle_count = struct.unpack('>H', data[12:14])[0]
            
            # Production date - bytes 14-15
            prod_date = struct.unpack('>H', data[14:16])[0]
            day = prod_date & 0x1F
            month = (prod_date >> 5) & 0x0F
            year = 2000 + (prod_date >> 9)
            self.production_date = f"{year}-{month:02d}-{day:02d}"
            
            # Balance status (4 bytes) - bytes 16-19
            self.balance_status = struct.unpack('>I', data[16:20])[0]
            
            # For 20-byte packets, remaining fields may not be present
            # Set defaults for missing data
            self.protection_status = 0
            self.software_version = 0
            self.soc = 0  # Not in this packet
            self.fet_status = 0
            self.cell_count = 0
            self.ntc_count = 0
            self.temps = []
            
            # If packet is longer, try to parse additional fields
            if len(data) >= 27:
                self.protection_status = struct.unpack('>H', data[20:22])[0]
                self.software_version = data[22]
                self.soc = data[23]
                self.fet_status = data[24]
                self.cell_count = data[25]
                self.ntc_count = data[26]
                
                # Temperatures (0.1K - 2731 = Celsius)
                for i in range(min(self.ntc_count, 3)):
                    if 27 + i*2 + 1 < len(data):
                        temp_raw = struct.unpack('>H', data[27+i*2:29+i*2])[0]
                        temp_c = (temp_raw - 2731) / 10.0
                        self.temps.append(temp_c)
            
            print(f"Parsed: V={self.voltage}V, I={self.current}A, Cap={self.balance_capacity}Ah, Cycles={self.cycle_count}")
            return True
        except Exception as e:
            print(f"Error parsing basic info: {e}")
            import sys
            sys.print_exception(e)
            return False
    
    def parse_cell_voltages(self, data):
        """Parse cell voltage response from BMS"""
        if len(data) < 4:
            print("Invalid cell voltage packet")
            return False
            
        try:
            # Cell voltages start at byte 4, 2 bytes each, in mV
            self.cell_voltages = []
            num_cells = ((len(data) - 4) // 2) -1
            
            for i in range(num_cells):
                cell_mv = struct.unpack('>H', data[4+i*2:6+i*2])[0]
                self.cell_voltages.append(cell_mv / 1000.0)
            
            # Calculate total voltage by summing all cell voltages
            self.calculated_voltage = sum(self.cell_voltages)
            
            return True
        except Exception as e:
            print(f"Error parsing cell voltages: {e}")
            return False
    
    def display(self):
        """Display battery data in console"""
        print("=" * 50)
        print("BMS Battery Data")
        print("=" * 50)
        print(f"Voltage:          {self.voltage:.2f} V")
        print(f"Calculated Voltage: {self.calculated_voltage:.2f} V")
        print(f"Current:          {self.current:.2f} A")
        print(f"Power:            {self.voltage * self.current:.2f} W")
        print(f"SOC:              {self.soc} %")
        print(f"Balance Capacity: {self.balance_capacity:.2f} Ah")
        print(f"Rate Capacity:    {self.rate_capacity:.2f} Ah")
        print(f"Cycle Count:      {self.cycle_count}")
        print(f"Production Date:  {self.production_date}")
        print(f"Cell Count:       {self.cell_count}")
        
        if self.temps:
            print(f"\nTemperatures:")
            for i, temp in enumerate(self.temps):
                print(f"  Sensor {i+1}: {temp:.1f} °C")
        
        if self.cell_voltages:
            print(f"\nCell Voltages:")
            for i, voltage in enumerate(self.cell_voltages):
                print(f"  Cell {i+1}: {voltage:.3f} V")
            if len(self.cell_voltages) > 1:
                max_v = max(self.cell_voltages)
                min_v = min(self.cell_voltages)
                print(f"\nMax Cell: {max_v:.3f} V")
                print(f"Min Cell: {min_v:.3f} V")
                print(f"Difference: {(max_v - min_v)*1000:.1f} mV")
        
        # Protection status
        if self.protection_status:
            print(f"\nProtection Status: 0x{self.protection_status:04X}")
            protections = []
            if self.protection_status & 0x01: protections.append("Cell Overvoltage")
            if self.protection_status & 0x02: protections.append("Cell Undervoltage")
            if self.protection_status & 0x04: protections.append("Pack Overvoltage")
            if self.protection_status & 0x08: protections.append("Pack Undervoltage")
            if self.protection_status & 0x10: protections.append("Charge Over Temp")
            if self.protection_status & 0x20: protections.append("Charge Under Temp")
            if self.protection_status & 0x40: protections.append("Discharge Over Temp")
            if self.protection_status & 0x80: protections.append("Discharge Under Temp")
            if self.protection_status & 0x100: protections.append("Charge Overcurrent")
            if self.protection_status & 0x200: protections.append("Discharge Overcurrent")
            if self.protection_status & 0x400: protections.append("Short Circuit")
            if protections:
                for p in protections:
                    print(f"  - {p}")
        
        # FET status
        charge_fet = "ON" if self.fet_status & 0x01 else "OFF"
        discharge_fet = "ON" if self.fet_status & 0x02 else "OFF"
        print(f"\nFET Status:")
        print(f"  Charge FET:    {charge_fet}")
        print(f"  Discharge FET: {discharge_fet}")
        print("=" * 50)


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


async def read_bms_data():
    """Main function to read BMS data"""
    bms_data = BMSData()
    
    # Find BMS device
    device = await find_bms_device(BMS_DEVICE_NAME, timeout_ms=15000)
    if not device:
        print("BMS device not found!")
        return None
    
    # Connect to device
    connection = await connect_to_bms(device)
    if not connection:
        print("Failed to connect to BMS!")
        return None
    
    try:
        async with connection:
            print("Discovering services...")
            
            # Get BMS service
            try:
                service = await connection.service(BMS_SERVICE_UUID)
                print(f"Found service: {service.uuid}")
            except Exception as e:
                print(f"Service not found: {e}")
                return None
            
            # Get RX (write) and TX (notify) characteristics
            try:
                rx_char = await service.characteristic(BMS_CHAR_RX_UUID)
                tx_char = await service.characteristic(BMS_CHAR_TX_UUID)
                print("Found characteristics")
            except Exception as e:
                print(f"Characteristics not found: {e}")
                return None
            
            # Subscribe to notifications
            print("Subscribing to notifications...")
            await tx_char.subscribe(notify=True)
            
            # Wait for BMS to be ready for commands (important!)
            print("Waiting for BMS to be ready...")
            await asyncio.sleep(2)
            
            # Request cell voltages FIRST (helps wake up the BMS)
            print("\nRequesting cell voltages...")
            success = False
            for attempt in range(3):
                await rx_char.write(CMD_CELL_VOLTAGES, response=False)
                try:
                    data = await asyncio.wait_for(tx_char.notified(), timeout=10.0)
                    print(f"Received {len(data)} bytes")
                    if data[0] == 0xDD and data[1] == 0x04:
                        bms_data.parse_cell_voltages(data)
                        success = True
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
                    print(f"Raw hex: {data.hex()}")
                    
                    # Print first 10 bytes safely
                    first_bytes = []
                    for byte in data[:min(10, len(data))]:
                        first_bytes.append(f'0x{byte:02x}')
                    print(f"First 10 bytes: {first_bytes}")
                    
                    # Check for expected DD 03 header
                    if data[0] == 0xDD and data[1] == 0x03:
                        print("Header matches DD 03, attempting to parse...")
                        bms_data.parse_basic_info(data)
                        break
                    # Check if data starts with 0x00 0x00 (might be padding or fragment)
                    elif data[0] == 0x00 and data[1] == 0x00:
                        print("Found 0x00 0x00 header - might be notification queue issue")
                        # Try to find DD 03 in the data
                        for i in range(len(data) - 1):
                            if data[i] == 0xDD and data[i+1] == 0x03:
                                print(f"Found DD 03 at offset {i}")
                                bms_data.parse_basic_info(data[i:])
                                break
                        else:
                            # Try waiting for another notification - retry for up to 15 seconds
                            print("Trying to get next notification...")
                            notification_found = False
                            for retry in range(15):
                                try:
                                    data2 = await asyncio.wait_for(tx_char.notified(), timeout=1.0)
                                    print(f"Got second notification: {len(data2)} bytes - {data2.hex()}")
                                    if data2[0] == 0xDD and data2[1] == 0x03:
                                        bms_data.parse_basic_info(data2)
                                        notification_found = True
                                        break
                                except asyncio.TimeoutError:
                                    if retry < 14:
                                        print(f"No notification yet, waiting... ({retry + 1}/15)")
                                    else:
                                        print("No second notification after 15 seconds")
                            
                            if notification_found:
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
            bms_data.display()
            
            return bms_data
            
    except Exception as e:
        print(f"Error reading BMS data: {e}")
        import sys
        sys.print_exception(e)
        return None


async def continuous_monitoring(interval_seconds=10):
    """Continuously monitor BMS data"""
    while True:
        try:
            print(f"\n\n{'='*50}")
            print(f"Reading BMS at {time.localtime()}")
            print(f"{'='*50}")
            
            data = await read_bms_data()
            
            if data is None:
                print("Failed to read BMS data, retrying in 30 seconds...")
                await asyncio.sleep(30)
            else:
                print(f"\nNext update in {interval_seconds} seconds...")
                await asyncio.sleep(interval_seconds)
                
        except Exception as e:
            print(f"Error in monitoring loop: {e}")
            await asyncio.sleep(30)


def main():
    """Main entry point"""
    print("=" * 50)
    print("ESP32 BMS Battery Monitor")
    print("Using aioble library")
    print("=" * 50)
    print(f"Target Device: {BMS_DEVICE_NAME}")
    print(f"Service UUID: {BMS_SERVICE_UUID}")
    print("=" * 50)
    print()
    
    try:
        # Run one-time read or continuous monitoring
        # For one-time read:
        asyncio.run(read_bms_data())
        
        # For continuous monitoring (uncomment below):
        # asyncio.run(continuous_monitoring(interval_seconds=10))
        
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        import sys
        sys.print_exception(e)


if __name__ == "__main__":
    main()
