from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal


class PomodoroTimer(QObject):
    tick = Signal(int, str)
    session_completed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_timeout)
        self._seconds_left = 0
        self._phase = "INIT"

    def start_focus(self, minutes: int) -> None:
        self._start(minutes, "FOCUS")

    def start_break(self, minutes: int) -> None:
        self._start(minutes, "BREAK")

    def stop(self) -> None:
        self._timer.stop()
        self._seconds_left = 0
        self._phase = "INIT"
        self.tick.emit(0, self._phase)

    def _start(self, minutes: int, phase: str) -> None:
        self._phase = phase
        self._seconds_left = max(1, int(minutes) * 60)
        self.tick.emit(self._seconds_left, self._phase)
        self._timer.start()

    def _on_timeout(self) -> None:
        self._seconds_left -= 1
        self.tick.emit(max(0, self._seconds_left), self._phase)
        if self._seconds_left <= 0:
            completed_phase = self._phase
            self._timer.stop()
            self.session_completed.emit(completed_phase)
