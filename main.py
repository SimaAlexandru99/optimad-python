from datetime import datetime, timedelta
import threading
import time
from typing import Optional
from tkinter import IntVar, StringVar
from tkinter.ttk import Button, Entry, Label, Progressbar
from ttkthemes import ThemedTk

from utils.helpers import Logger, SystemUtils, ScreenshotManager

class ScreenshotApp:
    def __init__(self):
        self.logger = Logger()
        self.system_utils = SystemUtils()
        self.stop_requested = False
        self.is_running = False

        self.setup_ui()

    def setup_ui(self):
        self.app = ThemedTk(theme="arc")
        self.app.title("Optimad")
        self.app.geometry("700x400")

        # Variables
        self.hours_var = StringVar()
        self.screenshots_var = StringVar()
        self.status_var = StringVar(value="Pregătit")
        self.progress_var = IntVar()

        # UI Elements
        self._create_ui_elements()

    def _create_ui_elements(self):
        Label(self.app, text="Numărul de ore de curs:", font=("Arial", 12)).pack(pady=5)
        Entry(self.app, textvariable=self.hours_var, font=("Arial", 12), width=30).pack(pady=5)

        Label(self.app, text="Numărul de screenshot-uri:", font=("Arial", 12)).pack(pady=5)
        Entry(self.app, textvariable=self.screenshots_var, font=("Arial", 12), width=30).pack(pady=5)

        self.start_button = Button(self.app, text="Pornește Procesul", command=self.start_process)
        self.start_button.pack(pady=10)

        self.stop_button = Button(self.app, text="Oprește Procesul", command=self.stop_process, state="disabled")
        self.stop_button.pack(pady=5)

        Label(self.app, textvariable=self.status_var, font=("Arial", 10)).pack(pady=10)

        self.progress_bar = Progressbar(self.app, orient="horizontal", length=400, mode="determinate", variable=self.progress_var)
        self.progress_bar.pack(pady=10)

    def start_process(self):
        if self.is_running:
            return

        try:
            hours = int(self.hours_var.get())
            screenshots = int(self.screenshots_var.get())

            if hours < 1 or screenshots < 1:
                raise ValueError("Values must be positive")

            self.is_running = True
            self.stop_requested = False
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

            # Run process in background
            thread = threading.Thread(
                target=self._process_screenshots,
                args=(hours, screenshots)
            )
            thread.daemon = True
            thread.start()

        except ValueError as e:
            self.logger.log(f"Invalid input: {e}")
            self.status_var.set("Error: Invalid input")

    def _process_screenshots(self, hours: int, screenshots: int):
        initial_date = datetime.now().strftime("%m/%d/%Y")
        screenshot_mgr = ScreenshotManager(
            datetime.now().strftime("%Y-%m-%d"),
            self.logger
        )

        try:
            interval = (hours * 3600) // screenshots
            self._update_progress(0, screenshots)

            for i in range(screenshots):
                if self.stop_requested:
                    break

                screenshot_date = datetime.now() + timedelta(days=i)

                # Set system date and wait for first screenshot
                if i > 0:
                    self.system_utils.set_system_date(
                        screenshot_date.strftime("%m/%d/%Y"),
                        self.logger
                    )
                else:
                    self._countdown(15, "First screenshot in")

                # Take screenshot
                if self.system_utils.focus_window("Zoom", self.logger):
                    screenshot_mgr.capture(screenshot_date)
                    self._update_progress(i + 1, screenshots)

                if i < screenshots - 1:  # Skip wait on last iteration
                    self._countdown(interval, "Next screenshot in")

        finally:
            self.system_utils.set_system_date(initial_date, self.logger)
            self._cleanup()

    def _cleanup(self):
        self.is_running = False
        self.stop_requested = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Proces completat")

    def _update_progress(self, current: int, total: int):
        self.progress_var.set(int((current / total) * 100))
        self.status_var.set(f"Progress: {current}/{total}")
        self.app.update()

    def _countdown(self, seconds: int, message: str):
        for remaining in range(seconds, 0, -1):
            if self.stop_requested:
                break
            self.status_var.set(f"{message} {remaining}s")
            self.app.update()
            time.sleep(1)

    def stop_process(self):
        self.stop_requested = True
        self.status_var.set("Se opreste...")

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    app = ScreenshotApp()
    app.run()
