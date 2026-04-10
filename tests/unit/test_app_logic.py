from datetime import datetime

import pytest

from main import ScreenshotApp
from utils.course_db import CourseSession


class DummyVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class DummyApp:
    def __init__(self):
        self.calls = []

    def after(self, delay, callback):
        self.calls.append((delay, callback))
        return f"after-{len(self.calls)}"


class DummyLogger:
    def __init__(self):
        self.messages = []

    def log(self, message):
        self.messages.append(message)


class DummyButton:
    def __init__(self):
        self.state = None

    def config(self, **kwargs):
        self.state = kwargs.get("state", self.state)


def build_app(hours="2", screenshots="10", start_time="18:10", option="daily"):
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.hours_var = DummyVar(hours)
    app.screenshots_var = DummyVar(screenshots)
    app.start_time_var = DummyVar(start_time)
    app.start_option = DummyVar(option)
    app.next_run_var = DummyVar("")
    app.status_var = DummyVar("")
    app.auto_course_enabled_var = DummyVar(False)
    app.course_auto_status_var = DummyVar("")
    app.course_auto_tracked_var = DummyVar("")
    app.course_auto_next_run_var = DummyVar("")
    app.course_auto_batch_summary_var = DummyVar("")
    app.course_auto_batch_progress_var = DummyVar("")
    app.course_note_var = DummyVar("")
    app.schedule_config = {
        "last_run": None,
        "auto_course_enabled": False,
        "tracked_course_session_id": None,
        "last_auto_course_run_ids": [],
        "last_completed_batch_key": None,
        "last_auto_course_run_at": None,
    }
    app.logger = DummyLogger()
    app.app = DummyApp()
    app.available_course_sessions = {}
    app.course_adapter = type(
        "Adapter",
        (),
        {
            "sort_sessions": staticmethod(lambda sessions: list(sessions)),
            "format_session_label": staticmethod(
                lambda session: f"{session.course_date} | {session.start_time} | {session.course_name}"
            ),
        },
    )()
    app.tracked_course_session_id = None
    app.last_auto_course_run_ids = []
    app.last_completed_batch_key = None
    app.last_auto_course_run_at = None
    app.active_course_batch_ids = []
    app.active_course_batch_index = 0
    app.active_batch_key = None
    return app


def build_course_session(
    session_id="session-1",
    course_date="2026-04-06",
    start_time="18:10",
    course_name="Excel Avansat",
):
    return CourseSession(
        id=session_id,
        course_date=course_date,
        start_time=start_time,
        end_time="20:10",
        duration_hours=2.0,
        course_name=course_name,
        group_name="Grupa A",
        trainer="Ion",
        is_recurring="DA",
        weekdays="LUNI",
        platform="zoom",
        meeting_link="https://zoom.us/test",
        created_at="2026-04-06 10:00:00",
    )


def test_validate_inputs_accepts_valid_values():
    app = build_app(hours="2", screenshots="10")
    assert app._validate_inputs() == (2, 10)


def test_validate_inputs_accepts_decimal_hours():
    app = build_app(hours="1.5", screenshots="10")
    assert app._validate_inputs() == (1.5, 10)


@pytest.mark.parametrize(
    ("hours", "screenshots", "message"),
    [
        ("0", "10", "Orele trebuie sa fie intre 1 si 24"),
        ("25", "10", "Orele trebuie sa fie intre 1 si 24"),
        ("2", "0", "Capturile de ecran trebuie sa fie intre 1 si 60"),
        ("2", "500", "Capturile de ecran trebuie sa fie intre 1 si 60"),
        ("1", "61", "Capturile de ecran trebuie sa fie intre 1 si 60"),
    ],
)
def test_validate_inputs_rejects_invalid_ranges(hours, screenshots, message):
    app = build_app(hours=hours, screenshots=screenshots)
    with pytest.raises(ValueError, match=message):
        app._validate_inputs()


def test_validate_inputs_requires_numeric_values():
    app = build_app(hours="doua", screenshots="10")
    with pytest.raises(ValueError, match="Introduceti numere valide"):
        app._validate_inputs()


