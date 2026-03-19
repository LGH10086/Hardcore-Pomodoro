from __future__ import annotations

import threading
import time
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal

from os_services.base import IProcessMonitor, OSInteractError


class WatchdogService(QObject):
    violation_detected = Signal(str)
    monitor_error = Signal(str)

    def __init__(
        self,
        process_monitor: IProcessMonitor,
        whitelist_provider: Callable[[], list[str]],
        poll_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self._process_monitor = process_monitor
        self._whitelist_provider = whitelist_provider
        self._poll_interval = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="WatchdogThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.is_running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                process_name = self._process_monitor.get_foreground_process_name().lower()
                whitelist = {name.lower() for name in self._whitelist_provider()}
                if process_name and process_name not in whitelist:
                    self.violation_detected.emit(process_name)
            except OSInteractError as exc:
                self.monitor_error.emit(str(exc))
            except Exception as exc:  # pragma: no cover
                self.monitor_error.emit(f"Watchdog unexpected error: {exc}")
            time.sleep(self._poll_interval)
