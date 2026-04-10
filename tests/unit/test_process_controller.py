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
    def __init__(self):
        self.focus_calls = []

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
    scheduled_datetime=None,
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
        if event["type"] == "prepare_overlay":
            controller_holder["controller"].respond_overlay_ready(True)

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
    controller.run(
        hours,
        screenshots,
        start_option,
        start_time,
        app_choice,
        scheduled_datetime,
    )
    return controller, logger, events


def test_controller_runs_successfully_with_overlay_dates():
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

    assert controller.initial_capture_datetime == datetime(2026, 4, 6, 10, 0, 0)
    assert screenshot_manager.root_dir == "."
    assert screenshot_manager.captures[0] == datetime(2026, 4, 6, 10, 0, 0)
    assert screenshot_manager.captures[1] == datetime(2026, 4, 7, 10, 0, 0)
    assert events[-1] == {"type": "finished", "status": "Proces finalizat"}
    assert [event["simulated_date"] for event in events if event["type"] == "prepare_overlay"] == [
        "06-04-2026",
        "07-04-2026",
    ]
    assert any(event["type"] == "progress" and event["current"] == 2 for event in events)
    assert "Captura 2/2 realizata cu succes" in logger.messages


def test_controller_stops_during_initial_countdown():
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


def test_controller_hides_overlay_when_process_finishes():
    clock = FakeClock(datetime(2026, 4, 6, 10, 0, 0))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([True])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
    )

    assert any(event["type"] == "hide_overlay" for event in events)


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


def test_controller_waits_for_absolute_scheduled_datetime():
    clock = FakeClock(datetime(2026, 4, 6, 9, 59, 58))
    system_utils = FakeSystemUtils()
    screenshot_manager = FakeScreenshotManager([True])

    _, _, events = run_controller(
        clock=clock,
        system_utils=system_utils,
        screenshot_manager=screenshot_manager,
        start_option="scheduled",
        start_time="10:00",
        scheduled_datetime=datetime(2026, 4, 7, 10, 0, 0),
    )

    assert any(
        event["type"] == "status"
        and event["message"].startswith("Asteptare pana la 07-04-2026 10:00")
        for event in events
    )
