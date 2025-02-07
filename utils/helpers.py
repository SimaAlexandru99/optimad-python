import os
import time
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import messagebox
from typing import Optional, Union, NoReturn
import pyautogui
from pywinauto import Desktop
from pywinauto.findwindows import ElementNotFoundError

class Logger:
    """
    Handles application logging with support for both file and widget output.
    """
    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the logger with a specified log directory.

        Args:
            log_dir: Directory path for log files

        Raises:
            RuntimeError: If logger initialization fails
        """
        try:
            self.log_dir = Path(log_dir).resolve()
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.log_file = self.log_dir / "jurnal_erori.txt"

            # Validate write permissions
            if not os.access(self.log_dir, os.W_OK):
                raise PermissionError(f"No write permission for {self.log_dir}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize logger: {e}")

    def log(self, message: str, log_widget: Optional[tk.Text] = None) -> None:
        """
        Log a message to file and optionally to a tkinter widget.

        Args:
            message: Message to log
            log_widget: Optional tkinter Text widget for display
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            log_entry = f"{timestamp} - {message}\n"

            # Write to file
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(log_entry)

            # Update widget if provided
            if log_widget:
                log_widget.config(state='normal')
                log_widget.insert(tk.END, log_entry)
                log_widget.see(tk.END)
                log_widget.config(state='disabled')

        except Exception as e:
            # If logging fails, attempt to show error dialog
            messagebox.showerror("Logging Error", f"Failed to log message: {str(e)}")

class SystemUtils:
    """
    Utility class for system-level operations.
    """
    @staticmethod
    def set_system_date(new_date: str, logger: Logger) -> bool:
        """
        Set the system date with platform-specific implementation.

        Args:
            new_date: Date string in format MM/DD/YYYY
            logger: Logger instance

        Returns:
            bool: Success status
        """
        try:
            # Validate date format
            datetime.strptime(new_date, "%m/%d/%Y")

            # Set date based on operating system
            if os.name == 'nt':  # Windows
                result = os.system(f'date {new_date}')
            else:  # Unix-like systems
                result = os.system(f'sudo date -s "{new_date}"')

            if result != 0:
                raise OSError(f"Failed to set system date. Exit code: {result}")

            logger.log(f"System date successfully set to {new_date}")
            return True

        except ValueError as e:
            logger.log(f"Invalid date format: {e}")
            return False
        except OSError as e:
            logger.log(f"System error setting date: {e}")
            return False
        except Exception as e:
            logger.log(f"Unexpected error setting date: {e}")
            return False

    @staticmethod
    def focus_window(app_name: str, logger: Logger, retry_attempts: int = 3) -> bool:
        """
        Focus a window with retries and improved error handling.

        Args:
            app_name: Name of the application window
            logger: Logger instance
            retry_attempts: Number of retries before giving up

        Returns:
            bool: True if window was focused successfully
        """
        for attempt in range(retry_attempts):
            try:
                windows = Desktop(backend="uia").windows()
                for window in windows:
                    if app_name.lower() in window.window_text().lower():
                        window.set_focus()
                        logger.log(f"Successfully focused {app_name} window")
                        return True

                if attempt < retry_attempts - 1:
                    logger.log(f"Attempt {attempt + 1}: {app_name} not found, retrying...")
                    time.sleep(1)  # Wait before retry
                else:
                    logger.log(f"Failed to find {app_name} after {retry_attempts} attempts")

            except ElementNotFoundError as e:
                if attempt < retry_attempts - 1:
                    logger.log(f"Attempt {attempt + 1} failed: {e}")
                    time.sleep(1)
                else:
                    logger.log(f"Failed to focus window after {retry_attempts} attempts: {e}")

        return False

class ScreenshotManager:
    """
    Manages screenshot capture and storage operations.
    """
    SUPPORTED_FORMATS = {'png', 'jpg', 'jpeg'}

    def __init__(self, save_dir: Union[str, Path], logger: Logger):
        """
        Initialize the screenshot manager.

        Args:
            save_dir: Directory for saving screenshots
            logger: Logger instance

        Raises:
            RuntimeError: If initialization fails
        """
        try:
            self.save_dir = Path(save_dir).resolve()
            self.logger = logger

            self.save_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(self.save_dir, os.W_OK):
                raise PermissionError(f"No write permission for {self.save_dir}")

        except Exception as e:
            raise RuntimeError(f"Failed to initialize screenshot directory: {e}")

    def capture(self,
                screenshot_date: datetime,
                format_imagine: str = "png",
                quality: int = 95) -> bool:
        """
        Capture and save a screenshot.

        Args:
            screenshot_date: Date for the screenshot filename
            format_imagine: Image format (png/jpg/jpeg)
            quality: Image quality for JPEG format

        Returns:
            bool: Success status
        """
        if format_imagine.lower() not in self.SUPPORTED_FORMATS:
            self.logger.log(f"Unsupported image format: {format_imagine}")
            return False

        try:
            # Validate screenshot date
            if not isinstance(screenshot_date, datetime):
                raise ValueError("Invalid screenshot date provided")

            # Capture screenshot
            screenshot = pyautogui.screenshot()
            filename = f"{screenshot_date.strftime('%Y-%m-%d_%H-%M-%S')}.{format_imagine}"
            filepath = self.save_dir / filename

            # Check for existing file
            if filepath.exists():
                self.logger.log(f"Warning: Overwriting existing file {filepath}")

            # Save with appropriate format
            if format_imagine.lower() in {'jpg', 'jpeg'}:
                screenshot = screenshot.convert("RGB")
                screenshot.save(filepath, quality=quality)
            else:
                screenshot.save(filepath)

            self.logger.log(f"Screenshot successfully saved to {filepath}")
            return True

        except Exception as e:
            self.logger.log(f"Failed to capture screenshot: {str(e)}")
            messagebox.showerror("Screenshot Error",
                               f"Failed to capture screenshot: {str(e)}")
            return False

    def cleanup_old_screenshots(self, days: int = 30) -> None:
        """
        Remove screenshots older than specified days.

        Args:
            days: Number of days to keep screenshots
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            for file in self.save_dir.glob("*.*"):
                if file.is_file():
                    # Extract date from filename
                    try:
                        file_date = datetime.strptime(
                            file.stem[:10],
                            "%Y-%m-%d"
                        )
                        if file_date < cutoff_date:
                            file.unlink()
                            self.logger.log(f"Removed old screenshot: {file.name}")
                    except ValueError:
                        self.logger.log(f"Could not parse date from filename: {file.name}")

        except Exception as e:
            self.logger.log(f"Error during cleanup: {e}")
