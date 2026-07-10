import time
from tkinter import messagebox

import numpy as np

from driver import (
    MODE_COMMANDS,
    extract_choice_command,
    format_amplitude_command,
    format_frequency_command,
)


def _instrument(app):
    if hasattr(app, "instrument"):
        return app.instrument
    if hasattr(app, "driver"):
        return app.driver.instrument
    return None


def _write(app, command):
    if hasattr(app, "instrument_write_safe"):
        app.instrument_write_safe(command)
    elif hasattr(app, "driver"):
        app.driver.write_safe(command)


def _read(app):
    instrument = _instrument(app)
    if not instrument:
        return None
    return float(instrument.read().strip())


def _selected_option_commands(app):
    widgets = [
        "combo_hp_filter",
        "combo_lp_filter",
        "combo_out_imp",
        "combo_input_range",
        "combo_detector",
        "combo_gain",
    ]
    for name in widgets:
        widget = getattr(app, name, None)
        if not widget:
            continue
        command = extract_choice_command(widget.get())
        if command:
            yield command


def execute_stepped_sweep(app):
    instrument = _instrument(app)
    if not instrument:
        app.is_sweeping = False
        if hasattr(app, "btn_start_step"):
            app.btn_start_step.configure(state="normal")
        return

    num_sweeps = int(app.combo_sweeps.get())

    for sweep_idx in range(num_sweeps):
        if not app.is_sweeping:
            break

        if sweep_idx > 0:
            time.sleep(1.8)

        try:
            f_start = app.parse_universal_input(app.entry_f_start.get(), "freq")
            f_stop = app.parse_universal_input(app.entry_f_stop.get(), "freq")
            points = app.parse_universal_input(app.entry_points.get(), "points")
        except ValueError as exc:
            app.show_error("Data Error", str(exc))
            break

        mode = app.meas_mode.get()
        ratio_on = app.check_ratio_var.get()
        unit = app.combo_unit.get()
        amplitude = app.entry_amp.get()

        _write(app, MODE_COMMANDS.get(mode, "M3"))
        _write(app, "R1" if ratio_on else "R0")
        _write(app, "LN" if unit in ["%", "V", "mV"] else "LG")

        if amplitude:
            try:
                value, amp_unit = app.parse_universal_input(amplitude, "amp")
                _write(app, format_amplitude_command(value, amp_unit))
            except ValueError:
                pass

        for command in _selected_option_commands(app):
            _write(app, command)

        time.sleep(1)

        color = app.colors[sweep_idx % len(app.colors)]
        line, = app.ax.plot(
            [],
            [],
            "o-",
            color=color,
            linewidth=2,
            markersize=5,
            label=f"Lan {sweep_idx + 1}",
        )
        app.lines.append(line)
        app.ax.legend(loc="upper right", frameon=True, fontsize=18)

        current_freq = []
        current_meas = []
        app.all_freq_data.append(current_freq)
        app.all_meas_data.append(current_meas)

        frequencies = np.logspace(np.log10(f_start), np.log10(f_stop), num=points)
        for freq in frequencies:
            if not app.is_sweeping:
                break

            freq_rounded = int(round(freq))
            app.lbl_live_freq.configure(
                text=f"Lan do {sweep_idx + 1}" if num_sweeps > 1 else ""
            )

            try:
                with app.hw_lock:
                    instrument.write(format_frequency_command(freq_rounded))
                    time.sleep(0.15)
                    instrument.write("T3")
                    measured_val = _read(app)
                if measured_val is None:
                    continue
            except Exception as exc:
                print(exc)
                break

            if unit == "mV":
                measured_val *= 1000.0

            current_freq.append(freq_rounded)
            current_meas.append(measured_val)
            app.lbl_live_val_freq.configure(text=f"{freq_rounded:>7,} Hz")
            app.lbl_live_val_meas.configure(text=f"{measured_val:>8.3f} {unit:<3}")
            line.set_data(current_freq, current_meas)
            app.update_ui_limits(reset_label=False)
            app.canvas.draw_idle()

    was_stopped_by_user = not app.is_sweeping
    app.is_sweeping = False
    app.btn_start_step.configure(state="normal")
    app.btn_clear.configure(state="normal")
    app.toggle_ui_inputs(is_sweeping=False)

    if _instrument(app):
        _write(app, "T0")
        app.lbl_live_freq.configure(text="")
        if was_stopped_by_user:
            app.after(0, lambda: messagebox.showinfo("Thong bao", "Da dung do"))
        else:
            app.after(0, lambda: messagebox.showinfo("Thong bao", "Da hoan thanh do"))
