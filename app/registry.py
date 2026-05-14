from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import httpx

from app.paths import data_dir


REGISTRY_URL = "https://aprs-deviceid.aprsfoundation.org/tocalls.pretty.json"
REGISTRY_MASTER_URL = "https://github.com/aprsorg/aprs-deviceid/blob/main/tocalls.yaml"
REGISTRY_WEB_URL = "https://aprsorg.github.io/aprs-deviceid-web/"
DATA_DIR = data_dir()
REGISTRY_CACHE = DATA_DIR / "tocalls.pretty.json"


class TocallRegistry:
    def __init__(self) -> None:
        self.entries: dict[str, str] = {}

    async def refresh(self) -> dict[str, str]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        headers = {"User-Agent": "TOCALL-Census/1.0 (+https://github.com/aprsorg/aprs-deviceid)"}
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=headers) as client:
            response = await client.get(REGISTRY_URL)
            response.raise_for_status()
            REGISTRY_CACHE.write_text(response.text, encoding="utf-8")
            self.entries = parse_registry_json(response.json())
        return self.entries

    def load_cached(self) -> dict[str, str]:
        if REGISTRY_CACHE.exists():
            self.entries = parse_registry_json(json.loads(REGISTRY_CACHE.read_text(encoding="utf-8")))
        return self.entries

    def lookup(self, tocall: str) -> str | None:
        key = tocall.upper()
        if key in self.entries:
            return self.entries[key]
        wildcard_matches = [
            (pattern, label)
            for pattern, label in self.entries.items()
            if has_wildcard(pattern) and tocall_pattern_matches(pattern, key)
        ]
        if wildcard_matches:
            pattern, label = max(wildcard_matches, key=lambda item: wildcard_specificity(item[0]))
            return label
        return None

    def search(self, query: str, limit: int = 25) -> list[dict[str, str]]:
        needle = query.strip().upper()
        if not needle:
            return []
        results: list[dict[str, str]] = []
        exact = self.lookup(needle)
        if exact:
            results.append({"tocall": needle, "label": exact, "match": "resolved"})

        for pattern, label in sorted(self.entries.items()):
            haystack = f"{pattern} {label}".upper()
            pattern_matches_query = has_wildcard(pattern) and tocall_pattern_matches(pattern, needle)
            if (needle in haystack or pattern_matches_query) and not any(row["tocall"] == pattern for row in results):
                results.append({"tocall": pattern, "label": label, "match": "registry"})
            if len(results) >= limit:
                break
        return results[:limit]


def has_wildcard(pattern: str) -> bool:
    return any(char in pattern for char in ("?", "*", "n"))


def wildcard_specificity(pattern: str) -> tuple[int, int]:
    literal_count = sum(1 for char in pattern if char not in ("?", "*", "n"))
    return literal_count, len(pattern)


def tocall_pattern_matches(pattern: str, tocall: str) -> bool:
    regex = []
    for char in pattern:
        if char == "?":
            regex.append(".")
        elif char == "n":
            regex.append(r"\d")
        elif char == "*":
            regex.append(".*")
        else:
            regex.append(re.escape(char.upper()))
    return re.fullmatch("".join(regex), tocall.upper()) is not None


def parse_registry_json(payload: Any) -> dict[str, str]:
    entries: dict[str, str] = {}
    walk_registry(payload, entries)
    return entries


def walk_registry(node: Any, entries: dict[str, str]) -> None:
    if isinstance(node, dict):
        key = first_string(node, ("tocall", "destination", "dst", "id", "prefix", "pattern", "key"))
        label = first_string(node, ("description", "name", "vendor", "model", "device", "software"))

        if key and label and looks_like_tocall(key):
            entries[key.upper()] = label

        if "tocalls" in node and isinstance(node["tocalls"], dict):
            for tocall, value in node["tocalls"].items():
                label = stringify_registry_value(value)
                if looks_like_tocall(tocall) and label:
                    entries[tocall.upper()] = label

        for value in node.values():
            walk_registry(value, entries)
    elif isinstance(node, list):
        for item in node:
            walk_registry(item, entries)


def first_string(node: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = node.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def stringify_registry_value(value: Any) -> str | None:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        parts = [
            str(value[key]).strip()
            for key in ("vendor", "model", "name", "description", "software")
            if value.get(key)
        ]
        return " ".join(parts) if parts else None
    return None


def looks_like_tocall(value: str) -> bool:
    clean = value.replace("*", "").replace("?", "").replace("n", "")
    return 2 <= len(clean) <= 9 and clean.isalnum()
