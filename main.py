import ctypes
import json
import queue
import sys
import threading
import tkinter as tk
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import BooleanVar, IntVar, StringVar, filedialog, messagebox, ttk
from typing import Any, Dict, Optional, Tuple

import ttkbootstrap as tb  # type: ignore
from ttkbootstrap.constants import BOTTOM, BOTH, LEFT, RIGHT, S, W, X, YES  # type: ignore

from utils.constants import (
    APP_TITLE,
    APP_VERSION,
    AUTO_COURSE_HISTORY_LIMIT,
    CONFIG_FILENAME,
    COUNTDOWN_CHECK_INTERVAL,
    COURSE_AUTO_CHECK_INTERVAL_MS,
    COURSE_AUTO_LAUNCH_WINDOW_SECONDS,
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
from utils.course_db import CourseRepository
from utils.course_selection import (
    CourseSessionAdapter,
    CourseSessionOption,
    CourseSessionPrefill,
)
from utils.excel_import import ExcelCourseImporter, ImportResult
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
        self.course_repository = CourseRepository(Path("optimad.db"))
        self.course_importer = ExcelCourseImporter()
        self.course_adapter = CourseSessionAdapter()
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
            "auto_course_enabled": False,
            "tracked_course_session_id": None,
            "last_auto_course_run_ids": [],
            "last_completed_batch_key": None,
            "last_auto_course_run_at": None,
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
        self._prune_auto_course_history()
        self.schedule_config.update(
            {
                "start_option": self.start_option.get(),
                "start_time": self.start_time_var.get(),
                "hours": self.hours_var.get(),
                "screenshots": self.screenshots_var.get(),
                "app_choice": self.app_choice.get(),
                "auto_course_enabled": self.auto_course_enabled_var.get(),
                "tracked_course_session_id": self.tracked_course_session_id,
                "last_auto_course_run_ids": self.last_auto_course_run_ids,
                "last_completed_batch_key": self.last_completed_batch_key,
                "last_auto_course_run_at": self.last_auto_course_run_at,
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
        self._create_capture_overlay()

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
        self.course_file_var = StringVar(value="")
        self.course_import_status_var = StringVar(value="Niciun import efectuat.")
        self.course_selector_var = StringVar(value="")
        self.course_mode_var = StringVar(value="Mod manual activ.")
        self.course_session_date_var = StringVar(value="Data sesiune: -")
        self.course_meeting_link_var = StringVar(value="Link sedinta: -")
        self.course_note_var = StringVar(value="")
        self.overlay_date_var = StringVar(value="")
        self.overlay_time_var = StringVar(value="")
        self.auto_course_enabled_var = BooleanVar(
            value=bool(self.schedule_config.get("auto_course_enabled", False))
        )
        self.course_auto_status_var = StringVar(value="Automatizare cursuri: oprita.")
        self.course_auto_tracked_var = StringVar(value="Sesiune urmarita: -")
        self.course_auto_next_run_var = StringVar(value="Pornire automata: -")
        self.course_auto_batch_summary_var = StringVar(value="Batch planificat: -")
        self.course_auto_batch_progress_var = StringVar(value="Batch curent: -")
        self.selected_course_session_id: Optional[str] = None
        self.course_backed_mode = False
        self.last_applied_meeting_link = ""
        self.manual_form_snapshot: Optional[Dict[str, str]] = None
        self.course_auto_prefill_enabled = True
        self.tracked_course_session_id = self.schedule_config.get(
            "tracked_course_session_id"
        )
        self.last_auto_course_run_ids = list(
            self.schedule_config.get("last_auto_course_run_ids", [])
        )
        self.last_completed_batch_key = self.schedule_config.get(
            "last_completed_batch_key"
        )
        self.last_auto_course_run_at = self.schedule_config.get("last_auto_course_run_at")
        self.last_auto_course_link_opened_session_id: Optional[str] = None
        self.last_auto_course_link_opened_at: Optional[datetime] = None
        self.capture_overlay_visible = False
        self.active_course_batch_ids: list[str] = []
        self.active_course_batch_index = 0
        self.active_batch_key: Optional[str] = None
        self.available_course_sessions: Dict[str, Any] = {}
        self.course_session_options: list[CourseSessionOption] = []

    def _create_content_area(self) -> None:
        self.notebook = tb.Notebook(self.main_container)
        self.notebook.pack(fill=BOTH, expand=YES)
        self._create_settings_tab()
        self._create_courses_tab()
        self._create_about_tab()

    def _create_settings_tab(self) -> None:
        settings_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(settings_frame, text="Setari")

        left_frame = tb.Frame(settings_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=YES, padx=(0, 10))

        right_frame = tb.Frame(settings_frame)
        right_frame.pack(side=RIGHT, fill=BOTH, expand=YES, padx=(10, 0))

        session_frame = tb.LabelFrame(
            left_frame, text="Sesiune importata", padding=15
        )
        session_frame.pack(fill=X, pady=(0, 15))

        selector_row = tb.Frame(session_frame)
        selector_row.pack(fill=X, pady=(0, 8))

        self.course_selector = ttk.Combobox(
            selector_row,
            textvariable=self.course_selector_var,
            state="normal",
            width=45,
        )
        self.course_selector.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        self.course_selector.bind(
            "<<ComboboxSelected>>",
            lambda _event: self._update_course_selector_values(),
        )
        self.course_selector.bind(
            "<KeyRelease>",
            lambda _event: self._update_course_selector_values(),
        )

        tb.Button(
            selector_row,
            text="Aplica",
            command=self._apply_selected_course_session,
            bootstyle="primary",  # type: ignore[arg-type]
        ).pack(side=LEFT, padx=(0, 5))

        tb.Button(
            selector_row,
            text="Curata",
            command=lambda: self._clear_course_session_selection(
                disable_auto_prefill=True
            ),
            bootstyle="secondary",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        tb.Label(
            session_frame,
            textvariable=self.course_mode_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(0, 4))

        tb.Label(
            session_frame,
            textvariable=self.course_session_date_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(0, 4))

        tb.Label(
            session_frame,
            textvariable=self.course_meeting_link_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(0, 4))

        meeting_link_actions = tb.Frame(session_frame)
        meeting_link_actions.pack(fill=X, anchor=W, pady=(0, 4))

        tb.Button(
            meeting_link_actions,
            text="Copiaza linkul",
            command=self._copy_course_meeting_link,
            bootstyle="secondary",  # type: ignore[arg-type]
        ).pack(side=LEFT, padx=(0, 5))

        tb.Button(
            meeting_link_actions,
            text="Deschide linkul",
            command=self._open_course_meeting_link,
            bootstyle="info",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        tb.Label(
            session_frame,
            textvariable=self.course_note_var,
            justify=LEFT,
            wraplength=320,
            bootstyle="warning",  # type: ignore[arg-type]
        ).pack(fill=X, anchor=W)

        auto_course_frame = tb.LabelFrame(
            session_frame, text="Automatizare cursuri", padding=10
        )
        auto_course_frame.pack(fill=X, pady=(10, 0))

        tb.Checkbutton(
            auto_course_frame,
            text="Ruleaza automat cursurile importate",
            variable=self.auto_course_enabled_var,
            command=self._on_auto_course_toggle,
            bootstyle="success-round-toggle",  # type: ignore[arg-type]
        ).pack(anchor=W, pady=(0, 6))

        tb.Button(
            auto_course_frame,
            text="Testeaza batch-ul acum",
            command=self._trigger_course_batch_now,
            bootstyle="warning",  # type: ignore[arg-type]
        ).pack(anchor=W, pady=(0, 6))

        tb.Label(
            auto_course_frame,
            textvariable=self.course_auto_status_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(0, 4))

        tb.Label(
            auto_course_frame,
            textvariable=self.course_auto_tracked_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(0, 4))

        tb.Label(
            auto_course_frame,
            textvariable=self.course_auto_next_run_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W)
        tb.Label(
            auto_course_frame,
            textvariable=self.course_auto_batch_summary_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(4, 0))
        tb.Label(
            auto_course_frame,
            textvariable=self.course_auto_batch_progress_var,
            justify=LEFT,
            wraplength=320,
        ).pack(fill=X, anchor=W, pady=(4, 0))

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
        self._refresh_course_selector()

    def _create_courses_tab(self) -> None:
        courses_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(courses_frame, text="Cursuri")

        import_frame = tb.LabelFrame(courses_frame, text="Import Excel", padding=15)
        import_frame.pack(fill=X, pady=(0, 10))

        tb.Entry(
            import_frame,
            textvariable=self.course_file_var,
            state="readonly",
            width=70,
        ).pack(side=LEFT, fill=X, expand=YES, padx=(0, 10))

        tb.Button(
            import_frame,
            text="Alege fisier",
            command=self._browse_course_excel,
            bootstyle="secondary",  # type: ignore[arg-type]
        ).pack(side=LEFT, padx=(0, 5))

        tb.Button(
            import_frame,
            text="Importa",
            command=self._import_course_excel,
            bootstyle="success",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        action_frame = tb.Frame(courses_frame)
        action_frame.pack(fill=X, pady=(0, 10))

        tb.Button(
            action_frame,
            text="Sterge sesiunea selectata",
            command=self._delete_selected_course_session,
            bootstyle="warning",  # type: ignore[arg-type]
        ).pack(side=LEFT, padx=(0, 5))

        tb.Button(
            action_frame,
            text="Aplica in formular",
            command=self._apply_selected_course_from_table,
            bootstyle="primary",  # type: ignore[arg-type]
        ).pack(side=LEFT, padx=(0, 5))

        tb.Button(
            action_frame,
            text="Goleste toate sesiunile",
            command=self._clear_all_course_sessions,
            bootstyle="danger",  # type: ignore[arg-type]
        ).pack(side=LEFT)

        status_frame = tb.LabelFrame(courses_frame, text="Rezultat import", padding=15)
        status_frame.pack(fill=X, pady=(0, 10))
        tb.Label(
            status_frame,
            textvariable=self.course_import_status_var,
            justify=LEFT,
            wraplength=740,
        ).pack(fill=X)

        table_frame = tb.LabelFrame(courses_frame, text="Sesiuni importate", padding=10)
        table_frame.pack(fill=BOTH, expand=YES)

        columns = (
            "course_date",
            "start_time",
            "end_time",
            "duration_hours",
            "course_name",
            "group_name",
            "trainer",
            "is_recurring",
            "weekdays",
            "platform",
            "meeting_link",
        )
        self.course_tree = ttk.Treeview(
            table_frame,
            columns=columns,
            show="headings",
            height=14,
        )

        headings = {
            "course_date": "Data",
            "start_time": "Start",
            "end_time": "Stop",
            "duration_hours": "Durata",
            "course_name": "Curs",
            "group_name": "Grupa",
            "trainer": "Trainer",
            "is_recurring": "Recurent",
            "weekdays": "Zile",
            "platform": "Platforma",
            "meeting_link": "Link",
        }

        widths = {
            "course_date": 90,
            "start_time": 70,
            "end_time": 70,
            "duration_hours": 70,
            "course_name": 170,
            "group_name": 90,
            "trainer": 130,
            "is_recurring": 80,
            "weekdays": 90,
            "platform": 90,
            "meeting_link": 260,
        }

        for column in columns:
            self.course_tree.heading(column, text=headings[column])
            self.course_tree.column(column, width=widths[column], anchor=W, stretch=True)

        scrollbar = ttk.Scrollbar(
            table_frame,
            orient="vertical",
            command=self.course_tree.yview,
        )
        self.course_tree.configure(yscrollcommand=scrollbar.set)
        self.course_tree.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill="y")

        self._refresh_course_sessions()

    def _create_about_tab(self) -> None:
        about_frame = tb.Frame(self.notebook, padding=15)
        self.notebook.add(about_frame, text="Despre")

        about_text = (
            f"{APP_TITLE} - Aplicatie pentru capturarea automata a ecranului\n\n"
            "Aceasta aplicatie permite capturi automate de ecran la intervale regulate "
            "si poate afisa un overlay cu data simulata peste fereastra cursului pentru a genera capturi pe mai multe zile.\n\n"
            "Functionalitati:\n"
            "- Captare automata de ecran\n"
            "- Simulare de activitate prin overlay topmost cu data cursului\n"
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
        self._hide_capture_overlay()
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
        now = self._now()
        self.time_var.set(now.strftime("%d-%m-%Y %H:%M:%S"))
        if hasattr(self, "overlay_time_var"):
            self.overlay_time_var.set(now.strftime("%H:%M:%S"))
        if getattr(self, "capture_overlay_visible", False):
            self._position_capture_overlay()
        self._time_update_id = self.app.after(1000, self._update_time)

    def _create_capture_overlay(self) -> None:
        self.capture_overlay = tk.Toplevel(self.app)
        self.capture_overlay.withdraw()
        self.capture_overlay.overrideredirect(True)
        self.capture_overlay.attributes("-topmost", True)
        self.capture_overlay.configure(bg="black")

        container = tk.Frame(
            self.capture_overlay,
            bg="black",
            highlightbackground="#00e5ff",
            highlightthickness=2,
            padx=14,
            pady=10,
        )
        container.pack(fill="both", expand=True)

        tk.Label(
            container,
            textvariable=self.overlay_date_var,
            fg="#00e5ff",
            bg="black",
            font=("Consolas", 16, "bold"),
            anchor="e",
        ).pack(fill="x")
        tk.Label(
            container,
            textvariable=self.overlay_time_var,
            fg="#ffffff",
            bg="black",
            font=("Consolas", 20, "bold"),
            anchor="e",
        ).pack(fill="x")

    def _position_capture_overlay(self) -> None:
        if not hasattr(self, "capture_overlay"):
            return

        self.capture_overlay.update_idletasks()
        width = self.capture_overlay.winfo_reqwidth()
        height = self.capture_overlay.winfo_reqheight()
        screen_width = self.app.winfo_screenwidth()
        x_pos = max(0, screen_width - width - 24)
        y_pos = 24
        self.capture_overlay.geometry(f"{width}x{height}+{x_pos}+{y_pos}")
        self.capture_overlay.lift()
        self.capture_overlay.attributes("-topmost", True)

    def _show_capture_overlay(self, simulated_date: str) -> None:
        if not hasattr(self, "capture_overlay"):
            return

        self.overlay_date_var.set(simulated_date)
        self.overlay_time_var.set(self._now().strftime("%H:%M:%S"))
        self.capture_overlay.deiconify()
        self.capture_overlay_visible = True
        self._position_capture_overlay()

    def _hide_capture_overlay(self) -> None:
        if hasattr(self, "capture_overlay"):
            try:
                self.capture_overlay.withdraw()
            except Exception:
                pass
        self.capture_overlay_visible = False

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

        self._schedule_config_save()

    def _schedule_config_save(self) -> None:
        if self._save_config_id is not None:
            self.app.after_cancel(self._save_config_id)
        self._save_config_id = self.app.after(500, self._save_schedule_config)

    def _on_auto_course_toggle(self) -> None:
        enabled = self.auto_course_enabled_var.get()
        if enabled:
            self.course_note_var.set(
                "Automatizarea cursurilor importate este activa."
            )
        else:
            self.course_note_var.set(
                "Automatizarea cursurilor importate este oprita."
            )
        self._update_course_auto_status()
        self._schedule_config_save()

    def _set_course_action_status(self, message: str) -> None:
        self.course_note_var.set(message)
        self.status_var.set(message)
        self.logger.log(message)

    def _validate_inputs(self) -> Tuple[float, int]:
        try:
            hours = float(self.hours_var.get())
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
            if "could not convert string to float" in str(exc) or "invalid literal for int()" in str(exc):
                raise ValueError("Introduceti numere valide") from exc
            raise

    def _get_selected_course_session(self) -> Optional[Any]:
        session_id = getattr(self, "selected_course_session_id", None)
        if not session_id:
            return None
        return self.available_course_sessions.get(session_id)

    def _get_course_scheduled_datetime(self) -> Optional[datetime]:
        if not getattr(self, "course_backed_mode", False):
            return None
        if self.start_option.get() != "scheduled":
            return None

        session = self._get_selected_course_session()
        if session is None:
            return None

        try:
            return datetime.strptime(
                f"{session.course_date} {self.start_time_var.get()}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            return None

    def _get_manual_scheduled_datetime(self) -> Optional[datetime]:
        if self.start_option.get() != "scheduled":
            return None
        if getattr(self, "course_backed_mode", False):
            return None

        try:
            target_time = datetime.strptime(
                self.start_time_var.get(), "%H:%M"
            ).time()
        except ValueError:
            return None

        return datetime.combine(self._now().date(), target_time)

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

        if event_type == "prepare_overlay":
            self._show_capture_overlay(event["simulated_date"])
            if self.process_controller:
                self.process_controller.respond_overlay_ready(True)
            return

        if event_type == "hide_overlay":
            self._hide_capture_overlay()
            return

        if event_type == "finished":
            self._finish_run(event.get("status", "Proces finalizat"))

    def _browse_course_excel(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Selecteaza fisierul Excel",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if file_path:
            self.course_file_var.set(file_path)

    def _import_course_excel(self) -> None:
        file_path = self.course_file_var.get().strip()
        if not file_path:
            messagebox.showerror(
                "Import Excel",
                "Selectati mai intai un fisier Excel pentru import.",
            )
            return

        try:
            result = self.course_importer.import_file(file_path)
            if result.errors:
                messagebox.showerror("Import Excel", "\n".join(result.errors))
                self.course_import_status_var.set("\n".join(result.errors))
                return

            self.course_auto_prefill_enabled = True
            inserted = self.course_repository.replace_all_sessions(result.sessions)
            self._refresh_course_sessions()
            self.course_import_status_var.set(
                self._format_import_result(result, inserted)
            )
        except Exception as exc:
            self.logger.log(f"Eroare la importul Excel: {exc}")
            messagebox.showerror("Import Excel", f"Importul a esuat: {exc}")

    def _format_import_result(self, result: ImportResult, inserted: int) -> str:
        parts = [
            f"Import finalizat. Sesiuni importate: {inserted}.",
            f"Randuri sarite: {result.skipped_count}.",
        ]
        if result.warnings:
            parts.append("Avertismente:")
            parts.extend(f"- {warning}" for warning in result.warnings[:10])
            if len(result.warnings) > 10:
                parts.append(f"- ... si inca {len(result.warnings) - 10} avertismente")
        return "\n".join(parts)

    def _refresh_course_selector(self) -> None:
        sessions = self.course_repository.list_sessions()
        self.available_course_sessions = {session.id: session for session in sessions}
        self.course_session_options = self.course_adapter.build_options(sessions)
        self._update_course_selector_values()

        selected_course_session_id = getattr(self, "selected_course_session_id", None)
        if selected_course_session_id and (
            selected_course_session_id not in self.available_course_sessions
        ):
            self._clear_course_session_selection(
                restore_snapshot=True,
                clear_selector=True,
                note="Sesiunea aplicata nu mai exista in baza locala. Formularul a revenit la valorile manuale.",
            )

        self._maybe_auto_apply_course_session()

    def _update_course_selector_values(self) -> None:
        if not hasattr(self, "course_selector"):
            return

        filtered_options = self.course_adapter.filter_options(
            self.course_session_options,
            self.course_selector_var.get(),
        )
        self.course_selector["values"] = [option.label for option in filtered_options]

    def _find_course_option(self, selector_value: str) -> Optional[CourseSessionOption]:
        normalized_value = selector_value.strip()
        if not normalized_value:
            return None

        exact_match = next(
            (
                option
                for option in self.course_session_options
                if option.label == normalized_value
            ),
            None,
        )
        if exact_match:
            return exact_match

        filtered_options = self.course_adapter.filter_options(
            self.course_session_options,
            normalized_value,
        )
        if len(filtered_options) == 1:
            return filtered_options[0]
        return None

    def _capture_manual_form_snapshot(self) -> Dict[str, str]:
        return {
            "hours": self.hours_var.get(),
            "start_option": self.start_option.get(),
            "start_time": self.start_time_var.get(),
            "app_choice": self.app_choice.get(),
        }

    def _format_meeting_link_display(self, meeting_link: str) -> str:
        if not meeting_link:
            return "Link sedinta: -"

        if len(meeting_link) <= 60:
            return f"Link sedinta: {meeting_link}"

        return f"Link sedinta: {meeting_link[:57]}..."

    def _open_meeting_link(
        self,
        meeting_link: str,
        *,
        automatic: bool = False,
        session_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> bool:
        if not meeting_link:
            if automatic:
                self.course_note_var.set(
                    "Sesiunea urmarita nu are link; pornirea continua fara deschiderea unei sedinte."
                )
            else:
                messagebox.showinfo(
                    "Link sedinta",
                    "Nu exista niciun link disponibil pentru sesiunea curenta.",
                )
            return False

        if automatic and session_id:
            current_time = now or self._now()
            if (
                self.last_auto_course_link_opened_session_id == session_id
                and self.last_auto_course_link_opened_at is not None
                and (
                    current_time - self.last_auto_course_link_opened_at
                ).total_seconds()
                < COURSE_AUTO_LAUNCH_WINDOW_SECONDS
            ):
                return True

        try:
            webbrowser.open(meeting_link)
            if automatic:
                self.course_note_var.set("Linkul sedintei a fost deschis automat.")
                if session_id:
                    self.last_auto_course_link_opened_session_id = session_id
                    self.last_auto_course_link_opened_at = now or self._now()
            else:
                self.course_note_var.set("Linkul sedintei a fost deschis explicit.")
            return True
        except Exception as exc:
            self.logger.log(f"Eroare la deschiderea linkului de sedinta: {exc}")
            if automatic:
                self.course_note_var.set(
                    f"Nu am putut deschide automat linkul sedintei: {exc}"
                )
            else:
                messagebox.showerror(
                    "Link sedinta",
                    f"Nu am putut deschide linkul: {exc}",
                )
            return False

    def _close_active_meeting(self) -> bool:
        app_name = SUPPORTED_APPS.get(self.app_choice.get(), "")
        if not app_name:
            self.logger.log("Nu exista nicio aplicatie selectata pentru inchidere.")
            return False

        closed = self.system_utils.close_window(app_name, self.logger)
        if closed:
            self.course_note_var.set("Sesiunea curenta a fost inchisa.")
        else:
            self.course_note_var.set(
                "Nu am putut inchide sesiunea curenta automat. Continui cu urmatorul link."
            )
        return closed

    def _restore_manual_form_snapshot(self) -> None:
        if not self.manual_form_snapshot:
            return

        self.hours_var.set(self.manual_form_snapshot["hours"])
        self.start_option.set(self.manual_form_snapshot["start_option"])
        self.start_time_var.set(self.manual_form_snapshot["start_time"])
        self.app_choice.set(self.manual_form_snapshot["app_choice"])
        self._toggle_time_input()
        self.manual_form_snapshot = None

    def _apply_prefill_to_form(self, prefill: CourseSessionPrefill) -> None:
        if not getattr(self, "course_backed_mode", False):
            self.manual_form_snapshot = self._capture_manual_form_snapshot()

        self.hours_var.set(prefill.hours_value)
        self.start_option.set("scheduled")
        self.start_time_var.set(prefill.start_time)
        if prefill.suggested_app_choice:
            self.app_choice.set(prefill.suggested_app_choice)
        self._toggle_time_input()

        self.selected_course_session_id = prefill.session_id
        self.course_backed_mode = True
        self.last_applied_meeting_link = prefill.meeting_link
        self.course_selector_var.set(prefill.label)
        self.course_mode_var.set(f"Sesiune aplicata: {prefill.label}")
        self.course_session_date_var.set(
            f"Data sesiune: {self.course_adapter.format_session_date(prefill.course_date)}"
        )
        self.course_meeting_link_var.set(
            self._format_meeting_link_display(prefill.meeting_link)
        )
        self.course_note_var.set(
            prefill.warning
            or "Valorile au fost preluate in formular. Pornirea ramane manuala."
        )
        self.course_auto_prefill_enabled = True

    def _apply_selected_course_session(self) -> None:
        option = self._find_course_option(self.course_selector_var.get())
        if option is None:
            messagebox.showinfo(
                "Sesiune importata",
                "Selectati o singura sesiune valida din lista pentru a o aplica.",
            )
            return

        session = self.available_course_sessions.get(option.session_id)
        if session is None:
            messagebox.showerror(
                "Sesiune importata",
                "Sesiunea selectata nu mai exista in baza locala. Reincarcati lista.",
            )
            self._refresh_course_selector()
            return

        self._apply_prefill_to_form(self.course_adapter.build_prefill(session))

    def _clear_course_session_selection(
        self,
        restore_snapshot: bool = True,
        clear_selector: bool = True,
        note: str = "Mod manual activ.",
        disable_auto_prefill: bool = False,
    ) -> None:
        if restore_snapshot:
            self._restore_manual_form_snapshot()
        else:
            self.manual_form_snapshot = None

        self.selected_course_session_id = None
        self.course_backed_mode = False
        self.last_applied_meeting_link = ""
        if clear_selector:
            self.course_selector_var.set("")
        self.course_mode_var.set(note)
        self.course_session_date_var.set("Data sesiune: -")
        self.course_meeting_link_var.set("Link sedinta: -")
        self.course_note_var.set("")
        if disable_auto_prefill:
            self.course_auto_prefill_enabled = False
        self._update_course_selector_values()

    def _copy_course_meeting_link(self) -> None:
        if not self.last_applied_meeting_link:
            messagebox.showinfo(
                "Link sedinta",
                "Nu exista niciun link disponibil pentru sesiunea curenta.",
            )
            return

        self.app.clipboard_clear()
        self.app.clipboard_append(self.last_applied_meeting_link)
        self.course_note_var.set("Linkul sedintei a fost copiat in clipboard.")

    def _open_course_meeting_link(self) -> None:
        self._open_meeting_link(self.last_applied_meeting_link)

    def _find_next_relevant_course_session(self) -> Optional[Any]:
        if not self.available_course_sessions:
            return None

        sessions = self.course_adapter.sort_sessions(
            self.available_course_sessions.values()
        )
        now = self._now()
        future_sessions = []
        for session in sessions:
            try:
                session_dt = datetime.strptime(
                    f"{session.course_date} {session.start_time}",
                    "%Y-%m-%d %H:%M",
                )
            except ValueError:
                continue
            if session_dt >= now:
                future_sessions.append((session_dt, session))

        if future_sessions:
            future_sessions.sort(key=lambda item: item[0])
            return future_sessions[0][1]
        return None

    def _maybe_auto_apply_course_session(self) -> None:
        if not getattr(self, "course_auto_prefill_enabled", True):
            return
        if getattr(self, "course_backed_mode", False):
            return
        if getattr(self, "selected_course_session_id", None):
            return
        if getattr(self, "manual_form_snapshot", None):
            return
        required_attrs = (
            "hours_var",
            "start_option",
            "start_time_var",
            "app_choice",
            "course_mode_var",
            "course_session_date_var",
            "course_meeting_link_var",
            "course_note_var",
            "course_selector_var",
        )
        if any(not hasattr(self, attr) for attr in required_attrs):
            return

        next_session = self._find_next_relevant_course_session()
        if next_session is None:
            return

        self._apply_prefill_to_form(self.course_adapter.build_prefill(next_session))
        self.course_note_var.set(
            "Sesiunea viitoare a fost aplicata automat. Pornirea ramane manuala."
        )

    def get_runnable_course_sessions(
        self, now: datetime
    ) -> Tuple[list[Any], Optional[datetime], Optional[str]]:
        sessions = self.course_adapter.sort_sessions(
            self.available_course_sessions.values()
        )
        first_session = None
        first_session_dt = None
        for session in sessions:
            if session.id in getattr(self, "last_auto_course_run_ids", []):
                continue
            try:
                session_dt = datetime.strptime(
                    f"{session.course_date} {session.start_time}",
                    "%Y-%m-%d %H:%M",
                )
            except ValueError:
                continue
            if session_dt >= now:
                first_session = session
                first_session_dt = session_dt
                break
            if abs((now - session_dt).total_seconds()) <= COURSE_AUTO_LAUNCH_WINDOW_SECONDS:
                first_session = session
                first_session_dt = session_dt
                break

        if first_session is None or first_session_dt is None:
            return [], None, None

        batch_key = first_session_dt.strftime("%Y-%m-%d %H:%M")
        return (
            self._get_batch_sessions_for_key(batch_key),
            first_session_dt,
            batch_key,
        )

    def _set_active_course_batch(
        self, sessions: list[Any], batch_key: Optional[str]
    ) -> None:
        self.active_course_batch_ids = [session.id for session in sessions]
        self.active_course_batch_index = 0
        self.active_batch_key = batch_key

    def _get_active_batch_session(self) -> Optional[Any]:
        if not self.active_course_batch_ids:
            return None
        if self.active_course_batch_index >= len(self.active_course_batch_ids):
            return None
        session_id = self.active_course_batch_ids[self.active_course_batch_index]
        return self.available_course_sessions.get(session_id)

    def _clear_active_course_batch(self) -> None:
        self.active_course_batch_ids = []
        self.active_course_batch_index = 0
        self.active_batch_key = None

    def _get_batch_key_for_session(self, session: Any) -> Optional[str]:
        try:
            return datetime.strptime(
                f"{session.course_date} {session.start_time}",
                "%Y-%m-%d %H:%M",
            ).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return None

    def _get_batch_sessions_for_key(
        self, batch_key: str, *, include_processed: bool = False
    ) -> list[Any]:
        sessions = []
        processed_ids = set()
        if not include_processed:
            processed_ids = set(getattr(self, "last_auto_course_run_ids", []))

        for session in self.course_adapter.sort_sessions(
            self.available_course_sessions.values()
        ):
            if session.id in processed_ids:
                continue
            if self._get_batch_key_for_session(session) == batch_key:
                sessions.append(session)
        return sessions

    def _get_batch_sessions_for_seed(
        self, session: Any, *, include_processed: bool = False
    ) -> tuple[list[Any], Optional[str]]:
        batch_key = self._get_batch_key_for_session(session)
        if batch_key is None:
            return [], None
        return (
            self._get_batch_sessions_for_key(
                batch_key,
                include_processed=include_processed,
            ),
            batch_key,
        )

    def _prune_auto_course_history(self) -> None:
        history = list(dict.fromkeys(getattr(self, "last_auto_course_run_ids", [])))
        available_ids = set(getattr(self, "available_course_sessions", {}).keys())
        if available_ids:
            history = [session_id for session_id in history if session_id in available_ids]
        if len(history) > AUTO_COURSE_HISTORY_LIMIT:
            history = history[-AUTO_COURSE_HISTORY_LIMIT:]
        self.last_auto_course_run_ids = history

    def _get_planned_batch_size(self, tracked_session: Any) -> int:
        tracked_key = self._get_batch_key_for_session(tracked_session)
        if tracked_key is None:
            return 1

        return max(len(self._get_batch_sessions_for_key(tracked_key)), 1)

    def _start_course_batch(
        self,
        sessions: list[Any],
        batch_key: Optional[str],
        *,
        trigger_reason: str,
    ) -> bool:
        if not sessions or batch_key is None:
            self._set_course_action_status(
                "Nu exista sesiuni eligibile pentru batch-ul selectat."
            )
            return False

        first_session = sessions[0]
        try:
            session_dt = datetime.strptime(
                f"{first_session.course_date} {first_session.start_time}",
                "%Y-%m-%d %H:%M",
            )
        except ValueError:
            session_dt = None

        self._set_active_course_batch(sessions, batch_key)
        self.tracked_course_session_id = first_session.id
        self._update_course_auto_status(first_session, session_dt)
        self.logger.log(f"{trigger_reason} pentru batch-ul de cursuri {batch_key}")
        self.status_var.set(f"{trigger_reason} pentru batch-ul cursurilor importate")
        return self.start_course_session(first_session, automatic=True)

    def _trigger_course_batch_now(self) -> None:
        if self.is_running:
            self._set_course_action_status(
                "Nu pot porni testul de batch cat timp exista deja un proces activ."
            )
            return

        self._refresh_course_sessions()
        seed_session = self._get_selected_course_session()
        if seed_session is None and getattr(self, "tracked_course_session_id", None):
            seed_session = self.available_course_sessions.get(self.tracked_course_session_id)
        if seed_session is None:
            seed_session = self._find_next_relevant_course_session()
        if seed_session is None:
            self._set_course_action_status(
                "Nu exista nicio sesiune disponibila pentru testarea batch-ului."
            )
            return

        sessions, batch_key = self._get_batch_sessions_for_seed(
            seed_session,
            include_processed=True,
        )
        if not self._start_course_batch(
            sessions,
            batch_key,
            trigger_reason="Test batch pornit manual",
        ):
            self._clear_active_course_batch()

    def _advance_course_batch(self) -> bool:
        self.active_course_batch_index += 1
        next_session = self._get_active_batch_session()
        if next_session is None:
            self.last_completed_batch_key = self.active_batch_key
            self._clear_active_course_batch()
            self._save_schedule_config()
            self._update_course_auto_status()
            return False

        self._set_course_action_status(
            "Se inchide sesiunea curenta si se trece la urmatorul curs din batch."
        )
        closed = self._close_active_meeting()
        if not closed:
            self._set_course_action_status(
                "Inchiderea sesiunii curente a esuat. Continui cu urmatorul curs din batch."
            )

        started = self.start_course_session(next_session, automatic=True)
        if not started:
            self._set_course_action_status(
                "Pornirea cursului urmator din batch a esuat. Batch-ul ramane activ pentru retry."
            )
        return started

    def _update_course_auto_status(
        self,
        tracked_session: Optional[Any] = None,
        tracked_datetime: Optional[datetime] = None,
    ) -> None:
        required_vars = (
            "auto_course_enabled_var",
            "course_auto_status_var",
            "course_auto_tracked_var",
            "course_auto_next_run_var",
            "course_auto_batch_summary_var",
            "course_auto_batch_progress_var",
        )
        if any(not hasattr(self, attr) for attr in required_vars):
            return

        enabled = self.auto_course_enabled_var.get()
        self.course_auto_status_var.set(
            "Automatizare cursuri: activa."
            if enabled
            else "Automatizare cursuri: oprita."
        )

        tracked_session_id = getattr(self, "tracked_course_session_id", None)
        if tracked_session is None and tracked_session_id:
            tracked_session = self.available_course_sessions.get(
                tracked_session_id
            )
            if tracked_session is not None:
                try:
                    tracked_datetime = datetime.strptime(
                        f"{tracked_session.course_date} {tracked_session.start_time}",
                        "%Y-%m-%d %H:%M",
                    )
                except ValueError:
                    tracked_datetime = None

        if tracked_session is None:
            self.course_auto_tracked_var.set("Sesiune urmarita: -")
            self.course_auto_next_run_var.set("Pornire automata: -")
            self.course_auto_batch_summary_var.set("Batch planificat: -")
            self.course_auto_batch_progress_var.set("Batch curent: -")
            return

        self.course_auto_tracked_var.set(
            f"Sesiune urmarita: {self.course_adapter.format_session_label(tracked_session)}"
        )
        if tracked_datetime is not None:
            self.course_auto_next_run_var.set(
                "Pornire automata: "
                + tracked_datetime.strftime("%d-%m-%Y %H:%M")
            )
        else:
            self.course_auto_next_run_var.set("Pornire automata: necunoscuta")

        batch_size = len(getattr(self, "active_course_batch_ids", []))
        if batch_size > 0:
            self.course_auto_batch_summary_var.set(
                f"Batch planificat: {batch_size} cursuri"
            )
            current_index = min(
                getattr(self, "active_course_batch_index", 0) + 1, batch_size
            )
            self.course_auto_batch_progress_var.set(
                f"Batch curent: Curs {current_index}/{batch_size}"
            )
        else:
            planned_batch_size = self._get_planned_batch_size(tracked_session)
            self.course_auto_batch_summary_var.set(
                f"Batch planificat: {planned_batch_size} cursuri"
            )
            self.course_auto_batch_progress_var.set("Batch curent: -")

    def start_course_session(self, session: Any, *, automatic: bool = False) -> bool:
        prefill = self.course_adapter.build_prefill(session)
        self._apply_prefill_to_form(prefill)
        if automatic:
            now = self._now()
            self.tracked_course_session_id = session.id
            try:
                session_dt = datetime.strptime(
                    f"{session.course_date} {session.start_time}",
                    "%Y-%m-%d %H:%M",
                )
            except ValueError:
                session_dt = now
            self._update_course_auto_status(session, session_dt)
            self._open_meeting_link(
                prefill.meeting_link,
                automatic=True,
                session_id=session.id,
                now=now,
            )
            started = self.start_process(force_now=True)
            if started:
                if session.id not in self.last_auto_course_run_ids:
                    self.last_auto_course_run_ids.append(session.id)
                self._prune_auto_course_history()
                self.last_auto_course_run_at = now.strftime("%Y-%m-%d %H:%M:%S")
                self.tracked_course_session_id = session.id
                self.course_note_var.set(
                    "Sesiunea importata a fost pornita automat."
                )
                self._save_schedule_config()
            else:
                self.status_var.set(
                    "Pornirea automata a sesiunii importate a esuat. Batch-ul poate fi reluat."
                )
            return started

        return self.start_process()

    def _check_course_auto_schedule(self, now: datetime) -> None:
        if not hasattr(self, "course_repository"):
            return

        self._refresh_course_sessions()
        sessions, session_dt, batch_key = self.get_runnable_course_sessions(now)
        first_session = sessions[0] if sessions else None
        self.tracked_course_session_id = first_session.id if first_session is not None else None
        self._update_course_auto_status(first_session, session_dt)

        if not self.auto_course_enabled_var.get():
            return
        if self.is_running or not sessions or session_dt is None or batch_key is None:
            return

        if batch_key == self.last_completed_batch_key:
            return

        delta_seconds = (session_dt - now).total_seconds()
        if abs(delta_seconds) > COURSE_AUTO_LAUNCH_WINDOW_SECONDS:
            return

        self._start_course_batch(
            sessions,
            batch_key,
            trigger_reason="Pornire automata",
        )

    def _apply_selected_course_from_table(self) -> None:
        if not hasattr(self, "course_tree"):
            return

        selection = self.course_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Sesiune importata",
                "Selectati o sesiune din lista pentru a o aplica in formular.",
            )
            return

        session = self.available_course_sessions.get(selection[0])
        if session is None:
            messagebox.showerror(
                "Sesiune importata",
                "Sesiunea selectata nu mai exista in baza locala.",
            )
            self._refresh_course_selector()
            return

        self._apply_prefill_to_form(self.course_adapter.build_prefill(session))
        self.notebook.select(0)

    def _refresh_course_sessions(self) -> None:
        sessions = self.course_repository.list_sessions()
        self.available_course_sessions = {session.id: session for session in sessions}
        self._prune_auto_course_history()

        if hasattr(self, "course_tree"):
            for item_id in self.course_tree.get_children():
                self.course_tree.delete(item_id)

            for session in sessions:
                self.course_tree.insert(
                    "",
                    "end",
                    iid=session.id,
                    values=self._course_tree_values(session),
                )

        self._refresh_course_selector()
        if (
            getattr(self, "tracked_course_session_id", None)
            and self.tracked_course_session_id not in self.available_course_sessions
        ):
            self.tracked_course_session_id = None
        self._update_course_auto_status()

    def _course_tree_values(self, session) -> tuple[str, ...]:
        return (
            session.course_date,
            session.start_time,
            session.end_time,
            f"{session.duration_hours:.2f}",
            session.course_name,
            session.group_name,
            session.trainer,
            session.is_recurring,
            session.weekdays,
            session.platform,
            session.meeting_link,
        )

    def _delete_selected_course_session(self) -> None:
        if not hasattr(self, "course_tree"):
            return

        selection = self.course_tree.selection()
        if not selection:
            messagebox.showinfo(
                "Stergere sesiune",
                "Selectati o sesiune din lista pentru stergere.",
            )
            return

        if not messagebox.askyesno(
            "Stergere sesiune",
            "Sigur doriti sa stergeti sesiunea selectata?",
            icon="warning",
        ):
            return

        self.course_repository.delete_session(selection[0])
        self._refresh_course_sessions()
        self.course_import_status_var.set("Sesiunea selectata a fost stearsa.")

    def _clear_all_course_sessions(self) -> None:
        if self.course_repository.count_sessions() == 0:
            self.course_import_status_var.set("Nu exista sesiuni de sters.")
            return

        if not messagebox.askyesno(
            "Golire sesiuni",
            "Sigur doriti sa stergeti toate sesiunile importate?",
            icon="warning",
        ):
            return

        self.course_repository.clear_all_sessions()
        self._refresh_course_sessions()
        self.course_import_status_var.set("Toate sesiunile importate au fost sterse.")

    def start_process(self, force_now: bool = False) -> bool:
        """Start the screenshot process."""
        if self.is_running:
            return False

        try:
            hours, screenshots = self._validate_inputs()
            scheduled_datetime = None
            effective_start_option = "now" if force_now else self.start_option.get()

            if effective_start_option in {"scheduled", "daily"} and (
                not self.start_time_var.get()
                or not self._validate_time_format(self.start_time_var.get())
            ):
                self.show_error(ERROR_MESSAGES["invalid_time"], "Eroare Validare")
                return False

            if effective_start_option == "scheduled":
                scheduled_datetime = self._get_course_scheduled_datetime()
                if scheduled_datetime is None:
                    scheduled_datetime = self._get_manual_scheduled_datetime()
                if scheduled_datetime is not None and scheduled_datetime <= self._now():
                    self.show_error(
                        "Sesiunea selectata este programata in trecut. Alegeti o alta sesiune sau reveniti la modul manual.",
                        "Eroare Validare",
                    )
                    return False

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
                    effective_start_option,
                    self.start_time_var.get(),
                    self.app_choice.get(),
                    scheduled_datetime,
                ),
                daemon=True,
            )

            self.is_running = True
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.clear_error()
            self.status_var.set("Proces pornit")
            self.process_thread.start()
            return True
        except ValueError as exc:
            self.show_error(str(exc), "Eroare Validare")
            return False
        except Exception as exc:
            self.show_error(f"Eroare neasteptata: {exc}", "Eroare Sistem")
            return False

    def _finish_run(self, status: str) -> None:
        self.is_running = False
        self._hide_capture_overlay()
        self.start_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_var.set(status)
        self.countdown_var.set("In asteptare")
        self.counter_var.set("0/0 capturi")
        self.progress_var.set(0)
        self.process_thread = None
        self.process_controller = None
        if (
            not self._closing
            and status == "Proces finalizat"
            and getattr(self, "active_course_batch_ids", [])
        ):
            if self._advance_course_batch():
                return
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

            self._update_course_auto_status()
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
            now = self._now()
            self._check_course_auto_schedule(now)
            if not self.is_running and self.start_option.get() == "daily":
                next_run = self._calculate_next_daily_run()

                if next_run is not None:
                    new_display = next_run.strftime("%d-%m-%Y %H:%M")
                    if self.next_run_var.get() != new_display:
                        self.next_run_var.set(new_display)

                    time_diff = (next_run - now).total_seconds()
                    if 0 <= time_diff < 30 and not self._already_ran_today(now):
                        self.logger.log("Pornire automata programata zilnic")
                        self.status_var.set("Pornire automata programata")
                        if self.start_process():
                            self.schedule_config["last_run"] = now.strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            self._save_schedule_config()
        finally:
            self._daily_check_id = self.app.after(
                COURSE_AUTO_CHECK_INTERVAL_MS, self._check_daily_schedule
            )

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
