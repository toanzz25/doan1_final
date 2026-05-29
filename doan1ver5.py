import sys
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

# Cấu hình giao diện matplotlib
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
        
        # VISA
        self.rm = pyvisa.ResourceManager()
        self.instrument = None
        
        # dữ liệu sweep
        self.freq_data = []
        self.meas_data = []
        self.is_sweeping = False
        
        # Trạng thái con trỏ đồ thị (1: Snap, 2: Crosshair)
        self.cursor_mode = 1 
        
        self.create_widgets()
        
        # Ràng buộc phím tắt toàn cục để đổi chế độ con trỏ
        self.bind('<KeyPress-1>', self.set_cursor_mode_snap)
        self.bind('<KeyPress-2>', self.set_cursor_mode_crosshair)

    def create_widgets(self):
        # ================= TITLE =================
        title_label = ctk.CTkLabel(
            self,
            text="HP 8903B AUDIO ANALYZER CONTROL SYSTEM",
            font=ctk.CTkFont(size=22, weight="bold")
        )
        title_label.pack(pady=10)
        
        # ================= MAIN =================
        main_frame = ctk.CTkFrame(self)
        main_frame.pack(fill="both", expand=True, padx=15, pady=15)
        
        # SỬ DỤNG CTkScrollableFrame ĐỂ CÓ THỂ CUỘN NẾU GIAO DIỆN QUÁ DÀI
        left_frame = ctk.CTkScrollableFrame(main_frame, width=380)
        left_frame.pack(side="left", fill="both", padx=10, pady=10)
        
        right_frame = ctk.CTkFrame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)
        
        # ================= CONNECTION =================
        conn_label = ctk.CTkLabel(
            left_frame, text="KẾT NỐI HỆ THỐNG (GPIB)", font=ctk.CTkFont(size=14, weight="bold")
        )
        conn_label.pack(pady=(10, 5), padx=10, anchor="w")
        self.gpib_entry = ctk.CTkEntry(left_frame, placeholder_text="GPIB0::28::INSTR")
        self.gpib_entry.insert(0, "GPIB0::28::INSTR")
        self.gpib_entry.pack(fill="x", padx=10, pady=5)
        self.btn_connect = ctk.CTkButton(
            left_frame, text="CONNECT", fg_color="#27ae60", hover_color="#2ecc71", command=self.connect_instrument
        )
        self.btn_connect.pack(fill="x", padx=10, pady=5)
        
        # ================= MODE =================
        mode_label = ctk.CTkLabel(
            left_frame, text="CHẾ ĐỘ ĐO XOAY CHIỀU", font=ctk.CTkFont(size=14, weight="bold")
        )
        mode_label.pack(pady=(15, 5), padx=10, anchor="w")
        self.meas_mode = tk.StringVar(value="THD")
        r_thd = ctk.CTkRadioButton(left_frame, text="Đo méo dạng (THD+N)", variable=self.meas_mode, value="THD", command=self.update_ui_limits)
        r_sinad = ctk.CTkRadioButton(left_frame, text="Đo tỷ số SINAD", variable=self.meas_mode, value="SINAD", command=self.update_ui_limits)
        r_ac = ctk.CTkRadioButton(left_frame, text="Đo điện áp xoay chiều (AC Level)", variable=self.meas_mode, value="AC", command=self.update_ui_limits)
        r_thd.pack(anchor="w", padx=20, pady=3)
        r_sinad.pack(anchor="w", padx=20, pady=3)
        r_ac.pack(anchor="w", padx=20, pady=3)
        
        # ================= PARAMETERS =================
        param_label = ctk.CTkLabel(
            left_frame, text="THIẾT LẬP THAM SỐ QUÉT TỰ ĐỘNG", font=ctk.CTkFont(size=14, weight="bold")
        )
        param_label.pack(pady=(15, 5), padx=10, anchor="w")
        
        ctk.CTkLabel(left_frame, text="Tần số bắt đầu (20Hz - 100kHz):").pack(anchor="w", padx=15)
        self.entry_f_start = ctk.CTkEntry(left_frame)
        self.entry_f_start.insert(0, "20")
        self.entry_f_start.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(left_frame, text="Tần số kết thúc (20Hz - 100kHz):").pack(anchor="w", padx=15)
        self.entry_f_stop = ctk.CTkEntry(left_frame)
        self.entry_f_stop.insert(0, "20000")
        self.entry_f_stop.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(left_frame, text="Biên độ nguồn phát ( MAX 6V):").pack(anchor="w", padx=15)
        self.entry_amp = ctk.CTkEntry(left_frame, placeholder_text="VD: 1.5 V hoặc 500 mV")
        self.entry_amp.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(left_frame, text="Số điểm quét ( MAX 255 point):").pack(anchor="w", padx=15)
        self.entry_points = ctk.CTkEntry(left_frame, placeholder_text="VD: 50, 100, 200")
        self.entry_points.pack(fill="x", padx=10, pady=2)

        # ================= CẤU HÌNH NÂNG CAO (SPECIAL FUNCTIONS) =================
        adv_label = ctk.CTkLabel(
            left_frame, text="CẤU HÌNH MÁY ĐO NÂNG CAO", font=ctk.CTkFont(size=14, weight="bold")
        )
        adv_label.pack(pady=(15, 5), padx=10, anchor="w")
        
        # 1. Trở kháng ngõ ra (Source Output Impedance)
        ctk.CTkLabel(left_frame, text="Trở kháng ngõ ra (Output Impedance):").pack(anchor="w", padx=15)
        self.combo_out_imp = ctk.CTkComboBox(left_frame, values=[
            "Bỏ qua (Giữ nguyên hiện tại)", 
            "600 Ω (47.0 SP)", 
            "50 Ω (47.1 SP)"
        ], state="readonly")
        self.combo_out_imp.set("Bỏ qua (Giữ nguyên hiện tại)")
        self.combo_out_imp.pack(fill="x", padx=10, pady=2)

        # 2. Khuếch đại (Post-Notch Gain)
        ctk.CTkLabel(left_frame, text="Khuếch đại (Post-Notch Gain):").pack(anchor="w", padx=15)
        self.combo_gain = ctk.CTkComboBox(left_frame, values=[
            "Bỏ qua (Giữ nguyên hiện tại)", 
            "Tự động (3.0 SP)", 
            "0 dB (3.1 SP)", 
            "20 dB (3.2 SP)", 
            "40 dB (3.3 SP)", 
            "60 dB (3.4 SP)"
        ], state="readonly")
        self.combo_gain.set("Bỏ qua (Giữ nguyên hiện tại)")
        self.combo_gain.pack(fill="x", padx=10, pady=2)

        # 3. Chế độ dò (Detector Response)
        ctk.CTkLabel(left_frame, text="Chế độ phân tích dò (Detector):").pack(anchor="w", padx=15)
        self.combo_detector = ctk.CTkComboBox(left_frame, values=[
            "Bỏ qua (Giữ nguyên hiện tại)", 
            "Fast RMS (5.0 SP)", 
            "Slow RMS (5.1 SP)", 
            "Fast AVG (5.2 SP)", 
            "Slow AVG (5.3 SP)",
            "Quasi-Peak (5.7 SP)"
        ], state="readonly")
        self.combo_detector.set("Bỏ qua (Giữ nguyên hiện tại)")
        self.combo_detector.pack(fill="x", padx=10, pady=2)

        # ================= BUTTONS =================
        self.btn_start = ctk.CTkButton(left_frame, text="START", fg_color="#2980b9", hover_color="#3498db", state="disabled", command=self.start_measurement)
        self.btn_start.pack(fill="x", padx=10, pady=(20, 5))
        self.btn_clear = ctk.CTkButton(left_frame, text="STOP", fg_color="#c0392b", hover_color="#e74c3c", state="disabled", command=self.stop_measurement)
        self.btn_clear.pack(fill="x", padx=10, pady=5)
        
        # ================= MONITOR =================
        monitor_frame = ctk.CTkFrame(right_frame, height=80)
        monitor_frame.pack(fill="x", padx=10, pady=5)

        self.lbl_live_freq = ctk.CTkLabel(monitor_frame, text="Current Counter Freq: -- Hz", font=ctk.CTkFont(size=14, weight="bold"))
        self.lbl_live_freq.pack(side="left", padx=30, pady=10)
        self.lbl_live_val = ctk.CTkLabel(monitor_frame, text="Current Measurement: -- %", font=ctk.CTkFont(size=16, weight="bold"), text_color="#f1c40f")
        self.lbl_live_val.pack(side="right", padx=30, pady=10)
        
        # ================= PLOT =================
        self.plot_frame = ctk.CTkFrame(right_frame)
        self.plot_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.fig, self.ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
        self.ax.set_xlabel("Frequency (Hz)")
        
        self.line, = self.ax.plot([], [], 'o-', color='#e74c3c', linewidth=2, markersize=5)
        
        self.crosshair_h = self.ax.axhline(y=0, color='#7f8c8d', linestyle='--', linewidth=1, visible=False)
        self.crosshair_v = self.ax.axvline(x=0, color='#7f8c8d', linestyle='--', linewidth=1, visible=False)
        
        self.snap_point, = self.ax.plot([], [], 'ro', markersize=8, visible=False, zorder=5)
        self.snap_annot = self.ax.annotate(
            "", xy=(0,0), xytext=(15,15), textcoords="offset points",
            bbox=dict(boxstyle="round", fc="#ecf0f1", ec="#bdc3c7"),
            arrowprops=dict(arrowstyle="->", connectionstyle="arc3,rad=0"),
            zorder=6
        )
        self.snap_annot.set_visible(False)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plot_frame)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.pack(fill="both", expand=True)
        
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('axes_leave_event', self.on_axes_leave)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)
        
        toolbar_container = ctk.CTkFrame(right_frame, height=50)
        toolbar_container.pack(fill="x", padx=10, pady=5)
        self.toolbar = NavigationToolbar2Tk(self.canvas, toolbar_container, pack_toolbar=False)
        self.toolbar.update()
        self.toolbar.pack(side="left", padx=5, pady=5)
        
        self.update_ui_limits()
        
        btn_export_csv = ctk.CTkButton(
            toolbar_container, text="Xuất dữ liệu (.CSV)", width=150, 
            fg_color="#34495e", hover_color="#2c3e50", command=self.export_csv_data
        )
        btn_export_csv.pack(side="right", padx=5, pady=5)
        
        btn_export_img = ctk.CTkButton(
            toolbar_container, text="Xuất ảnh đồ thị (.PNG)", width=150, 
            fg_color="#16a085", hover_color="#1abc9c", command=self.export_plot_image
        )
        btn_export_img.pack(side="right", padx=5, pady=5)

    def on_scroll(self, event):
        if not event.inaxes: return
        base_scale = 1.3
        if event.button == 'up': scale_factor = 1.0 / base_scale
        elif event.button == 'down': scale_factor = base_scale
        else: return
        
        cur_ylim = self.ax.get_ylim()
        ydata = event.ydata
        new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
        rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
        self.ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])
        
        cur_xlim = self.ax.get_xlim()
        xdata = event.xdata
        if cur_xlim[0] > 0 and cur_xlim[1] > 0 and xdata > 0:
            log_xlim = [np.log10(cur_xlim[0]), np.log10(cur_xlim[1])]
            log_xdata = np.log10(xdata)
            log_width = log_xlim[1] - log_xlim[0]
            new_log_width = log_width * scale_factor
            relx = (log_xlim[1] - log_xdata) / log_width
            new_log_xlim = [log_xdata - new_log_width * (1 - relx), log_xdata + new_log_width * relx]
            self.ax.set_xlim([10**new_log_xlim[0], 10**new_log_xlim[1]])
        self.canvas.draw_idle()

    def export_csv_data(self):
        if not self.freq_data:
            messagebox.showwarning("Cảnh báo", "Không có dữ liệu đo lường để xuất!")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV file", "*.csv"), ("All Files", "*.*")],
            title="Chọn vị trí lưu file CSV"
        )
        if file_path:
            try:
                mode = self.meas_mode.get()
                unit_str = "THD+N (%)" if mode == "THD" else "SINAD (dB)" if mode == "SINAD" else "AC Level (V)"
                with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["Frequency (Hz)", unit_str])
                    for freq, meas in zip(self.freq_data, self.meas_data):
                        writer.writerow([freq, meas])
                messagebox.showinfo("Export Success", f"Dữ liệu đã được xuất thành công ra file CSV tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Lỗi trong quá trình lưu file CSV:\n{e}")

    def set_cursor_mode_snap(self, event=None):
        self.cursor_mode = 1
        self.crosshair_h.set_visible(False)
        self.crosshair_v.set_visible(False)
        self.canvas.draw_idle()
        
    def set_cursor_mode_crosshair(self, event=None):
        self.cursor_mode = 2
        self.snap_annot.set_visible(False)
        self.snap_point.set_visible(False)
        self.canvas.draw_idle()

    def on_axes_leave(self, event):
        self.crosshair_h.set_visible(False)
        self.crosshair_v.set_visible(False)
        self.snap_annot.set_visible(False)
        self.snap_point.set_visible(False)
        self.canvas.draw_idle()

    def on_mouse_move(self, event):
        if not event.inaxes:
            self.on_axes_leave(event)
            return
        if self.cursor_mode == 2:
            self.snap_annot.set_visible(False)
            self.snap_point.set_visible(False)
            self.crosshair_h.set_ydata([event.ydata, event.ydata])
            self.crosshair_v.set_xdata([event.xdata, event.xdata])
            self.crosshair_h.set_visible(True)
            self.crosshair_v.set_visible(True)
            self.canvas.draw_idle()
        elif self.cursor_mode == 1:
            self.crosshair_h.set_visible(False)
            self.crosshair_v.set_visible(False)
            if not self.freq_data: return
            idx = (np.abs(np.array(self.freq_data) - event.xdata)).argmin()
            closest_x = self.freq_data[idx]
            closest_y = self.meas_data[idx]
            self.snap_point.set_data([closest_x], [closest_y])
            self.snap_point.set_visible(True)
            self.snap_annot.xy = (closest_x, closest_y)
            unit_str = "%" if self.meas_mode.get() == "THD" else "dB" if self.meas_mode.get() == "SINAD" else "V"
            self.snap_annot.set_text(f"{closest_x:g} Hz\n{closest_y:g} {unit_str}")
            self.snap_annot.set_visible(True)
            self.canvas.draw_idle()

    def update_ui_limits(self):
        mode = self.meas_mode.get()
        
        # Cấu hình font size cho tiêu đề (Bạn có thể chỉnh con số 30 to hơn nếu muốn)
        title_font_size = 30 
        
        if mode == "THD":
            self.lbl_live_val.configure(text="Current Measurement: -- %")
            # Thay đổi tên và tăng kích cỡ chữ
            self.ax.set_title("Đồ thị đo THD+N", fontweight='bold', fontsize=title_font_size, pad=35)
            self.ax.set_ylabel("%", fontsize=24, fontweight='bold', rotation=0)
            
        elif mode == "SINAD":
            self.lbl_live_val.configure(text="Current Measurement: -- dB")
            # Thay đổi tên và tăng kích cỡ chữ
            self.ax.set_title("Đồ thị đo SINAD", fontweight='bold', fontsize=title_font_size, pad=35)
            self.ax.set_ylabel("dB", fontsize=24, fontweight='bold', rotation=0)
            
        elif mode == "AC":
            self.lbl_live_val.configure(text="Current Measurement: -- V")
            # Thay đổi tên và tăng kích cỡ chữ
            self.ax.set_title("Đồ thị đo AC LEVEL", fontweight='bold', fontsize=title_font_size, pad=35)
            self.ax.set_ylabel("V", fontsize=24, fontweight='bold', rotation=0)
            
        # Giữ nguyên vị trí nhãn đơn vị Y sát đỉnh trục tung
        self.ax.yaxis.set_label_coords(0.0, 1.02)
        
        self.fig.canvas.draw_idle()

    def connect_instrument(self):
        address = self.gpib_entry.get().strip()
        try:
            self.instrument = self.rm.open_resource(address)
            self.instrument.timeout = 8000
            self.instrument.write_termination = "\n"
            self.instrument.read_termination = "\n"
            self.instrument.clear()
            self.instrument.write("AU")
            time.sleep(0.5)
            messagebox.showinfo("Success", f"Đã kết nối thành công với HP8903B tại {address}")
            self.btn_start.configure(state="normal")
            self.btn_clear.configure(state="normal")
        except Exception as e:
            messagebox.showerror("Connection Error", f"Không thể kết nối:\n{str(e)}")

    def parse_amplitude_string(self, amp_str):
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

    def query_measurement(self):
        try:
            raw_data = self.instrument.read().strip()
            return float(raw_data)
        except Exception as e:
            print("Query Error:", e)
            return None

    def format_device_value(self, value, mode):
        try:
            val_float = float(value)
            if mode == "THD":
                if val_float < 0.1: return f"{val_float:.4f}"
                elif val_float < 3.0: return f"{val_float:.3f}"
                elif val_float < 30.0: return f"{val_float:.2f}"
                else: return f"{val_float:.1f}"
            elif mode in ["SINAD", "AC"]:
                return f"{val_float:.2f}"
        except:
            return str(value)

    # ================= HÀM MỚI: LẤY LỆNH SPECIAL FUNCTIONS =================
    def get_special_functions_cmd(self):
        spcl_cmds = ""
        
        # 1. Output Impedance
        imp_val = self.combo_out_imp.get()
        if "47.0" in imp_val: spcl_cmds += "47.0SP"
        elif "47.1" in imp_val: spcl_cmds += "47.1SP"
        
        # 2. Post-Notch Gain
        gain_val = self.combo_gain.get()
        if "3.0" in gain_val: spcl_cmds += "3.0SP"
        elif "3.1" in gain_val: spcl_cmds += "3.1SP"
        elif "3.2" in gain_val: spcl_cmds += "3.2SP"
        elif "3.3" in gain_val: spcl_cmds += "3.3SP"
        elif "3.4" in gain_val: spcl_cmds += "3.4SP"
        
        # 3. Detector Response
        det_val = self.combo_detector.get()
        if "5.0" in det_val: spcl_cmds += "5.0SP"
        elif "5.1" in det_val: spcl_cmds += "5.1SP"
        elif "5.2" in det_val: spcl_cmds += "5.2SP"
        elif "5.3" in det_val: spcl_cmds += "5.3SP"
        elif "5.7" in det_val: spcl_cmds += "5.7SP"
        
        return spcl_cmds

    def start_measurement(self):
        if self.is_sweeping: return

        # 1. Kiểm tra dải tần số
        try:
            f_start = float(self.entry_f_start.get())
            f_stop = float(self.entry_f_stop.get())
        except ValueError:
            messagebox.showerror("Input Error", "Vui lòng nhập giá trị tần số hợp lệ bằng số!")
            return

        if (f_start < 20 or f_start > 100000 or f_stop < 20 or f_stop > 100000):
            messagebox.showerror("Limit Out", "Tần số ngoài phạm vi an toàn (20Hz - 100kHz)!")
            return

        # 2. Kiểm tra phần ô nhập trống và biên độ
        amp_input = self.entry_amp.get().strip()
        if not amp_input:
            messagebox.showerror("Input Error", "Vui lòng nhập Biên độ nguồn phát!")
            return
            
        try:
            amp_code = self.parse_amplitude_string(amp_input)
        except ValueError as e:
            messagebox.showerror("Input Error", str(e))
            return
            
        # 3. Kiểm tra phần ô nhập trống và số điểm quét
        points_input = self.entry_points.get().strip()
        if not points_input:
            messagebox.showerror("Input Error", "Vui lòng nhập Số điểm quét!")
            return
            
        try:
            num_points = int(points_input)
            if num_points <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Input Error", "Số điểm quét phải là một số nguyên dương (VD: 50, 100)!")
            return

        mode = self.meas_mode.get()
        if mode == "THD": mode_code = "M3"
        elif mode == "SINAD": mode_code = "M2"
        else: mode_code = "M1"
        
        # 4. Lấy chuỗi lệnh Special Functions
        spcl_cmd_string = self.get_special_functions_cmd()

        self.is_sweeping = True
        self.btn_start.configure(state="disabled")
        self.freq_data = []
        self.meas_data = []

        sweep_thread = threading.Thread(
            target=self.start_sweep, 
            args=(f_start, f_stop, amp_code, mode_code, num_points, mode, spcl_cmd_string)
        )
        sweep_thread.daemon = True
        sweep_thread.start()

    def stop_measurement(self):
        self.is_sweeping = False
        self.btn_start.configure(state="normal")
        try:
            if self.instrument: self.instrument.clear()
        except: pass
        messagebox.showinfo("STOP", "Đã dừng quá trình đo.")

    def start_sweep(self, f_start, f_stop, amp_code, mode_code, num_points, mode, spcl_cmd_string):
        if not self.instrument:
            self.is_sweeping = False
            self.btn_start.configure(state="normal")
            return
            
        # Gửi cấu hình Special Functions (nếu có chọn) trước khi quét
        if spcl_cmd_string:
            try:
                self.instrument.write(spcl_cmd_string)
                time.sleep(0.5) # Chờ máy đo phản hồi lệnh cài đặt
            except Exception as e:
                print(f"Lỗi gửi Special Functions: {e}")

        frequencies = np.logspace(np.log10(f_start), np.log10(f_stop), num=num_points)

        for f in frequencies:
            if not self.is_sweeping: break
                
            f_rounded = int(round(f))
            self.lbl_live_freq.configure(text=f"Current Counter Freq: {f_rounded} Hz")
            self.update_idletasks()

            try:
                if f_rounded >= 1000:
                    val_khz = round(f_rounded / 1000.0, 3)
                    freq_cmd = f"FR{val_khz:g}KZ"
                else:
                    freq_cmd = f"FR{f_rounded}HZ"

                combined_command = f"{freq_cmd}{amp_code}{mode_code}T3"
                self.instrument.write(combined_command)
                measured_val = self.query_measurement()

                if measured_val is None: continue

                self.freq_data.append(f_rounded)
                self.meas_data.append(measured_val)

                formatted_str = self.format_device_value(measured_val, mode)
                unit_str = "%" if mode == "THD" else "dB" if mode == "SINAD" else "V"

                self.lbl_live_val.configure(text=f"Current Measurement: {formatted_str} {unit_str}")
                self.line.set_data(self.freq_data, self.meas_data)
                
                self.ax.relim()
                self.ax.autoscale_view()
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

    def export_plot_image(self):
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[("PNG file", "*.png"), ("All Files", "*.*")],
            title="Chọn vị trí lưu đồ thị"
        )
        if file_path:
            try:
                self.fig.savefig(file_path, format='png', dpi=300, bbox_inches='tight')
                messagebox.showinfo("Export Success", f"Đồ thị được lưu tại:\n{file_path}")
            except Exception as e:
                messagebox.showerror("Export Error", f"Lỗi lưu ảnh: {e}")

if __name__ == "__main__":
    app = HP8903B_App()
    app.mainloop()