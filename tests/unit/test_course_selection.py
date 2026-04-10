from datetime import datetime

from utils.course_db import CourseSession
from utils.course_selection import CourseSessionAdapter
from main import ScreenshotApp


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyCombobox(dict):
    pass


class DummyLogger:
    def __init__(self):
        self.messages = []

    def log(self, message):
        self.messages.append(message)


class DummyWindow:
    def __init__(self):
        self.opened = []

    def open(self, url):
        self.opened.append(url)
        return True


def build_session(
    session_id="session-1",
    course_date="2026-04-10",
    start_time="18:00",
    end_time="20:00",
    duration_hours=2.0,
    course_name="Excel Avansat",
    group_name="Grupa A",
    platform="zoom",
    meeting_link="https://zoom.us/test",
):
    return CourseSession(
        id=session_id,
        course_date=course_date,
        start_time=start_time,
        end_time=end_time,
        duration_hours=duration_hours,
        course_name=course_name,
        group_name=group_name,
        trainer="Ion",
        is_recurring="DA",
        weekdays="LUNI",
        platform=platform,
        meeting_link=meeting_link,
        created_at="2026-04-06 10:00:00",
    )


def test_course_session_adapter_sorts_and_builds_prefill():
    adapter = CourseSessionAdapter()
    later = build_session(session_id="2", course_date="2026-04-11", course_name="B")
    earlier = build_session(session_id="1", course_date="2026-04-10", course_name="A")

    options = adapter.build_options([later, earlier])
    assert [option.session_id for option in options] == ["1", "2"]
    assert options[0].label == "2026-04-10 | 18:00 | A | Grupa A"

    prefill = adapter.build_prefill(
        build_session(platform="custom", meeting_link="")
    )
    assert prefill.hours_value == "2"
    assert prefill.suggested_app_choice is None
    assert "nu se poate mapa automat" in prefill.warning


def test_apply_selected_course_session_prefills_and_clear_restores_manual_values():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.hours_var = DummyVar("3")
    app.start_option = DummyVar("daily")
    app.start_time_var = DummyVar("19:30")
    app.app_choice = DummyVar("desktop")
    app.course_selector_var = DummyVar("2026-04-10")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.course_backed_mode = False
    app.last_applied_meeting_link = ""
    app.manual_form_snapshot = None
    app.selected_course_session_id = None
    app.course_session_options = app.course_adapter.build_options([build_session()])
    app.available_course_sessions = {"session-1": build_session()}
    app._toggle_time_input = lambda: None

    app._apply_selected_course_session()

    assert app.hours_var.get() == "2"
    assert app.start_option.get() == "scheduled"
    assert app.start_time_var.get() == "18:00"
    assert app.app_choice.get() == "zoom"
    assert app.course_backed_mode is True
    assert app.selected_course_session_id == "session-1"
    assert app.course_meeting_link_var.get() == "Link sedinta: https://zoom.us/test"

    app._clear_course_session_selection()

    assert app.hours_var.get() == "3"
    assert app.start_option.get() == "daily"
    assert app.start_time_var.get() == "19:30"
    assert app.app_choice.get() == "desktop"
    assert app.course_backed_mode is False
    assert app.selected_course_session_id is None


def test_refresh_course_sessions_updates_selector_values_and_clears_missing_selection():
    class DummyRepository:
        def __init__(self, sessions):
            self.sessions = sessions

        def list_sessions(self):
            return list(self.sessions)

    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.course_repository = DummyRepository([build_session()])
    app.course_selector_var = DummyVar("")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.hours_var = DummyVar("2")
    app.start_option = DummyVar("now")
    app.start_time_var = DummyVar("18:00")
    app.app_choice = DummyVar("desktop")
    app.course_selector = DummyCombobox()
    app.course_session_options = []
    app.available_course_sessions = {}
    app.course_backed_mode = True
    app.last_applied_meeting_link = "https://zoom.us/test"
    app.manual_form_snapshot = {
        "hours": "5",
        "start_option": "daily",
        "start_time": "20:00",
        "app_choice": "teams",
    }
    app.selected_course_session_id = "missing"
    app.course_auto_prefill_enabled = False
    app._toggle_time_input = lambda: None

    app._refresh_course_sessions()

    assert app.course_selector["values"] == [
        "2026-04-10 | 18:00 | Excel Avansat | Grupa A"
    ]
    assert app.hours_var.get() == "5"
    assert app.start_option.get() == "daily"
    assert app.app_choice.get() == "teams"
    assert app.course_backed_mode is False


