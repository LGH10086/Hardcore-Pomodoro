from __future__ import annotations

from abc import ABC, abstractmethod


class OSInteractError(RuntimeError):
    """Raised when low-level OS interaction fails."""


class IProcessMonitor(ABC):
    @abstractmethod
    def get_foreground_process_name(self) -> str:
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
