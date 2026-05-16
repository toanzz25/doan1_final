# ========================= driver.py =========================

import pyvisa


class HP8903B_Driver:

    def __init__(self):

        # Khởi tạo Visa Resource Manager
        self.rm = pyvisa.ResourceManager()

        self.instrument = None

    def connect(self, address):

        # Khởi tạo kết nối thực tế bằng PyVisa
        self.instrument = self.rm.open_resource(address)

        # Thiết lập thời gian timeout của bus dài hơn do máy đo analog cân bằng Notch cần thời gian trễ
        self.instrument.timeout = 5000

        # Gửi cấu hình khởi tạo tự động toàn hệ thống
        self.instrument.write("AU")  # Lệnh AU (Automatic Operation) xóa các hàm đặc biệt cũ

        self.instrument.write("L2")  # Bật mặc định Bộ lọc thông thấp 80 kHz để triệt nhiễu cao tần

    def parse_amplitude_string(self, amp_str):

        """Chuyển đổi chuỗi từ ComboBox thành cú pháp HP-IB chuẩn"""

        val, unit = amp_str.split()

        if unit == "mV":

            return f"{val}MV"

        return f"{val}VL"

    def format_device_value(self, value, mode):

        """Định dạng chuỗi hiển thị số trên đồ thị và màn hình giống chính xác màn hình HP 8903B"""

        try:

            val_float = float(value)

            # Tránh định dạng khoa học 2x10^1 thành số nguyên 20 dễ đọc, không đè chữ
            if mode == "THD":

                # Định dạng chữ số thập phân dựa theo mức giá trị méo thực tế của HP8903B
                if val_float < 0.1:

                    return f"{val_float:.4f}"

                elif val_float < 3.0:

                    return f"{val_float:.3f}"

                elif val_float < 30.0:

                    return f"{val_float:.2f}"

                else:

                    return f"{val_float:.1f}"

            elif mode in ["SINAD", "AC"]:

                return f"{val_float:.2f}"

        except:

            return str(value)

    def reset(self):

        """Hàm xử lý dừng khẩn cấp thiết bị bằng mã lệnh Clear (CL)"""

        if self.instrument:

            self.instrument.write("CL")