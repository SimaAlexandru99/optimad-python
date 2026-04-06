import threading
from datetime import datetime, timedelta

from utils.process_controller import ScreenshotProcessController


class FakeClock:
    def __init__(self, current):
        self.current = current
        self.monotonic_value = 0.0

    def now(self):
        return self.current

    def monotonic(self):
        return self.monotonic_value

    def sleep(self, seconds):
        self.current += timedelta(seconds=seconds)
        self.monotonic_value += seconds


class FakeLogger:
    def __init__(self):
        self.messages = []

    def log(self, message):
        self.messages.append(message)


class FakeSystemUtils:
    def __init__(self, fail_dates=None):
        self.fail_dates = set(fail_dates or [])
        self.set_calls = []
        self.focus_calls = []

    def set_system_date(self, new_date, logger):
        self.set_calls.append(new_date)
        return new_date not in self.fail_dates

    def focus_window(self, app_name, logger, retry_attempts=3):
        self.focus_calls.append((app_name, retry_attempts))
        return True


class FakeScreenshotManager:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.captures = []
        self.root_dir = None

    def factory(self, root_dir, logger):
        self.root_dir = root_dir
        return self

    def capture(self, screenshot_date):
        self.captures.append(screenshot_date)
        if self.outcomes:
            return self.outcomes.pop(0)
        return True


def run_controller(
    *,
    clock,
    system_utils,
    screenshot_manager,
    start_option="now",
    start_time="18:10",
    app_choice="desktop",
    hours=1,
    screenshots=1,
    prompt_response=None,
    stop_event=None,
):
    events = []
    logger = FakeLogger()
    controller_holder = {}

    def event_sink(event):
        events.append(event)
        if event["type"] == "prompt_capture_failure" and prompt_response is not None:
            controller_holder["controller"].respond_capture_failure(prompt_response)

    controller = ScreenshotProcessController(
        logger=logger,
        system_utils=system_utils,
        event_sink=event_sink,
        stop_event=stop_event or threading.Event(),
        screenshot_manager_cls=screenshot_manager.factory,
        now_provider=clock.now,
        monotonic_provider=clock.monotonic,
        sleep_fn=clock.sleep,
        countdown_interval=1,
        retry_delay=1,
    )
    controller_holder["controller"] = controller
    controller.run(hours, screenshots, start_option, start_time, app_choice)
    return controller, logger, events


def test_controller_runs_successfully_and_restores_original_date():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([True, True])

    controller, logger, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
        hours=1,
        screenshots=2,
    )

    assert controller.original_system_datetime == datetime(2026, 4, 6, 10, 0, 0)
    assert system_utils.set_calls == ["04/07/2026", "04/06/2026"]
    assert screenshot_manager.root_dir == "2026-04-06"
    assert screenshot_manager.captures[0] == datetime(2026, 4, 6, 10, 0, 0)
    assert screenshot_manager.captures[1] == datetime(2026, 4, 7, 10, 0, 0)
    assert events[-1] == {"type": "finished", "status": "Proces finalizat"}
    assert any(event["type"] == "progress" and event["current"] == 2 for event in events)
    assert "Captura 2/2 realizata cu succes" in logger.messages


def test_controller_stops_during_initial_countdown_and_restores():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([True])
    stop_event = threading.Event()

    def stop_on_first_sleep(seconds):
        stop_event.set()
        clock.sleep(seconds)

    events = []
    controller = ScreenshotProcessController(
        logger=FakeLogger(),
        system_utils=system_utils,
        event_sink=events.append,
        stop_event=stop_event,
        screenshot_manager_cls=screenshot_manager.factory,
        now_provider=clock.now,
        monotonic_provider=clock.monotonic,
        sleep_fn=stop_on_first_sleep,
        countdown_interval=1,
        retry_delay=1,
    )

    controller.run(1, 1, "now", "18:10", "desktop")

    assert screenshot_manager.captures == []
    assert system_utils.set_calls == ["04/06/2026"]
    assert events[-1] == {"type": "finished", "status": "Oprit"}


def test_controller_continues_after_retry_prompt():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([False, False, False, True])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
        hours=1,
        screenshots=2,
        prompt_response=True,
    )

    assert any(event["type"] == "prompt_capture_failure" for event in events)
    assert events[-1] == {"type": "finished", "status": "Proces finalizat"}


def test_controller_aborts_after_retry_prompt_when_user_declines():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([False, False, False])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
        prompt_response=False,
    )

    assert any(
        event["type"] == "error"
        and event["message"] == "Proces oprit din cauza esecului capturii de ecran"
        for event in events
    )
    assert events[-1] == {"type": "finished", "status": "Oprit"}


def test_controller_reports_date_restore_failure_after_second_attempt():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils({"04/06/2026"})
    screenshot_manager = FakeScreenshotManager([True])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
    )

    assert system_utils.set_calls == ["04/06/2026", "04/06/2026"]
    assert any(
        event["type"] == "error"
        and event["message"] == "Restaurarea datei a esuat. Verificati data sistemului manual."
        for event in events
    )


def test_controller_waits_for_scheduled_start():
    clock = FakeClock(datetime(2026, 4, 6, 9, 59, 58))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([True])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
        start_option="scheduled",
        start_time="10:00",
    )

    assert any(
        event["type"] == "status"
        and event["message"].startswith("Asteptare pana la 10:00")
        for event in events
    )
