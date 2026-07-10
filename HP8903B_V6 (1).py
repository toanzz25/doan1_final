import tkinter as tk
from tkinter import messagebox, filedialog
import customtkinter as ctk
import matplotlib
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import matplotlib.ticker
import numpy as np
import pyvisa
import threading
import time
import csv
import re
from datetime import datetime
import os

matplotlib.use('TkAgg')
plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

class HP8903B_App(ctk.CTk):
    def __init__(self):
        """Khởi tạo giao diện chính, thiết lập các biến trạng thái, khóa đa luồng (RLock) và gán phím tắt (bind keys)."""
        super().__init__()          
        self.title("HP 8903B Pro Automation System - Stepped Sweep Edition")
        self.geometry("1450x880") 
        ctk.set_appearance_mode("Dark")
        self.colors = ['#e74c3c', '#2980b9', '#27ae60', '#f39c12', '#8e44ad']
        
        self.rm = pyvisa.ResourceManager() # Khởi tạo trình quản lý thiết bị của PyVISA (tìm kiếm cổng GPIB/USB/COM)
        self.instrument = None # Biến lưu trữ object kết nối tới máy đo HP 8903B
        
        self.is_sweeping = False # Cờ (flag) trạng thái: True khi đang trong quá trình đo, dùng để ngắt luồng an toàn
        self.cursor_mode = "snap"
        self.lines = []
        self.all_freq_data = [] 
        self.all_meas_data = []
        self._error_showing = False 
        
        self.hw_lock = threading.RLock()
        
        self.create_widgets()
        
        self.bind('<Alt-s>', self.set_cursor_mode_snap)
        self.bind('<Alt-S>', self.set_cursor_mode_snap)
        self.bind('<Alt-c>', self.set_cursor_mode_crosshair)
        self.bind('<Alt-C>', self.set_cursor_mode_crosshair)

        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    # ================= KHỐI KIỂM SOÁT LỖI =================
    def show_error(self, title, msg):
        """Hiển thị hộp thoại báo lỗi. Tích hợp cơ chế 'debounce' để chống spam bảng lỗi liên tục gây treo phần mềm."""
        if self._error_showing: return
        self._error_showing = True
        messagebox.showerror(title, msg)
        self.after(500, lambda: setattr(self, "_error_showing", False))

    def parse_universal_input(self, val_str, type_check="freq"):
        # Hàm đa năng xử lý chuỗi nhập liệu từ người dùng:
        # Dùng Regex tách phần giá trị (số) và phần đơn vị (chữ).
        # Tự động quy đổi các tiền tố (k, m, mV) về đơn vị chuẩn (Hz, V) cho phần cứng.
        # Kiểm tra giới hạn an toàn phần cứng (VD: Không vượt quá 6V hoặc 100kHz).
        s = str(val_str).lower().replace(',', '.').replace(' ', '')
        if not s: raise ValueError("Trường nhập liệu không được để trống")
        match = re.match(r"^([+-]?\d*\.?\d+)(.*)$", s)
        if not match: raise ValueError("Không đúng định dạng số học")
        
        val, unit = float(match.group(1)), match.group(2)
        
        if type_check == "freq":
            if 'k' in unit: val *= 1000.0
            if 'm' in unit and 'hz' in unit: val *= 1000000.0
            if val < 20 or val > 100000: raise ValueError(f"Tần số {val} Hz nằm ngoài phạm vi hoạt động (20 Hz - 100 kHz)")
            return val
        elif type_check == "amp":
            if val <= 0: raise ValueError("Biên độ nguồn phát phải lớn hơn 0")
            if unit == 'mv':
                if val > 6000: raise ValueError("Vượt quá an toàn 6000 mV")
                return (val, "MV")
            else:
                if val > 6.0: raise ValueError("Vượt quá an toàn 6 V")
                return (val, "VL")
        elif type_check == "points":
            if not val.is_integer(): raise ValueError("Số điểm quét phải là số nguyên")
            val = int(val)
            if val < 2 or val > 255: raise ValueError("Số điểm từ 2 đến 255")
            return val

    def validate_and_send_freq_start(self, event=None):
        """Xác thực ô nhập Tần số Bắt đầu. Nếu máy đang rảnh (không quét), gửi lệnh (FR) set tần số ngay lập tức."""
        try:
            val = self.parse_universal_input(self.entry_f_start.get(), "freq")
            if self.instrument and not self.is_sweeping:
                self.instrument.write(f"FR{round(val/1000.0, 3):g}KZ" if val >= 1000 else f"FR{int(round(val))}HZ")
        except ValueError as e: self.show_error("Lỗi nhập liệu", str(e))

    def validate_and_send_freq_stop(self, event=None):
        """Xác thực ô nhập Tần số Kết thúc. Gửi trực tiếp lệnh (FR) xuống máy đo nếu định dạng đúng."""
        try:
            val = self.parse_universal_input(self.entry_f_stop.get(), "freq")
            if self.instrument and not self.is_sweeping:
                self.instrument.write(f"FR{round(val/1000.0, 3):g}KZ" if val >= 1000 else f"FR{int(round(val))}HZ")
        except ValueError as e: 
            self.show_error("Lỗi nhập liệu", str(e))
            
    def validate_and_send_amp(self, event=None):
        """Phân tích ô nhập Biên độ (V/mV), kiểm tra chuẩn an toàn (< 6V) và gửi lệnh Amplitude (AP) xuống phần cứng."""
        try:
            val, unit = self.parse_universal_input(self.entry_amp.get(), "amp")
            if self.instrument and not self.is_sweeping:
                self.instrument.write(f"AP {int(val)} MV" if unit == "MV" and val.is_integer() else f"AP {val} {unit}")
        except ValueError as e: self.show_error("Lỗi nhập liệu", str(e))

    def validate_points(self, event=None):
        """Xác thực tham số số điểm quét phải là số nguyên và nằm trong khoảng cho phép (2 - 255 điểm)."""
        try: self.parse_universal_input(self.entry_points.get(), "points")
        except ValueError as e: self.show_error("Lỗi nhập liệu", str(e))

    # ================= GIAO DIỆN CHÍNH =================
    def create_widgets(self):
        """Khởi tạo và sắp xếp toàn bộ bố cục UI (CustomTkinter) và nhúng khung đồ thị động (Matplotlib Canvas)."""
        
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        left_frame = ctk.CTkFrame(main_frame, width=370)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # --- KẾT NỐI ---
        ctk.CTkLabel(left_frame, text="ĐỊA CHỈ THIẾT BỊ", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(2, 0), padx=10, anchor="w")
        self.gpib_entry = ctk.CTkEntry(left_frame, placeholder_text="GPIB0::28::INSTR", height=28)
        self.gpib_entry.insert(0, "GPIB0::28::INSTR")
        self.gpib_entry.pack(fill="x", padx=10, pady=1)
        
        conn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        conn_frame.pack(fill="x", padx=10, pady=(1, 5))
        self.btn_connect = ctk.CTkButton(conn_frame, text="KẾT NỐI", fg_color="#2ecc71", hover_color="#27ae60", text_color="#1e272e", text_color_disabled="#8395a7", font=ctk.CTkFont(weight="bold"), height=28, command=self.connect_instrument)
        self.btn_connect.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.btn_disconnect = ctk.CTkButton(conn_frame, text="NGẮT KẾT NỐI", fg_color="#922b21", hover_color="#76241a", text_color="#ffffff", text_color_disabled="#8395a7", font=ctk.CTkFont(weight="bold"), height=28, state="disabled", command=self.disconnect_instrument)
        self.btn_disconnect.pack(side="right", fill="x", expand=True, padx=(5,0))

        # --- CHẾ ĐỘ ĐO ---
        ctk.CTkLabel(left_frame, text="CHỌN CHẾ ĐỘ ĐO", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(2, 0), padx=10, anchor="w")
        mode_container = ctk.CTkFrame(left_frame, fg_color="transparent")
        mode_container.pack(fill="x", padx=10)

        mode_left = ctk.CTkFrame(mode_container, fg_color="transparent")
        mode_left.pack(side="left", fill="both", expand=True)

        mode_right = ctk.CTkFrame(mode_container, fg_color="transparent")
        mode_right.pack(side="right", fill="both", expand=True, padx=(5, 0))

        self.meas_mode = tk.StringVar(value="DISTN")
        modes = [("Đo AC LEVEL - M1", "AC"), 
                 ("Đo DC LEVEL - S1", "DC"), 
                 ("Đo tỷ số SINAD - M2", "SINAD"), 
                 ("Đo SIG/NOISE - S2", "SIG_NOISE"), 
                 ("Đo DISTN / THD+N - M3", "DISTN"), 
                 ("Đo DISTN LEVEL - S3", "DISTN_LEVEL")]
        for txt, val in modes:
            ctk.CTkRadioButton(mode_left, text=txt, variable=self.meas_mode, value=val, font=ctk.CTkFont(size=12), radiobutton_width=16, radiobutton_height=16, command=self.update_mode_and_units).pack(anchor="w", pady=1)

        self.check_ratio_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(mode_right, text="Bật RATIO (R1)", variable=self.check_ratio_var, command=self.on_ratio_changed, checkbox_width=18, checkbox_height=18, font=ctk.CTkFont(size=12), text_color="#3498db").pack(anchor="w", pady=(0, 10))

        ctk.CTkLabel(mode_right, text="Đơn vị hiển thị:", font=ctk.CTkFont(size=12)).pack(anchor="w")
        self.combo_unit = ctk.CTkComboBox(mode_right, values=["%", "dB"], state="readonly", command=self.on_unit_changed, height=28)
        self.combo_unit.set("%")
        self.combo_unit.pack(fill="x", pady=1)

        # --- THAM SỐ QUÉT ---
        ctk.CTkLabel(left_frame, text="THIẾT LẬP THAM SỐ QUÉT", font=ctk.CTkFont(size=12, weight="bold")).pack(pady=(5, 0), padx=10, anchor="w")
        
        ctk.CTkLabel(left_frame, text="Tần số Start - Stop (20 Hz - 100 kHz)", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10)
        freq_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        freq_frame.pack(fill="x", padx=10, pady=1)
        
        self.entry_f_start = ctk.CTkEntry(freq_frame, placeholder_text="20", height=28)
        self.entry_f_start.insert(0, "20")
        self.entry_f_start.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_f_start.bind("<FocusOut>", self.validate_and_send_freq_start)
        self.entry_f_start.bind("<Return>", self.validate_and_send_freq_start)
        
        self.entry_f_stop = ctk.CTkEntry(freq_frame, placeholder_text="20000", height=28)
        self.entry_f_stop.insert(0, "20000")
        self.entry_f_stop.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.entry_f_stop.bind("<FocusOut>", self.validate_and_send_freq_stop)
        self.entry_f_stop.bind("<Return>", self.validate_and_send_freq_stop)

        ctk.CTkLabel(left_frame, text="Điện áp (Max 6V) - Số điểm (Max 255)", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=10, pady=(2,0))
        amp_pts_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        amp_pts_frame.pack(fill="x", padx=10, pady=1)
        
        self.entry_amp = ctk.CTkEntry(amp_pts_frame, placeholder_text="VD: 1.5 V", height=28)
        self.entry_amp.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.entry_amp.bind("<FocusOut>", self.validate_and_send_amp)
        self.entry_amp.bind("<Return>", self.validate_and_send_amp)

        self.entry_points = ctk.CTkEntry(amp_pts_frame, placeholder_text="50", height=28)
        self.entry_points.insert(0, "50")
        self.entry_points.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.entry_points.bind("<FocusOut>", self.validate_points)
        self.entry_points.bind("<Return>", self.validate_points)

        # --- BỘ LỌC & NÂNG CAO ---
        adv_container = ctk.CTkFrame(left_frame, fg_color="transparent")
        adv_container.pack(fill="x", padx=10, pady=(5, 2))

        col1 = ctk.CTkFrame(adv_container, fg_color="transparent")
        col1.pack(side="left", fill="both", expand=True, padx=(0,5))

        col2 = ctk.CTkFrame(adv_container, fg_color="transparent")
        col2.pack(side="right", fill="both", expand=True, padx=(5,0))

        ctk.CTkLabel(col1, text="BỘ LỌC & QUÉT", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=0)
        self.combo_hp_filter = ctk.CTkComboBox(col1, values=["HP/BP Off (H0)", "Left Plug-in (H1)", "Right Plug-in (H2)"], height=28, font=ctk.CTkFont(size=12), command=self.on_filter_changed)
        self.combo_hp_filter.pack(fill="x", pady=1)
        self.combo_lp_filter = ctk.CTkComboBox(col1, values=["LP Off (L0)", "30 kHz LP (L1)", "80 kHz LP (L2)"], height=28, font=ctk.CTkFont(size=12), command=self.on_filter_changed)
        self.combo_lp_filter.pack(fill="x", pady=1)

        sweep_frame = ctk.CTkFrame(col1, fg_color="transparent")
        sweep_frame.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(sweep_frame, text="Số lượt quét:", text_color="#1abc9c", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left")
        self.combo_sweeps = ctk.CTkComboBox(sweep_frame, values=["1", "2", "3", "4", "5"], state="readonly", width=60, height=28)
        self.combo_sweeps.set("1")
        self.combo_sweeps.pack(side="right")

        ctk.CTkLabel(col2, text="NÂNG CAO", font=ctk.CTkFont(size=12, weight="bold")).pack(anchor="w", pady=0)
        self.combo_out_imp = ctk.CTkComboBox(col2, values=["Trở kháng: Bỏ qua", "600 Ω (47.0 SP)", "50 Ω (47.1 SP)"], height=28, font=ctk.CTkFont(size=12), command=self.on_out_imp_changed)
        self.combo_out_imp.pack(fill="x", pady=1)
        self.combo_input_range = ctk.CTkComboBox(col2, values=["Dải đo: Bỏ qua", "Auto (1.0 SP)", "300V (1.1 SP)", "30V (1.6 SP)", "3V (1.11 SP)", "0.3V (1.16 SP)"], height=28, font=ctk.CTkFont(size=12), command=self.on_special_function_changed)
        self.combo_input_range.pack(fill="x", pady=1)
        self.combo_detector = ctk.CTkComboBox(col2, values=["Chế độ dò: Bỏ qua", "Fast RMS (5.0 SP)", "Slow RMS (5.1 SP)"], height=28, font=ctk.CTkFont(size=12), command=self.on_special_function_changed)
        self.combo_detector.pack(fill="x", pady=1)
        self.combo_gain = ctk.CTkComboBox(col2, values=["Khuếch đại: Bỏ qua", "Auto (3.0 SP)", "0 dB (3.1 SP)", "20 dB (3.2 SP)"], height=28, font=ctk.CTkFont(size=12), command=self.on_special_function_changed)
        self.combo_gain.pack(fill="x", pady=1)

        # --- NÚT ĐIỀU KHIỂN ---
        btn_frame = ctk.CTkFrame(left_frame, fg_color="transparent")
        btn_frame.pack(side='bottom', fill="x", padx=10, pady=(5, 5))
        self.btn_start_step = ctk.CTkButton(btn_frame, text="START", fg_color="#2980b9", hover_color="#3498db", font=ctk.CTkFont(weight="bold"), height=35, state="disabled", command=self.start_stepped_measurement)
        self.btn_start_step.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.btn_clear = ctk.CTkButton(btn_frame, text="STOP", fg_color="#c0392b", hover_color="#e74c3c", font=ctk.CTkFont(weight="bold"), height=35, state="disabled", command=self.stop_measurement)
        self.btn_clear.pack(side="right", fill="x", expand=True, padx=(5, 0))
        
        # --- KHU VỰC ĐỒ THỊ ---
        ctk.CTkLabel(right_frame, text="HP 8903B AUDIO ANALYZER ", font=ctk.CTkFont(size=20, weight="bold")).pack(side="top", pady=(5, 5))

        monitor_frame = ctk.CTkFrame(right_frame, height=40)
        monitor_frame.pack(side="top", fill="x", padx=10, pady=0)
        self.lbl_live_freq = ctk.CTkLabel(monitor_frame, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_live_freq.pack(side="left", padx=20, pady=5)
        live_val_container = ctk.CTkFrame(monitor_frame, fg_color="transparent")
        live_val_container.pack(side="right", padx=20, pady=5)
        
        self.lbl_live_val_freq = ctk.CTkLabel(live_val_container, text=f"{'--':>7} Hz", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color="#f1c40f")
        self.lbl_live_val_freq.pack(side="left", padx=(0, 20)) # Tạo khoảng cách giữa 2 trường
        
        self.lbl_live_val_meas = ctk.CTkLabel(live_val_container, text=f"{'--':>8} {'%':<3}", font=ctk.CTkFont(family="Consolas", size=16, weight="bold"), text_color="#f1c40f")
        self.lbl_live_val_meas.pack(side="left")
        
        self.plot_frame = ctk.CTkFrame(right_frame)
        self.plot_frame.pack(side="top", fill="both", expand=True, padx=10, pady=5)
        
        self.fig, self.ax = plt.subplots(figsize=(6, 4))
        self.fig.subplots_adjust(left=0.06, right=0.98, bottom=0.12, top=0.88)
        self.ax.set_xlabel("Tần số (Hz)", fontsize=20, fontweight='bold', labelpad=2)
        self.ax.tick_params(axis='both', which='major', labelsize=18) 
        self.ax.tick_params(axis='both', which='minor', labelsize=18)
        self.ax.set_xscale('log')
        self.ax.set_xlim([20, 20000])
        # Cấu hình Major/Minor Grid
        self.ax.grid(True, which='major', color='#999999', linestyle='-', linewidth=1.0)
        self.ax.grid(True, which='minor', color='#DDDDDD', linestyle='--', linewidth=0.5)
        
        # Cấu hình viền khung đồ thị đậm
        for spine in self.ax.spines.values():
            spine.set_edgecolor('black')
            spine.set_linewidth(1.5)
        
        def custom_major_formatter(x, pos): return f"{x:g}" if x < 1000 else f"{x/1000:g} kHz"
        def custom_minor_formatter(x, pos):
            xlim = self.ax.get_xlim()
            if xlim[1] / xlim[0] > 50: return ""
            
            # Trích xuất chữ số đầu tiên của giá trị tọa độ
            first_digit = int(str(x).replace('.', '').lstrip('0')[0])
            # Ẩn các mốc từ 5 đến 9 để chống đè chữ trên thang Logarit
            if first_digit in [5, 6, 7, 8, 9]: return "" 
            
            return f"{x:g}" if x < 1000 else f"{x/1000:g} kHz"

        self.ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(custom_major_formatter))
        self.ax.xaxis.set_minor_formatter(matplotlib.ticker.FuncFormatter(custom_minor_formatter))
        self.ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda y, pos: "0" if abs(y) == 0 else f"{y:g}"))
        
        self.crosshair_h = self.ax.axhline(y=0, color='#7f8c8d', linestyle='--', linewidth=1, visible=False)
        self.crosshair_v = self.ax.axvline(x=0, color='#7f8c8d', linestyle='--', linewidth=1, visible=False)
        self.snap_point, = self.ax.plot([], [], 'ro', markersize=8, visible=False, zorder=10)
        self.snap_annot = self.ax.annotate("", xy=(0,0), xytext=(15,15), textcoords="offset points", bbox=dict(boxstyle="round", fc="#ecf0f1", ec="#bdc3c7"), arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"), zorder=11)
        self.snap_annot.set_visible(False)
        
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('axes_leave_event', self.on_axes_leave)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        self.canvas.mpl_connect('button_press_event', self.on_button_press)
        self.canvas.mpl_connect('button_release_event', self.on_button_release)
        
        toolbar_container = ctk.CTkFrame(right_frame, height=50)
        toolbar_container.pack(side="bottom", fill="x", padx=10, pady=(0, 5))
        
        ctk.CTkButton(toolbar_container, text="🔄 Hiển thị đầy đủ", fg_color="#f39c12", hover_color="#d35400", command=self.reset_plot_view).pack(side="left", padx=15, pady=5)
        ctk.CTkButton(toolbar_container, text="Xuất file Excel", width=120, fg_color="#34495e", hover_color="#2c3e50", command=self.export_csv_data).pack(side="right", padx=5, pady=5)
        ctk.CTkButton(toolbar_container, text="Xuất ảnh đồ thị", width=120, fg_color="#16a085", hover_color="#1abc9c", command=self.export_plot_image).pack(side="right", padx=5, pady=5)
        
        self.update_mode_and_units()

    # ================= HÀM TỐI ƯU: TÍNH GIỚI HẠN BIÊN TRỤC =================
    def _get_absolute_limits(self):
        # 1. Lấy thông số đầu vào
        try: f_start_input = self.parse_universal_input(self.entry_f_start.get(), "freq")
        except: f_start_input = 20.0
            
        try: f_stop_input = self.parse_universal_input(self.entry_f_stop.get(), "freq")
        except: f_stop_input = 20000.0

        try:
            val, amp_unit = self.parse_universal_input(self.entry_amp.get(), "amp")
            amp_input = val / 1000.0 if amp_unit == "MV" else val
        except: amp_input = 5.0

        min_freq_in_sweep = min(f_start_input, f_stop_input)
        max_freq_in_sweep = max(f_start_input, f_stop_input)
        
        # 2. TÌM GIÁ TRỊ Y MAX/MIN THỰC TẾ
        current_max_y = 0.0
        current_min_y = 0.0
        has_data = False
        if hasattr(self, 'all_meas_data') and self.all_meas_data:
            for sweep in self.all_meas_data:
                if sweep:
                    if not has_data:
                        current_max_y = max(sweep)
                        current_min_y = min(sweep)
                        has_data = True
                    else:
                        current_max_y = max(current_max_y, max(sweep))
                        current_min_y = min(current_min_y, min(sweep))
        
        unit_str = self.combo_unit.get()
        mode = self.meas_mode.get()
        
        # 3. THIẾT LẬP TRỤC X (Bode Plot): 
        # Căn giữa dữ liệu hoàn hảo trên thang Logarit bằng cách chuyển đổi min/max 
        # sang log10, mở rộng biên độ (span) thêm 5% mỗi bên, rồi mũ 10 ngược lại.
        log_min_f = np.log10(min_freq_in_sweep)
        log_max_f = np.log10(max_freq_in_sweep)
        log_span = log_max_f - log_min_f
        if log_span == 0: log_span = 1.0 
        
        min_x_limit = 10**(log_min_f - log_span * 0.05)
        max_x_limit = 10**(log_max_f + log_span * 0.05)
        
        # 4. THIẾT LẬP TRỤC Y (Luôn căn giữa dữ liệu)
        if has_data:
            y_span = current_max_y - current_min_y
            if y_span < 1e-6:
                pad = abs(current_max_y) * 0.1 if current_max_y != 0 else 1.0
            else:
                pad = y_span * 0.15 
                
            return min_x_limit, max_x_limit, current_min_y - pad, current_max_y + pad
        else:
            if unit_str in ["dB", "dBm"]: 
                return min_x_limit, max_x_limit, -120.0, 20.0
            elif unit_str == "%": 
                return min_x_limit, max_x_limit, 0.0, 100.0
            else: 
                default_lower = -(amp_input * 2.0) if mode == "DC" else 0.0
                return min_x_limit, max_x_limit, default_lower, amp_input * 2.0

    def _hide_all_cursors(self):
        self.crosshair_h.set_visible(False)
        self.crosshair_v.set_visible(False)
        self.snap_annot.set_visible(False)
        self.snap_point.set_visible(False)

    # ================= CÁC HÀM CẤU HÌNH GIAO DIỆN & KẾT NỐI =================
    def reset_plot_view(self):
        self.update_ui_limits(reset_label=False)
        self.fig.canvas.draw_idle()

    def update_ui_limits(self, reset_label=True): 
        mode = self.meas_mode.get()
        unit_str = self.combo_unit.get()
        ratio_txt = " (Ratio ON)" if self.check_ratio_var.get() else ""
        
        if reset_label: 
            self.lbl_live_freq.configure(text="")
            self.lbl_live_val_freq.configure(text=f"{'--':>7} Hz")
            self.lbl_live_val_meas.configure(text=f"{'--':>8} {unit_str:<3}")
        title_dict = {
            "AC": f"Điện áp xoay chiều (AC LEVEL){ratio_txt}",
            "DC": f"Điện áp một chiều (DC LEVEL){ratio_txt}",
            "SINAD": f"Tỷ số SINAD (SINAD){ratio_txt}",
            "SIG_NOISE": f"Tín hiệu/Nhiễu (SIG/NOISE){ratio_txt}",
            "DISTN": f"Độ méo hài (DISTN / THD+N){ratio_txt}",
            "DISTN_LEVEL": f"Biên độ méo (DISTN LEVEL){ratio_txt}"
        }
        title_str = title_dict.get(mode)
        if mode in ["AC", "DC"] and unit_str == "dBm":
            title_str = f"{mode} LEVEL (dBm into 600Ω)"
        if mode in ["DISTN_LEVEL"] and unit_str == "dBm":
            title_str = f"{mode} (dBm into 600Ω)"
            
        absolute_min_x, max_x_limit, min_y_limit, max_y_limit = self._get_absolute_limits()
        self.ax.set_xlim(absolute_min_x, max_x_limit)
        self.ax.set_ylim(min_y_limit, max_y_limit)

        self.ax.set_title(title_str, fontweight='bold', fontsize=24, pad=20)
        self.ax.set_ylabel(unit_str, fontsize=20, fontweight='bold', rotation=0, labelpad=20, va='bottom')
        self.ax.yaxis.set_label_coords(0.0, 1.03)
        self.fig.canvas.draw_idle()

    def instrument_write_safe(self, cmd):
        # Gửi lệnh GPIB an toàn giữa các luồng (Thread-safe):
        # Sử dụng hw_lock (threading.RLock) để ngăn chặn lỗi đụng độ (race condition) 
        # khi luồng quét ngầm (sweep) và luồng giao diện (UI) cùng lúc gửi lệnh xuống thiết bị.
        if self.instrument:
            with self.hw_lock:
                try:
                    self.instrument.write(cmd)
                    time.sleep(0.05)
                except: pass

    def update_mode_and_units(self, event=None):
        """
        Đồng bộ hóa giao diện và thiết bị:
        1. Cập nhật lại danh sách đơn vị (V, mV, dB, %) dựa theo chế độ đo (AC/DC/DISTN).
        2. Gửi mã lệnh đo tương ứng (M1 -> S3) và đơn vị (LN/LG) xuống thiết bị.
        """
        mode = self.meas_mode.get()
        ratio_on = self.check_ratio_var.get()
        out_imp = self.combo_out_imp.get()
        
        if ratio_on: values = ["%", "dB"]
        else:
            if mode in ["AC", "DC", "DISTN_LEVEL"]: 
                values = ["V", "mV"] if "50 Ω" in out_imp else ["V", "mV", "dBm"] 
            elif mode in ["SINAD", "SIG_NOISE", "DISTN"]: 
                values = ["%", "dB"]
                
        self.combo_unit.configure(values=values)
        if self.combo_unit.get() not in values: self.combo_unit.set(values[0])
            
        self.update_ui_limits()
        # Từ điển ánh xạ (Dictionary) chuyển đổi từ tên chế độ UI sang mã lệnh chuẩn của HP 8903B
        mode_mapping = {"AC": "M1", "DC": "S1", "SINAD": "M2", "SIG_NOISE": "S2", "DISTN": "M3", "DISTN_LEVEL": "S3"} 
        self.instrument_write_safe(mode_mapping[mode])
        self.on_unit_changed(self.combo_unit.get())

    def on_ratio_changed(self):
        self.update_mode_and_units() 
        self.instrument_write_safe("R1" if self.check_ratio_var.get() else "R0")

    def on_unit_changed(self, choice):
        self.update_ui_limits()
        self.instrument_write_safe("LN" if choice in ["%", "V", "mV"] else "LG")

    def on_filter_changed(self, choice):
        match = re.search(r"\(([HL][012])\)", choice)
        if match: self.instrument_write_safe(match.group(1))

    def on_special_function_changed(self, choice):
        if "Bỏ qua" in choice: return
        match = re.search(r"\((\d+\.\d+)\s*SP\)", choice)
        if match: self.instrument_write_safe(f"{match.group(1)}SP")
        
    def on_out_imp_changed(self, choice):
        self.on_special_function_changed(choice) 
        self.update_mode_and_units()            

    def connect_instrument(self):
        """Thiết lập kết nối VISA tới địa chỉ GPIB, cấu hình timeout và ký tự kết thúc chuỗi lệnh (Termination)."""
        address = self.gpib_entry.get().strip()
        try:
            self.instrument = self.rm.open_resource(address)
            self.instrument.timeout = 3000 # Timeout 3000ms: Tránh treo phần mềm nếu thiết bị không phản hồi kịp
            self.instrument.write_termination = "\n" # Chuẩn ký tự kết thúc (Line Feed) bắt buộc cho HP 8903B
            self.instrument.read_termination = "\n"
            self.instrument.clear() # Xóa buffer rác còn sót lại trên đường truyền GPIB
            self.instrument_write_safe("AU") # Lệnh 'AU' (Auto Range): Đặt máy về chế độ tự động chọn dải đo
            time.sleep(0.3)
            
            self.update_mode_and_units()
            self.on_filter_changed(self.combo_hp_filter.get())
            self.on_filter_changed(self.combo_lp_filter.get())
            
            messagebox.showinfo("Thành công", f"Đã kết nối {address}")
            self.btn_start_step.configure(state="normal")
            self.btn_clear.configure(state="normal")
            self.btn_connect.configure(state="disabled")
            self.btn_disconnect.configure(state="normal")
        except Exception as e:
            self.show_error("Lỗi Kết Nối", str(e))

    def disconnect_instrument(self):
        if self.instrument:
            try:
                # Gửi lệnh Go To Local (GTL) trả thiết bị về chế độ điều khiển mặt máy
                self.instrument.control_ren(6)
            except:
                pass
            self.instrument.close()
            self.instrument = None
            messagebox.showinfo("Ngắt kết nối", "Đã giải phóng thiết bị đo HP 8903B.")
            self.btn_start_step.configure(state="disabled")
            self.btn_clear.configure(state="disabled")
            self.btn_connect.configure(state="normal")
            self.btn_disconnect.configure(state="disabled")

    # ================= XUẤT ẢNH & CSV =================
    def get_auto_filename(self):
        num_sweeps = int(self.combo_sweeps.get())
        # Tạo hậu tố phân biệt số lượt quét (nếu > 1)
        sweep_suffix = f"_Quet_{num_sweeps}_Luot" if num_sweeps > 1 else ""
        return f"Do_thi_{self.meas_mode.get()}{sweep_suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}"

    def export_plot_image(self):
        popup = ctk.CTkToplevel(self)
        popup.title("Lựa chọn Xuất Ảnh")
        popup.geometry("350x150")
        popup.grab_set()
        ctk.CTkLabel(popup, text="Bạn muốn lưu ảnh như thế nào?", font=ctk.CTkFont(weight="bold")).pack(pady=20)
        
        def save_to_file():
            popup.destroy()
            file_path = filedialog.asksaveasfilename(initialfile=self.get_auto_filename(), defaultextension=".png", filetypes=[("PNG Image", "*.png")], title="Lưu ảnh đồ thị")
            if file_path:
                try:
                    self.fig.savefig(file_path, format='png', dpi=300, bbox_inches='tight')
                    messagebox.showinfo("Thành công", f"Đã lưu ảnh ra {file_path}")
                except Exception as e: messagebox.showerror("Lỗi", str(e))

        def copy_to_clipboard():
            popup.destroy()
            try:
                import io, win32clipboard
                from PIL import Image
                buf = io.BytesIO()
                self.fig.savefig(buf, format='png', dpi=300, bbox_inches='tight')
                buf.seek(0)
                image = Image.open(buf)
                output = io.BytesIO()
                image.convert("RGB").save(output, "BMP")
                data = output.getvalue()[14:]
                output.close()

                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
                win32clipboard.CloseClipboard()
                messagebox.showinfo("Thành công", "Đã lưu ảnh vào Clipboard.")
            except ImportError:
                messagebox.showerror("Lỗi Thư viện", "Máy tính thiếu thư viện (pywin32, Pillow). Hãy chọn 'Lưu File'.")
            except Exception as e: messagebox.showerror("Lỗi", f"Không thể lưu vào Clipboard: {str(e)}")

        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack()
        ctk.CTkButton(btn_frame, text="1. Lưu thành File", command=save_to_file, fg_color="#2980b9").pack(side="left", padx=10)
        ctk.CTkButton(btn_frame, text="2. Copy Paste (Clipboard)", command=copy_to_clipboard, fg_color="#27ae60").pack(side="left", padx=10)

    def export_csv_data(self):
        """
        Xuất toàn bộ mảng dữ liệu (Tần số, Giá trị đo các lượt) ra file CSV.
        Tự động xử lý nội suy (padding khoảng trắng) nếu người dùng nhấn STOP ngắt quãng, 
        dẫn đến các lượt quét có số lượng điểm đo không bằng nhau.
        """
        if not self.all_meas_data:
            return messagebox.showwarning("Cảnh báo", "Chưa có dữ liệu để xuất!")
        
        file_path = filedialog.asksaveasfilename(initialfile=self.get_auto_filename(), defaultextension=".csv", filetypes=[("CSV File", "*.csv")], title="Lưu CSV")
        if file_path:
            try:
                unit_str = self.combo_unit.get()
                num_sweeps = len(self.all_meas_data)
                header = ["Frequency (Hz)"] + [f"Sweep {i+1} ({unit_str})" for i in range(num_sweeps)]
                if num_sweeps > 1: header.append(f"Average ({unit_str})")
                
                with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(header)
                    # Tìm lượt quét có dữ liệu dài nhất để làm mốc cột Tần số chuẩn (base_freqs)
                    max_len = max(len(sweep) for sweep in self.all_meas_data)
                    base_freqs = next((s for s in self.all_freq_data if len(s) == max_len), [])
                            
                    for i in range(max_len):
                        row = [base_freqs[i] if i < len(base_freqs) else ""]
                        meas_vals = []
                        for j in range(num_sweeps):
                            if i < len(self.all_meas_data[j]):
                                val = self.all_meas_data[j][i]
                                row.append(val)
                                meas_vals.append(val)
                            else: row.append("")
                        if num_sweeps > 1: row.append(sum(meas_vals) / len(meas_vals) if meas_vals else "")
                        writer.writerow(row)
                messagebox.showinfo("Thành công", f"Đã lưu CSV ra {file_path}")
            except Exception as e: messagebox.showerror("Lỗi", str(e))

    # ================= ĐO ĐẠC =================
    def toggle_ui_inputs(self, is_sweeping):
        """Bật/tắt trạng thái (Enable/Disable) toàn bộ nút bấm và ô nhập liệu để tránh người dùng can thiệp khi máy đang đo."""
        normal_widgets = [
            self.entry_f_start, self.entry_f_stop, 
            self.entry_amp, self.entry_points,
            self.combo_hp_filter, self.combo_lp_filter,
            self.combo_out_imp, self.combo_input_range, 
            self.combo_detector, self.combo_gain
        ]
        for widget in normal_widgets:
            widget.configure(state="disabled" if is_sweeping else "normal")

        readonly_widgets = [self.combo_unit, self.combo_sweeps]
        for widget in readonly_widgets:
            widget.configure(state="disabled" if is_sweeping else "readonly")

    def stop_measurement(self):
        if not self.is_sweeping: return
        self.is_sweeping = False
        self.btn_clear.configure(state="disabled") 
        
        self.toggle_ui_inputs(is_sweeping=False)

    def start_stepped_measurement(self):
        if self.is_sweeping: return
        self.btn_start_step.configure(state="disabled")
        self.is_sweeping = True
        
        self.toggle_ui_inputs(is_sweeping=True)
        
        for line in self.lines:
            try: line.remove()
            except: pass
        self.lines.clear()
        if self.ax.get_legend(): self.ax.get_legend().remove()
        self.all_freq_data = []
        self.all_meas_data = []

        threading.Thread(target=self.run_stepped_sweep_logic, daemon=True).start()

    def run_stepped_sweep_logic(self):
        # Luồng (Thread) chạy ngầm thực hiện quá trình đo Stepped Sweep.
        # Chạy tách biệt với Main Thread để không làm treo giao diện GUI (Non-blocking).
        if not self.instrument:
            self.stop_measurement()
            return

        num_sweeps = int(self.combo_sweeps.get())

        for sweep_idx in range(num_sweeps):
            if not self.is_sweeping: break
            
            if sweep_idx > 0:
                time.sleep(1.8) # Timer 1.8s chờ máy reload giữa các lần đo
                
            try:
                f_start = self.parse_universal_input(self.entry_f_start.get(), "freq")
                f_stop = self.parse_universal_input(self.entry_f_stop.get(), "freq")
                pts = self.parse_universal_input(self.entry_points.get(), "points")
            except ValueError as e:
                self.show_error("Lỗi Dữ Liệu", str(e))
                break

            mode = self.meas_mode.get()
            ratio_on = self.check_ratio_var.get()
            unit = self.combo_unit.get()
            amp = self.entry_amp.get()
            
            mode_mapping = {"AC": "M1", "DC": "S1", "SINAD": "M2", "SIG_NOISE": "S2", "DISTN": "M3", "DISTN_LEVEL": "S3"}
            self.instrument_write_safe(mode_mapping.get(mode, "M3"))
            self.instrument_write_safe("R1" if ratio_on else "R0")
            self.instrument_write_safe("LN" if unit in ["%", "V", "mV"] else "LG")
            
            if amp:
                try:
                    v, u = self.parse_universal_input(amp, "amp")
                    self.instrument_write_safe(f"AP {int(v)} MV" if u == "MV" and v.is_integer() else f"AP {v} {u}")
                except: pass
            # Vòng lặp quét qua tất cả các ComboBox cấu hình nâng cao trên UI.
            # Dùng Regex lấy mã lệnh bên trong dấu ngoặc tròn, ví dụ: "LP Off (L0)" -> trích xuất "L0"
            for sp_key in [self.combo_hp_filter.get(), self.combo_lp_filter.get(), 
                           self.combo_out_imp.get(), self.combo_input_range.get(), 
                           self.combo_detector.get(), self.combo_gain.get()]:
                if sp_key and "Bỏ qua" not in sp_key:
                    m = re.search(r"\(([A-Z0-9\.]+)\s*(?:SP)?\)", sp_key)
                    if m: self.instrument_write_safe(f"{m.group(1)}SP" if "SP" in sp_key else m.group(1))

            time.sleep(1) 

            color = self.colors[sweep_idx % len(self.colors)]
            new_line, = self.ax.plot([], [], 'o-', color=color, linewidth=2, markersize=5, label=f"Lần {sweep_idx + 1}")
            self.lines.append(new_line)
            self.ax.legend(loc="upper right", frameon=True, fontsize=18)
            
            current_freq, current_meas = [], []
            self.all_freq_data.append(current_freq)
            self.all_meas_data.append(current_meas)

            frequencies = np.logspace(np.log10(f_start), np.log10(f_stop), num=pts)
            # Tạo mảng tần số quét theo thang Logarit để mật độ điểm phân bố đều trên đồ thị.
            for f in frequencies:
                if not self.is_sweeping: break
                f_rounded = int(round(f))
                self.lbl_live_freq.configure(text=f"Lần đo {sweep_idx+1}" if num_sweeps > 1 else "")
                
                try:
                    with self.hw_lock:
                        # Gửi lệnh đặt tần số (FR). Nếu >= 1000Hz thì dùng đơn vị KZ, ngược lại dùng HZ
                        self.instrument_write_safe(f"FR{round(f_rounded/1000.0, 3):g}KZ" if f_rounded >= 1000 else f"FR{f_rounded}HZ")
                        time.sleep(0.15) # Trễ 150ms để bộ dao động nội của máy đo ổn định tần số mới
                        self.instrument_write_safe("T3") # Lệnh 'T3': Yêu cầu thiết bị thực hiện đo 1 lần (Single Trigger) và lấy kết quả
                        val = self.instrument.read().strip() # Đọc giá trị trả về từ bộ đệm GPIB
                    measured_val = float(val)

                    current_unit = unit
                    if current_unit == "mV": measured_val *= 1000.0
                    
                    current_freq.append(f_rounded)
                    current_meas.append(measured_val)
                    
                    self.lbl_live_val_freq.configure(text=f"{f_rounded:>7,} Hz")
                    self.lbl_live_val_meas.configure(text=f"{measured_val:>8.3f} {current_unit:<3}")
                    new_line.set_data(current_freq, current_meas)
                    
                    # Gọi trực tiếp hàm Auto-Scale
                    self.update_ui_limits(reset_label=False)
                    
                    self.canvas.draw_idle()
                except Exception as e:
                    print(e)
                    break

        was_stopped_by_user = not self.is_sweeping
        self.is_sweeping = False
        self.btn_start_step.configure(state="normal")
        self.btn_clear.configure(state="normal")
        
        self.toggle_ui_inputs(is_sweeping=False)
        
        if self.instrument:
            self.instrument_write_safe("T0") 
            if was_stopped_by_user: 
                self.lbl_live_freq.configure(text="")
                messagebox.showinfo("Thông báo", "Đã dừng đo")
            else: 
                self.lbl_live_freq.configure(text="")
                messagebox.showinfo("Thông báo", "Đã hoàn thành đo")

    # ================= ZOOM THÔNG MINH & TƯƠNG TÁC CHUỘT =================
    def on_scroll(self, event):
        if not event.inaxes: return
        
        base_scale = 1.2
        scale_factor = 1.0 / base_scale if event.button == 'up' else base_scale
        
        cur_xlim = self.ax.get_xlim()
        cur_ylim = self.ax.get_ylim()
        
        absolute_min_x, absolute_max_x, absolute_min_y, absolute_max_y = self._get_absolute_limits()

        try: f_start_input = self.parse_universal_input(self.entry_f_start.get(), "freq")
        except: f_start_input = 20.0
        try: f_stop_input = self.parse_universal_input(self.entry_f_stop.get(), "freq")
        except: f_stop_input = 20000.0

        min_x_log_span = (np.log10(f_stop_input) - np.log10(f_start_input)) * 0.5
        if min_x_log_span <= 0: min_x_log_span = 0.1  
        
        min_y_span = (absolute_max_y - absolute_min_y) * 0.5

        # --- XỬ LÝ TRỤC X ---
        xdata = event.xdata
        if xdata is not None and xdata > 0:
            log_min, log_max = np.log10(cur_xlim[0]), np.log10(cur_xlim[1])
            log_data = np.log10(xdata)
            log_abs_min, log_abs_max = np.log10(absolute_min_x), np.log10(absolute_max_x)
            
            log_span = log_max - log_min
            new_log_span = max(min_x_log_span, min(log_span * scale_factor, log_abs_max - log_abs_min))

            x_frac = (log_data - log_min) / log_span
            new_log_min = log_data - x_frac * new_log_span
            new_log_max = log_data + (1.0 - x_frac) * new_log_span
            
            if new_log_min < log_abs_min:
                new_log_min = log_abs_min
                new_log_max = log_abs_min + new_log_span
            if new_log_max > log_abs_max:
                new_log_max = log_abs_max
                new_log_min = log_abs_max - new_log_span
                
            self.ax.set_xlim([10**new_log_min, 10**new_log_max])

        # --- XỬ LÝ TRỤC Y ---
        ydata = event.ydata
        if ydata is not None:
            y_span = cur_ylim[1] - cur_ylim[0]
            new_y_span = max(min_y_span, min(y_span * scale_factor, absolute_max_y - absolute_min_y))

            y_frac = (ydata - cur_ylim[0]) / y_span
            new_ymin = ydata - y_frac * new_y_span
            new_ymax = ydata + (1.0 - y_frac) * new_y_span
            
            if new_ymin < absolute_min_y:
                new_ymin = absolute_min_y
                new_ymax = absolute_min_y + new_y_span
            if new_ymax > absolute_max_y:
                new_ymax = absolute_max_y
                new_ymin = absolute_max_y - new_y_span
                
            self.ax.set_ylim([new_ymin, new_ymax])
        
        self.canvas.draw_idle()

    def on_axes_leave(self, event):
        self._hide_all_cursors()
        self.canvas.draw_idle()

    def on_button_press(self, event):
        """
        Bắt sự kiện click chuột trên biểu đồ Matplotlib:
        - Chuột phải (button 3): Tắt tính năng Cursor.
        - Chuột trái (button 1): Đánh dấu vị trí bắt đầu để chuẩn bị thao tác kéo (Pan).
        """
        
        if event.button == 3: 
            self.cursor_mode = "none"
            self._hide_all_cursors()
            self.canvas.draw_idle()
        elif event.button == 1 and event.inaxes: 
            self._is_panning = True
            self._last_pan_x, self._last_pan_y = event.x, event.y
            
    def on_button_release(self, event):
        if event.button == 1: self._is_panning = False

    def on_mouse_move(self, event):
        if not event.inaxes: return self.on_axes_leave(event)
        
        # ================= LOGIC KÉO ĐỒ THỊ (PAN) =================
        if getattr(self, '_is_panning', False) and event.x is not None:
            # Xử lý kéo đồ thị (Pan): 
            # Chuyển đổi tọa độ pixel của chuột (event.x, event.y) sang tọa độ dữ liệu (transData)
            # Tính toán tỷ lệ dịch chuyển (shift) và chặn lại nếu kéo vượt quá giới hạn an toàn.
            if event.x == self._last_pan_x and event.y == self._last_pan_y: return
            
            cur_xlim = self.ax.get_xlim()
            cur_ylim = self.ax.get_ylim()
            
            inv = self.ax.transData.inverted()
            x0_data, y0_data = inv.transform((self._last_pan_x, self._last_pan_y))
            x1_data, y1_data = inv.transform((event.x, event.y))
            
            shift_x_ratio = x0_data / x1_data
            shift_y_diff = y0_data - y1_data
            
            new_xlim = [cur_xlim[0] * shift_x_ratio, cur_xlim[1] * shift_x_ratio]
            new_ylim = [cur_ylim[0] + shift_y_diff, cur_ylim[1] + shift_y_diff]
            
            absolute_min_x, absolute_max_x, absolute_min_y, absolute_max_y = self._get_absolute_limits()
                
            if new_xlim[0] < absolute_min_x:
                span_ratio = new_xlim[1] / new_xlim[0]
                new_xlim[0] = absolute_min_x
                new_xlim[1] = absolute_min_x * span_ratio
            if new_xlim[1] > absolute_max_x:
                span_ratio = new_xlim[1] / new_xlim[0]
                new_xlim[1] = absolute_max_x
                new_xlim[0] = absolute_max_x / span_ratio
                
            if new_ylim[0] < absolute_min_y:
                span_y = new_ylim[1] - new_ylim[0]
                new_ylim[0] = absolute_min_y
                new_ylim[1] = absolute_min_y + span_y
            if new_ylim[1] > absolute_max_y:
                span_y = new_ylim[1] - new_ylim[0]
                new_ylim[1] = absolute_max_y
                new_ylim[0] = absolute_max_y - span_y
                
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)
            self.canvas.draw_idle()
            
            self._last_pan_x, self._last_pan_y = event.x, event.y
            return 

        # ================= LOGIC CURSOR (Crosshair/Snap) =================
        unit_str = self.combo_unit.get()
        if self.cursor_mode == "crosshair":
            self.snap_point.set_visible(False)
            self.crosshair_h.set_ydata([event.ydata, event.ydata])
            self.crosshair_v.set_xdata([event.xdata, event.xdata])
            self.crosshair_h.set_visible(True)
            self.crosshair_v.set_visible(True)
            self.snap_annot.xy = (event.xdata, event.ydata)
            freq_str = f"{event.xdata/1000:.2f} kHz" if event.xdata >= 1000 else f"{event.xdata:.1f} Hz"
            self.snap_annot.set_text(f"{freq_str}\n{event.ydata:.3f} {unit_str}")
            self.snap_annot.set_visible(True)
            self.canvas.draw_idle()
            
        elif self.cursor_mode == "snap":
            self.crosshair_h.set_visible(False)
            self.crosshair_v.set_visible(False)
            if not self.all_freq_data: return
            
            mouse_x, mouse_y = event.x, event.y
            min_dist, closest_x, closest_y = float('inf'), None, None
            for i in range(len(self.all_freq_data)):
                if not self.all_freq_data[i]: continue
                pts = np.column_stack((self.all_freq_data[i], self.all_meas_data[i]))
                screen_pts = self.ax.transData.transform(pts)
                dists = np.sqrt((screen_pts[:, 0] - mouse_x)**2 + (screen_pts[:, 1] - mouse_y)**2)
                idx = dists.argmin()
                if dists[idx] < min_dist:
                    min_dist, closest_x, closest_y = dists[idx], self.all_freq_data[i][idx], self.all_meas_data[i][idx]
                    
            if min_dist > 50 or closest_x is None:
                self.snap_point.set_visible(False)
                self.snap_annot.set_visible(False)
                self.canvas.draw_idle()
                return
                
            self.snap_point.set_data([closest_x], [closest_y])
            self.snap_point.set_visible(True)
            self.snap_annot.xy = (closest_x, closest_y)
            freq_str = f"{closest_x/1000:g} kHz" if closest_x >= 1000 else f"{closest_x:g} Hz"
            self.snap_annot.set_text(f"{freq_str}\n{closest_y:.3f} {unit_str}")
            self.snap_annot.set_visible(True)
            self.canvas.draw_idle()

    def set_cursor_mode_snap(self, event=None):
        self.cursor_mode = "snap"
        self._hide_all_cursors()
        self.canvas.draw()
        
    def set_cursor_mode_crosshair(self, event=None):
        self.cursor_mode = "crosshair"
        self._hide_all_cursors()
        self.canvas.draw()

# ================= ĐÓNG ỨNG DỤNG AN TOÀN =================
    def on_closing(self):
        # 1. Ngắt cờ quét để dừng ngay luồng ngầm (nếu đang chạy)
        self.is_sweeping = False
        
        # 2. Giải phóng kết nối phần cứng HP 8903B
        if self.instrument:
            try:
                self.instrument.control_ren(6) # Trả máy về chế độ Local
                self.instrument.close()
            except:
                pass
                
        # 3. Đóng tất cả các luồng đồ thị Matplotlib
        plt.close('all')
        
        # 4. Hủy giao diện
        self.quit()
        self.destroy()
        
        # 5. Can thiệp hệ điều hành đóng hẳn ứng dụng đang chạy
        os._exit(0)

if __name__ == "__main__":
    app = HP8903B_App()
    app.mainloop()