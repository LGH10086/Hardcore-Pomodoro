from __future__ import annotations

from os_services.base import INetworkBlocker


class HybridNetworkBlocker(INetworkBlocker):
    """Use DNS blocking as primary strategy, fallback to hosts on failure."""

    def __init__(self, dns_blocker: INetworkBlocker, hosts_blocker: INetworkBlocker) -> None:
        self._dns_blocker = dns_blocker
        self._hosts_blocker = hosts_blocker
        self._using_hosts_fallback = False

    def block_domains(self, domains: list[str]) -> bool:
        self._using_hosts_fallback = False
        if self._dns_blocker.block_domains(domains):
            return True

        self._using_hosts_fallback = True
        return self._hosts_blocker.block_domains(domains)

    def unblock_all(self) -> bool:
        dns_ok = self._dns_blocker.unblock_all()
        hosts_ok = self._hosts_blocker.unblock_all()
        self._using_hosts_fallback = False
        return dns_ok or hosts_ok
