"""
BMS Data Parser for JBD Battery Management Systems
Handles parsing and storage of battery data
"""

import struct


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
        self.calculated_soc_voltage = 0.0
        
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
    
    def calculate_soc_from_voltage(self, cell_voltage):
        """
        Calculate SOC based on cell voltage for 12V LiFePO4 battery
        Uses piecewise linear interpolation
        Based on LiFePO4 voltage chart for 12V systems (4 cells in series)
        Reference: https://www.bluettipower.eu/blogs/news/lifepo4-voltage-chart
        """
        # LiFePO4 voltage to SOC curve (per cell)
        # Format: (voltage, soc_percent)
        # Derived from 12V system values: 12V ÷ 4 cells = per-cell voltage
        voltage_soc_curve = [
            (2.50, 0),    # 10.0V total - Empty (safety cutoff)
            (3.00, 5),    # 12.0V total - Very low
            (3.10, 10),   # 12.4V total - Low
            (3.20, 20),   # 12.8V total - Below 30%
            (3.22, 30),   # 12.9V total - 30% (from chart)
            (3.25, 50),   # 13.0V total - Mid-range
            (3.30, 70),   # 13.2V total - Good
            (3.35, 90),   # 13.4V total - 90% (from chart)
            (3.40, 100),  # 13.6V total - 100% Rest (from chart)
            (3.65, 100),  # 14.6V total - Full charge (stays at 100%)
        ]
        
        # Clamp voltage to valid range
        if cell_voltage <= voltage_soc_curve[0][0]:
            return 0.0
        if cell_voltage >= voltage_soc_curve[-1][0]:
            return 100.0
        
        # Find the two points to interpolate between
        for i in range(len(voltage_soc_curve) - 1):
            v1, soc1 = voltage_soc_curve[i]
            v2, soc2 = voltage_soc_curve[i + 1]
            
            if v1 <= cell_voltage <= v2:
                # Linear interpolation
                ratio = (cell_voltage - v1) / (v2 - v1)
                soc = soc1 + ratio * (soc2 - soc1)
                return soc
        
        return 0.0
    
    def parse_cell_voltages(self, data):
        """Parse cell voltage response from BMS"""
        if len(data) < 4:
            print("Invalid cell voltage packet")
            return False
            
        try:
            # Cell voltages start at byte 4, 2 bytes each, in mV
            self.cell_voltages = []
            num_cells = ((len(data) - 4) // 2) - 1
            
            for i in range(num_cells):
                cell_mv = struct.unpack('>H', data[4+i*2:6+i*2])[0]
                self.cell_voltages.append(cell_mv / 1000.0)
            
            # Calculate total voltage by summing all cell voltages
            self.calculated_voltage = sum(self.cell_voltages)
            
            # Calculate SOC from average cell voltage
            if len(self.cell_voltages) > 0:
                avg_cell_voltage = self.calculated_voltage / len(self.cell_voltages)
                self.calculated_soc_voltage = self.calculate_soc_from_voltage(avg_cell_voltage)
            
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
        print(f"SOC (from V):     {self.calculated_soc_voltage:.1f} %")
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
