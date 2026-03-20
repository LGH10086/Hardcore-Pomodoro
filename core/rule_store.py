from __future__ import annotations

import sqlite3
from pathlib import Path

from core.models import NetworkRule, ProcessRule


class RuleStore:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS process_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile TEXT NOT NULL,
                    name TEXT NOT NULL,
                    path TEXT NOT NULL DEFAULT '',
                    require_signature INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS network_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1
                )
                """
            )

    def is_empty(self, profile: str = "default") -> bool:
        with self._connect() as conn:
            process_count = conn.execute(
                "SELECT COUNT(1) AS c FROM process_rules WHERE profile = ?", (profile,)
            ).fetchone()["c"]
            network_count = conn.execute(
                "SELECT COUNT(1) AS c FROM network_rules WHERE profile = ?", (profile,)
            ).fetchone()["c"]
        return int(process_count) == 0 and int(network_count) == 0

    def replace_process_rules(self, rules: list[ProcessRule], profile: str = "default") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM process_rules WHERE profile = ?", (profile,))
            conn.executemany(
                """
                INSERT INTO process_rules (profile, name, path, require_signature, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        profile,
                        rule.name.strip().lower(),
                        str(rule.path).strip(),
                        1 if rule.require_signature else 0,
                        1 if rule.is_active else 0,
                    )
                    for rule in rules
                    if rule.name.strip()
                ],
            )

    def replace_network_rules(self, rules: list[NetworkRule], profile: str = "default") -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM network_rules WHERE profile = ?", (profile,))
            conn.executemany(
                """
                INSERT INTO network_rules (profile, domain, start_time, end_time, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        profile,
                        rule.domain.strip().lower(),
                        rule.start_time.strip(),
                        rule.end_time.strip(),
                        1 if rule.is_active else 0,
                    )
                    for rule in rules
                    if rule.domain.strip()
                ],
            )

    def get_process_rules(self, profile: str = "default") -> list[ProcessRule]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name, path, require_signature, is_active
                FROM process_rules
                WHERE profile = ?
                ORDER BY id ASC
                """,
                (profile,),
            ).fetchall()

        return [
            ProcessRule(
                name=str(row["name"]).strip().lower(),
                path=str(row["path"] or "").strip(),
                require_signature=bool(row["require_signature"]),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def get_network_rules(self, profile: str = "default") -> list[NetworkRule]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT domain, start_time, end_time, is_active
                FROM network_rules
                WHERE profile = ?
                ORDER BY id ASC
                """,
                (profile,),
            ).fetchall()

        return [
            NetworkRule(
                domain=str(row["domain"]).strip().lower(),
                start_time=str(row["start_time"]).strip(),
                end_time=str(row["end_time"]).strip(),
                is_active=bool(row["is_active"]),
            )
            for row in rows
        ]

    def bootstrap_from_legacy(
        self,
        process_whitelist: list[str],
        network_blacklist: list[dict],
        profile: str = "default",
    ) -> None:
        if not self.is_empty(profile=profile):
            return

        process_rules = [ProcessRule(name=str(name).strip().lower()) for name in process_whitelist if str(name).strip()]
        network_rules = [
            NetworkRule(
                domain=str(item.get("domain", "")).strip().lower(),
                start_time=str(item.get("start_time", "00:00")).strip(),
                end_time=str(item.get("end_time", "23:59")).strip(),
                is_active=bool(item.get("is_active", True)),
            )
            for item in network_blacklist
            if str(item.get("domain", "")).strip()
        ]

        self.replace_process_rules(process_rules, profile=profile)
        self.replace_network_rules(network_rules, profile=profile)