def test_calculate_next_daily_run_uses_next_day_when_time_passed():
    app = build_app(start_time="18:10")
    app._now = lambda: datetime(2026, 4, 6, 18, 11, 0)

    next_run = app._calculate_next_daily_run()

    assert next_run == datetime(2026, 4, 7, 18, 10, 0)


def test_get_manual_scheduled_datetime_uses_today():
    app = build_app(start_time="18:10", option="scheduled")
    app.course_backed_mode = False
    app._now = lambda: datetime(2026, 4, 6, 10, 0, 0)

    scheduled = app._get_manual_scheduled_datetime()

    assert scheduled == datetime(2026, 4, 6, 18, 10, 0)


def test_check_daily_schedule_starts_process_when_due():
    app = build_app(start_time="18:10")
    app._now = lambda: datetime(2026, 4, 6, 18, 9, 40)
    called = []
    saved = []
    app.is_running = False
    app.start_process = lambda: called.append(True) or True
    app._save_schedule_config = lambda: saved.append(True) or True

    app._check_daily_schedule()

    assert called == [True]
    assert saved == [True]
    assert app.schedule_config["last_run"] == "2026-04-06 18:09:40"
    assert app.app.calls[-1][0] == 10000


def test_check_daily_schedule_skips_if_recent_run_exists():
    app = build_app(start_time="18:10")
    app._now = lambda: datetime(2026, 4, 6, 18, 9, 40)
    app.schedule_config["last_run"] = "2026-04-06 18:08:00"
    called = []
    app.is_running = False
    app.start_process = lambda: called.append(True)
    app._save_schedule_config = lambda: True

    app._check_daily_schedule()

    assert called == []


def test_check_daily_schedule_does_not_save_last_run_if_start_fails():
    app = build_app(start_time="18:10")
    app._now = lambda: datetime(2026, 4, 6, 18, 9, 40)
    called = []
    saved = []
    app.is_running = False
    app.start_process = lambda: called.append(True) or False
    app._save_schedule_config = lambda: saved.append(True) or True

    app._check_daily_schedule()

    assert called == [True]
    assert saved == []
    assert app.schedule_config["last_run"] is None


def test_get_runnable_course_sessions_returns_same_slot_batch():
    app = build_app()
    first = build_course_session(
        session_id="early",
        course_date="2026-04-06",
        start_time="18:15",
        course_name="A",
    )
    second = build_course_session(
        session_id="same-slot-2",
        course_date="2026-04-06",
        start_time="18:15",
        course_name="B",
    )
    late = build_course_session(
        session_id="late", course_date="2026-04-06", start_time="18:30", course_name="C"
    )
    app.available_course_sessions = {
        "late": late,
        "early": first,
        "same-slot-2": second,
    }
    app.course_adapter.sort_sessions = lambda sessions: sorted(
        sessions,
        key=lambda session: (session.course_date, session.start_time, session.course_name),
    )

    sessions, scheduled_at, batch_key = app.get_runnable_course_sessions(
        datetime(2026, 4, 6, 18, 10)
    )

    assert [session.id for session in sessions] == ["early", "same-slot-2"]
    assert scheduled_at == datetime(2026, 4, 6, 18, 15)
    assert batch_key == "2026-04-06 18:15"


def test_get_runnable_course_sessions_skips_processed_sessions():
    app = build_app()
    session = build_course_session(session_id="processed")
    next_session = build_course_session(session_id="next", course_name="B")
    app.available_course_sessions = {session.id: session, next_session.id: next_session}
    app.last_auto_course_run_ids = [session.id]

    sessions, scheduled_at, batch_key = app.get_runnable_course_sessions(
        datetime(2026, 4, 6, 18, 10)
    )

    assert [session.id for session in sessions] == ["next"]
    assert scheduled_at == datetime(2026, 4, 6, 18, 10)
    assert batch_key == "2026-04-06 18:10"


