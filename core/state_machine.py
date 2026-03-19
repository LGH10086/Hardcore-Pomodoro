from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal


class PomodoroState(str, Enum):
    INIT = "INIT"
    FOCUS = "FOCUS"
    BREAK = "BREAK"


class StateMachine(QObject):
    state_changed = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._state = PomodoroState.INIT

    @property
    def state(self) -> PomodoroState:
        return self._state

    def to_init(self) -> None:
        self._transition(PomodoroState.INIT)

    def to_focus(self) -> None:
        self._transition(PomodoroState.FOCUS)

    def to_break(self) -> None:
        self._transition(PomodoroState.BREAK)

    def _transition(self, new_state: PomodoroState) -> None:
        if self._state == new_state:
            return
        self._state = new_state
        self.state_changed.emit(new_state.value)
