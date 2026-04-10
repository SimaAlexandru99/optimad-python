from utils.helpers import SystemUtils


class DummyLogger:
    def __init__(self):
        self.messages = []

    def log(self, message):
        self.messages.append(message)


class FakeRect:
    def __init__(self, width=1200, height=800):
        self._width = width
        self._height = height

    def width(self):
        return self._width

    def height(self):
        return self._height


class FakeWindow:
    def __init__(self, title):
        self.title = title
        self.focused = False
        self.maximized = False
        self.clicks = []

    def window_text(self):
        return self.title

    def set_focus(self):
        self.focused = True

    def maximize(self):
        self.maximized = True

    def rectangle(self):
        return FakeRect()

    def click_input(self, coords=None, double=False):
        self.clicks.append({"coords": coords, "double": double})


class FakeDesktop:
    def __init__(self, windows):
        self._windows = windows

    def windows(self):
        return self._windows


def test_focus_window_attempts_zoom_fullscreen(monkeypatch):
    zoom_window = FakeWindow("Zoom Workplace")
    logger = DummyLogger()

    monkeypatch.setattr(
        "utils.helpers.Desktop",
        lambda backend=None: FakeDesktop([zoom_window]),
    )

    focused = SystemUtils.focus_window("Zoom", logger)

    assert focused is True
    assert zoom_window.focused is True
    assert zoom_window.maximized is True
    assert zoom_window.clicks == [{"coords": (600, 18), "double": True}]


def test_focus_window_skips_fullscreen_for_other_apps(monkeypatch):
    teams_window = FakeWindow("Microsoft Teams")
    logger = DummyLogger()

    monkeypatch.setattr(
        "utils.helpers.Desktop",
        lambda backend=None: FakeDesktop([teams_window]),
    )

    focused = SystemUtils.focus_window("Microsoft Teams", logger)

    assert focused is True
    assert teams_window.focused is True
    assert teams_window.maximized is True
    assert teams_window.clicks == []
