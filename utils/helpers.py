# utils/helpers.py

import os
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Union

import pyautogui
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError

class Logger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / "jurnal_erori.txt"

    def log(self, message: str, log_widget: Optional[tk.Text] = None) -> None:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        log_entry = f"{timestamp} - {message}\n"

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

        if log_widget:
            log_widget.config(state='normal')
            log_widget.insert(tk.END, log_entry)
            log_widget.see(tk.END)
            log_widget.config(state='disabled')

class SystemUtils:
    @staticmethod
    def set_system_date(new_date: str, logger: Logger) -> bool:
        try:
            os.system(f"date {new_date}")
            logger.log(f"System date set to {new_date}")
            return True
        except OSError as e:
            logger.log(f"Error setting date: {e}")
            messagebox.showerror("Error", str(e))
            return False

    @staticmethod
    def focus_window(app_name: str, logger: Logger) -> bool:
        try:
            for window in Desktop(backend="uia").windows():
                if app_name.lower() in window.window_text().lower():
                    window.set_focus()
                    logger.log(f"{app_name} activated")
                    return True
            logger.log(f"{app_name} not found")
            return False
        except ElementNotFoundError as e:
            logger.log(f"Window {app_name} not found: {e}")
            return False

class ScreenshotManager:
    def __init__(self, save_dir: Union[str, Path], logger: Logger):
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(exist_ok=True)
        self.logger = logger

    def capture(self, screenshot_date: datetime,
                format_imagine: str = "png",
                quality: int = 95) -> bool:
        try:
            screenshot = pyautogui.screenshot()
            filename = f"{screenshot_date.strftime('%Y-%m-%d_%H-%M-%S')}.{format_imagine}"
            filepath = self.save_dir / filename

            if format_imagine == "jpg":
                screenshot = screenshot.convert("RGB")
                screenshot.save(filepath, quality=quality)
            else:
                screenshot.save(filepath)

            self.logger.log(f"Screenshot saved to {filepath}")
            return True
        except Exception as e:
            self.logger.log(f"Screenshot error: {e}")
            messagebox.showerror("Error", str(e))
            return False
