from datetime import datetime, timedelta
import threading
import time
from typing import Optional, Tuple, Dict, Any
import os
import json
import sys
import ctypes
from pathlib import Path
from tkinter import IntVar, StringVar, BooleanVar, PhotoImage, messagebox
import ttkbootstrap as tb  # type: ignore
from ttkbootstrap.constants import * # type: ignore

from utils.helpers import Logger, SystemUtils, ScreenshotManager
from utils.constants import *  # Import all constants

def is_admin():
    """Verifică dacă programul rulează cu drepturi de administrator"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def restart_as_admin():
    """Repornește aplicația cu drepturi de administrator"""
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit(0)

class ScreenshotApp:
    def __init__(self, logger=None, system_utils=None):
        """Initialize the application with required components and state"""
        self.logger = logger or Logger(LOG_DIR)
        self.system_utils = system_utils or SystemUtils()
        self.stop_requested = False
        self.is_running = False
        self.process_thread = None
        self.stop_event = threading.Event()
        self.theme = self._load_theme()
        self.notification_visible = False
        self.schedule_config = self._load_schedule_config()
        self.setup_ui()

    def _load_theme(self):
        """Load theme configuration from file"""
        theme_config_path = Path(CONFIG_FILENAME)
        theme = DEFAULT_THEME

        try:
            if theme_config_path.exists():
                with open(theme_config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    if "theme" in config and config["theme"] in VALID_THEMES:
                        theme = config["theme"]
                    else:
                        config["theme"] = theme
                        with open(theme_config_path, "w", encoding="utf-8") as f:
                            json.dump(config, f, indent=2)
                        print(f"Temă invalidă în fișierul de configurare. S-a revenit la tema implicită: {theme}")
        except Exception as e:
            print(f"Eroare la încărcarea temei: {e}")
            try:
                with open(theme_config_path, "w", encoding="utf-8") as f:
                    json.dump({"mode": "dark", "theme": theme}, f, indent=2)
            except:
                pass

        return theme

    def _load_schedule_config(self) -> Dict[str, Any]:
        """Load scheduling configuration from file"""
        config_path = Path(SCHEDULE_CONFIG_FILENAME)
        default_config = {
            "start_option": DEFAULT_START_OPTION,
            "start_time": DEFAULT_START_TIME,
            "hours": DEFAULT_HOURS,
            "screenshots": DEFAULT_SCREENSHOTS,
            "app_choice": DEFAULT_APP_CHOICE,
            "last_run": None,
            "is_scheduled_daily": DEFAULT_START_OPTION == "daily"
        }

        if not config_path.exists():
            # Create default config file if it doesn't exist
            try:
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(default_config, f, indent=2)
            except Exception as e:
                self.logger.log(f"Eroare la crearea fișierului de configurare: {e}")

            return default_config

        # Load existing config
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                # Ensure all default fields exist
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
            return config
        except Exception as e:
            self.logger.log(f"Eroare la încărcarea configurației: {e}")
            return default_config

    def _save_schedule_config(self) -> bool:
        """Save current scheduling configuration to file"""
        config_path = Path(SCHEDULE_CONFIG_FILENAME)

        # Update config with current UI values
        self.schedule_config.update({
            "start_option": self.start_option.get(),
            "start_time": self.start_time_var.get(),
            "hours": self.hours_var.get(),
            "screenshots": self.screenshots_var.get(),
            "app_choice": self.app_choice.get(),
            "is_scheduled_daily": self.start_option.get() == "daily"
        })

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(self.schedule_config, f, indent=2)
            return True
        except Exception as e:
            self.logger.log(f"Eroare la salvarea configurației: {e}")
            return False

    def _save_and_notify(self):
        """Save configuration and notify the user"""
        success = self._save_schedule_config()

        if success:
            messagebox.showinfo(
                "Configurație salvată",
                "Configurația de programare a fost salvată cu succes."
            )

            if self.start_option.get() == "daily":
                # Update next run time display
                next_run = self._calculate_next_daily_run()
                if next_run:
                    self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))
        else:
            messagebox.showerror(
                "Eroare salvare",
                "Nu s-a putut salva configurația. Verificați jurnalul pentru mai multe informații."
            )

    def setup_ui(self):
        """Set up the user interface components"""
        self.app = tb.Window(themename=self.theme)
        self.app.title(APP_TITLE)
        self.app.geometry(WINDOW_SIZE)
        self.app.minsize(*MIN_WINDOW_SIZE)

        # Create main container
        self.main_container = tb.Frame(self.app)
        self.main_container.pack(fill=BOTH, expand=YES, padx=20, pady=15)

        self._create_header()
        self._init_variables()
        self._create_content_area()
        self._create_status_bar()

    def _create_header(self):
        """Create header with logo and title"""
        header_frame = tb.Frame(self.main_container)
        header_frame.pack(fill=X, pady=(0, 15))

        title = tb.Label(header_frame, text=APP_TITLE, font=FONTS['header'])
        title.pack(side=LEFT)

        version = tb.Label(header_frame, text=f"v{APP_VERSION}", font=FONTS['small'])
        version.pack(side=RIGHT, padx=10)

    def _init_variables(self):
        """Initialize all UI variables"""
        self.hours_var = StringVar(value=DEFAULT_HOURS)
        self.screenshots_var = StringVar(value=DEFAULT_SCREENSHOTS)
        self.status_var = StringVar(value="Gata")
        self.progress_var = IntVar()
        self.start_option = StringVar(value=DEFAULT_START_OPTION)
        self.start_time_var = StringVar(value=DEFAULT_START_TIME)
        self.app_choice = StringVar(value=DEFAULT_APP_CHOICE)

    def _create_content_area(self):
        """Create main content area with tabbed interface"""
        # Use a notebook to organize content into tabs
        self.notebook = tb.Notebook(self.main_container)
        self.notebook.pack(fill=BOTH, expand=YES)

        # Main settings tab
        self._create_settings_tab()

        # About tab
        self._create_about_tab()

    def _create_settings_tab(self):
        """Create the main settings tab"""
        settings_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(settings_frame, text="Setari")

        # Left and right split
        left_frame = tb.Frame(settings_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))

        right_frame = tb.Frame(settings_frame)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(10, 0))

        # ===== Left Frame Content =====
        # Input Form
        form_frame = tb.LabelFrame(left_frame, text="Configurari Capturi", padding=15)
        form_frame.pack(fill=BOTH, expand=YES)

        tb.Label(form_frame, text="Ore de curs:").grid(row=0, column=0, sticky=W, pady=5)
        hours_entry = tb.Entry(form_frame, textvariable=self.hours_var, width=10)
        hours_entry.grid(row=0, column=1, sticky=W, pady=5)

        tb.Label(form_frame, text="Numar de capturi de ecran:").grid(row=1, column=0, sticky=W, pady=5)
        screenshots_entry = tb.Entry(form_frame, textvariable=self.screenshots_var, width=10)
        screenshots_entry.grid(row=1, column=1, sticky=W, pady=5)

        # App Selection
        app_frame = tb.LabelFrame(left_frame, text="Selecteaza aplicatia", padding=15)
        app_frame.pack(fill=X, pady=15)

        for i, (key, name) in enumerate(SUPPORTED_APPS.items()):
            tb.Radiobutton(
                app_frame, text=name, variable=self.app_choice,
                value=key, bootstyle="primary"  # type: ignore
            ).pack(side=LEFT, padx=10)

        # ===== Right Frame Content =====
        # Start Options
        start_frame = tb.LabelFrame(right_frame, text="Optiuni de pornire", padding=15)
        start_frame.pack(fill=X)

        tb.Radiobutton(
            start_frame, text=SCHEDULING_OPTIONS["now"], variable=self.start_option,
            value="now", command=self._toggle_time_input, bootstyle="success"  # type: ignore
        ).pack(anchor=W, pady=5)

        scheduled_frame = tb.Frame(start_frame)
        scheduled_frame.pack(anchor=W, pady=5)

        tb.Radiobutton(
            scheduled_frame, text=SCHEDULING_OPTIONS["scheduled"], variable=self.start_option,
            value="scheduled", command=self._toggle_time_input, bootstyle="success"  # type: ignore
        ).pack(side=LEFT)

        self.time_entry = tb.Entry(scheduled_frame, textvariable=self.start_time_var, width=8, state="disabled")
        self.time_entry.pack(side=LEFT, padx=5)

        tb.Label(scheduled_frame, text="(Format: HH:MM)").pack(side=LEFT)

        # Add daily scheduling option
        daily_frame = tb.Frame(start_frame)
        daily_frame.pack(anchor=W, pady=5)

        tb.Radiobutton(
            daily_frame, text=SCHEDULING_OPTIONS["daily"], variable=self.start_option,
            value="daily", command=self._toggle_time_input, bootstyle="success"  # type: ignore
        ).pack(side=LEFT)

        self.daily_time_entry = tb.Entry(daily_frame, textvariable=self.start_time_var, width=8)
        self.daily_time_entry.pack(side=LEFT, padx=5)

        tb.Label(daily_frame, text="(Format: HH:MM)").pack(side=LEFT)

        # Initialize time value from config
        self.start_time_var.set(self.schedule_config.get("start_time", DEFAULT_START_TIME))
        self.hours_var.set(self.schedule_config.get("hours", DEFAULT_HOURS))
        self.screenshots_var.set(self.schedule_config.get("screenshots", DEFAULT_SCREENSHOTS))
        self.start_option.set(self.schedule_config.get("start_option", DEFAULT_START_OPTION))
        self.app_choice.set(self.schedule_config.get("app_choice", DEFAULT_APP_CHOICE))

        # Controls
        control_frame = tb.Frame(right_frame)
        control_frame.pack(fill=X, pady=20, anchor=S)

        # Add buttons with better styling
        self.start_button = tb.Button(
            control_frame, text="Porneste Procesul",
            command=self.start_process, bootstyle="success", width=20  # type: ignore
        )
        self.start_button.pack(pady=5)

        self.stop_button = tb.Button(
            control_frame, text="Opreste Procesul",
            command=self.stop_process, bootstyle="danger", width=20, state="disabled"  # type: ignore
        )
        self.stop_button.pack(pady=5)

        self.save_button = tb.Button(
            control_frame, text="Salvează Configurația",
            command=self._save_and_notify, bootstyle="info", width=20  # type: ignore
        )
        self.save_button.pack(pady=5)

        # Progress area with detailed status
        progress_frame = tb.LabelFrame(right_frame, text="Progres", padding=15)
        progress_frame.pack(fill=BOTH, expand=YES, pady=10)

        # Progress status labels
        status_info_frame = tb.Frame(progress_frame)
        status_info_frame.pack(fill=X, pady=(0, 10))

        # Countdown indicator
        self.countdown_var = StringVar(value="In asteptare")
        countdown_frame = tb.Frame(status_info_frame)
        countdown_frame.pack(fill=X, pady=2)
        tb.Label(countdown_frame, text="Timp ramas:", bootstyle="info").pack(side=LEFT)  # type: ignore
        tb.Label(countdown_frame, textvariable=self.countdown_var, bootstyle="info", font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=5)  # type: ignore

        # Screenshot counter
        self.counter_var = StringVar(value="0/0 capturi")
        counter_frame = tb.Frame(status_info_frame)
        counter_frame.pack(fill=X, pady=2)
        tb.Label(counter_frame, text="Progres capturi:", bootstyle="info").pack(side=LEFT)  # type: ignore
        tb.Label(counter_frame, textvariable=self.counter_var, bootstyle="info", font=("Segoe UI", 10, "bold")).pack(side=LEFT, padx=5)  # type: ignore

        # Next run indicator for daily scheduling
        self.next_run_var = StringVar(value="")
        next_run_frame = tb.Frame(status_info_frame)
        next_run_frame.pack(fill=X, pady=2)
        self.next_run_label = tb.Label(next_run_frame, text="Următoarea rulare:", bootstyle="info")  # type: ignore
        self.next_run_value = tb.Label(next_run_frame, textvariable=self.next_run_var, bootstyle="info", font=("Segoe UI", 10, "bold"))  # type: ignore

        # Show/hide next run indicator based on scheduling mode
        if self.start_option.get() == "daily":
            self.next_run_label.pack(side=LEFT)
            self.next_run_value.pack(side=LEFT, padx=5)

        # Progress bar
        self.progress_bar = tb.Progressbar(
            progress_frame, orient="horizontal",
            mode="determinate", variable=self.progress_var,
            bootstyle="success"  # type: ignore
        )
        self.progress_bar.pack(fill=X, pady=5)

        # Apply the current scheduling mode
        self._toggle_time_input()

    def _create_about_tab(self):
        """Create the about tab"""
        about_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(about_frame, text="Despre")

        about_text = (
            f"{APP_TITLE} - Aplicatie pentru capturarea automata a ecranului\n\n"
            "Aceasta aplicatie va permite sa captati automat ecranul la intervale regulate, "
            "precum si sa modificati data sistemului pentru a simula diferite momente de timp.\n\n"
            "Functionalitati:\n"
            "• Captare automata de ecran\n"
            "• Simulare de activitate in timp prin modificarea datei sistemului\n"
            "• Focalizare automata pe aplicatia tinta (Zoom, Teams, Chrome)\n"
            "• Posibilitatea de a programa ora de start\n\n"
            "© 2024 Optimad"
        )

        about_label = tb.Label(
            about_frame, text=about_text, justify=LEFT, wraplength=600
        )
        about_label.pack(pady=20)

    def _create_status_bar(self):
        """Create status bar at bottom of window"""
        status_frame = tb.Frame(self.app)
        status_frame.pack(fill=X, side=BOTTOM, pady=5)

        # Create notification area
        self.notification_frame = tb.Frame(status_frame)
        self.notification_frame.configure(style='danger.TFrame')

        # Error icon and message
        self.error_label = tb.Label(
            self.notification_frame,
            text="⚠️",
            font=("Segoe UI", 12),
            bootstyle="danger"  # type: ignore
        )
        self.error_label.pack(side=LEFT, padx=5)

        self.notification_label = tb.Label(
            self.notification_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bootstyle="danger"  # type: ignore
        )
        self.notification_label.pack(side=LEFT, padx=5)

        # Normal status display
        self.status_label = tb.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side=LEFT, padx=10)

        # Current date/time display
        self.time_var = StringVar()
        self._update_time()

        time_label = tb.Label(status_frame, textvariable=self.time_var)
        time_label.pack(side=RIGHT, padx=10)

    def show_error(self, message: str, title: str = "Eroare"):
        """Display error in UI and show error dialog"""
        self.logger.log(f"Eroare: {message}")

        # Update status with error
        self.status_var.set(message)

        # Show error notification
        if not self.notification_visible:
            self.notification_frame.pack(fill=X, pady=5)
            self.notification_visible = True

            # Initial style configuration
            self.notification_label.configure(style="danger.TLabel")  # Changed from bootstyle to style
            self.error_label.configure(style="danger.TLabel")  # Changed from bootstyle to style

        # Flash the notification
        self._flash_notification()

        # Show error dialog
        messagebox.showerror(title, message)

    def clear_error(self):
        """Clear error notification"""
        if self.notification_visible:
            self.notification_frame.pack_forget()
            self.notification_visible = False

    def _flash_notification(self):
        """Flash the notification to draw attention"""
        def flash():
            if not self.notification_visible:
                return

            # Get the current style configuration
            current_style = self.notification_label.cget("style").split(".")[0]  # Extract the style prefix
            new_style = "danger" if current_style == "warning" else "warning"

            # Update both the label and frame styles
            self.notification_label.configure(style=f"{new_style}.TLabel")  # Changed from bootstyle to style
            self.error_label.configure(style=f"{new_style}.TLabel")  # Changed from bootstyle to style

            # Schedule next flash
            self.app.after(500, flash)

        flash()

    def _update_time(self):
        """Update the current time display in status bar"""
        self.time_var.set(datetime.now().strftime("%d-%m-%Y %H:%M:%S"))
        self.app.after(1000, self._update_time)

    def _toggle_time_input(self):
        """Toggle time input fields based on start option"""
        option = self.start_option.get()

        # Handle time entry field states
        if option == "scheduled":
            self.time_entry.config(state="normal")
            self.daily_time_entry.config(state="disabled")
        elif option == "daily":
            self.time_entry.config(state="disabled")
            self.daily_time_entry.config(state="normal")

            # Calculate and show next run time
            next_run = self._calculate_next_daily_run()
            if next_run:
                self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))

            # Show next run indicator
            self.next_run_label.pack(side=LEFT)
            self.next_run_value.pack(side=LEFT, padx=5)
        else:  # "now"
            self.time_entry.config(state="disabled")
            self.daily_time_entry.config(state="disabled")

            # Hide next run indicator
            self.next_run_label.pack_forget()
            self.next_run_value.pack_forget()

        # Save current configuration
        self._save_schedule_config()

    def _validate_inputs(self) -> Tuple[int, int]:
        """Validate input values and return validated hours and screenshots"""
        try:
            hours = int(self.hours_var.get())
            screenshots = int(self.screenshots_var.get())

            if hours <= 0 or hours > MAX_HOURS:
                raise ValueError(ERROR_MESSAGES['invalid_hours'].format(max_hours=MAX_HOURS))

            if screenshots <= 0 or screenshots > MAX_SCREENSHOTS:
                raise ValueError(ERROR_MESSAGES['invalid_screenshots'].format(max_screenshots=MAX_SCREENSHOTS))

            if (hours * 60 / screenshots) < MIN_INTERVAL_MINUTES:
                raise ValueError(ERROR_MESSAGES['invalid_interval'].format(min_interval=MIN_INTERVAL_MINUTES))

            return hours, screenshots

        except ValueError as e:
            if "invalid literal for int()" in str(e):
                raise ValueError("Introduceti numere valide")
            raise

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
            self.status_var.set(f"Asteptare pana la {start_time} ({minutes:02d}:{seconds:02d})")
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
                    self.show_error("Format de timp invalid. Folositi HH:MM", "Eroare Validare")
                    return

            self.is_running = True
            self.stop_requested = False
            self.stop_event.clear()
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.clear_error()  # Clear any previous errors

            self.process_thread = threading.Thread(
                target=self._run_scheduled_process,
                args=(hours, screenshots)
            )
            self.process_thread.daemon = True
            self.process_thread.start()

        except ValueError as e:
            self.show_error(str(e), "Eroare Validare")
        except Exception as e:
            self.show_error(f"Eroare neasteptata: {str(e)}", "Eroare Sistem")

    def _run_scheduled_process(self, hours: int, screenshots: int):
        """Run the scheduled screenshot process"""
        if self.start_option.get() == "scheduled":
            if not self._wait_until_start_time(self.start_time_var.get()):
                self._cleanup()
                return

        self._process_screenshots(hours, screenshots)

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
            logger.log(f"Eroare la setarea datei sistemului: {e}")
            return False

    def _process_screenshots(self, hours: int, screenshots: int):
        """Process screenshots with fixed date progression"""
        initial_date = datetime.now()
        screenshot_mgr = ScreenshotManager(
            initial_date.strftime("%Y-%m-%d"),
            self.logger
        )

        app_name = SUPPORTED_APPS.get(self.app_choice.get(), "Desktop")
        current_date = initial_date

        try:
            interval = (hours * 3600) // screenshots
            self._update_progress(0, screenshots)
            self.clear_error()  # Clear any previous errors

            for i in range(screenshots):
                # Check for stop at iteration start
                if self.stop_requested:
                    self.logger.log("Proces oprit de utilizator")
                    break  # Changed from return to break to ensure date restoration

                # System date management
                if i > 0:
                    current_date += timedelta(days=1)
                    if not self._manage_system_date(current_date, self.logger):
                        self.show_error("Nu s-a putut seta data sistemului", "Eroare Sistem")
                        raise RuntimeError("Nu s-a putut seta data sistemului")
                else:
                    if not self._countdown(INITIAL_COUNTDOWN, "Prima captura in"):
                        break  # Changed from return to break to ensure date restoration

                # Screenshot capture with retry logic
                screenshot_success = False
                retry_count = 0

                while not screenshot_success and retry_count < MAX_CAPTURE_RETRIES:
                    if retry_count > 0:
                        self.status_var.set(f"Reincerc captura de ecran ({retry_count + 1}/{MAX_CAPTURE_RETRIES})")
                        self.app.update()
                        time.sleep(RETRY_DELAY)

                    if self.app_choice.get() == "desktop" or self.system_utils.focus_window(app_name, self.logger):
                        screenshot_success = screenshot_mgr.capture(current_date)

                    if not screenshot_success:
                        retry_count += 1
                        if retry_count < MAX_CAPTURE_RETRIES:
                            self.show_error(
                                f"Incercare esuata {retry_count}/{MAX_CAPTURE_RETRIES}. Se reincearca...",
                                "Eroare Captura"
                            )

                if not screenshot_success:
                    user_response = messagebox.askyesno(
                        "Eroare Captura",
                        "Nu s-a putut realiza captura de ecran dupa mai multe incercari.\n"
                        "Doriti sa continuati cu urmatoarea captura?",
                        icon="warning"
                    )
                    if not user_response:
                        self.show_error("Proces oprit din cauza esecului capturii de ecran", "Eroare Fatala")
                        break  # Changed from raise to break to ensure date restoration
                    self.logger.log("Utilizatorul a ales sa continue dupa esecul capturii")
                else:
                    self._update_progress(i + 1, screenshots)
                    self.clear_error()  # Clear error if capture was successful
                    self.logger.log(f"Captura {i + 1}/{screenshots} realizata cu succes")

                # Wait for next screenshot
                if i < screenshots - 1:
                    if not self._countdown(interval, "Urmatoarea captura in"):
                        break  # Changed from return to break to ensure date restoration

        except Exception as e:
            self.logger.log(f"Eroare în procesul de captura: {e}")
            self.show_error(str(e), "Eroare in Proces")

        finally:
            # Restore initial date - always executed
            self.logger.log("Se restaurează data inițială a sistemului")
            if not self._manage_system_date(initial_date, self.logger):
                self.show_error("Nu s-a putut restaura data initiala a sistemului", "Avertisment")

            # Make a second restoration attempt if needed
            current_system_date = datetime.now()
            if abs((current_system_date - initial_date).days) > 0:
                self.logger.log("Se face o încercare suplimentară de restaurare a datei")
                time.sleep(1)  # Wait a moment before trying again
                if not self._manage_system_date(initial_date, self.logger):
                    self.show_error("Restaurarea datei a eșuat. Verificați data sistemului manual.", "Avertisment")

            self._cleanup()

    def _cleanup(self):
        """Clean up resources and reset UI state"""
        self.is_running = False
        self.stop_requested = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set("Proces finalizat")
        self.countdown_var.set("In asteptare")
        self.counter_var.set("0/0 capturi")
        self.progress_var.set(0)

    def _update_progress(self, current: int, total: int):
        """Update progress bar and status"""
        self.progress_var.set(int((current / total) * 100))
        self.status_var.set(f"Progres: {current}/{total}")
        self.counter_var.set(f"{current}/{total} capturi")
        self.app.update()

    def _countdown(self, seconds: int, message: str) -> bool:
        """Perform countdown with improved interruption handling"""
        try:
            end_time = time.time() + seconds

            while time.time() < end_time:
                if self.stop_event.is_set():
                    self.logger.log("Numaratoarea inversa intrerupta")
                    return False

                remaining = max(0, int(end_time - time.time()))
                self.status_var.set(f"{message} {remaining}s")
                self.countdown_var.set(f"{remaining}s")
                self.app.update()

                if self.stop_event.wait(timeout=COUNTDOWN_CHECK_INTERVAL):
                    return False

            return True

        except Exception as e:
            self.logger.log(f"Eroare in numaratoarea inversa: {e}")
            return False

    def stop_process(self):
        """Stop the process and update UI"""
        self.logger.log("Oprire solicitata - terminare proces")
        self.stop_requested = True
        self.stop_event.set()

        self.status_var.set("Se opreste...")
        self.app.update()

        if self.process_thread and self.process_thread.is_alive():
            self.process_thread.join(timeout=THREAD_CLEANUP_TIMEOUT)

        self._cleanup()
        self.status_var.set("Oprit")
        self.app.update()

        self.process_thread = None
        self.logger.log("Proces oprit cu succes")

    def run(self):
        """Start the application main loop"""
        try:
            # Start the daily schedule checker if needed
            if self.start_option.get() == "daily":
                # Calculate and display next run time
                next_run = self._calculate_next_daily_run()
                if next_run:
                    self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))
                    self.status_var.set(f"Programat pentru {self.start_time_var.get()}")

            # Start the daily schedule checker
            self._check_daily_schedule()

            # Start main application loop
            self.app.mainloop()
        except Exception as e:
            self.logger.log(f"Eroare aplicatie: {e}")
            raise
        finally:
            # Ensure system date is restored if application crashes
            self.system_utils.set_system_date(
                datetime.now().strftime("%m/%d/%Y"),
                self.logger
            )

    def _calculate_next_daily_run(self) -> Optional[datetime]:
        """
        Calculate the next execution time for a daily scheduled task

        Returns:
            Optional[datetime]: The next scheduled run time or None if invalid
        """
        try:
            if not self.start_time_var.get() or not self._validate_time_format(self.start_time_var.get()):
                return None

            target_time = datetime.strptime(self.start_time_var.get(), "%H:%M").time()
            now = datetime.now()

            # Create a datetime for today with the target time
            next_run = datetime.combine(now.date(), target_time)

            # If that time has already passed today, schedule for tomorrow
            if next_run <= now:
                next_run += timedelta(days=1)

            return next_run
        except Exception as e:
            self.logger.log(f"Eroare la calcularea următoarei rulări: {e}")
            return None

    def _check_daily_schedule(self) -> None:
        """
        Check if it's time to run the daily scheduled task
        This method is called periodically from the application main loop
        """
        if not self.is_running and self.start_option.get() == "daily":
            now = datetime.now()
            next_run = self._calculate_next_daily_run()

            if next_run is None:
                return

            # Update the next run display
            self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))

            # Calculate time difference in seconds
            time_diff = (next_run - now).total_seconds()

            # If it's time to run (within a 30-second window)
            if 0 <= time_diff < 30:
                # Check if we've already run today
                last_run_str = self.schedule_config.get("last_run")
                if last_run_str:
                    try:
                        last_run = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
                        # If the last run was today and at approximately the same time, don't run again
                        if (last_run.date() == now.date() and
                            abs((last_run.hour * 60 + last_run.minute) -
                                (now.hour * 60 + now.minute)) < 5):
                            return
                    except Exception:
                        pass

                # It's time to run and we haven't run yet today
                self.logger.log("Pornire automată programată zilnic")
                self.status_var.set("Pornire automată programată")

                # Record the run time
                self.schedule_config["last_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
                self._save_schedule_config()

                # Start the process
                self.start_process()

        # Schedule the next check in 10 seconds
        self.app.after(10000, self._check_daily_schedule)

def main():
    """Main entry point for the application"""
    try:
        # Verificare drepturi administrator
        if not is_admin():
            # Incearca repornirea cu drepturi de administrator
            messagebox.showinfo("Drepturi de administrator necesare",
                "Aplicatia necesita drepturi de administrator pentru a functiona corect.\n"
                "Se va reporni cu drepturi de administrator.")
            restart_as_admin()
            return

        # Pornirea aplicației doar dacă suntem administrator
        app = ScreenshotApp()
        app.run()
    except Exception as e:
        print(f"Eroare fatala: {e}")
        # In a production environment, you might want to log this to a file
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
