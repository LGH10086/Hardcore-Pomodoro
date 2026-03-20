from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class OSInteractError(RuntimeError):
    """Raised when low-level OS interaction fails."""


@dataclass(frozen=True)
class ForegroundProcessInfo:
    pid: int
    name: str
    exe_path: str


class IProcessMonitor(ABC):
    @abstractmethod
    def get_foreground_process_name(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def get_foreground_process_info(self) -> ForegroundProcessInfo:
        raise NotImplementedError

    @abstractmethod
    def force_bring_to_front(self, window_title: str) -> bool:
        raise NotImplementedError


class INetworkBlocker(ABC):
    @abstractmethod
    def block_domains(self, domains: list[str]) -> bool:
        raise NotImplementedError

    @abstractmethod
    def unblock_all(self) -> bool:
        raise NotImplementedError