def test_refresh_course_sessions_auto_applies_next_relevant_session():
    class DummyRepository:
        def __init__(self, sessions):
            self.sessions = sessions

        def list_sessions(self):
            return list(self.sessions)

    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.course_repository = DummyRepository(
        [
            build_session(
                session_id="past",
                course_date="2026-04-05",
                start_time="18:00",
                course_name="Curs vechi",
            ),
            build_session(
                session_id="next",
                course_date="2026-04-07",
                start_time="19:00",
                course_name="Curs viitor",
            ),
        ]
    )
    app.course_selector_var = DummyVar("")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.hours_var = DummyVar("1")
    app.start_option = DummyVar("now")
    app.start_time_var = DummyVar("09:00")
    app.app_choice = DummyVar("desktop")
    app.course_selector = DummyCombobox()
    app.course_session_options = []
    app.available_course_sessions = {}
    app.course_backed_mode = False
    app.last_applied_meeting_link = ""
    app.manual_form_snapshot = None
    app.selected_course_session_id = None
    app.course_auto_prefill_enabled = True
    app._toggle_time_input = lambda: None
    app._now = lambda: datetime(2026, 4, 6, 12, 0)

    app._refresh_course_sessions()

    assert app.selected_course_session_id == "next"
    assert app.hours_var.get() == "2"
    assert app.start_option.get() == "scheduled"
    assert app.start_time_var.get() == "19:00"
    assert "aplicata automat" in app.course_note_var.get()


def test_manual_clear_disables_auto_prefill_until_reenabled():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.course_selector_var = DummyVar("2026-04-10")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.hours_var = DummyVar("2")
    app.start_option = DummyVar("scheduled")
    app.start_time_var = DummyVar("18:00")
    app.app_choice = DummyVar("zoom")
    app.course_selector = DummyCombobox()
    app.course_session_options = []
    app.available_course_sessions = {}
    app.course_backed_mode = True
    app.last_applied_meeting_link = "https://zoom.us/test"
    app.manual_form_snapshot = {
        "hours": "4",
        "start_option": "daily",
        "start_time": "20:00",
        "app_choice": "desktop",
    }
    app.selected_course_session_id = "session-1"
    app.course_auto_prefill_enabled = True
    app._toggle_time_input = lambda: None

    app._clear_course_session_selection(disable_auto_prefill=True)

    assert app.course_auto_prefill_enabled is False
    assert app.hours_var.get() == "4"
    assert app.start_option.get() == "daily"


def test_start_process_rejects_course_session_scheduled_in_past():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.hours_var = DummyVar("2")
    app.screenshots_var = DummyVar("10")
    app.start_option = DummyVar("scheduled")
    app.start_time_var = DummyVar("18:00")
    app.app_choice = DummyVar("zoom")
    app.course_backed_mode = True
    app.selected_course_session_id = "session-1"
    app.available_course_sessions = {
        "session-1": build_session(course_date="2026-04-05", start_time="18:00")
    }
    app.stop_event = type("Stop", (), {"clear": lambda self: None})()
    app.logger = DummyLogger()
    captured_errors = []
    app.show_error = lambda message, title="Eroare", show_dialog=True: captured_errors.append(
        (message, title)
    )
    app._now = lambda: datetime(2026, 4, 6, 12, 0)
    app.is_running = False

    app.start_process()

    assert captured_errors
    assert "programata in trecut" in captured_errors[0][0]


def test_start_process_rejects_manual_scheduled_time_in_past():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.hours_var = DummyVar("2")
    app.screenshots_var = DummyVar("10")
    app.start_option = DummyVar("scheduled")
    app.start_time_var = DummyVar("10:00")
    app.app_choice = DummyVar("zoom")
    app.course_backed_mode = False
    app.stop_event = type("Stop", (), {"clear": lambda self: None})()
    app.logger = DummyLogger()
    captured_errors = []
    app.show_error = lambda message, title="Eroare", show_dialog=True: captured_errors.append(
        (message, title)
    )
    app._now = lambda: datetime(2026, 4, 6, 12, 0)
    app.is_running = False

    app.start_process()

    assert captured_errors
    assert "programata in trecut" in captured_errors[0][0]


