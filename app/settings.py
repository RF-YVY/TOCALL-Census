from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.paths import data_dir


DEFAULT_SETTINGS: dict[str, str | int | bool] = {
    "server": "rotate.aprs2.net",
    "port": 14580,
    "callsign": "N0CALL",
    "passcode": "-1",
    "filter": "r/0/0/9999",
    "target_tocall": "",
    "auto_connect": False,
    "retention_days": 0,
    "max_packets": 0,
}

SETTINGS_PATH = data_dir() / "settings.json"


class AppSettings:
    def __init__(self, path: Path = SETTINGS_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.values = DEFAULT_SETTINGS.copy()
        self.load()

    def load(self) -> dict[str, str | int | bool]:
        if not self.path.exists():
            return self.values
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return self.values
        if isinstance(payload, dict):
            for key in DEFAULT_SETTINGS:
                if key in payload:
                    self.values[key] = payload[key]
        return self.values

    def update(self, values: dict[str, Any]) -> dict[str, str | int | bool]:
        for key in DEFAULT_SETTINGS:
            if key in values and values[key] is not None:
                self.values[key] = values[key]
        self.save()
        return self.values

    def save(self) -> None:
        self.path.write_text(json.dumps(self.values, indent=2), encoding="utf-8")

    def public(self) -> dict[str, str | int | bool]:
        return {
            **self.values,
            "passcode": "masked" if self.values.get("passcode") else "",
        }
