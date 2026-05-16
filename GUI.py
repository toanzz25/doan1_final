# ========================= gui.py =========================
import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk
)
import pyperclip
from io import BytesIO
from PIL import Image
from driver import HP8903B_Driver
from sweep import SweepEngine
# Cấu hình phong cách hiển thị đồ thị giống MATLAB/Phòng thí nghiệm
matplotlib.use('TkAgg')
plt.style.use(
    'seaborn-v0_8-whitegrid'
    if 'seaborn-v0_8-whitegrid' in plt.style.available
    else 'default'
)
class HP8903B_App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("HP 8903B Audio Analyzer Automation System")
        self.geometry("1280x760")
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")
        self.driver = HP8903B_Driver()
        self.sweeper = SweepEngine(self.driver)
        # Khởi tạo giao diện
        self.create_widgets()
    def create_widgets(self):
        # ------------------ TOP BANNER ------------------
        title_label = ctk.CTkLabel(
            self,
            text="HP 8903B AUDIO ANALYZER CONTROL SYSTEM",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.pack(pady=10)
        # ------------------ MAIN FRAME ------------------
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(
            fill="both",
            expand=True,
            padx=15,
            pady=15
        )
        # Left Frame: Control & Configurations
        left_frame = ctk.CTkFrame(
            main_frame,
            width=380
        )
        left_frame.pack(
            side="left",
            fill="both",
            padx=10,
            pady=10
        )
        # Right Frame: Plots & Live Monitor
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(
            side="right",
            fill="both",
            expand=True,
            padx=10,
            pady=10
        )
        # ------------------ LEFT FRAME CONTENT ------------------
        # 1. Connection Panel
        conn_label = ctk.CTkLabel(
            left_frame,
            text="KẾT NỐI HỆ THỐNG (GPIB)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        conn_label.pack(
            pady=(10, 5),
            padx=10,
            anchor="w"
        )
        self.gpib_entry = ctk.CTkEntry(
            left_frame,
            placeholder_text="GPIB0::28::INSTR"
        )
        self.gpib_entry.insert(0, "GPIB0::28::INSTR")
        self.gpib_entry.pack(
            fill="x",
            padx=10,
            pady=5
        )
        self.btn_connect = ctk.CTkButton(
            left_frame,
            text="CONNECT",
            fg_color="#27ae60",
            hover_color="#2ecc71",
            command=self.connect_instrument
        )
        self.btn_connect.pack(
            fill="x",
            padx=10,
            pady=5
        )
        # 2. Measurement Mode
        mode_label = ctk.CTkLabel(
            left_frame,
            text="CHẾ ĐỘ ĐO XOAY CHIỀU",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        mode_label.pack(
            pady=(15, 5),
            padx=10,
            anchor="w"
        )
        self.meas_mode = tk.StringVar(value="THD")
        r_thd = ctk.CTkRadioButton(
            left_frame,
            text="Đo méo dạng (THD+N)",
            variable=self.meas_mode,
            value="THD",
            command=self.update_ui_limits
        )
        r_sinad = ctk.CTkRadioButton(
            left_frame,
            text="Đo tỷ số SINAD",
            variable=self.meas_mode,
            value="SINAD",
            command=self.update_ui_limits
        )
        r_ac = ctk.CTkRadioButton(
            left_frame,
            text="Đo điện áp xoay chiều (AC Level)",
            variable=self.meas_mode,
            value="AC",
            command=self.update_ui_limits
        )
        r_thd.pack(anchor="w", padx=20, pady=3)
        r_sinad.pack(anchor="w", padx=20, pady=3)
        r_ac.pack(anchor="w", padx=20, pady=3)
        # Frequency Scan Limits
        f_start_label = ctk.CTkLabel(
            left_frame,
            text="Tần số bắt đầu (Start Freq: 20Hz - 100kHz):"
        )
        f_start_label.pack(anchor="w", padx=15)
        self.entry_f_start = ctk.CTkEntry(left_frame)
        self.entry_f_start.insert(0, "20")
        self.entry_f_start.pack(fill="x", padx=10, pady=2)
        f_stop_label = ctk.CTkLabel(
            left_frame,
            text="Tần số kết thúc (Stop Freq: 20Hz - 100kHz):"
        )
        f_stop_label.pack(anchor="w", padx=15)
        self.entry_f_stop = ctk.CTkEntry(left_frame)
        self.entry_f_stop.insert(0, "20000")
        self.entry_f_stop.pack(fill="x", padx=10, pady=2)
        amp_label = ctk.CTkLabel(
            left_frame,
            text="Biên độ nguồn phát"
        )
        amp_label.pack(anchor="w", padx=15)
        self.allowed_amplitudes = [
            "0.6 mV",
            "1.0 mV",
            "10.0 mV",
            "50.0 mV",
            "100.0 mV",
            "500.0 mV",
            "1.0 V",
            "1.5 V",
            "2.0 V",
            "3.0 V",
            "5.0 V",
            "6.0 V"
        ]
        self.combo_amp = ctk.CTkComboBox(
            left_frame,
            values=self.allowed_amplitudes,
            state="readonly"
        )
        self.combo_amp.set("1.5 V")
        self.combo_amp.pack(fill="x", padx=10, pady=2)
        points_label = ctk.CTkLabel(
            left_frame,
            text="Số điểm quét"
        )
        points_label.pack(anchor="w", padx=15)
        self.allowed_points = [
            "10",
            "20",
            "50",
            "100",
            "150",
            "200",
            "255"
        ]
        self.combo_points = ctk.CTkComboBox(
            left_frame,
            values=self.allowed_points,
            state="readonly"
        )
        self.combo_points.set("50")
        self.combo_points.pack(fill="x", padx=10, pady=2)
        self.btn_start = ctk.CTkButton(
            left_frame,
            text="BẮT ĐẦU ĐO CHẠY QUÉT FREQUENCY",
            fg_color="#2980b9",
            hover_color="#3498db",
            command=self.start_sweep
        )
        self.btn_start.pack(
            fill="x",
            padx=10,
            pady=(20, 5)
        )
        self.btn_clear = ctk.CTkButton(
            left_frame,
            text="DỪNG KHẨN CẤP / RESET MÁY (CLEAR)",
            fg_color="#c0392b",
            hover_color="#e74c3c",
            command=self.reset_instrument
        )
        self.btn_clear.pack(
            fill="x",
            padx=10,
            pady=5
        )
        # Live Monitor Values Area
        monitor_frame = ctk.CTkFrame(
            right_frame,
            height=80
        )
        monitor_frame.pack(
            fill="x",
            padx=10,
            pady=5
        )
        self.lbl_live_freq = ctk.CTkLabel(
            monitor_frame,
            text="Live Counter Freq: -- Hz"
        )
        self.lbl_live_freq.pack(
            side="left",
            padx=30,
            pady=10
        )
        self.lbl_live_val = ctk.CTkLabel(
            monitor_frame,
            text="Live Measurement: -- %"
        )
        self.lbl_live_val.pack(
            side="right",
            padx=30,
            pady=10
        )
        self.plot_frame = ctk.CTkFrame(right_frame)
        self.plot_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=5
        )
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.ax.set_title("HP 8903B Sweep Graph Output")
        self.ax.set_xlabel("Frequency (Hz)")
        self.ax.set_ylabel("Results")
        self.line, = self.ax.plot([], [], 'o-')
        self.canvas = FigureCanvasTkAgg(
            self.fig,
            master=self.plot_frame
        )
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(
            fill="both",
            expand=True
        )
        toolbar_container = ctk.CTkFrame(
            right_frame,
            height=50
        )
        toolbar_container.pack(
            fill="x",
            padx=10,
            pady=5
        )
        self.toolbar = NavigationToolbar2Tk(
            self.canvas,
            toolbar_container,
            pack_toolbar=False
        )
        self.toolbar.update()
        self.toolbar.pack(
            side="left",
            padx=5,
            pady=5
        )
    def update_ui_limits(self):
        """Thay đổi nhãn màn hình động"""
        mode = self.meas_mode.get()
        if mode == "THD":
            self.lbl_live_val.configure(
                text="Live Measurement: -- %"
            )
            self.ax.set_ylabel(
                "Distortion & Noise (THD+N %)"
            )
        elif mode == "SINAD":
            self.lbl_live_val.configure(
                text="Live Measurement: -- dB"
            )
            self.ax.set_ylabel(
                "SINAD Ratio (dB)"
            )
        elif mode == "AC":
            self.lbl_live_val.configure(
                text="Live Measurement: -- V"
            )
            self.ax.set_ylabel(
                "AC Voltage Level (V / mV)"
            )
        self.canvas.draw()
    def connect_instrument(self):
        address = self.gpib_entry.get().strip()
        try:
            self.driver.connect(address)
            messagebox.showinfo(
                "Success",
                f"Đã kết nối thành công với HP8903B tại địa chỉ {address}"
            )
        except Exception as e:
            messagebox.showerror(
                "Connection Error",
                str(e)
            )
    def start_sweep(self):
        try:
            f_start = float(self.entry_f_start.get())
            f_stop = float(self.entry_f_stop.get())
        except ValueError:
            messagebox.showerror(
                "Input Error",
                "Vui lòng nhập giá trị tần số quét hợp lệ!"
            )
            return
        amp_selection = self.combo_amp.get()
        amp_code = self.driver.parse_amplitude_string(
            amp_selection
        )
        num_points = int(
            self.combo_points.get()
        )
        mode = self.meas_mode.get()
        self.sweeper.start_sweep(
            f_start,
            f_stop,
            num_points,
            amp_code,
            mode,
            callback=self.update_realtime_plot
        )
    def update_realtime_plot(
        self,
        freq,
        value,
        freq_data,
        meas_data
    ):
        formatted_str = self.driver.format_device_value(
            value,
            self.meas_mode.get()
        )
        unit_str = (
            "%"
            if self.meas_mode.get() == "THD"
            else "dB"
            if self.meas_mode.get() == "SINAD"
            else "V"
        )
        self.lbl_live_freq.configure(
            text=f"Live Counter Freq: {freq} Hz"
        )
        self.lbl_live_val.configure(
            text=f"Live Measurement: {formatted_str} {unit_str}"
        )
        self.line.set_data(
            freq_data,
            meas_data
        )
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw()
    def reset_instrument(self):
        self.sweeper.is_sweeping = False
        try:
            self.driver.reset()
            messagebox.showinfo(
                "Reset",
                "Đã gửi lệnh dừng khẩn cấp"
            )
        except Exception as e:
            messagebox.showerror(
                "Error",
                str(e)
            )