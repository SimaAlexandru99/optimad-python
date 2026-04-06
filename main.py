import ctypes
import json
import queue
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import IntVar, StringVar, messagebox
from typing import Any, Dict, Optional, Tuple

import ttkbootstrap as tb  # type: ignore
from ttkbootstrap.constants import BOTTOM, BOTH, LEFT, RIGHT, S, W, X, YES  # type: ignore

from utils.constants import (
    APP_TITLE,
    APP_VERSION,
    CONFIG_FILENAME,
    COUNTDOWN_CHECK_INTERVAL,
    DEFAULT_APP_CHOICE,
    DEFAULT_HOURS,
    DEFAULT_SCREENSHOTS,
    DEFAULT_START_OPTION,
    DEFAULT_START_TIME,
    DEFAULT_THEME,
    ERROR_MESSAGES,
    FONTS,
    LOG_DIR,
    MAX_HOURS,
    MAX_SCREENSHOTS,
    MIN_INTERVAL_MINUTES,
    MIN_WINDOW_SIZE,
    RETRY_DELAY,
    SCHEDULE_CONFIG_FILENAME,
    SCHEDULING_OPTIONS,
    SUPPORTED_APPS,
    THREAD_CLEANUP_TIMEOUT,
    VALID_THEMES,
    WINDOW_SIZE,
)
from utils.helpers import Logger, SystemUtils
from utils.process_controller import ScreenshotProcessController


