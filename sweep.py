import numpy as np
import time
import matplotlib.ticker

def execute_sweep(app, f_start, f_stop, amp_code, mode_code, num_points, mode, spcl_cmd_string):
    if not app.driver.instrument:
        app.is_sweeping = False
        app.btn_start.configure(state="normal")
        return
        
    # Gửi cấu hình Special Functions (nếu có chọn) trước khi quét
    if spcl_cmd_string:
        try:
            app.driver.write(spcl_cmd_string)
            time.sleep(0.5) # Chờ máy đo phản hồi lệnh cài đặt
        except Exception as e:
            print(f"Lỗi gửi Special Functions: {e}")

    frequencies = np.logspace(np.log10(f_start), np.log10(f_stop), num=num_points)

    for f in frequencies:
        if not app.is_sweeping: break
            
        f_rounded = int(round(f))
        app.lbl_live_freq.configure(text=f"Current Counter Freq: {f_rounded} Hz")
        app.update_idletasks()

        try:
            if f_rounded >= 1000:
                val_khz = round(f_rounded / 1000.0, 3)
                freq_cmd = f"FR{val_khz:g}KZ"
            else:
                freq_cmd = f"FR{f_rounded}HZ"

            combined_command = f"{freq_cmd}{amp_code}{mode_code}T3"
            app.driver.write(combined_command)
            measured_val = app.driver.query_measurement()

            if measured_val is None: continue

            app.freq_data.append(f_rounded)
            app.meas_data.append(measured_val)

            formatted_str = app.format_device_value(measured_val, mode)
            unit_str = "%" if mode == "THD" else "dB" if mode == "SINAD" else "V"

            app.lbl_live_val.configure(text=f"Current Measurement: {formatted_str} {unit_str}")
            app.line.set_data(app.freq_data, app.meas_data)
            
            app.ax.relim()
            app.ax.autoscale_view()
            app.ax.set_xscale('log')
            app.ax.xaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%g'))
            app.ax.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter('%g'))
            
            app.canvas.draw()
            app.update_idletasks()

        except Exception as e:
            print(f"Error during scan loop: {e}")
            break

    app.is_sweeping = False
    app.btn_start.configure(state="normal")