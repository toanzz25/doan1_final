import numpy as np

class SweepEngine:
    def __init__(self, driver):
        self.driver = driver

        self.freq_data = []
        self.meas_data = []

        self.is_sweeping = False

    def start_sweep(
        self,
        f_start,
        f_stop,
        num_points,
        amp_code,
        mode,
        callback=None
    ):

        self.freq_data = []
        self.meas_data = []

        self.is_sweeping = True

        frequencies = np.logspace(
            np.log10(f_start),
            np.log10(f_stop),
            num=num_points
        )

        if mode == "THD":
            mode_code = "M3"
        elif mode == "SINAD":
            mode_code = "M2"
        else:
            mode_code = "M1"

        for f in frequencies:

            if not self.is_sweeping:
                break

            f_rounded = round(f, 1)

            cmd_string = (
                f"FR{f_rounded}HZ"
                f"AP{amp_code}"
                f"{mode_code}T3"
            )

            self.driver.write(cmd_string)

            raw_data = self.driver.read()

            measured_val = float(raw_data)

            self.freq_data.append(f_rounded)
            self.meas_data.append(measured_val)

            if callback:
                callback(
                    f_rounded,
                    measured_val,
                    self.freq_data,
                    self.meas_data
                )

    def stop(self):
        self.is_sweeping = False