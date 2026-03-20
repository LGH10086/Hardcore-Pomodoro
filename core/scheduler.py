from __future__ import annotations

import threading
import time
from datetime import datetime

from PySide6.QtCore import QObject, Signal

from core.models import PolicySnapshot
from os_services.base import INetworkBlocker


class SchedulerService(QObject):
    block_applied = Signal(list)
    unblock_applied = Signal()
    scheduler_error = Signal(str)

    def __init__(
        self,
        snapshot_provider,
        network_blocker: INetworkBlocker,
        poll_interval_seconds: int = 30,
    ) -> None:
        super().__init__()
        self._snapshot_provider = snapshot_provider
        self._network_blocker = network_blocker
        self._poll_interval_seconds = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._apply_lock = threading.Lock()
        self._is_blocking_active = False
        self._active_domains: list[str] = []

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
            self.apply_now()
            time.sleep(self._poll_interval_seconds)

    def apply_now(self) -> None:
        with self._apply_lock:
            try:
                self._evaluate_and_apply()
            except Exception as exc:  # pragma: no cover
                self.scheduler_error.emit(f"Scheduler error: {exc}")

    def _evaluate_and_apply(self) -> None:
        domains_to_block = self._get_active_domains_for_now()
        if domains_to_block:
            # Re-apply when blocked domains changed to keep runtime behavior in sync
            # with latest rules even before next unblock.
            domains_changed = domains_to_block != self._active_domains
            if not self._is_blocking_active or domains_changed:
                if self._network_blocker.block_domains(domains_to_block):
                    self._is_blocking_active = True
                    self._active_domains = list(domains_to_block)
                    self.block_applied.emit(domains_to_block)
            return

        if self._is_blocking_active:
            self._safe_unblock()

    def _safe_unblock(self) -> None:
        try:
            if self._network_blocker.unblock_all():
                self._is_blocking_active = False
                self._active_domains = []
                self.unblock_applied.emit()
        except Exception as exc:  # pragma: no cover
            self.scheduler_error.emit(f"Unblock error: {exc}")

    def _get_active_domains_for_now(self) -> list[str]:
        now = datetime.now().time()
        active_domains: list[str] = []
        snapshot: PolicySnapshot = self._snapshot_provider()
        for rule in snapshot.network_rules:
            if not bool(rule.is_active):
                continue
            domain = str(rule.domain).strip()
            if not domain:
                continue
            start = self._parse_time(str(rule.start_time))
            end = self._parse_time(str(rule.end_time))
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
