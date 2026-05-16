import tkinter as tk
from tkinter import messagebox, filedialog

import customtkinter as ctk

import matplotlib
import matplotlib.pyplot as plt

from matplotlib.backends.backend_tkagg import (
    FigureCanvasTkAgg,
    NavigationToolbar2Tk
)

from driver import HP8903B_Driver
from sweep import SweepEngine

matplotlib.use("TkAgg")

class HP8903B_App(ctk.CTk):

    def __init__(self):
        super().__init__()

        self.title("HP 8903B Audio Analyzer")
        self.geometry("1280x760")

        self.driver = HP8903B_Driver()

        self.sweeper = SweepEngine(self.driver)

        self.create_widgets()

    def create_widgets(self):

        # GUI code đặt ở đây
        pass

    def connect_instrument(self):

        address = self.gpib_entry.get().strip()

        try:
            self.driver.connect(address)

            messagebox.showinfo(
                "Success",
                "Connected to HP8903B"
            )

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )

    def start_sweep(self):

        try:
            f_start = float(self.entry_f_start.get())
            f_stop = float(self.entry_f_stop.get())

        except:
            messagebox.showerror(
                "Error",
                "Invalid frequency"
            )
            return

        amp_code = self.driver.parse_amplitude_string(
            self.combo_amp.get()
        )

        num_points = int(self.combo_points.get())

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

        formatted = self.driver.format_device_value(
            value,
            self.meas_mode.get()
        )

        self.lbl_live_freq.configure(
            text=f"{freq} Hz"
        )

        self.lbl_live_val.configure(
            text=formatted
        )

        self.line.set_data(
            freq_data,
            meas_data
        )

        self.ax.relim()
        self.ax.autoscale_view()

        self.canvas.draw()