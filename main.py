# ========================= main.py =========================

from gui import HP8903B_App

if __name__ == "__main__":
    
    # Khởi chạy hệ thống phần mềm điều khiển thiết bị
    app = HP8903B_App()

    app.mainloop()