import sys
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import numpy as np
import pyvisa
import pyperclip
from io import BytesIO
from PIL import Image

# Cấu hình phong cách hiển thị đồ thị giống MATLAB/Phòng thí nghiệm
matplotlib.use('TkAgg')
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

class HP8903B_App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HP 8903B Audio Analyzer Automation System")
        self.geometry("1280x760")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        # Khởi tạo Visa Resource Manager
        self.rm = pyvisa.ResourceManager()
        self.instrument = None
        
        # Dữ liệu đo quét
        self.freq_data = []
        self.meas_data = []
        self.is_sweeping = False

        # Khởi tạo giao diện
        self.create_widgets()

    def create_widgets(self):
        # ------------------ TOP BANNER ------------------
        title_label = ctk.CTkLabel(self, text="HP 8903B AUDIO ANALYZER CONTROL SYSTEM", 
                                   font=ctk.CTkFont(size=22, weight="bold"))
        title_label.pack(pady=10)

        # ------------------ MAIN FRAME ------------------
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)

        # Left Frame: Control & Configurations
        left_frame = ctk.CTkFrame(main_frame, width=380)
        left_frame.pack(side="left", fill="both", padx=10, pady=10)

        # Right Frame: Plots & Live Monitor
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        # ------------------ LEFT FRAME CONTENT ------------------
        # 1. Connection Panel
        conn_label = ctk.CTkLabel(left_frame, text="KẾT NỐI HỆ THỐNG (GPIB)", font=ctk.CTkFont(size=14, weight="bold"))
        conn_label.pack(pady=(10, 5), padx=10, anchor="w")

        self.gpib_entry = ctk.CTkEntry(left_frame, placeholder_text="GPIB0::28::INSTR")
        self.gpib_entry.insert(0, "GPIB0::28::INSTR")  # Địa chỉ mặc định nhà máy của HP8903B là 28
        self.gpib_entry.pack(fill="x", padx=10, pady=5)

        self.btn_connect = ctk.CTkButton(left_frame, text="CONNECT", fg_color="#27ae60", hover_color="#2ecc71", command=self.connect_instrument)
        self.btn_connect.pack(fill="x", padx=10, pady=5)

        # 2. Measurement Mode
        mode_label = ctk.CTkLabel(left_frame, text="CHẾ ĐỘ ĐO XOAY CHIỀU", font=ctk.CTkFont(size=14, weight="bold"))
        mode_label.pack(pady=(15, 5), padx=10, anchor="w")

        self.meas_mode = tk.StringVar(value="THD")
        r_thd = ctk.CTkRadioButton(left_frame, text="Đo méo dạng (THD+N)", variable=self.meas_mode, value="THD", command=self.update_ui_limits)
        r_sinad = ctk.CTkRadioButton(left_frame, text="Đo tỷ số SINAD", variable=self.meas_mode, value="SINAD", command=self.update_ui_limits)
        r_ac = ctk.CTkRadioButton(left_frame, text="Đo điện áp xoay chiều (AC Level)", variable=self.meas_mode, value="AC", command=self.update_ui_limits)
        r_thd.pack(anchor="w", padx=20, pady=3)
        r_sinad.pack(anchor="w", padx=20, pady=3)
        r_ac.pack(anchor="w", padx=20, pady=3)

        # 3. Parameters Lock Settings
        param_label = ctk.CTkLabel(left_frame, text="THIẾT LẬP THAM SỐ QUÉT TỰ ĐỘNG", font=ctk.CTkFont(size=14, weight="bold"))
        param_label.pack(pady=(15, 5), padx=10, anchor="w")

        # Frequency Scan Limits
        f_start_label = ctk.CTkLabel(left_frame, text="Tần số bắt đầu (Start Freq: 20Hz - 100kHz):", font=ctk.CTkFont(size=12))
        f_start_label.pack(anchor="w", padx=15)
        self.entry_f_start = ctk.CTkEntry(left_frame)
        self.entry_f_start.insert(0, "20")
        self.entry_f_start.pack(fill="x", padx=10, pady=2)

        f_stop_label = ctk.CTkLabel(left_frame, text="Tần số kết thúc (Stop Freq: 20Hz - 100kHz):", font=ctk.CTkFont(size=12))
        f_stop_label.pack(anchor="w", padx=15)
        self.entry_f_stop = ctk.CTkEntry(left_frame)
        self.entry_f_stop.insert(0, "20000")
        self.entry_f_stop.pack(fill="x", padx=10, pady=2)

        # Source Amplitudes Lock (ComboBox Dropdown to avoid incorrect values)
        amp_label = ctk.CTkLabel(left_frame, text="Biên độ nguồn phát (Source Amplitude Lock):", font=ctk.CTkFont(size=12))
        amp_label.pack(anchor="w", padx=15)
        self.allowed_amplitudes = ["0.6 mV", "1.0 mV", "10.0 mV", "50.0 mV", "100.0 mV", "500.0 mV", "1.0 V", "1.5 V", "2.0 V", "3.0 V", "5.0 V", "6.0 V"]
        self.combo_amp = ctk.CTkComboBox(left_frame, values=self.allowed_amplitudes, state="readonly")
        self.combo_amp.set("1.5 V")  # Mức mặc định tối ưu để đo THD theo tài liệu thiết bị
        self.combo_amp.pack(fill="x", padx=10, pady=2)

        # Sweep Points Number Lock (ComboBox Dropdown to prevent input overrun)
        points_label = ctk.CTkLabel(left_frame, text="Số điểm quét (Fixed Sweep Points Max 255):", font=ctk.CTkFont(size=12))
        points_label.pack(anchor="w", padx=15)
        self.allowed_points = ["10", "20", "50", "100", "150", "200", "255"]
        self.combo_points = ctk.CTkComboBox(left_frame, values=self.allowed_points, state="readonly")
        self.combo_points.set("50")
        self.combo_points.pack(fill="x", padx=10, pady=2)

        # Action Buttons
        self.btn_start = ctk.CTkButton(left_frame, text="BẮT ĐẦU ĐO CHẠY QUÉT FREQUENCY", fg_color="#2980b9", hover_color="#3498db", state="disabled", command=self.start_sweep)
        self.btn_start.pack(fill="x", padx=10, pady=(20, 5))

        self.btn_clear = ctk.CTkButton(left_frame, text="DỪNG KHẨN CẤP / RESET MÁY (CLEAR)", fg_color="#c0392b", hover_color="#e74c3c", state="disabled", command=self.reset_instrument)
        self.btn_clear.pack(fill="x", padx=10, pady=5)

        # ------------------ RIGHT FRAME CONTENT ------------------
        # Live Monitor Values Area
        monitor_frame = ctk.CTkFrame(right_frame, height=80)
        monitor_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_live_freq = ctk.CTkLabel(monitor_frame, text="Live Counter Freq: -- Hz", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_live_freq.pack(side="left", padx=30, pady=10)

        self.lbl_live_val = ctk.CTkLabel(monitor_frame, text="Live Measurement: -- %", font=ctk.CTkFont(size=16, weight="bold"), text_color="#f1c40f")
        self.lbl_live_val.pack(side="right", padx=30, pady=10)

        # Matplotlib Plot Window Frame
        self.plot_frame = ctk.CTkFrame(right_frame)
        self.plot_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_title("HP 8903B Sweep Graph Output")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Results")
        self.line, = self.ax.plot([], [], 'o-', color='#e74c3c', linewidth=2, markersize=5)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)

        # Toolbar Frame for MATLAB Zoom and Copy/Export Actions
        toolbar_container = ctk.CTkFrame(right_frame, height=50)
        toolbar_container.pack(fill="x", padx=10, pady=5)

        # nhúng thanh công cụ gốc của matplotlib để sử dụng tính năng Kéo Chuột Phóng To (Zoom) của MATLAB
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", padx=5, pady=5)

        # Nút tính năng sao chép hoặc xuất đồ thị chất lượng cao
        btn_copy = ctk.CTkButton(toolbar_container, text="Sao chép ảnh đồ thị", width=150, fg_color="#34495e", hover_color="#2c3e50", command=self.copy_plot_to_clipboard)
        btn_copy.pack(side="right", padx=5, pady=5)

        btn_export = ctk.CTkButton(toolbar_container, text="Xuất ảnh đồ thị (.PNG)", width=150, fg_color="#16a085", hover_color="#1abc9c", command=self.export_plot_image)
        btn_export.pack(side="right", padx=5, pady=5)

    def update_ui_limits(self):
        """Thay đổi nhãn màn hình động dựa trên dải tần và chế độ làm việc của máy đo"""
        mode = self.meas_mode.get()
        if mode == "THD":
            self.lbl_live_val.configure(text="Live Measurement: -- %")
            self.ax.set_ylabel("Distortion & Noise (THD+N %)")
        elif mode == "SINAD":
            self.lbl_live_val.configure(text="Live Measurement: -- dB")
            self.ax.set_ylabel("SINAD Ratio (dB)")
        elif mode == "AC":
            self.lbl_live_val.configure(text="Live Measurement: -- V")
            self.ax.set_ylabel("AC Voltage Level (V / mV)")
        self.canvas.draw()

    def connect_instrument(self):
        address = self.gpib_entry.get().strip()
        try:
            # Khởi tạo kết nối thực tế bằng PyVisa
            self.instrument = self.rm.open_resource(address)
            # Thiết lập thời gian timeout của bus dài hơn do máy đo analog cân bằng Notch cần thời gian trễ
            self.instrument.timeout = 5000 
            
            # Gửi cấu hình khởi tạo tự động toàn hệ thống
            self.instrument.write("AU")  # Lệnh AU (Automatic Operation) xóa các hàm đặc biệt cũ [cite: 706, 715]
            self.instrument.write("L2")  # Bật mặc định Bộ lọc thông thấp 80 kHz để triệt nhiễu cao tần [cite: 718]
            
            messagebox.showinfo("Success", f"Đã kết nối thành công với HP 8903B tại địa chỉ {address}!")
            self.btn_start.configure(state="normal")
            self.btn_clear.configure(state="normal")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Không thể kết nối đến thiết bị: \n{str(e)}")

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
                # Định dạng chữ số thập phân dựa theo mức giá trị méo thực tế của HP8903B Spec [cite: 321, 322]
                if val_float < 0.1:
                    return f"{val_float:.4f}"  # Độ phân giải hiển thị 0.0001% 
                elif val_float < 3.0:
                    return f"{val_float:.3f}"  # Độ phân giải hiển thị 0.001% 
                elif val_float < 30.0:
                    return f"{val_float:.2f}"  # Độ phân giải hiển thị 0.01% 
                else:
                    return f"{val_float:.1f}"  # Độ phân giải hiển thị 0.1% 
            elif mode in ["SINAD", "AC"]:
                # SINAD hiển thị độ phân giải cố định 0.01 dB [cite: 315]
                return f"{val_float:.2f}"
        except:
            return str(value)

    def start_sweep(self):
        if not self.instrument:
            return
        
        # Đọc dữ liệu đầu vào và kiểm duyệt ràng buộc (Security Lock)
        try:
            f_start = float(self.entry_f_start.get())
            f_stop = float(self.entry_f_stop.get())
        except ValueError:
            messagebox.showerror("Input Error", "Vui lòng nhập giá trị tần số quét hợp lệ!")
            return

        if f_start < 20 or f_start > 100000 or f_stop < 20 or f_stop > 100000:
            messagebox.showerror("Limit Out", "Tần số ngoài phạm vi an toàn kỹ thuật (20 Hz - 100 kHz)!")
            return

        amp_selection = self.combo_amp.get()
        amp_code = self.parse_amplitude_string(amp_selection)
        num_points = int(self.combo_points.get())

        mode = self.meas_mode.get()
        
        # Thiết lập mã lệnh chế độ đo chuẩn của HP-IB [cite: 706]
        if mode == "THD":
            mode_code = "M3"  # M3: Đo méo dạng Distortion [cite: 718]
        elif mode == "SINAD":
            mode_code = "M2"  # M2: Đo SINAD [cite: 640]
        else:
            mode_code = "M1"  # M1: Đo AC Level [cite: 717]

        # Khóa trạng thái giao diện tránh xung đột khi đang quét dữ liệu
        self.is_sweeping = True
        self.btn_start.configure(state="disabled")
        
        self.freq_data = []
        self.meas_data = []

        # Tính toán mảng tần số quét Logarithmic đồng đều giống MATLAB
        frequencies = np.logspace(np.log10(f_start), np.log10(f_stop), num=num_points)

        # Chạy vòng lặp quét tự động qua bus dữ liệu
        for f in frequencies:
            if not self.is_sweeping:
                break
            
            f_rounded = round(f, 1)
            self.lbl_live_freq.configure(text=f"Live Counter Freq: {f_rounded} Hz")
            self.update_idletasks()

            try:
                # Gửi thiết lập tần số và biên độ an toàn đến khối dao động nội (Source Oscillator) [cite: 253, 716]
                cmd_string = f"FR{f_rounded}HZAP{amp_code}{mode_code}T3" # T3: Kích hoạt phép đo có độ trễ ổn định notch [cite: 717]
                self.instrument.write(cmd_string)
                
                # Trích xuất dữ liệu đo trực tiếp từ máy đo
                raw_data = self.instrument.read().strip()
                # Chuyển đổi dữ liệu khoa học dạng lũy thừa của HP thành số thực thông thường [cite: 703]
                measured_val = float(raw_data)

                # Lưu trữ kết quả đo
                self.freq_data.append(f_rounded)
                self.meas_data.append(measured_val)

                # Cập nhật kết quả thô lên màn hình trực thời
                formatted_str = self.format_device_value(measured_val, mode)
                unit_str = "%" if mode == "THD" else "dB" if mode == "SINAD" else "V"
                self.lbl_live_val.configure(text=f"Live Measurement: {formatted_str} {unit_str}")

                # Vẽ đồ thị động trong thời gian thực
                self.line.set_data(self.freq_data, self.meas_data)
                self.ax.relim()
                self.ax.autoscale_view()
                
                # Format lại hệ trục tọa độ đẹp, tránh chồng chéo ký tự chữ
                self.ax.set_xscale('log')
                self.ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%g'))
                self.ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%g'))
                
                self.canvas.draw()
                self.update_idletasks()

            except Exception as e:
                print(f"Error during scan loop: {e}")
                break

        self.is_sweeping = False
        self.btn_start.configure(state="normal")

    def reset_instrument(self):
        """Hàm xử lý dừng khẩn cấp thiết bị bằng mã lệnh Clear (CL) [cite: 31]"""
        self.is_sweeping = False
        if self.instrument:
            try:
                self.instrument.write("CL") # Đưa máy đo về cấu hình an toàn (0 mV, 1kHz, AC level) [cite: 31]
                messagebox.showinfo("Reset", "Đã gửi lệnh dừng khẩn cấp (CL). Thiết bị đã chuyển về chế độ mặc định an toàn.")
            except Exception as e:
                messagebox.showerror("Error", f"Không thể gửi lệnh điều khiển: {e}")

    def copy_plot_to_clipboard(self):
        """Tính năng cao cấp: Sao chép trực tiếp ảnh đồ thị vào bộ nhớ tạm (Clipboard)"""
        try:
            output = BytesIO()
            self.fig.savefig(output, format='png', dpi=200, bbox_inches='tight')
            im = Image.open(output)
            
            # Lưu ảnh tạm dạng bitmap tương thích với hệ thống Clipboard của OS Windows
            output.seek(0)
            output.truncate(0)
            im.convert("RGB").save(output, "BMP")
            data = output.getvalue()[14:]  # Cắt bỏ header 14-byte của file BMP chuẩn để đưa vào clipboard
            output.close()
            
            # Gửi dữ liệu ảnh vào Clipboard hệ thống
            pyperclip.copy(None) # Clear cũ
            import win32clipboard # Yêu cầu thư viện win32 trên Windows nếu muốn dán ảnh nguyên bản cao cấp
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            messagebox.showinfo("Success", "Đã sao chép ảnh đồ thị độ phân giải cao vào Clipboard thành công!")
        except Exception as e:
            # Phương pháp dự phòng nếu không có pywin32
            messagebox.showwarning("Clipboard", "Đồ thị đã sẵn sàng. Sử dụng tính năng Xuất Ảnh hoặc cài đặt mở rộng pywin32 để sao chép ảnh trực tiếp.")

    def export_plot_image(self):
        """Tính năng lưu đồ thị ra file PNG"""
        file_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG file", "*.png"), ("All Files", "*.*")],
                                                 title="Chọn vị trí lưu đồ thị âm thanh")
        if file_path:
            try:
                self.fig.savefig(file_path, format='png', dpi=300, bbox_inches='tight')
                messagebox.showinfo("Export Success", f"Đồ thị được xuất thành công tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Lỗi không thể lưu ảnh: {e}")

if __name__ == "__main__":
    # Khởi chạy hệ thống phần mềm điều khiển thiết bị
    app = HP8903B_App()
    app.mainloop()