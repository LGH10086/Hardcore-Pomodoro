from __future__ import annotations

import json
import subprocess

from os_services.base import INetworkBlocker


class WindowsDnsNetworkBlocker(INetworkBlocker):
    """Primary DNS blocker on Windows with runtime backup/restore."""

    def __init__(self) -> None:
        self._dns_backup: dict[str, list[str]] = {}
        self._is_dns_blocking = False

    def block_domains(self, domains: list[str]) -> bool:  # noqa: ARG002
        adapters = self._get_active_adapters()
        if not adapters:
            return False

        backup = self._capture_dns_backup(adapters)
        changed: list[str] = []

        try:
            for alias in adapters:
                command = (
                    "Set-DnsClientServerAddress -InterfaceAlias '"
                    + alias.replace("'", "''")
                    + "' -ServerAddresses @('127.0.0.1')"
                )
                self._run_powershell(command)
                changed.append(alias)
        except Exception:
            self._restore_dns_for_aliases(backup, changed)
            return False

        self._dns_backup = backup
        self._is_dns_blocking = True
        self._flush_dns()
        return True

    def unblock_all(self) -> bool:
        restored = False
        if self._dns_backup:
            try:
                self._restore_dns_for_aliases(self._dns_backup, list(self._dns_backup.keys()))
                restored = True
            except Exception:
                restored = False
        elif self._is_dns_blocking:
            # Safety fallback if backup is unexpectedly empty.
            try:
                for alias in self._get_active_adapters():
                    command = (
                        "Set-DnsClientServerAddress -InterfaceAlias '"
                        + alias.replace("'", "''")
                        + "' -ResetServerAddresses"
                    )
                    self._run_powershell(command)
                restored = True
            except Exception:
                restored = False

        self._dns_backup = {}
        self._is_dns_blocking = False
        if restored:
            self._flush_dns()
        return restored

    def _capture_dns_backup(self, adapters: list[str]) -> dict[str, list[str]]:
        backup: dict[str, list[str]] = {}
        for alias in adapters:
            command = (
                "(Get-DnsClientServerAddress -InterfaceAlias '"
                + alias.replace("'", "''")
                + "' -AddressFamily IPv4).ServerAddresses | ConvertTo-Json"
            )
            raw = self._run_powershell(command)
            addresses: list[str] = []
            if raw.strip():
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    addresses = [str(item).strip() for item in parsed if str(item).strip()]
                elif isinstance(parsed, str) and parsed.strip():
                    addresses = [parsed.strip()]
            backup[alias] = addresses
        return backup

    def _restore_dns_for_aliases(self, backup: dict[str, list[str]], aliases: list[str]) -> None:
        for alias in aliases:
            addresses = backup.get(alias, [])
            if addresses:
                escaped = ",".join(["'" + value.replace("'", "''") + "'" for value in addresses])
                command = (
                    "Set-DnsClientServerAddress -InterfaceAlias '"
                    + alias.replace("'", "''")
                    + "' -ServerAddresses @(" + escaped + ")"
                )
            else:
                command = (
                    "Set-DnsClientServerAddress -InterfaceAlias '"
                    + alias.replace("'", "''")
                    + "' -ResetServerAddresses"
                )
            self._run_powershell(command)

    def _get_active_adapters(self) -> list[str]:
        command = "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty InterfaceAlias"
        raw = self._run_powershell(command)
        return [line.strip() for line in raw.splitlines() if line.strip()]

    @staticmethod
    def _run_powershell(script: str) -> str:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=8,
            check=False,
            creationflags=creation_flags,
        )
        if result.returncode != 0:
            error = result.stderr.strip() or result.stdout.strip() or "Unknown PowerShell error"
            raise RuntimeError(error)
        return result.stdout.strip()

    @staticmethod
    def _flush_dns() -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["ipconfig", "/flushdns"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            creationflags=creation_flags,
        )
