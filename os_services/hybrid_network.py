from __future__ import annotations

from os_services.base import INetworkBlocker


class HybridNetworkBlocker(INetworkBlocker):
    """Apply hosts block and DNS block together for stronger browser compatibility."""

    def __init__(self, dns_blocker: INetworkBlocker, hosts_blocker: INetworkBlocker) -> None:
        self._dns_blocker = dns_blocker
        self._hosts_blocker = hosts_blocker
        self._using_hosts_fallback = False

    def block_domains(self, domains: list[str]) -> bool:
        dns_ok = False
        hosts_ok = False

        try:
            dns_ok = self._dns_blocker.block_domains(domains)
        except Exception:
            dns_ok = False

        try:
            hosts_ok = self._hosts_blocker.block_domains(domains)
        except Exception:
            hosts_ok = False

        self._using_hosts_fallback = hosts_ok and not dns_ok
        return dns_ok or hosts_ok

    def unblock_all(self) -> bool:
        dns_ok = self._dns_blocker.unblock_all()
        hosts_ok = self._hosts_blocker.unblock_all()
        self._using_hosts_fallback = False
        return dns_ok or hosts_ok
