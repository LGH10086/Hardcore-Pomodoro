from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
    "timing": {
        "work_duration_minutes": 25,
        "break_duration_minutes": 5,
        "focus_rounds": 4,
    },
    "ui_customization": {
        "background_image_path": "",
        "motto": "Stay focused, stay foolish.",
    },
    "process_whitelist": ["code.exe", "pycharm64.exe", "chrome.exe"],
    "network_blacklist": [
        {
            "domain": "bilibili.com",
            "start_time": "08:00",
            "end_time": "11:30",
            "is_active": True,
        }
    ],
}


class ConfigManager:
    """Load and persist application settings in a JSON file."""

    def __init__(self, config_path: str | Path) -> None:
        self._path = Path(config_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._config: dict[str, Any] = {}
        self._load_or_init()

    def _load_or_init(self) -> None:
        if not self._path.exists():
            self._config = copy.deepcopy(DEFAULT_CONFIG)
            self.save()
            return

        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = copy.deepcopy(DEFAULT_CONFIG)

        self._config = self._merge_defaults(data)
        self.save()

    def _merge_defaults(self, data: dict[str, Any]) -> dict[str, Any]:
        merged = copy.deepcopy(DEFAULT_CONFIG)
        for key in ("timing", "ui_customization"):
            if isinstance(data.get(key), dict):
                merged[key].update(data[key])

        if isinstance(data.get("process_whitelist"), list):
            merged["process_whitelist"] = [str(item).lower() for item in data["process_whitelist"]]

        if isinstance(data.get("network_blacklist"), list):
            safe_items: list[dict[str, Any]] = []
            for rule in data["network_blacklist"]:
                if not isinstance(rule, dict):
                    continue
                safe_items.append(
                    {
                        "domain": str(rule.get("domain", "")).strip(),
                        "start_time": str(rule.get("start_time", "08:00")).strip(),
                        "end_time": str(rule.get("end_time", "23:59")).strip(),
                        "is_active": bool(rule.get("is_active", True)),
                    }
                )
            merged["network_blacklist"] = safe_items

        return merged

    def get_all(self) -> dict[str, Any]:
        return copy.deepcopy(self._config)

    def get_timing(self) -> dict[str, int]:
        return {
            "work_duration_minutes": int(self._config["timing"]["work_duration_minutes"]),
            "break_duration_minutes": int(self._config["timing"]["break_duration_minutes"]),
            "focus_rounds": int(self._config["timing"].get("focus_rounds", 4)),
        }

    def get_ui_customization(self) -> dict[str, str]:
        return {
            "background_image_path": str(self._config["ui_customization"].get("background_image_path", "")),
            "motto": str(self._config["ui_customization"].get("motto", "")),
        }

    def get_process_whitelist(self) -> list[str]:
        return [str(p).lower() for p in self._config.get("process_whitelist", [])]

    def get_network_blacklist(self) -> list[dict[str, Any]]:
        return [dict(rule) for rule in self._config.get("network_blacklist", [])]

    def update(
        self,
        *,
        timing: dict[str, Any],
        ui_customization: dict[str, Any],
        process_whitelist: list[str],
        network_blacklist: list[dict[str, Any]],
    ) -> None:
        self._config = self._merge_defaults(
            {
                "timing": timing,
                "ui_customization": ui_customization,
                "process_whitelist": process_whitelist,
                "network_blacklist": network_blacklist,
            }
        )
        self.save()

    def save(self) -> None:
        self._path.write_text(
            json.dumps(self._config, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
