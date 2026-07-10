import re
import threading
import time

import pyvisa


MODE_COMMANDS = {
    "AC": "M1",
    "DC": "S1",
    "SINAD": "M2",
    "SIG_NOISE": "S2",
    "DISTN": "M3",
    "DISTN_LEVEL": "S3",
}

LINEAR_UNITS = {"%", "V", "mV"}


def parse_universal_input(value, type_check="freq"):
    text = str(value).lower().replace(",", ".").replace(" ", "")
    if not text:
        raise ValueError("Input field cannot be empty")

    match = re.match(r"^([+-]?\d*\.?\d+)(.*)$", text)
    if not match:
        raise ValueError("Invalid numeric format")

    val = float(match.group(1))
    unit = match.group(2)

    if type_check == "freq":
        if "k" in unit:
            val *= 1000.0
        if "m" in unit and "hz" in unit:
            val *= 1000000.0
        if val < 20 or val > 100000:
            raise ValueError(f"Frequency {val} Hz is outside 20 Hz - 100 kHz")
        return val

    if type_check == "amp":
        if val <= 0:
            raise ValueError("Source amplitude must be greater than 0")
        if unit == "mv":
            if val > 6000:
                raise ValueError("Amplitude exceeds 6000 mV safety limit")
            return val, "MV"
        if val > 6.0:
            raise ValueError("Amplitude exceeds 6 V safety limit")
        return val, "VL"

    if type_check == "points":
        if not val.is_integer():
            raise ValueError("Sweep points must be an integer")
        points = int(val)
        if points < 2 or points > 255:
            raise ValueError("Sweep points must be from 2 to 255")
        return points

    raise ValueError(f"Unsupported input type: {type_check}")


def format_frequency_command(freq_hz):
    freq = int(round(float(freq_hz)))
    if freq >= 1000:
        return f"FR{round(freq / 1000.0, 3):g}KZ"
    return f"FR{freq}HZ"


def format_amplitude_command(value, unit):
    if unit == "MV" and float(value).is_integer():
        return f"AP {int(value)} MV"
    return f"AP {value} {unit}"


def extract_choice_command(choice):
    if not choice or "Bo qua" in choice or "Bỏ qua" in choice:
        return None
    match = re.search(r"\(([A-Z0-9.]+)\s*(?:SP)?\)", choice)
    if not match:
        return None
    command = match.group(1)
    return f"{command}SP" if "SP" in choice else command


class HP8903B_Driver:
    def __init__(self):
        self.rm = pyvisa.ResourceManager()
        self.instrument = None
        self.hw_lock = threading.RLock()

    def connect(self, address):
        self.instrument = self.rm.open_resource(address)
        self.instrument.timeout = 3000
        self.instrument.write_termination = "\n"
        self.instrument.read_termination = "\n"
        self.instrument.clear()
        self.write_safe("AU")
        time.sleep(0.3)
        return self.instrument

    def disconnect(self):
        if not self.instrument:
            return
        try:
            self.instrument.control_ren(6)
        except Exception:
            pass
        self.instrument.close()
        self.instrument = None

    def write_safe(self, command, delay=0.05):
        if not self.instrument:
            return
        with self.hw_lock:
            self.instrument.write(command)
            if delay:
                time.sleep(delay)

    def write(self, command):
        self.write_safe(command)

    def read_measurement(self):
        if not self.instrument:
            return None
        raw_data = self.instrument.read().strip()
        return float(raw_data)

    def trigger_read(self):
        if not self.instrument:
            return None
        with self.hw_lock:
            self.instrument.write("T3")
            raw_data = self.instrument.read().strip()
        return float(raw_data)

    def clear(self):
        if self.instrument:
            self.instrument.clear()

    def set_mode(self, mode):
        self.write_safe(MODE_COMMANDS.get(mode, "M3"))

    def set_ratio(self, enabled):
        self.write_safe("R1" if enabled else "R0")

    def set_unit(self, unit):
        self.write_safe("LN" if unit in LINEAR_UNITS else "LG")

    def set_frequency(self, freq_hz):
        self.write_safe(format_frequency_command(freq_hz))

    def set_amplitude_from_input(self, amplitude_text):
        value, unit = parse_universal_input(amplitude_text, "amp")
        command = format_amplitude_command(value, unit)
        self.write_safe(command)
        return command

    def apply_choice_command(self, choice):
        command = extract_choice_command(choice)
        if command:
            self.write_safe(command)
        return command

    @staticmethod
    def parse_amplitude_string(amplitude_text):
        value, unit = parse_universal_input(amplitude_text, "amp")
        return format_amplitude_command(value, unit)
