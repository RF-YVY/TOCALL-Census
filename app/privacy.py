from __future__ import annotations

import hashlib
import re


APRS_ADDRESS_RE = re.compile(r"\b[A-Z0-9]{1,6}(?:-\d{1,2})?\b", re.IGNORECASE)
MASKED_STATION_RE = re.compile(r"^STN-[0-9A-F]{8}$")
GENERIC_PATH_ALIASES = {
    "APRS",
    "BEACON",
    "GPS",
    "NOGATE",
    "RFONLY",
    "TCPIP",
    "TCPXX",
    "WIDE1-1",
    "WIDE2-1",
    "WIDE2-2",
    "WIDE3-3",
}
APRS_IS_Q_CONSTRUCTS = {"QAC", "QAO", "QAR", "QAS", "QAU", "QAX", "QAZ"}


def masked_station(value: str) -> str:
    """Return a deterministic anonymous station label with no callsign or SSID."""
    cleaned = value.strip().upper().rstrip("*")
    if not cleaned:
        return ""
    if MASKED_STATION_RE.fullmatch(cleaned):
        return cleaned
    digest = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()[:8].upper()
    return f"STN-{digest}"


def mask_path(path: str) -> str:
    if not path:
        return ""
    return ",".join(mask_path_part(part) for part in path.split(","))


def mask_raw_packet(raw: str, *, source: str, tocall: str, path: str) -> str:
    if not raw:
        return ""
    marker = f"{source}>{tocall}"
    if raw.upper().startswith(marker.upper()):
        replacement = f"{masked_station(source)}>{tocall}"
        if path:
            replacement += f",{mask_path(path)}"
        _, _, body = raw.partition(":")
        return f"{replacement}:{body}" if ":" in raw else replacement
    return APRS_ADDRESS_RE.sub(lambda match: mask_path_part(match.group(0)), raw)


def mask_path_part(value: str) -> str:
    suffix = "*" if value.endswith("*") else ""
    cleaned = value.strip().upper().rstrip("*")
    if not cleaned:
        return value
    if cleaned in GENERIC_PATH_ALIASES or cleaned in APRS_IS_Q_CONSTRUCTS or cleaned.startswith(("WIDE", "TRACE")):
        return cleaned + suffix
    if APRS_ADDRESS_RE.fullmatch(cleaned):
        return masked_station(cleaned) + suffix
    return value
