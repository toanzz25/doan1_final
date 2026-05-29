import pyvisa
import re
import time

class HP8903B_Driver:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = None

    def connect(self, address):
        self.instrument = self.rm.open_resource(address)
        self.instrument.timeout = 8000
        self.instrument.write_termination = "\n"
        self.instrument.read_termination = "\n"
        self.instrument.clear()
        self.instrument.write("AU")
        time.sleep(0.5)

    def write(self, cmd):
        if self.instrument:
            self.instrument.write(cmd)

    def query_measurement(self):
        try:
            raw_data = self.instrument.read().strip()
            return float(raw_data)
        except Exception as e:
            print("Query Error:", e)
            return None

    def clear(self):
        if self.instrument:
            self.instrument.clear()

    @staticmethod
    def parse_amplitude_string(amp_str):
        amp_str = amp_str.strip().lower()
        match = re.match(r"^([\d\.]+)\s*(mv|v)?$", amp_str)
        if not match:
            raise ValueError(
                "Định dạng biên độ không hợp lệ!\n\n"
                "Ví dụ nhập đúng:\n- 1.5 V\n- 500 mV\n- 2 (mặc định là V)"
            )
            
        val_str = match.group(1)
        unit = match.group(2) if match.group(2) else "v"
        val = float(val_str)
        if val.is_integer():
            val = int(val)
            
        if unit == "mv":
            return f"AP {val} MV"
        else: 
            return f"AP {val} VL"