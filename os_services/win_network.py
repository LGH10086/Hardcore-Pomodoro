from __future__ import annotations

import subprocess
from pathlib import Path

from os_services.base import INetworkBlocker


class WindowsHostsNetworkBlocker(INetworkBlocker):
    """Block domains by maintaining a managed section in Windows hosts file."""

    START_MARKER = "# --- POMODORO BLOCK START ---"
    END_MARKER = "# --- POMODORO BLOCK END ---"

    def __init__(self, hosts_path: str | Path | None = None) -> None:
        self._hosts_path = Path(hosts_path or r"C:\Windows\System32\drivers\etc\hosts")

    def block_domains(self, domains: list[str]) -> bool:
        content = self._read_hosts()
        cleaned = self._remove_managed_block(content)
        block_section = self._build_block_section(domains)
        merged = f"{cleaned.rstrip()}\n\n{block_section}\n"
        self._write_hosts(merged)
        self._flush_dns()
        return True

    def unblock_all(self) -> bool:
        content = self._read_hosts()
        cleaned = self._remove_managed_block(content)
        self._write_hosts(f"{cleaned.rstrip()}\n")
        self._flush_dns()
        return True

    def _build_block_section(self, domains: list[str]) -> str:
        safe_domains = sorted({d.strip().lower() for d in domains if d.strip()})
        lines = [self.START_MARKER]
        for domain in safe_domains:
            lines.append(f"127.0.0.1 {domain}")
            lines.append(f"127.0.0.1 www.{domain}")
        lines.append(self.END_MARKER)
        return "\n".join(lines)

    def _remove_managed_block(self, content: str) -> str:
        start = content.find(self.START_MARKER)
        end = content.find(self.END_MARKER)
        if start == -1 or end == -1:
            return content
        end += len(self.END_MARKER)
        if end < len(content) and content[end] == "\n":
            end += 1
        return content[:start] + content[end:]

    def _read_hosts(self) -> str:
        return self._hosts_path.read_text(encoding="utf-8", errors="ignore")

    def _write_hosts(self, value: str) -> None:
        self._hosts_path.write_text(value, encoding="utf-8")

    @staticmethod
    def _flush_dns() -> None:
        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["ipconfig", "/flushdns"],
            check=False,
            creationflags=creation_flags,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