def is_admin() -> bool:
    """Verifica daca programul ruleaza cu drepturi de administrator."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def restart_as_admin() -> None:
    """Reporneste aplicatia cu drepturi de administrator."""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )
    sys.exit(0)


class ScreenshotApp:
    def __init__(
        self, logger: Optional[Logger] = None, system_utils: Optional[SystemUtils] = None
    ):
        """Initialize the application with required components and state."""
        self.logger = logger or Logger(LOG_DIR)
        self.system_utils = system_utils or SystemUtils()
        self.is_running = False
        self.process_thread: Optional[threading.Thread] = None
        self.process_controller: Optional[ScreenshotProcessController] = None
        self.stop_event = threading.Event()
        self.ui_event_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self._time_update_id: Optional[str] = None
        self._daily_check_id: Optional[str] = None
        self._save_config_id: Optional[str] = None
        self._ui_event_pump_id: Optional[str] = None
        self._shutdown_check_id: Optional[str] = None
        self._closing = False
        self.theme = self._load_theme()
        self.notification_visible = False
        self.schedule_config = self._load_schedule_config()
        self.setup_ui()
        self._schedule_ui_event_pump()

    def _now(self) -> datetime:
        return datetime.now()

    def _load_theme(self) -> str:
        """Load theme configuration from file."""
        theme_config_path = Path(CONFIG_FILENAME)
        theme = DEFAULT_THEME

        try:
            if theme_config_path.exists():
                with open(theme_config_path, "r", encoding="utf-8") as file_obj:
                    config = json.load(file_obj)
                    if "theme" in config and config["theme"] in VALID_THEMES:
                        theme = config["theme"]
                    else:
                        config["theme"] = theme
                        with open(theme_config_path, "w", encoding="utf-8") as file_obj:
                            json.dump(config, file_obj, indent=2)
                        print(
                            f"Tema invalida in fisierul de configurare. S-a revenit la tema implicita: {theme}"
                        )
        except Exception as exc:
            print(f"Eroare la incarcarea temei: {exc}")
            try:
                with open(theme_config_path, "w", encoding="utf-8") as file_obj:
                    json.dump({"mode": "dark", "theme": theme}, file_obj, indent=2)
            except Exception:
                pass

        return theme

    def _load_schedule_config(self) -> Dict[str, Any]:
        """Load scheduling configuration from file."""
        config_path = Path(SCHEDULE_CONFIG_FILENAME)
        default_config = {
            "start_option": DEFAULT_START_OPTION,
            "start_time": DEFAULT_START_TIME,
            "hours": DEFAULT_HOURS,
            "screenshots": DEFAULT_SCREENSHOTS,
            "app_choice": DEFAULT_APP_CHOICE,
            "last_run": None,
        }

        if not config_path.exists():
            try:
                with open(config_path, "w", encoding="utf-8") as file_obj:
                    json.dump(default_config, file_obj, indent=2)
            except Exception as exc:
                self.logger.log(f"Eroare la crearea fisierului de configurare: {exc}")
            return default_config

        try:
            with open(config_path, "r", encoding="utf-8") as file_obj:
                config = json.load(file_obj)
            for key, value in default_config.items():
                config.setdefault(key, value)
            return config
        except Exception as exc:
            self.logger.log(f"Eroare la incarcarea configuratiei: {exc}")
            return default_config

    def _save_schedule_config(self) -> bool:
        """Save current scheduling configuration to file."""
        config_path = Path(SCHEDULE_CONFIG_FILENAME)
        self.schedule_config.update(
            {
                "start_option": self.start_option.get(),
                "start_time": self.start_time_var.get(),
                "hours": self.hours_var.get(),
                "screenshots": self.screenshots_var.get(),
                "app_choice": self.app_choice.get(),
            }
        )

        try:
            with open(config_path, "w", encoding="utf-8") as file_obj:
                json.dump(self.schedule_config, file_obj, indent=2)
            return True
        except Exception as exc:
            self.logger.log(f"Eroare la salvarea configuratiei: {exc}")
            return False

    def _save_and_notify(self) -> None:
        """Save configuration and notify the user."""
        success = self._save_schedule_config()

        if success:
            messagebox.showinfo(
                "Configuratie salvata",
                "Configuratia de programare a fost salvata cu succes.",
            )
            if self.start_option.get() == "daily":
                next_run = self._calculate_next_daily_run()
                if next_run:
                    self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))
        else:
            messagebox.showerror(
                "Eroare salvare",
                "Nu s-a putut salva configuratia. Verificati jurnalul pentru mai multe informatii.",
            )

    def setup_ui(self) -> None:
        """Set up the user interface components."""
        self.app = tb.Window(themename=self.theme)
        self.app.title(APP_TITLE)
        self.app.geometry(WINDOW_SIZE)
        self.app.minsize(*MIN_WINDOW_SIZE)
        self.app.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.main_container = tb.Frame(self.app)
        self.main_container.pack(fill=BOTH, expand=YES, padx=20, pady=15)

        self._create_header()
        self._init_variables()
        self._create_content_area()
        self._create_status_bar()

    def _create_header(self) -> None:
        header_frame = tb.Frame(self.main_container)
        header_frame.pack(fill=X, pady=(0, 15))

        tb.Label(header_frame, text=APP_TITLE, font=FONTS["header"]).pack(side=LEFT)
        tb.Label(header_frame, text=f"v{APP_VERSION}", font=FONTS["small"]).pack(
            side=RIGHT, padx=10
        )

    def _init_variables(self) -> None:
        self.hours_var = StringVar(value=DEFAULT_HOURS)
        self.screenshots_var = StringVar(value=DEFAULT_SCREENSHOTS)
        self.status_var = StringVar(value="Gata")
        self.progress_var = IntVar()
        self.start_option = StringVar(value=DEFAULT_START_OPTION)
        self.start_time_var = StringVar(value=DEFAULT_START_TIME)
        self.app_choice = StringVar(value=DEFAULT_APP_CHOICE)
        self.countdown_var = StringVar(value="In asteptare")
        self.counter_var = StringVar(value="0/0 capturi")
        self.next_run_var = StringVar(value="")

    def _create_content_area(self) -> None:
        self.notebook = tb.Notebook(self.main_container)
        self.notebook.pack(fill=BOTH, expand=YES)
        self._create_settings_tab()
        self._create_about_tab()

    def _create_settings_tab(self) -> None:
        settings_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(settings_frame, text="Setari")

        left_frame = tb.Frame(settings_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))

        right_frame = tb.Frame(settings_frame)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(10, 0))

        form_frame = tb.LabelFrame(left_frame, text="Configurari Capturi", padding=15)
        form_frame.pack(fill=BOTH, expand=YES)

        tb.Label(form_frame, text="Ore de curs:").grid(row=0, column=0, sticky=W, pady=5)
        tb.Entry(form_frame, textvariable=self.hours_var, width=10).grid(
            row=0, column=1, sticky=W, pady=5
        )

        tb.Label(form_frame, text="Numar de capturi de ecran:").grid(
            row=1, column=0, sticky=W, pady=5
        )
        tb.Entry(form_frame, textvariable=self.screenshots_var, width=10).grid(
            row=1, column=1, sticky=W, pady=5
        )

        app_frame = tb.LabelFrame(left_frame, text="Selecteaza aplicatia", padding=15)
        app_frame.pack(fill=X, pady=15)

        for key, name in SUPPORTED_APPS.items():
            tb.Radiobutton(
                app_frame,
                text=name,
                variable=self.app_choice,
                value=key,
                bootstyle="primary",  # type: ignore[arg-type]
            ).pack(side=LEFT, padx=10)

        start_frame = tb.LabelFrame(right_frame, text="Optiuni de pornire", padding=15)
        start_frame.pack(fill=X)

        tb.Radiobutton(
            start_frame,
            text=SCHEDULING_OPTIONS["now"],
            variable=self.start_option,
            value="now",
            command=self._toggle_time_input,
            bootstyle="success",  # type: ignore[arg-type]
        ).pack(anchor=W, pady=5)

        scheduled_frame = tb.Frame(start_frame)
        scheduled_frame.pack(anchor=W, pady=5)

        tb.Radiobutton(
            scheduled_frame,
            text=SCHEDULING_OPTIONS["scheduled"],
            variable=self.start_option,
            value="scheduled",
            command=self._toggle_time_input,
            bootstyle="success",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        self.time_entry = tb.Entry(
            scheduled_frame, textvariable=self.start_time_var, width=8, state="disabled"
        )
        self.time_entry.pack(side=LEFT, padx=5)
        tb.Label(scheduled_frame, text="(Format: HH:MM)").pack(side=LEFT)

        daily_frame = tb.Frame(start_frame)
        daily_frame.pack(anchor=W, pady=5)

        tb.Radiobutton(
            daily_frame,
            text=SCHEDULING_OPTIONS["daily"],
            variable=self.start_option,
            value="daily",
            command=self._toggle_time_input,
            bootstyle="success",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        self.daily_time_entry = tb.Entry(
            daily_frame, textvariable=self.start_time_var, width=8
        )
        self.daily_time_entry.pack(side=LEFT, padx=5)
        tb.Label(daily_frame, text="(Format: HH:MM)").pack(side=LEFT)

        self.start_time_var.set(self.schedule_config.get("start_time", DEFAULT_START_TIME))
        self.hours_var.set(self.schedule_config.get("hours", DEFAULT_HOURS))
        self.screenshots_var.set(
            self.schedule_config.get("screenshots", DEFAULT_SCREENSHOTS)
        )
        self.start_option.set(self.schedule_config.get("start_option", DEFAULT_START_OPTION))
        self.app_choice.set(self.schedule_config.get("app_choice", DEFAULT_APP_CHOICE))

        control_frame = tb.Frame(right_frame)
        control_frame.pack(fill=X, pady=20, anchor=S)

        self.start_button = tb.Button(
            control_frame,
            text="Porneste Procesul",
            command=self.start_process,
            bootstyle="success",  # type: ignore[arg-type]
            width=20,
        )
        self.start_button.pack(pady=5)

        self.stop_button = tb.Button(
            control_frame,
            text="Opreste Procesul",
            command=self.stop_process,
            bootstyle="danger",  # type: ignore[arg-type]
            width=20,
            state="disabled",
        )
        self.stop_button.pack(pady=5)

        self.save_button = tb.Button(
            control_frame,
            text="Salveaza Configuratia",
            command=self._save_and_notify,
            bootstyle="info",  # type: ignore[arg-type]
            width=20,
        )
        self.save_button.pack(pady=5)

        progress_frame = tb.LabelFrame(right_frame, text="Progres", padding=15)
        progress_frame.pack(fill=BOTH, expand=YES, pady=10)

        status_info_frame = tb.Frame(progress_frame)
        status_info_frame.pack(fill=X, pady=(0, 10))

        countdown_frame = tb.Frame(status_info_frame)
        countdown_frame.pack(fill=X, pady=2)
        tb.Label(countdown_frame, text="Timp ramas:", bootstyle="info").pack(side=LEFT)  # type: ignore[arg-type]
        tb.Label(
            countdown_frame,
            textvariable=self.countdown_var,
            bootstyle="info",  # type: ignore[arg-type]
            font=("Segoe UI", 10, "bold"),
        ).pack(side=LEFT, padx=5)

        counter_frame = tb.Frame(status_info_frame)
        counter_frame.pack(fill=X, pady=2)
        tb.Label(counter_frame, text="Progres capturi:", bootstyle="info").pack(side=LEFT)  # type: ignore[arg-type]
        tb.Label(
            counter_frame,
            textvariable=self.counter_var,
            bootstyle="info",  # type: ignore[arg-type]
            font=("Segoe UI", 10, "bold"),
        ).pack(side=LEFT, padx=5)

        next_run_frame = tb.Frame(status_info_frame)
        next_run_frame.pack(fill=X, pady=2)
        self.next_run_label = tb.Label(
            next_run_frame,
            text="Urmatoarea rulare:",
            bootstyle="info",  # type: ignore[arg-type]
        )
        self.next_run_value = tb.Label(
            next_run_frame,
            textvariable=self.next_run_var,
            bootstyle="info",  # type: ignore[arg-type]
            font=("Segoe UI", 10, "bold"),
        )

        if self.start_option.get() == "daily":
            self.next_run_label.pack(side=LEFT)
            self.next_run_value.pack(side=LEFT, padx=5)

        self.progress_bar = tb.Progressbar(
            progress_frame,
            orient="horizontal",
            mode="determinate",
            variable=self.progress_var,
            bootstyle="success",  # type: ignore[arg-type]
        )
        self.progress_bar.pack(fill=X, pady=5)

        self._toggle_time_input()

    def _create_about_tab(self) -> None:
        about_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(about_frame, text="Despre")

        about_text = (
            f"{APP_TITLE} - Aplicatie pentru capturarea automata a ecranului\n\n"
            "Aceasta aplicatie permite capturi automate de ecran la intervale regulate "
            "si poate modifica temporar data sistemului pentru a simula activitate pe mai multe zile.\n\n"
            "Functionalitati:\n"
            "- Captare automata de ecran\n"
            "- Simulare de activitate in timp prin modificarea datei sistemului\n"
            "- Focalizare automata pe aplicatia tinta (Zoom, Teams, Chrome)\n"
            "- Posibilitatea de a programa ora de start\n\n"
            "© 2026 Optimad"
        )

        tb.Label(about_frame, text=about_text, justify=LEFT, wraplength=600).pack(
            pady=20
        )

    def _create_status_bar(self) -> None:
        status_frame = tb.Frame(self.app)
        status_frame.pack(fill=X, side=BOTTOM, pady=5)

        self.notification_frame = tb.Frame(status_frame)
        self.notification_frame.configure(style="danger.TFrame")

        self.error_label = tb.Label(
            self.notification_frame,
            text="!",
            font=("Segoe UI", 12, "bold"),
            bootstyle="danger",  # type: ignore[arg-type]
        )
        self.error_label.pack(side=LEFT, padx=5)

        self.notification_label = tb.Label(
            self.notification_frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bootstyle="danger",  # type: ignore[arg-type]
        )
        self.notification_label.pack(side=LEFT, padx=5)

        self.status_label = tb.Label(status_frame, textvariable=self.status_var)
        self.status_label.pack(side=LEFT, padx=10)

        self.time_var = StringVar()
        self._update_time()
        tb.Label(status_frame, textvariable=self.time_var).pack(side=RIGHT, padx=10)

    def show_error(self, message: str, title: str = "Eroare", show_dialog: bool = True) -> None:
        """Display error in UI and optionally show an error dialog."""
        self.logger.log(f"Eroare: {message}")
        self.status_var.set(message)

        if not self.notification_visible:
            self.notification_frame.pack(fill=X, pady=5)
            self.notification_visible = True
            self.notification_label.configure(style="danger.TLabel")
            self.error_label.configure(style="danger.TLabel")

        self._flash_notification()
        if show_dialog and not self._closing:
            messagebox.showerror(title, message)

    def clear_error(self) -> None:
        if self.notification_visible:
            self.notification_frame.pack_forget()
            self.notification_visible = False

    def _flash_notification(self) -> None:
        def flash() -> None:
            if not self.notification_visible or not hasattr(self, "notification_label"):
                return
            current_style = self.notification_label.cget("style").split(".")[0]
            new_style = "danger" if current_style == "warning" else "warning"
            self.notification_label.configure(style=f"{new_style}.TLabel")
            self.error_label.configure(style=f"{new_style}.TLabel")
            self.app.after(500, flash)

        flash()

    def _on_closing(self) -> None:
        self._closing = True
        if self.is_running:
            self.stop_process()
            self._wait_for_shutdown_then_destroy()
            return
        self._destroy_app()

    def _wait_for_shutdown_then_destroy(self) -> None:
        if self.process_thread and self.process_thread.is_alive():
            self._shutdown_check_id = self.app.after(
                max(50, int(THREAD_CLEANUP_TIMEOUT * 1000)),
                self._wait_for_shutdown_then_destroy,
            )
            return
        self._destroy_app()

    def _destroy_app(self) -> None:
        for attr in (
            "_time_update_id",
            "_daily_check_id",
            "_save_config_id",
            "_ui_event_pump_id",
            "_shutdown_check_id",
        ):
            callback_id = getattr(self, attr, None)
            if callback_id is not None:
                try:
                    self.app.after_cancel(callback_id)
                except Exception:
                    pass
                setattr(self, attr, None)
        self.stop_event.set()
        if hasattr(self, "app"):
            self.app.destroy()

    def _update_time(self) -> None:
        self.time_var.set(self._now().strftime("%d-%m-%Y %H:%M:%S"))
        self._time_update_id = self.app.after(1000, self._update_time)

    def _toggle_time_input(self) -> None:
        option = self.start_option.get()

        if option == "scheduled":
            self.time_entry.config(state="normal")
            self.daily_time_entry.config(state="disabled")
            self.next_run_label.pack_forget()
            self.next_run_value.pack_forget()
        elif option == "daily":
            self.time_entry.config(state="disabled")
            self.daily_time_entry.config(state="normal")
            next_run = self._calculate_next_daily_run()
            if next_run:
                self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))
            self.next_run_label.pack(side=LEFT)
            self.next_run_value.pack(side=LEFT, padx=5)
        else:
            self.time_entry.config(state="disabled")
            self.daily_time_entry.config(state="disabled")
            self.next_run_label.pack_forget()
            self.next_run_value.pack_forget()

        if self._save_config_id is not None:
            self.app.after_cancel(self._save_config_id)
        self._save_config_id = self.app.after(500, self._save_schedule_config)

    def _validate_inputs(self) -> Tuple[int, int]:
        try:
            hours = int(self.hours_var.get())
            screenshots = int(self.screenshots_var.get())

            if hours <= 0 or hours > MAX_HOURS:
                raise ValueError(
                    ERROR_MESSAGES["invalid_hours"].format(max_hours=MAX_HOURS)
                )

            if screenshots <= 0 or screenshots > MAX_SCREENSHOTS:
                raise ValueError(
                    ERROR_MESSAGES["invalid_screenshots"].format(
                        max_screenshots=MAX_SCREENSHOTS
                    )
                )

            if (hours * 60 / screenshots) < MIN_INTERVAL_MINUTES:
                raise ValueError(
                    ERROR_MESSAGES["invalid_interval"].format(
                        min_interval=MIN_INTERVAL_MINUTES
                    )
                )

            return hours, screenshots
        except ValueError as exc:
            if "invalid literal for int()" in str(exc):
                raise ValueError("Introduceti numere valide") from exc
            raise

    def _validate_time_format(self, time_str: str) -> bool:
        try:
            datetime.strptime(time_str, "%H:%M")
            return True
        except ValueError:
            return False

    def _enqueue_ui_event(self, event: Dict[str, Any]) -> None:
        self.ui_event_queue.put(event)

    def _schedule_ui_event_pump(self) -> None:
        self._process_ui_events()
        self._ui_event_pump_id = self.app.after(100, self._schedule_ui_event_pump)

    def _process_ui_events(self) -> None:
        while True:
            try:
                event = self.ui_event_queue.get_nowait()
            except queue.Empty:
                break
            self._handle_ui_event(event)

    def _handle_ui_event(self, event: Dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "status":
            self.status_var.set(event["message"])
            return

        if event_type == "countdown":
            self.status_var.set(event["message"])
            self.countdown_var.set(event["countdown"])
            return

        if event_type == "progress":
            self._update_progress(event["current"], event["total"])
            return

        if event_type == "clear_error":
            self.clear_error()
            return

        if event_type == "error":
            self.show_error(
                event["message"],
                event.get("title", "Eroare"),
                show_dialog=event.get("dialog", True),
            )
            return

        if event_type == "prompt_capture_failure":
            should_continue = False
            if not self._closing:
                should_continue = messagebox.askyesno(
                    event.get("title", "Eroare Captura"),
                    event["message"],
                    icon="warning",
                )
            if self.process_controller:
                self.process_controller.respond_capture_failure(should_continue)
            return

        if event_type == "finished":
            self._finish_run(event.get("status", "Proces finalizat"))

    def start_process(self) -> None:
        """Start the screenshot process."""
        if self.is_running:
            return

        try:
            hours, screenshots = self._validate_inputs()

            if self.start_option.get() in {"scheduled", "daily"} and (
                not self.start_time_var.get()
                or not self._validate_time_format(self.start_time_var.get())
            ):
                self.show_error(ERROR_MESSAGES["invalid_time"], "Eroare Validare")
                return

            self.stop_event.clear()
            self.process_controller = ScreenshotProcessController(
                logger=self.logger,
                system_utils=self.system_utils,
                event_sink=self._enqueue_ui_event,
                stop_event=self.stop_event,
                countdown_interval=COUNTDOWN_CHECK_INTERVAL,
                retry_delay=RETRY_DELAY,
            )

            self.process_thread = threading.Thread(
                target=self.process_controller.run,
                args=(
                    hours,
                    screenshots,
                    self.start_option.get(),
                    self.start_time_var.get(),
                    self.app_choice.get(),
                ),
                daemon=True,
            )

            self.is_running = True
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.clear_error()
            self.status_var.set("Proces pornit")
            self.process_thread.start()
        except ValueError as exc:
            self.show_error(str(exc), "Eroare Validare")
        except Exception as exc:
            self.show_error(f"Eroare neasteptata: {exc}", "Eroare Sistem")

    def _finish_run(self, status: str) -> None:
        self.is_running = False
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set(status)
        self.countdown_var.set("In asteptare")
        self.counter_var.set("0/0 capturi")
        self.progress_var.set(0)
        self.process_thread = None
        self.process_controller = None
        if self._closing:
            self._wait_for_shutdown_then_destroy()

    def _update_progress(self, current: int, total: int) -> None:
        self.progress_var.set(int((current / total) * 100))
        self.status_var.set(f"Progres: {current}/{total}")
        self.counter_var.set(f"{current}/{total} capturi")

    def stop_process(self) -> None:
        if not self.is_running:
            return

        self.logger.log("Oprire solicitata - terminare proces")
        self.stop_event.set()
        self.stop_button.config(state="disabled")
        self.status_var.set("Se opreste...")
        if self._shutdown_check_id is None:
            self._monitor_worker_shutdown()

    def _monitor_worker_shutdown(self) -> None:
        if self.process_thread and self.process_thread.is_alive():
            self._shutdown_check_id = self.app.after(
                max(50, int(THREAD_CLEANUP_TIMEOUT * 1000)),
                self._monitor_worker_shutdown,
            )
            return

        self._shutdown_check_id = None
        if self.is_running:
            self._finish_run("Oprit")

    def run(self) -> None:
        """Start the application main loop."""
        try:
            if self.start_option.get() == "daily":
                next_run = self._calculate_next_daily_run()
                if next_run:
                    self.next_run_var.set(next_run.strftime("%d-%m-%Y %H:%M"))
                    self.status_var.set(f"Programat pentru {self.start_time_var.get()}")

            self._check_daily_schedule()
            self.app.mainloop()
        except Exception as exc:
            self.logger.log(f"Eroare aplicatie: {exc}")
            raise

    def _calculate_next_daily_run(self) -> Optional[datetime]:
        try:
            if not self.start_time_var.get() or not self._validate_time_format(
                self.start_time_var.get()
            ):
                return None

            target_time = datetime.strptime(self.start_time_var.get(), "%H:%M").time()
            now = self._now()
            next_run = datetime.combine(now.date(), target_time)
            if next_run <= now:
                next_run += timedelta(days=1)
            return next_run
        except Exception as exc:
            self.logger.log(f"Eroare la calcularea urmatoarei rulari: {exc}")
            return None

    def _check_daily_schedule(self) -> None:
        try:
            if not self.is_running and self.start_option.get() == "daily":
                now = self._now()
                next_run = self._calculate_next_daily_run()

                if next_run is not None:
                    new_display = next_run.strftime("%d-%m-%Y %H:%M")
                    if self.next_run_var.get() != new_display:
                        self.next_run_var.set(new_display)

                    time_diff = (next_run - now).total_seconds()
                    if 0 <= time_diff < 30 and not self._already_ran_today(now):
                        self.logger.log("Pornire automata programata zilnic")
                        self.status_var.set("Pornire automata programata")
                        self.schedule_config["last_run"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        self._save_schedule_config()
                        self.start_process()
        finally:
            self._daily_check_id = self.app.after(10000, self._check_daily_schedule)

    def _already_ran_today(self, now: datetime) -> bool:
        last_run_str = self.schedule_config.get("last_run")
        if not last_run_str:
            return False
        try:
            last_run = datetime.strptime(last_run_str, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return False

        return last_run.date() == now.date() and abs(
            (last_run.hour * 60 + last_run.minute) - (now.hour * 60 + now.minute)
        ) < 5


def main() -> None:
    """Main entry point for the application."""
    try:
        if not is_admin():
            messagebox.showinfo(
                "Drepturi de administrator necesare",
                "Aplicatia necesita drepturi de administrator pentru a functiona corect.\n"
                "Se va reporni cu drepturi de administrator.",
            )
            restart_as_admin()
            return

        app = ScreenshotApp()
        app.run()
    except Exception as exc:
        print(f"Eroare fatala: {exc}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
