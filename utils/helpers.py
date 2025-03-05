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
import subprocess
import shutil
from PIL import Image

from .constants import (
    MIN_DISK_SPACE, ERROR_MESSAGES, SUPPORTED_IMAGE_FORMATS,
    DEFAULT_IMAGE_FORMAT, DEFAULT_JPEG_QUALITY, LOG_DIR, LOG_FILENAME
)

class Logger:
    """
    Handles application logging with support for both file and widget output.
    """
    def __init__(self, log_dir: str = LOG_DIR):
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
            self.log_file = self.log_dir / LOG_FILENAME

            # Validate write permissions
            if not os.access(self.log_dir, os.W_OK):
                raise PermissionError(f"Nu exista permisiuni de scriere pentru {self.log_dir}")

        except Exception as e:
            raise RuntimeError(f"Esec la initializarea jurnalului: {e}")

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
            messagebox.showerror("Eroare de Jurnalizare", f"Eșec la jurnalizarea mesajului: {str(e)}")

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
            parsed_date = datetime.strptime(new_date, "%m/%d/%Y")

            # Set date based on operating system
            if os.name == 'nt':  # Windows
                # Try multiple approaches to set the date with admin rights
                success = False
                
                # Method 1: Direct command
                cmd1 = f'date {new_date}'
                result1 = subprocess.run(cmd1, shell=True, capture_output=True)
                if result1.returncode == 0:
                    success = True
                
                # Method 2: Via cmd
                if not success:
                    cmd2 = f'cmd /c date {new_date}'
                    result2 = subprocess.run(cmd2, shell=True, capture_output=True)
                    if result2.returncode == 0:
                        success = True
                
                # Method 3: PowerShell
                if not success:
                    ps_date = parsed_date.strftime("%Y-%m-%d")
                    cmd3 = f'powershell -Command "Set-Date -Date \'{ps_date}\'"'
                    result3 = subprocess.run(cmd3, shell=True, capture_output=True)
                    if result3.returncode == 0:
                        success = True
                
                # Method 4: Use WMIC (old but reliable)
                if not success:
                    wmic_date = parsed_date.strftime("%Y%m%d")
                    wmic_time = datetime.now().strftime("%H:%M:%S")
                    cmd4 = f'wmic path win32_localtime set Day={parsed_date.day},Month={parsed_date.month},Year={parsed_date.year}'
                    result4 = subprocess.run(cmd4, shell=True, capture_output=True)
                    if result4.returncode == 0:
                        success = True
                
                if not success:
                    raise OSError(f"Eșec la setarea datei sistemului folosind multiple metode")
            else:  # Unix-like systems
                result = os.system(f'sudo date -s "{new_date}"')
                if result != 0:
                    raise OSError(f"Eșec la setarea datei sistemului. Cod de ieșire: {result}")

            logger.log(f"Data sistemului setată cu succes la {new_date}")
            return True

        except ValueError as e:
            logger.log(f"Format de dată invalid: {e}")
            return False
        except OSError as e:
            logger.log(f"Eroare de sistem la setarea datei: {e}")
            return False
        except Exception as e:
            logger.log(f"Eroare neașteptată la setarea datei: {e}")
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
                        logger.log(f"Focalizat cu succes fereastra {app_name}")
                        return True

                if attempt < retry_attempts - 1:
                    logger.log(f"Încercare {attempt + 1}: {app_name} negăsit, se reîncearcă...")
                    time.sleep(1)  # Wait before retry
                else:
                    logger.log(f"Eșec în găsirea {app_name} după {retry_attempts} încercări")

            except ElementNotFoundError as e:
                if attempt < retry_attempts - 1:
                    logger.log(f"Încercarea {attempt + 1} a eșuat: {e}")
                    time.sleep(1)
                else:
                    logger.log(f"Eșec la focalizarea ferestrei după {retry_attempts} încercări: {e}")

        return False

