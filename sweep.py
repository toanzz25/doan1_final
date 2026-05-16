# ========================= sweep.py =========================

import numpy as np


class SweepEngine:

    def __init__(self, driver):

        self.driver = driver

        # Dữ liệu đo quét
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
        callback
    ):

        if not self.driver.instrument:
            return

        # Thiết lập mã lệnh chế độ đo chuẩn của HP-IB
        if mode == "THD":

            mode_code = "M3"  # M3: Đo méo dạng Distortion

        elif mode == "SINAD":

            mode_code = "M2"  # M2: Đo SINAD

        else:

            mode_code = "M1"  # M1: Đo AC Level

        # Khóa trạng thái giao diện tránh xung đột khi đang quét dữ liệu
        self.is_sweeping = True

        self.freq_data = []

        self.meas_data = []

        # Tính toán mảng tần số quét Logarithmic đồng đều giống MATLAB
        frequencies = np.logspace(
            np.log10(f_start),
            np.log10(f_stop),
            num=num_points
        )

        # Chạy vòng lặp quét tự động qua bus dữ liệu
        for f in frequencies:

            if not self.is_sweeping:
                break

            f_rounded = round(f, 1)

            try:

                # Gửi thiết lập tần số và biên độ an toàn đến khối dao động nội
                cmd_string = (
                    f"FR{f_rounded}HZ"
                    f"AP{amp_code}"
                    f"{mode_code}T3"
                )

                self.driver.instrument.write(cmd_string)

                # Trích xuất dữ liệu đo trực tiếp từ máy đo
                raw_data = self.driver.instrument.read().strip()

                # Chuyển đổi dữ liệu khoa học dạng lũy thừa của HP thành số thực thông thường
                measured_val = float(raw_data)

                # Lưu trữ kết quả đo
                self.freq_data.append(f_rounded)

                self.meas_data.append(measured_val)

                callback(
                    f_rounded,
                    measured_val,
                    self.freq_data,
                    self.meas_data
                )

            except Exception as e:

                print(f"Error during scan loop: {e}")

                break

        self.is_sweeping = False