def test_start_course_session_marks_auto_run_when_start_succeeds():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.hours_var = DummyVar("1")
    app.start_option = DummyVar("now")
    app.start_time_var = DummyVar("09:00")
    app.app_choice = DummyVar("desktop")
    app.course_selector_var = DummyVar("")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.auto_course_enabled_var = DummyVar(True)
    app.course_auto_status_var = DummyVar("")
    app.course_auto_tracked_var = DummyVar("")
    app.course_auto_next_run_var = DummyVar("")
    app.course_auto_batch_summary_var = DummyVar("")
    app.course_auto_batch_progress_var = DummyVar("")
    app.course_backed_mode = False
    app.last_applied_meeting_link = ""
    app.manual_form_snapshot = None
    app.selected_course_session_id = None
    app.logger = DummyLogger()
    app.available_course_sessions = {}
    app._toggle_time_input = lambda: None
    app._now = lambda: datetime(2026, 4, 6, 12, 0)
    app._save_schedule_config = lambda: True
    app.last_auto_course_run_ids = []
    app.last_completed_batch_key = None
    app.last_auto_course_run_at = None
    app.tracked_course_session_id = None
    app.last_auto_course_link_opened_session_id = None
    app.last_auto_course_link_opened_at = None
    app.active_course_batch_ids = []
    app.active_course_batch_index = 0
    app.active_batch_key = None
    app.start_process = lambda force_now=False: force_now is True
    opened = []
    app._open_meeting_link = lambda *args, **kwargs: opened.append(args[0]) or True
    session = build_session()

    started = app.start_course_session(session, automatic=True)

    assert started is True
    assert opened == ["https://zoom.us/test"]
    assert app.last_auto_course_run_ids == [session.id]
    assert app.tracked_course_session_id == session.id


def test_start_course_session_without_link_continues():
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.course_adapter = CourseSessionAdapter()
    app.hours_var = DummyVar("1")
    app.start_option = DummyVar("now")
    app.start_time_var = DummyVar("09:00")
    app.app_choice = DummyVar("desktop")
    app.course_selector_var = DummyVar("")
    app.course_mode_var = DummyVar("")
    app.course_session_date_var = DummyVar("")
    app.course_meeting_link_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.auto_course_enabled_var = DummyVar(True)
    app.course_auto_status_var = DummyVar("")
    app.course_auto_tracked_var = DummyVar("")
    app.course_auto_next_run_var = DummyVar("")
    app.course_auto_batch_summary_var = DummyVar("")
    app.course_auto_batch_progress_var = DummyVar("")
    app.course_backed_mode = False
    app.last_applied_meeting_link = ""
    app.manual_form_snapshot = None
    app.selected_course_session_id = None
    app.logger = DummyLogger()
    app.available_course_sessions = {}
    app._toggle_time_input = lambda: None
    app._now = lambda: datetime(2026, 4, 6, 12, 0)
    app._save_schedule_config = lambda: True
    app.last_auto_course_run_ids = []
    app.last_completed_batch_key = None
    app.last_auto_course_run_at = None
    app.tracked_course_session_id = None
    app.last_auto_course_link_opened_session_id = None
    app.last_auto_course_link_opened_at = None
    app.active_course_batch_ids = []
    app.active_course_batch_index = 0
    app.active_batch_key = None
    app.start_process = lambda force_now=False: force_now is True
    app._open_meeting_link = lambda *args, **kwargs: False
    session = build_session(meeting_link="")

    started = app.start_course_session(session, automatic=True)

    assert started is True
    assert app.last_auto_course_run_ids == [session.id]


def test_format_meeting_link_display_shortens_long_links():
    app = ScreenshotApp.__new__(ScreenshotApp)
    short = app._format_meeting_link_display("https://zoom.us/test")
    long_value = app._format_meeting_link_display("https://zoom.us/" + "a" * 80)

    assert short == "Link sedinta: https://zoom.us/test"
    assert long_value.endswith("...")
    assert long_value.startswith("Link sedinta: https://zoom.us/")