def test_check_course_auto_schedule_starts_session_in_launch_window():
    app = build_app()
    app.auto_course_enabled_var = DummyVar(True)
    session = build_course_session(start_time="18:10")
    app.course_repository = type(
        "Repo", (), {"list_sessions": lambda self: [session]}
    )()
    app._refresh_course_sessions = lambda: setattr(
        app, "available_course_sessions", {session.id: session}
    )
    app.get_runnable_course_sessions = lambda now: (
        [session],
        datetime(2026, 4, 6, 18, 10),
        "2026-04-06 18:10",
    )
    started = []
    app.start_course_session = lambda found_session, automatic=False: started.append(
        (found_session.id, automatic)
    ) or True
    app._update_course_auto_status = lambda *args, **kwargs: None
    app.is_running = False

    app._check_course_auto_schedule(datetime(2026, 4, 6, 18, 10, 20))

    assert started == [(session.id, True)]
    assert app.tracked_course_session_id == session.id
    assert app.active_course_batch_ids == [session.id]


def test_check_course_auto_schedule_does_not_run_when_disabled():
    app = build_app()
    session = build_course_session()
    app._refresh_course_sessions = lambda: setattr(
        app, "available_course_sessions", {session.id: session}
    )
    app.get_runnable_course_sessions = lambda now: (
        [session],
        datetime(2026, 4, 6, 18, 10),
        "2026-04-06 18:10",
    )
    called = []
    app.start_course_session = lambda found_session, automatic=False: called.append(True)
    app._update_course_auto_status = lambda *args, **kwargs: None
    app.is_running = False

    app._check_course_auto_schedule(datetime(2026, 4, 6, 18, 10))

    assert called == []


def test_update_course_auto_status_reports_tracked_session():
    app = build_app()
    session = build_course_session()
    app.available_course_sessions = {session.id: session}
    app.tracked_course_session_id = session.id

    app._update_course_auto_status(
        session, datetime(2026, 4, 6, 18, 10)
    )

    assert "activa" not in app.course_auto_status_var.get()
    assert "Excel Avansat" in app.course_auto_tracked_var.get()
    assert "06-04-2026 18:10" in app.course_auto_next_run_var.get()
    assert "1 cursuri" in app.course_auto_batch_summary_var.get()
    assert app.course_auto_batch_progress_var.get() == "Batch curent: -"


def test_prune_auto_course_history_keeps_recent_current_sessions_only():
    app = build_app()
    app.available_course_sessions = {
        "keep-1": build_course_session(session_id="keep-1", course_name="A"),
        "keep-2": build_course_session(session_id="keep-2", course_name="B"),
    }
    app.last_auto_course_run_ids = ["stale", "keep-1", "keep-1", "keep-2"]

    app._prune_auto_course_history()

    assert app.last_auto_course_run_ids == ["keep-1", "keep-2"]


def test_trigger_course_batch_now_starts_tracked_batch_immediately():
    app = build_app()
    first = build_course_session(session_id="first", course_name="A")
    second = build_course_session(session_id="second", course_name="B")
    app.available_course_sessions = {first.id: first, second.id: second}
    app.tracked_course_session_id = first.id
    app.selected_course_session_id = None
    app._refresh_course_sessions = lambda: None
    app.is_running = False
    app.course_backed_mode = False
    app._update_course_auto_status = lambda *args, **kwargs: None
    started = []
    app.start_course_session = lambda session, automatic=False: started.append(
        (session.id, automatic)
    ) or True

    app._trigger_course_batch_now()

    assert started == [("first", True)]
    assert app.active_course_batch_ids == ["first", "second"]
    assert app.active_batch_key == "2026-04-06 18:10"


def test_advance_course_batch_starts_next_session():
    app = build_app()
    first = build_course_session(session_id="first", course_name="A")
    second = build_course_session(session_id="second", course_name="B")
    app.available_course_sessions = {first.id: first, second.id: second}
    app.active_course_batch_ids = [first.id, second.id]
    app.active_course_batch_index = 0
    app.active_batch_key = "2026-04-06 18:10"
    app.course_note_var = DummyVar("")
    app._save_schedule_config = lambda: True
    app._update_course_auto_status = lambda *args, **kwargs: None
    closed = []
    started = []
    app._close_active_meeting = lambda: closed.append(True) or True
    app.start_course_session = lambda session, automatic=False: started.append(
        (session.id, automatic)
    ) or True

    advanced = app._advance_course_batch()

    assert advanced is True
    assert closed == [True]
    assert started == [("second", True)]


