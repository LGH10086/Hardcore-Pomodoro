from __future__ import annotations

from core.models import PolicySnapshot
from core.rule_store import RuleStore


class StrategyCompiler:
    def __init__(self, rule_store: RuleStore, profile: str = "default") -> None:
        self._store = rule_store
        self._profile = profile

    def compile(self) -> PolicySnapshot:
        process_rules = tuple(self._store.get_process_rules(profile=self._profile))
        network_rules = tuple(self._store.get_network_rules(profile=self._profile))
        return PolicySnapshot(process_rules=process_rules, network_rules=network_rules)
