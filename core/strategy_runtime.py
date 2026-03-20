from __future__ import annotations

import threading

from core.models import PolicySnapshot
from core.strategy_compiler import StrategyCompiler


class StrategyRuntime:
    def __init__(self, compiler: StrategyCompiler) -> None:
        self._compiler = compiler
        self._lock = threading.Lock()
        self._snapshot = self._compiler.compile()

    def reload(self) -> PolicySnapshot:
        new_snapshot = self._compiler.compile()
        with self._lock:
            self._snapshot = new_snapshot
        return new_snapshot

    def get_snapshot(self) -> PolicySnapshot:
        with self._lock:
            return self._snapshot
