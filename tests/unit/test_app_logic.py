from datetime import datetime

import pytest

from main import ScreenshotApp


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


def build_app(hours="2", screenshots="10", start_time="18:10", option="daily"):
    app = ScreenshotApp.__new__(ScreenshotApp)
    app.hours_var = DummyVar(hours)
    app.screenshots_var = DummyVar(screenshots)
    app.start_time_var = DummyVar(start_time)
    app.start_option = DummyVar(option)
    app.next_run_var = DummyVar("")
    app.status_var = DummyVar("")
    app.schedule_config = {"last_run": None}
    app.logger = DummyLogger()
    app.app = DummyApp()
    return app


def test_validate_inputs_accepts_valid_values():
    app = build_app(hours="2", screenshots="10")
    assert app._validate_inputs() == (2, 10)


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


def test_check_daily_schedule_starts_process_when_due():
    app = build_app(start_time="18:10")
    app._now = lambda: datetime(2026, 4, 6, 18, 9, 40)
    called = []
    saved = []
    app.is_running = False
    app.start_process = lambda: called.append(True)
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
