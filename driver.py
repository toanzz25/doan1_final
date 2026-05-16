import pyvisa

class HP8903B_Driver:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = None

    def connect(self, address):
        self.instrument = self.rm.open_resource(address)
        self.instrument.timeout = 5000

        self.instrument.write("AU")
        self.instrument.write("L2")

    def reset(self):
        if self.instrument:
            self.instrument.write("CL")

    def write(self, command):
        self.instrument.write(command)

    def read(self):
        return self.instrument.read().strip()

    def parse_amplitude_string(self, amp_str):
        val, unit = amp_str.split()

        if unit == "mV":
            return f"{val}MV"

        return f"{val}VL"

    def format_device_value(self, value, mode):
        try:
            val_float = float(value)

            if mode == "THD":
                if val_float < 0.1:
                    return f"{val_float:.4f}"
                elif val_float < 3.0:
                    return f"{val_float:.3f}"
                elif val_float < 30.0:
                    return f"{val_float:.2f}"
                else:
                    return f"{val_float:.1f}"

            return f"{val_float:.2f}"

        except:
            return str(value)