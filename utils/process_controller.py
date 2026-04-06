import queue
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, Optional, Type

from .constants import (
    ERROR_MESSAGES,
    INITIAL_COUNTDOWN,
    MAX_CAPTURE_RETRIES,
    SUPPORTED_APPS,
)
from .helpers import Logger, ScreenshotManager, SystemUtils


class ScreenshotProcessController:
    """Runs screenshot automation off the Tk thread and emits UI events."""

    def __init__(
        self,
        logger: Logger,
        system_utils: SystemUtils,
        event_sink: Callable[[Dict[str, Any]], None],
        stop_event,
        screenshot_manager_cls: Type[ScreenshotManager] = ScreenshotManager,
        now_provider: Callable[[], datetime] = datetime.now,
        monotonic_provider: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], None] = time.sleep,
        countdown_interval: float = 0.1,
        retry_delay: float = 2,
    ):
        self.logger = logger
        self.system_utils = system_utils
        self.event_sink = event_sink
        self.stop_event = stop_event
        self.screenshot_manager_cls = screenshot_manager_cls
        self.now_provider = now_provider
        self.monotonic_provider = monotonic_provider
        self.sleep_fn = sleep_fn
        self.countdown_interval = countdown_interval
        self.retry_delay = retry_delay
        self.original_system_datetime: Optional[datetime] = None
        self._prompt_responses: "queue.Queue[bool]" = queue.Queue()

    def run(
        self,
        hours: int,
        screenshots: int,
        start_option: str,
        start_time: str,
        app_choice: str,
    ) -> None:
        final_status = "Proces finalizat"
        self.original_system_datetime = self.now_provider()

        try:
            if start_option == "scheduled" and not self._wait_until_start_time(start_time):
                final_status = "Oprit"
                return

            screenshot_mgr = self.screenshot_manager_cls(
                self.original_system_datetime.strftime("%Y-%m-%d"),
                self.logger,
            )
            app_name = SUPPORTED_APPS.get(app_choice, "Desktop")
            current_date = self.original_system_datetime
            interval = max(1, (hours * 3600) // screenshots)

            self._emit("progress", current=0, total=screenshots)
            self._emit("clear_error")

            for index in range(screenshots):
                if self.stop_event.is_set():
                    self.logger.log("Proces oprit de utilizator")
                    final_status = "Oprit"
                    break

                if index > 0:
                    current_date += timedelta(days=1)
                    if not self.system_utils.set_system_date(
                        current_date.strftime("%m/%d/%Y"), self.logger
                    ):
                        raise RuntimeError(ERROR_MESSAGES["system_date_error"])
                else:
                    if not self._countdown(INITIAL_COUNTDOWN, "Prima captura in"):
                        final_status = "Oprit"
                        break

                screenshot_success = False
                retry_count = 0

                while not screenshot_success and retry_count < MAX_CAPTURE_RETRIES:
                    if retry_count > 0:
                        self._emit(
                            "status",
                            message=(
                                f"Reincerc captura de ecran "
                                f"({retry_count + 1}/{MAX_CAPTURE_RETRIES})"
                            ),
                        )
                        self._sleep_with_stop(self.retry_delay)
                        if self.stop_event.is_set():
                            final_status = "Oprit"
                            break

                    if app_choice == "desktop" or self.system_utils.focus_window(
                        app_name, self.logger
                    ):
                        screenshot_success = screenshot_mgr.capture(current_date)

                    if not screenshot_success:
                        retry_count += 1
                        if retry_count < MAX_CAPTURE_RETRIES:
                            self._emit(
                                "error",
                                message=(
                                    f"Incercare esuata {retry_count}/{MAX_CAPTURE_RETRIES}. "
                                    "Se reincearca..."
                                ),
                                title="Eroare Captura",
                                dialog=False,
                            )

                if self.stop_event.is_set():
                    final_status = "Oprit"
                    break

                if not screenshot_success:
                    should_continue = self._request_capture_retry()
                    if not should_continue:
                        self._emit(
                            "error",
                            message=ERROR_MESSAGES["process_stopped"],
                            title="Eroare Fatala",
                            dialog=True,
                        )
                        final_status = "Oprit"
                        break
                    self.logger.log("Utilizatorul a ales sa continue dupa esecul capturii")
                else:
                    self._emit("progress", current=index + 1, total=screenshots)
                    self._emit("clear_error")
                    self.logger.log(
                        f"Captura {index + 1}/{screenshots} realizata cu succes"
                    )

                if index < screenshots - 1 and not self._countdown(
                    interval, "Urmatoarea captura in"
                ):
                    final_status = "Oprit"
                    break

        except Exception as exc:
            self.logger.log(f"Eroare in procesul de captura: {exc}")
            self._emit(
                "error",
                message=str(exc),
                title="Eroare in Proces",
                dialog=True,
            )
        finally:
            restoration_error = self._restore_original_date()
            if restoration_error:
                self._emit(
                    "error",
                    message=restoration_error,
                    title="Avertisment",
                    dialog=True,
                )
            self._emit("finished", status=final_status)

    def respond_capture_failure(self, should_continue: bool) -> None:
        self._prompt_responses.put(should_continue)

    def _emit(self, event_type: str, **payload: Any) -> None:
        event = {"type": event_type}
        event.update(payload)
        self.event_sink(event)

    def _wait_until_start_time(self, start_time: str) -> bool:
        target_time = datetime.strptime(start_time, "%H:%M").time()
        while not self.stop_event.is_set():
            now = self.now_provider()
            if now.time() >= target_time:
                return True

            remaining = datetime.combine(now.date(), target_time) - now
            total_seconds = max(0, int(remaining.total_seconds()))
            minutes, seconds = divmod(total_seconds, 60)
            self._emit(
                "status",
                message=f"Asteptare pana la {start_time} ({minutes:02d}:{seconds:02d})",
            )
            self._sleep_with_stop(min(1, max(self.countdown_interval, 0.01)))
        return False

    def _countdown(self, seconds: int, message: str) -> bool:
        end_time = self.monotonic_provider() + seconds
        while self.monotonic_provider() < end_time:
            if self.stop_event.is_set():
                self.logger.log("Numaratoarea inversa intrerupta")
                return False

            remaining = max(0, int(end_time - self.monotonic_provider()))
            self._emit(
                "countdown",
                message=f"{message} {remaining}s",
                countdown=f"{remaining}s",
            )
            self._sleep_with_stop(self.countdown_interval)
        return not self.stop_event.is_set()

    def _sleep_with_stop(self, seconds: float) -> bool:
        deadline = self.monotonic_provider() + max(0, seconds)
        tick = max(0.01, self.countdown_interval)
        while self.monotonic_provider() < deadline:
            if self.stop_event.is_set():
                return False
            self.sleep_fn(min(tick, deadline - self.monotonic_provider()))
        return not self.stop_event.is_set()

    def _request_capture_retry(self) -> bool:
        self._emit(
            "prompt_capture_failure",
            title="Eroare Captura",
            message=(
                "Nu s-a putut realiza captura de ecran dupa mai multe incercari.\n"
                "Doriti sa continuati cu urmatoarea captura?"
            ),
        )

        while not self.stop_event.is_set():
            try:
                return self._prompt_responses.get_nowait()
            except queue.Empty:
                self.sleep_fn(max(0.01, self.countdown_interval))

        return False

    def _restore_original_date(self) -> Optional[str]:
        if self.original_system_datetime is None:
            return None

        target_date = self.original_system_datetime.strftime("%m/%d/%Y")
        self.logger.log("Se restaureaza data initiala a sistemului")
        if self.system_utils.set_system_date(target_date, self.logger):
            if self.now_provider().date() == self.original_system_datetime.date():
                return None

        self.logger.log("Se face o incercare suplimentara de restaurare a datei")
        self.sleep_fn(1)
        if self.system_utils.set_system_date(target_date, self.logger):
            if self.now_provider().date() == self.original_system_datetime.date():
                return None

        return "Restaurarea datei a esuat. Verificati data sistemului manual."