def test_advance_course_batch_continues_when_close_active_meeting_fails():
    app = build_app()
    first = build_course_session(session_id="first", course_name="A")
    second = build_course_session(session_id="second", course_name="B")
    app.available_course_sessions = {first.id: first, second.id: second}
    app.active_course_batch_ids = [first.id, second.id]
    app.active_course_batch_index = 0
    app.active_batch_key = "2026-04-06 18:10"
    app.course_note_var = DummyVar("")
    app._save_schedule_config = lambda: True
    app._update_course_auto_status = lambda *args, **kwargs: None
    closed = []
    started = []
    app._close_active_meeting = lambda: closed.append(False) or False
    app.start_course_session = lambda session, automatic=False: started.append(
        (session.id, automatic)
    ) or True

    advanced = app._advance_course_batch()

    assert advanced is True
    assert closed == [False]
    assert started == [("second", True)]
    assert app.active_course_batch_index == 1
    assert app.last_completed_batch_key is None
    assert (
        app.status_var.get()
        == "Inchiderea sesiunii curente a esuat. Continui cu urmatorul curs din batch."
    )


def test_advance_course_batch_keeps_batch_retryable_when_next_start_fails():
    app = build_app()
    first = build_course_session(session_id="first", course_name="A")
    second = build_course_session(session_id="second", course_name="B")
    app.available_course_sessions = {first.id: first, second.id: second}
    app.active_course_batch_ids = [first.id, second.id]
    app.active_course_batch_index = 0
    app.active_batch_key = "2026-04-06 18:10"
    app.course_note_var = DummyVar("")
    app._save_schedule_config = lambda: True
    app._update_course_auto_status = lambda *args, **kwargs: None
    closed = []
    started = []
    app._close_active_meeting = lambda: closed.append(True) or True
    app.start_course_session = lambda session, automatic=False: started.append(
        (session.id, automatic)
    ) or False

    advanced = app._advance_course_batch()

    assert advanced is False
    assert closed == [True]
    assert started == [("second", True)]
    assert app.active_course_batch_index == 1
    assert app.active_course_batch_ids == [first.id, second.id]
    assert app.last_completed_batch_key is None
    assert (
        app.status_var.get()
        == "Pornirea cursului urmator din batch a esuat. Batch-ul ramane activ pentru retry."
    )


def test_advance_course_batch_clears_state_after_last_session():
    app = build_app()
    session = build_course_session(session_id="only")
    app.available_course_sessions = {session.id: session}
    app.active_course_batch_ids = [session.id]
    app.active_course_batch_index = 0
    app.active_batch_key = "2026-04-06 18:10"
    saved = []
    app._save_schedule_config = lambda: saved.append(True) or True
    app._update_course_auto_status = lambda *args, **kwargs: None

    advanced = app._advance_course_batch()

    assert advanced is False
    assert app.active_course_batch_ids == []
    assert app.last_completed_batch_key == "2026-04-06 18:10"
    assert saved == [True]


def test_finish_run_advances_to_next_course_after_successful_batch_item():
    app = build_app()
    app.is_running = True
    app._closing = False
    app.active_course_batch_ids = ["first", "second"]
    app.start_button = DummyButton()
    app.stop_button = DummyButton()
    app.countdown_var = DummyVar("")
    app.counter_var = DummyVar("")
    app.progress_var = DummyVar(50)
    app.process_thread = object()
    app.process_controller = object()
    hidden = []
    advanced = []
    app._hide_capture_overlay = lambda: hidden.append(True)
    app._advance_course_batch = lambda: advanced.append(True) or True

    app._finish_run("Proces finalizat")

    assert hidden == [True]
    assert advanced == [True]
    assert app.is_running is False
    assert app.start_button.state == "normal"
    assert app.stop_button.state == "disabled"
    assert app.status_var.get() == "Proces finalizat"
    assert app.countdown_var.get() == "In asteptare"
    assert app.counter_var.get() == "0/0 capturi"
    assert app.progress_var.get() == 0
    assert app.process_thread is None
    assert app.process_controller is None
