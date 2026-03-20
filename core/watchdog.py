from __future__ import annotations

import subprocess
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.models import PolicySnapshot, ProcessRule
from os_services.base import IProcessMonitor, OSInteractError


class WatchdogService(QObject):
    violation_detected = Signal(str)
    allowed_foreground_detected = Signal(str)
    monitor_error = Signal(str)

    def __init__(
        self,
        process_monitor: IProcessMonitor,
        snapshot_provider: Callable[[], PolicySnapshot],
        poll_interval_seconds: float = 0.5,
    ) -> None:
        super().__init__()
        self._process_monitor = process_monitor
        self._snapshot_provider = snapshot_provider
        self._poll_interval = poll_interval_seconds
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._decision_cache: OrderedDict[tuple[int, str], bool] = OrderedDict()
        self._signature_cache: OrderedDict[str, bool] = OrderedDict()
        self._cache_limit = 512
        self._last_allowed_state: bool | None = None
        self._last_foreground_key: tuple[int, str] | None = None

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._last_allowed_state = None
        self._last_foreground_key = None
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
                info = self._process_monitor.get_foreground_process_info()
                snapshot = self._snapshot_provider()
                is_allowed = self._is_allowed(info.pid, info.name, info.exe_path, snapshot.process_rules)
                normalized_path = str(info.exe_path or "").strip().lower()
                current_key = (int(info.pid), normalized_path)

                if is_allowed:
                    # Emit whenever allowed foreground app changes, so UI can react
                    # to transitions like overlay-owned process -> user-selected allowed app.
                    if self._last_allowed_state is not True or self._last_foreground_key != current_key:
                        self.allowed_foreground_detected.emit(f"{info.name} | {info.exe_path}")
                elif self._last_allowed_state is not False:
                    self.violation_detected.emit(f"{info.name} | {info.exe_path}")

                self._last_allowed_state = is_allowed
                self._last_foreground_key = current_key
            except OSInteractError as exc:
                self.monitor_error.emit(str(exc))
            except Exception as exc:  # pragma: no cover
                self.monitor_error.emit(f"Watchdog unexpected error: {exc}")
            time.sleep(self._poll_interval)

    def _is_allowed(self, pid: int, name: str, exe_path: str, rules: tuple[ProcessRule, ...]) -> bool:
        normalized_name = str(name).lower().strip()
        normalized_path = str(exe_path or "").strip().lower()
        cache_key = (pid, normalized_path)
        if cache_key in self._decision_cache:
            return self._decision_cache[cache_key]

        active_rules = [rule for rule in rules if rule.is_active]
        if not active_rules:
            self._remember_decision(cache_key, False)
            return False

        for rule in active_rules:
            if normalized_name != rule.name.lower().strip():
                continue

            rule_path = rule.path.strip().lower()
            if rule_path and rule_path != normalized_path:
                continue

            if rule.require_signature and not self._is_path_signed(exe_path):
                continue

            self._remember_decision(cache_key, True)
            return True

        self._remember_decision(cache_key, False)
        return False

    def _remember_decision(self, key: tuple[int, str], decision: bool) -> None:
        self._decision_cache[key] = decision
        self._decision_cache.move_to_end(key)
        while len(self._decision_cache) > self._cache_limit:
            self._decision_cache.popitem(last=False)

    def _is_path_signed(self, exe_path: str) -> bool:
        normalized = str(exe_path or "").strip().lower()
        if not normalized:
            return False
        if normalized in self._signature_cache:
            return self._signature_cache[normalized]

        is_signed = self._query_signature_state(normalized)
        self._signature_cache[normalized] = is_signed
        self._signature_cache.move_to_end(normalized)
        while len(self._signature_cache) > self._cache_limit:
            self._signature_cache.popitem(last=False)
        return is_signed

    def _query_signature_state(self, exe_path: str) -> bool:
        if not Path(exe_path).exists():
            return False

        command = (
            "(Get-AuthenticodeSignature -FilePath '"
            + exe_path.replace("'", "''")
            + "').Status -eq 'Valid'"
        )
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2,
            check=False,
            creationflags=creation_flags,
        )
        return "True" in result.stdout
