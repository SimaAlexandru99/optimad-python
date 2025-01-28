from datetime import datetime, timedelta
import threading
import time
from tkinter import ttk
from typing import Optional
from tkinter import IntVar, StringVar, BooleanVar
from tkinter.ttk import Button, Entry, Label, Progressbar, Frame, Radiobutton
from ttkthemes import ThemedTk

from utils.helpers import Logger, SystemUtils, ScreenshotManager

class ScreenshotApp:
    # Configurări aplicație
    WINDOW_SIZE = "700x500"
    THEME = "arc"
    TITLE = "Optimad"

    # Configurări intervale și timpi
    INITIAL_COUNTDOWN = 15  # secunde până la primul screenshot
    COUNTDOWN_CHECK_INTERVAL = 0.1  # interval verificare pentru countdown
    THREAD_CLEANUP_TIMEOUT = 0.5  # timp așteptare pentru cleanup thread

    # Configurări UI
    ENTRY_WIDTH = 30
    PROGRESS_BAR_LENGTH = 400

    # Configurări font
    FONTS = {
        'header': ('Arial', 12),
        'normal': ('Arial', 10),
        'option': ('Arial', 11)
    }

    # Mapare aplicații
    APP_NAMES = {
        "zoom": "Zoom",
        "teams": "Microsoft Teams",
        "chrome": "Google Chrome"
    }

    def __init__(self):
        self.logger = Logger()
        self.system_utils = SystemUtils()
        self.stop_requested = False
        self.is_running = False
        self.process_thread = None
        self.stop_event = threading.Event()

        self.setup_ui()

    def setup_ui(self):
        self.app = ThemedTk(theme=self.THEME)
        self.app.title(self.TITLE)
        self.app.geometry(self.WINDOW_SIZE)

        # Configure style
        style = ttk.Style()
        style.configure('Header.TLabel', font=self.FONTS['header'])
        style.configure('Normal.TLabel', font=self.FONTS['normal'])
        style.configure('Option.TRadiobutton', font=self.FONTS['option'])

        # Initialize variables
        self._init_variables()

        # Create UI elements
        self._create_ui_elements()

    def _init_variables(self):
        """Initialize all UI variables"""
        self.hours_var = StringVar()
        self.screenshots_var = StringVar()
        self.status_var = StringVar(value="Pregătit")
        self.progress_var = IntVar()
        self.start_option = StringVar(value="now")
        self.start_time_var = StringVar()
        self.app_choice = StringVar(value="zoom")

    def _create_ui_elements(self):
        # Configure styles for ttk widgets
        style = ttk.Style()
        style.configure('Header.TLabel', font=('Arial', 12))
        style.configure('Normal.TLabel', font=('Arial', 10))
        style.configure('Option.TRadiobutton', font=('Arial', 11))

        # Input Frame
        input_frame = Frame(self.app)
        input_frame.pack(pady=10, padx=20, fill="x")

        Label(input_frame, text="Numărul de ore de curs:", style='Header.TLabel').pack(pady=5)
        Entry(input_frame, textvariable=self.hours_var, font=("Arial", 12), width=30).pack(pady=5)

        Label(input_frame, text="Numărul de screenshot-uri:", style='Header.TLabel').pack(pady=5)
        Entry(input_frame, textvariable=self.screenshots_var, font=("Arial", 12), width=30).pack(pady=5)

        # App Selection Frame
        app_frame = Frame(self.app)
        app_frame.pack(pady=5, padx=20, fill="x")

        Label(app_frame, text="Selectează aplicația:", style='Header.TLabel').pack(pady=5)

        app_options_frame = Frame(app_frame)
        app_options_frame.pack()

        Radiobutton(app_options_frame, text="Zoom", variable=self.app_choice,
                   value="zoom", style='Option.TRadiobutton').pack(side="left", padx=10)
        Radiobutton(app_options_frame, text="Microsoft Teams", variable=self.app_choice,
                   value="teams", style='Option.TRadiobutton').pack(side="left", padx=10)
        Radiobutton(app_options_frame, text="Google Chrome", variable=self.app_choice,
                   value="chrome", style='Option.TRadiobutton').pack(side="left", padx=10)

        # Start Options Frame
        options_frame = Frame(self.app)
        options_frame.pack(pady=10, padx=20, fill="x")

        Radiobutton(options_frame, text="Pornește acum", variable=self.start_option,
                   value="now", command=self._toggle_time_input,
                   style='Option.TRadiobutton').pack(pady=5)

        time_frame = Frame(options_frame)
        time_frame.pack(pady=5)

        Radiobutton(time_frame, text="Pornește la ora:", variable=self.start_option,
                   value="scheduled", command=self._toggle_time_input,
                   style='Option.TRadiobutton').pack(side="left")

        self.time_entry = Entry(time_frame, textvariable=self.start_time_var,
                              font=("Arial", 12), width=10, state="disabled")
        self.time_entry.pack(side="left", padx=5)
        Label(time_frame, text="(Format: HH:MM)", style='Normal.TLabel').pack(side="left")

        # Control Buttons
        self.start_button = Button(self.app, text="Pornește Procesul", command=self.start_process)
        self.start_button.pack(pady=10)

        self.stop_button = Button(self.app, text="Oprește Procesul", command=self.stop_process, state="disabled")
        self.stop_button.pack(pady=5)

        Label(self.app, textvariable=self.status_var, style='Normal.TLabel').pack(pady=10)

        self.progress_bar = Progressbar(self.app, orient="horizontal", length=400,
                                      mode="determinate", variable=self.progress_var)
        self.progress_bar.pack(pady=10)

    def _toggle_time_input(self):
        if self.start_option.get() == "scheduled":
            self.time_entry.config(state="normal")
        else:
            self.time_entry.config(state="disabled")

    def _validate_time_format(self, time_str: str) -> bool:
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _wait_until_start_time(self, start_time: str):
        target_time = datetime.strptime(start_time, "%H:%M").time()
        while datetime.now().time() < target_time and not self.stop_requested:
            remaining = datetime.combine(datetime.today(), target_time) - datetime.now()
            minutes = remaining.seconds // 60
            seconds = remaining.seconds % 60
            self.status_var.set(f"Așteptare până la {start_time} ({minutes:02d}:{seconds:02d})")
            self.app.update()
            time.sleep(1)
        return not self.stop_requested

    def start_process(self):
        if self.is_running:
            return

        try:
            hours = int(self.hours_var.get())
            screenshots = int(self.screenshots_var.get())

            if hours < 1 or screenshots < 1:
                raise ValueError("Values must be positive")

            if self.start_option.get() == "scheduled":
                if not self.start_time_var.get() or not self._validate_time_format(self.start_time_var.get()):
                    raise ValueError("Invalid time format. Use HH:MM")

            self.is_running = True
            self.stop_requested = False
            self.stop_event.clear()  # Reset stop event
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

            # Create and start new process thread
            self.process_thread = threading.Thread(
                target=self._run_scheduled_process,
                args=(hours, screenshots)
            )
            self.process_thread.daemon = True
            self.process_thread.start()

        except ValueError as e:
            self.logger.log(f"Invalid input: {e}")
            self.status_var.set(f"Error: {str(e)}")

    def _run_scheduled_process(self, hours: int, screenshots: int):
        if self.start_option.get() == "scheduled":
            if not self._wait_until_start_time(self.start_time_var.get()):
                self._cleanup()
                return

        self._process_screenshots(hours, screenshots)

    def _process_screenshots(self, hours: int, screenshots: int):
        initial_date = datetime.now().strftime("%m/%d/%Y")
        screenshot_mgr = ScreenshotManager(
            datetime.now().strftime("%Y-%m-%d"),
            self.logger
        )

        # Map pentru numele aplicațiilor
        app_names = {
            "zoom": "Zoom",
            "teams": "Microsoft Teams",
            "chrome": "Google Chrome"
        }
        app_name = app_names.get(self.app_choice.get(), "Zoom")  # Default la Zoom dacă ceva nu merge

        try:
            interval = (hours * 3600) // screenshots
            self._update_progress(0, screenshots)

            for i in range(screenshots):
                if self.stop_requested:
                    self.logger.log("Process stopped by user")
                    break

                screenshot_date = datetime.now() + timedelta(days=i)

                # Check stop flag before starting countdown
                if self.stop_requested:
                    break

                if i > 0:
                    if self.stop_requested:
                        break
                    self.system_utils.set_system_date(
                        screenshot_date.strftime("%m/%d/%Y"),
                        self.logger
                    )
                else:
                    if not self._countdown(15, "First screenshot in"):
                        break

                # Check stop flag before focus and capture
                if self.stop_requested:
                    break

                if self.system_utils.focus_window(app_name, self.logger):
                    if self.stop_requested:
                        break
                    screenshot_mgr.capture(screenshot_date)
                    self._update_progress(i + 1, screenshots)

                # Check stop flag before next interval
                if self.stop_requested:
                    break

                if i < screenshots - 1 and not self.stop_requested:
                    if not self._countdown(interval, "Next screenshot in"):
                        break

        finally:
            if self.stop_requested:
                self.logger.log("Restoring initial date after stop")
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

    def _countdown(self, seconds: int, message: str) -> bool:
        """
        Improved countdown timer that can be interrupted.
        Uses precise timing and better error handling.

        Args:
            seconds: Number of seconds to count down
            message: Message to display during countdown

        Returns:
            bool: True if countdown completed normally, False if interrupted
        """
        try:
            end_time = time.time() + seconds

            while time.time() < end_time:
                if self.stop_event.is_set():
                    self.logger.log("Countdown interrupted")
                    return False

                remaining = max(0, int(end_time - time.time()))
                self.status_var.set(f"{message} {remaining}s")
                self.app.update()

                # Use event wait instead of sleep for better responsiveness
                if self.stop_event.wait(timeout=self.COUNTDOWN_CHECK_INTERVAL):
                    return False

            return True

        except Exception as e:
            self.logger.log(f"Error in countdown: {e}")
            return False

    def stop_process(self):
        """
        Immediately stops the process and updates the UI
        """
        self.logger.log("Stop requested - terminating process")
        self.stop_requested = True
        self.stop_event.set()  # Signal all operations to stop

        self.status_var.set("Se opreste...")
        self.app.update()

        # Wait briefly for thread to clean up
        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=0.5)

        self._cleanup()
        self.status_var.set("Oprit")
        self.app.update()

        # Reset thread
        self.process_thread = None
        self.logger.log("Process stopped successfully")

    def run(self):
        self.app.mainloop()

if __name__ == "__main__":
    app = ScreenshotApp()
    app.run()
