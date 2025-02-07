from datetime import datetime, timedelta
import threading
import time
from tkinter import ttk
from typing import Optional, Tuple
from tkinter import IntVar, StringVar, BooleanVar
from tkinter.ttk import Button, Entry, Label, Progressbar, Frame, Radiobutton
from ttkthemes import ThemedTk

from utils.helpers import Logger, SystemUtils, ScreenshotManager

class ScreenshotApp:
    # Application configurations
    WINDOW_SIZE = "700x500"
    THEME = "arc"
    TITLE = "Optimad"

    # Interval and timing configurations
    INITIAL_COUNTDOWN = 15  # seconds until first screenshot
    COUNTDOWN_CHECK_INTERVAL = 0.1  # countdown check interval
    THREAD_CLEANUP_TIMEOUT = 0.5  # thread cleanup wait time

    # Validation limits
    MAX_HOURS = 24
    MAX_SCREENSHOTS = 60
    MIN_INTERVAL_MINUTES = 1  # Minimum interval between screenshots in minutes

    # UI configurations
    ENTRY_WIDTH = 30
    PROGRESS_BAR_LENGTH = 400

    # Font configurations
    FONTS = {
        'header': ('Arial', 12),
        'normal': ('Arial', 10),
        'option': ('Arial', 11)
    }

    # Application mapping
    APP_NAMES = {
        "zoom": "Zoom",
        "teams": "Microsoft Teams",
        "chrome": "Google Chrome"
    }

    def __init__(self):
        """Initialize the application with required components and state"""
        self.logger = Logger()
        self.system_utils = SystemUtils()
        self.stop_requested = False
        self.is_running = False
        self.process_thread = None
        self.stop_event = threading.Event()
        self.setup_ui()

    def setup_ui(self):
        """Set up the user interface components"""
        self.app = ThemedTk(theme=self.THEME)
        self.app.title(self.TITLE)
        self.app.geometry(self.WINDOW_SIZE)

        style = ttk.Style()
        style.configure('Header.TLabel', font=self.FONTS['header'])
        style.configure('Normal.TLabel', font=self.FONTS['normal'])
        style.configure('Option.TRadiobutton', font=self.FONTS['option'])

        self._init_variables()
        self._create_ui_elements()

    def _init_variables(self):
        """Initialize all UI variables"""
        self.hours_var = StringVar()
        self.screenshots_var = StringVar()
        self.status_var = StringVar(value="Ready")
        self.progress_var = IntVar()
        self.start_option = StringVar(value="now")
        self.start_time_var = StringVar()
        self.app_choice = StringVar(value="zoom")

    def _create_ui_elements(self):
        """Create and layout all UI elements"""
        # Input Frame
        input_frame = Frame(self.app)
        input_frame.pack(pady=10, padx=20, fill="x")

        Label(input_frame, text="Course hours:", style='Header.TLabel').pack(pady=5)
        Entry(input_frame, textvariable=self.hours_var, font=self.FONTS['normal'],
              width=self.ENTRY_WIDTH).pack(pady=5)

        Label(input_frame, text="Number of screenshots:", style='Header.TLabel').pack(pady=5)
        Entry(input_frame, textvariable=self.screenshots_var, font=self.FONTS['normal'],
              width=self.ENTRY_WIDTH).pack(pady=5)

        # App Selection Frame
        self._create_app_selection_frame()

        # Start Options Frame
        self._create_start_options_frame()

        # Control Buttons and Progress Elements
        self._create_control_elements()

    def _create_app_selection_frame(self):
        """Create the application selection frame"""
        app_frame = Frame(self.app)
        app_frame.pack(pady=5, padx=20, fill="x")

        Label(app_frame, text="Select application:", style='Header.TLabel').pack(pady=5)

        app_options_frame = Frame(app_frame)
        app_options_frame.pack()

        for key, name in self.APP_NAMES.items():
            Radiobutton(app_options_frame, text=name, variable=self.app_choice,
                       value=key, style='Option.TRadiobutton').pack(side="left", padx=10)

    def _create_start_options_frame(self):
        """Create the start options frame"""
        options_frame = Frame(self.app)
        options_frame.pack(pady=10, padx=20, fill="x")

        Radiobutton(options_frame, text="Start now", variable=self.start_option,
                   value="now", command=self._toggle_time_input,
                   style='Option.TRadiobutton').pack(pady=5)

        time_frame = Frame(options_frame)
        time_frame.pack(pady=5)

        Radiobutton(time_frame, text="Start at:", variable=self.start_option,
                   value="scheduled", command=self._toggle_time_input,
                   style='Option.TRadiobutton').pack(side="left")

        self.time_entry = Entry(time_frame, textvariable=self.start_time_var,
                              font=self.FONTS['normal'], width=10, state="disabled")
        self.time_entry.pack(side="left", padx=5)
        Label(time_frame, text="(Format: HH:MM)", style='Normal.TLabel').pack(side="left")

    def _create_control_elements(self):
        """Create control buttons and progress elements"""
        self.start_button = Button(self.app, text="Start Process", command=self.start_process)
        self.start_button.pack(pady=10)

        self.stop_button = Button(self.app, text="Stop Process",
                                command=self.stop_process, state="disabled")
        self.stop_button.pack(pady=5)

        Label(self.app, textvariable=self.status_var,
              style='Normal.TLabel').pack(pady=10)

        self.progress_bar = Progressbar(self.app, orient="horizontal",
                                      length=self.PROGRESS_BAR_LENGTH,
                                      mode="determinate", variable=self.progress_var)
        self.progress_bar.pack(pady=10)

    def _validate_inputs(self) -> Tuple[int, int]:
        """
        Validate input values and return validated hours and screenshots

        Returns:
            Tuple[int, int]: Validated (hours, screenshots)

        Raises:
            ValueError: If validation fails
        """
        try:
            hours = int(self.hours_var.get())
            screenshots = int(self.screenshots_var.get())

            if hours <= 0 or hours > self.MAX_HOURS:
                raise ValueError(f"Hours must be between 1 and {self.MAX_HOURS}")

            if screenshots <= 0 or screenshots > self.MAX_SCREENSHOTS:
                raise ValueError(f"Screenshots must be between 1 and {self.MAX_SCREENSHOTS}")

            if (hours * 60 / screenshots) < self.MIN_INTERVAL_MINUTES:
                raise ValueError(f"Minimum interval between screenshots is {self.MIN_INTERVAL_MINUTES} minute(s)")

            return hours, screenshots

        except ValueError as e:
            if "invalid literal for int()" in str(e):
                raise ValueError("Please enter valid numbers")
            raise

    def _manage_system_date(self, date: datetime, logger: Logger) -> bool:
        """
        Centralized system date management

        Args:
            date: The date to set
            logger: Logger instance

        Returns:
            bool: Success status
        """
        try:
            return self.system_utils.set_system_date(
                date.strftime("%m/%d/%Y"),
                logger
            )
        except Exception as e:
            logger.log(f"Error setting system date: {e}")
            return False

    def _toggle_time_input(self):
        """Toggle time input field based on start option"""
        self.time_entry.config(
            state="normal" if self.start_option.get() == "scheduled" else "disabled"
        )

    def _validate_time_format(self, time_str: str) -> bool:
        """
        Validate time string format

        Args:
            time_str: Time string to validate

        Returns:
            bool: True if valid format
        """
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _wait_until_start_time(self, start_time: str) -> bool:
        """
        Wait until the scheduled start time

        Args:
            start_time: Target start time

        Returns:
            bool: True if wait completed, False if interrupted
        """
        target_time = datetime.strptime(start_time, "%H:%M").time()
        while datetime.now().time() < target_time and not self.stop_requested:
            remaining = datetime.combine(datetime.today(), target_time) - datetime.now()
            minutes, seconds = divmod(remaining.seconds, 60)
            self.status_var.set(f"Waiting until {start_time} ({minutes:02d}:{seconds:02d})")
            self.app.update()
            time.sleep(1)
        return not self.stop_requested

    def start_process(self):
        """Start the screenshot process"""
        if self.is_running:
            return

        try:
            hours, screenshots = self._validate_inputs()

            if self.start_option.get() == "scheduled":
                if not self.start_time_var.get() or not self._validate_time_format(self.start_time_var.get()):
                    raise ValueError("Invalid time format. Use HH:MM")

            self.is_running = True
            self.stop_requested = False
            self.stop_event.clear()
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")

            self.process_thread = threading.Thread(
                target=self._run_scheduled_process,
                args=(hours, screenshots)
            )
            self.process_thread.daemon = True
            self.process_thread.start()

        except ValueError as e:
            self.logger.log(f"Invalid input: {e}")
            self.status_var.set(f"Error: {str(e)}")
        except Exception as e:
            self.logger.log(f"Unexpected error: {e}")
            self.status_var.set("An unexpected error occurred")

    def _run_scheduled_process(self, hours: int, screenshots: int):
        """
        Run the scheduled screenshot process

        Args:
            hours: Number of hours
            screenshots: Number of screenshots
        """
        if self.start_option.get() == "scheduled":
            if not self._wait_until_start_time(self.start_time_var.get()):
                self._cleanup()
                return

        self._process_screenshots(hours, screenshots)

    def _process_screenshots(self, hours: int, screenshots: int):
        """
        Process screenshots with fixed date progression

        Args:
            hours: Number of hours
            screenshots: Number of screenshots
        """
        initial_date = datetime.now()
        screenshot_mgr = ScreenshotManager(
            initial_date.strftime("%Y-%m-%d"),
            self.logger
        )

        app_name = self.APP_NAMES.get(self.app_choice.get(), "Zoom")
        current_date = initial_date

        try:
            interval = (hours * 3600) // screenshots
            self._update_progress(0, screenshots)

            for i in range(screenshots):
                # Single check for stop at iteration start
                if self.stop_requested:
                    self.logger.log("Process stopped by user")
                    return

                # System date management
                if i > 0:
                    current_date += timedelta(days=1)
                    if not self._manage_system_date(current_date, self.logger):
                        raise RuntimeError("Could not set system date")
                else:
                    if not self._countdown(self.INITIAL_COUNTDOWN, "First screenshot in"):
                        return

                # Screenshot capture
                if self.system_utils.focus_window(app_name, self.logger):
                    screenshot_mgr.capture(current_date)
                    self._update_progress(i + 1, screenshots)

                # Wait for next screenshot
                if i < screenshots - 1:
                    if not self._countdown(interval, "Next screenshot in"):
                        return

        except Exception as e:
            self.logger.log(f"Error during process: {e}")
            raise

        finally:
            # Restore initial date
            self._manage_system_date(initial_date, self.logger)
            self._cleanup()

    def _cleanup(self):
        """Clean up resources and reset UI state"""
        self.is_running = False
        self.stop_requested = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Process completed")

    def _update_progress(self, current: int, total: int):
        """
        Update progress bar and status

        Args:
            current: Current progress
            total: Total steps
        """
        self.progress_var.set(int((current / total) * 100))
        self.status_var.set(f"Progress: {current}/{total}")
        self.app.update()

    def _countdown(self, seconds: int, message: str) -> bool:
        """
        Perform countdown with improved interruption handling

        Args:
            seconds: Number of seconds
            message: Message to display

        Returns:
            bool: True if completed, False if interrupted
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

                if self.stop_event.wait(timeout=self.COUNTDOWN_CHECK_INTERVAL):
                    return False

            return True

        except Exception as e:
            self.logger.log(f"Error in countdown: {e}")
            return False

    def stop_process(self):
        """Stop the process and update UI"""
        self.logger.log("Stop requested - terminating process")
        self.stop_requested = True
        self.stop_event.set()

        self.status_var.set("Stopping...")
        self.app.update()

        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=self.THREAD_CLEANUP_TIMEOUT)

        self._cleanup()
        self.status_var.set("Stopped")
        self.app.update()

        self.process_thread = None
        self.logger.log("Process stopped successfully")

    def run(self):
        """Start the application main loop"""
        try:
            self.app.mainloop()
        except Exception as e:
            self.logger.log(f"Application error: {e}")
            raise
        finally:
            # Ensure system date is restored if application crashes
            self.system_utils.set_system_date(
                datetime.now().strftime("%m/%d/%Y"),
                self.logger
            )

def main():
    """
    Main entry point for the application
    """
    try:
        app = ScreenshotApp()
        app.run()
    except Exception as e:
        print(f"Fatal error: {e}")
        # In a production environment, you might want to log this to a file
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