class ScreenshotManager:
    """Manages screenshot capture and storage operations."""
    
    def __init__(self, root_dir: Union[str, Path], logger: Logger):
        """Initialize the screenshot manager."""
        try:
            self.root_dir = Path(root_dir).resolve()
            self.logger = logger

            self.root_dir.mkdir(parents=True, exist_ok=True)
            if not os.access(self.root_dir, os.W_OK):
                raise PermissionError(f"Nu exista permisiuni de scriere pentru {self.root_dir}")

            if not self._check_disk_space():
                raise RuntimeError(ERROR_MESSAGES['disk_space'])

        except Exception as e:
            raise RuntimeError(f"Esec la initializarea directorului de capturi de ecran: {e}")

    def _get_date_dir(self, date: datetime) -> Path:
        """Get or create date-specific directory for screenshots."""
        date_dir = self.root_dir / date.strftime("%Y-%m-%d")
        date_dir.mkdir(parents=True, exist_ok=True)
        return date_dir

    def _check_disk_space(self) -> bool:
        """Verifica daca exista suficient spatiu pe disc"""
        try:
            total, used, free = shutil.disk_usage(self.root_dir)
            return free > MIN_DISK_SPACE
        except Exception as e:
            self.logger.log(f"Eroare la verificarea spatiului pe disc: {e}")
            return False

    def _verify_saved_file(self, filepath: Path) -> bool:
        """Verifica daca fisierul a fost salvat corect"""
        try:
            if not filepath.exists():
                return False
            
            if filepath.stat().st_size == 0:
                return False
                
            Image.open(filepath).verify()
            return True
        except Exception:
            return False

    def capture(self,
                screenshot_date: datetime,
                format_imagine: str = DEFAULT_IMAGE_FORMAT,
                quality: int = DEFAULT_JPEG_QUALITY) -> bool:
        """Capture and save a screenshot."""
        if format_imagine.lower() not in SUPPORTED_IMAGE_FORMATS:
            self.logger.log(f"Format de imagine neacceptat: {format_imagine}")
            return False

        try:
            if not self._check_disk_space():
                raise RuntimeError(ERROR_MESSAGES['disk_space'])

            if not isinstance(screenshot_date, datetime):
                raise ValueError("Data de captura de ecran invalida furnizata")

            # Get date-specific directory
            save_dir = self._get_date_dir(screenshot_date)
            screenshot = pyautogui.screenshot()
            filename = f"{screenshot_date.strftime('%H-%M-%S')}.{format_imagine}"
            filepath = save_dir / filename

            if filepath.exists():
                self.logger.log(f"Avertisment: Se suprascrie fisierul existent {filepath}")

            if format_imagine.lower() in {'jpg', 'jpeg'}:
                screenshot = screenshot.convert("RGB")
                screenshot.save(filepath, quality=quality)
            else:
                screenshot.save(filepath)

            if not self._verify_saved_file(filepath):
                raise RuntimeError(ERROR_MESSAGES['file_verification'])

            self.logger.log(f"Captura de ecran salvata cu succes la {filepath}")
            
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_OK)
            except:
                pass
                
            return True

        except Exception as e:
            self.logger.log(f"Esec la captura de ecran: {str(e)}")
            messagebox.showerror("Eroare Captura Ecran",
                               f"Esec la capturarea ecranului: {str(e)}")
            return False

    def cleanup_old_screenshots(self, days: int = 30) -> None:
        """
        Remove screenshots older than specified days.

        Args:
            days: Number of days to keep screenshots
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            # Iterate through date directories
            for date_dir in self.root_dir.glob("????-??-??"):
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        shutil.rmtree(date_dir)
                        self.logger.log(f"Sters director vechi de capturi: {date_dir.name}")
                except ValueError:
                    self.logger.log(f"Director invalid ignorat: {date_dir.name}")
                except Exception as e:
                    self.logger.log(f"Eroare la stergerea directorului {date_dir.name}: {e}")

        except Exception as e:
            self.logger.log(f"Eroare in timpul curatarii: {e}")
