from __future__ import annotations

import threading
import time
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from core.config_manager import ConfigManager
from os_services.base import INetworkBlocker


class SchedulerService(QObject):
    block_applied = Signal(list)
    unblock_applied = Signal()
    scheduler_error = Signal(str)

    def __init__(
        self,
        config_manager: ConfigManager,
        network_blocker: INetworkBlocker,
        poll_interval_seconds: int = 30,
    ) -> None:
        super().__init__()
        self._config_manager = config_manager
        self._network_blocker = network_blocker
        self._poll_interval_seconds = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._is_blocking_active = False

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, name="SchedulerThread", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.is_running:
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self._thread = None
        self._safe_unblock()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                domains_to_block = self._get_active_domains_for_now()
                if domains_to_block and not self._is_blocking_active:
                    if self._network_blocker.block_domains(domains_to_block):
                        self._is_blocking_active = True
                        self.block_applied.emit(domains_to_block)
                elif not domains_to_block and self._is_blocking_active:
                    self._safe_unblock()
            except Exception as exc:  # pragma: no cover
                self.scheduler_error.emit(f"Scheduler error: {exc}")
            time.sleep(self._poll_interval_seconds)

    def _safe_unblock(self) -> None:
        try:
            if self._network_blocker.unblock_all():
                self._is_blocking_active = False
                self.unblock_applied.emit()
        except Exception as exc:  # pragma: no cover
            self.scheduler_error.emit(f"Unblock error: {exc}")

    def _get_active_domains_for_now(self) -> list[str]:
        now = datetime.now().time()
        active_domains: list[str] = []
        for rule in self._config_manager.get_network_blacklist():
            if not bool(rule.get("is_active", True)):
                continue
            domain = str(rule.get("domain", "")).strip()
            if not domain:
                continue
            start = self._parse_time(str(rule.get("start_time", "00:00")))
            end = self._parse_time(str(rule.get("end_time", "23:59")))
            if self._is_now_in_range(now, start, end):
                active_domains.append(domain)
        return sorted(set(active_domains))

    @staticmethod
    def _parse_time(value: str):
        return datetime.strptime(value, "%H:%M").time()

    @staticmethod
    def _is_now_in_range(now, start, end) -> bool:
        if start <= end:
            return start <= now <= end
        return now >= start or now <= end
