from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessRule:
    name: str
    path: str = ""
    require_signature: bool = False
    is_active: bool = True


@dataclass(frozen=True)
class NetworkRule:
    domain: str
    start_time: str = "00:00"
    end_time: str = "23:59"
    is_active: bool = True


@dataclass(frozen=True)
class PolicySnapshot:
    process_rules: tuple[ProcessRule, ...]
    network_rules: tuple[NetworkRule, ...]
