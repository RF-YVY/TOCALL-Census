from __future__ import annotations

import asyncio
import contextlib
import re
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime


PACKET_RE = re.compile(r"^(?P<source>[^>:\s]+)>(?P<header>[^:]+):(?P<body>.*)$")
POSITION_RE = re.compile(
    r"(?P<lat_deg>\d{2})(?P<lat_min>\d{2}\.\d{2})(?P<lat_hemi>[NS])"
    r"(?P<symbol_table>.).?"
    r"(?P<lon_deg>\d{3})(?P<lon_min>\d{2}\.\d{2})(?P<lon_hemi>[EW])"
)


@dataclass(slots=True)
class ParsedPacket:
    raw: str
    source: str
    tocall: str
    path: str
    body: str
    heard_at: datetime
    lat: float | None = None
    lon: float | None = None
    transport: str = "unknown"


def parse_packet(raw: str) -> ParsedPacket | None:
    """Extract APRS header fields from a raw APRS-IS line."""
    line = raw.strip()
    if not line or line.startswith("#"):
        return None

    match = PACKET_RE.match(line)
    if not match:
        return None

    header = match.group("header")
    if "," in header:
        tocall, path = header.split(",", 1)
    else:
        tocall, path = header, ""

    body = match.group("body")
    lat, lon = extract_position(body)
    return ParsedPacket(
        raw=line,
        source=match.group("source"),
        tocall=tocall.strip().upper(),
        path=path.strip(),
        body=body,
        heard_at=datetime.now(UTC),
        lat=lat,
        lon=lon,
        transport=classify_transport(path),
    )


def extract_position(body: str) -> tuple[float | None, float | None]:
    """Parse common uncompressed APRS latitude/longitude payloads."""
    if not body or body[0] not in ("!", "=", "/", "@"):
        return None, None

    search_area = body[1:40]
    match = POSITION_RE.search(search_area)
    if not match:
        return None, None

    lat = int(match.group("lat_deg")) + float(match.group("lat_min")) / 60
    lon = int(match.group("lon_deg")) + float(match.group("lon_min")) / 60

    if match.group("lat_hemi") == "S":
        lat *= -1
    if match.group("lon_hemi") == "W":
        lon *= -1

    return round(lat, 6), round(lon, 6)


def classify_transport(path: str) -> str:
    path_upper = path.upper()
    parts = {part.strip("*") for part in path_upper.split(",") if part}
    if {"QAR", "QAO", "QAS"} & parts:
        return "rf_igate"
    if {"QAC", "TCPIP", "TCPXX"} & parts:
        return "aprs_is"
    if "WIDE" in path_upper or "TRACE" in path_upper:
        return "rf_path"
    return "unknown"


PacketCallback = Callable[[ParsedPacket], Awaitable[None]]
StatusCallback = Callable[[str, str], Awaitable[None]]
RECONNECT_DELAY_SECONDS = 1
INITIAL_RETRY_DELAY_SECONDS = 2
MAX_RETRY_DELAY_SECONDS = 30
READ_TIMEOUT_SECONDS = 90


class LoginRejectedError(RuntimeError):
    pass


class AprsIsConnectionDropped(RuntimeError):
    pass


def server_comment_status(comment: str) -> tuple[str, str]:
    cleaned = comment.lstrip("# ").strip()
    lowered = cleaned.lower()
    if "login" in lowered and "not allowed" in lowered:
        return (
            "rejected",
            "APRS-IS rejected the login. Open Advanced APRS-IS identity and use your callsign/passcode, "
            f"or try another server. Server said: {cleaned}",
        )
    if "verified" in lowered or "logresp" in lowered:
        return "running", f"APRS-IS login accepted. {cleaned}"
    return "server", cleaned


class AprsIsClient:
    def __init__(self, on_packet: PacketCallback, on_status: StatusCallback) -> None:
        self._on_packet = on_packet
        self._on_status = on_status
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()
        self.settings: dict[str, str | int] = {}
        self._passcode = ""
        self.started_at: datetime | None = None
        self.connected_at: datetime | None = None
        self.last_packet_at: datetime | None = None
        self.reconnect_count = 0
        self.last_reconnect_reason = ""

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(
        self,
        *,
        server: str,
        port: int,
        callsign: str,
        passcode: str,
        aprs_filter: str,
    ) -> None:
        await self.stop()
        self._stop_event = asyncio.Event()
        self._passcode = passcode
        self.started_at = datetime.now(UTC)
        self.connected_at = None
        self.last_packet_at = None
        self.reconnect_count = 0
        self.last_reconnect_reason = ""
        self.settings = {
            "server": server,
            "port": port,
            "callsign": callsign,
            "filter": aprs_filter,
        }
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self.running:
            return
        self._stop_event.set()
        assert self._task is not None
        self._task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self._task
        self.connected_at = None
        await self._on_status("stopped", "Disconnected from APRS-IS")

    async def _run(self) -> None:
        retry_delay = INITIAL_RETRY_DELAY_SECONDS
        while not self._stop_event.is_set():
            try:
                await self._connect_once()
                retry_delay = INITIAL_RETRY_DELAY_SECONDS
            except asyncio.CancelledError:
                raise
            except LoginRejectedError as exc:
                await self._on_status("rejected", str(exc))
                self._stop_event.set()
            except AprsIsConnectionDropped as exc:
                self.connected_at = None
                self.reconnect_count += 1
                self.last_reconnect_reason = str(exc)
                await self._on_status("reconnecting", f"{exc}; reconnecting")
                await asyncio.sleep(RECONNECT_DELAY_SECONDS)
                retry_delay = INITIAL_RETRY_DELAY_SECONDS
            except (OSError, TimeoutError, UnicodeDecodeError) as exc:
                self.connected_at = None
                self.last_reconnect_reason = f"{type(exc).__name__}: {exc}"
                await self._on_status("reconnecting", f"{type(exc).__name__}: {exc}; retrying in {retry_delay}s")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, MAX_RETRY_DELAY_SECONDS)

    async def _connect_once(self) -> None:
        server = str(self.settings["server"])
        port = int(self.settings["port"])
        callsign = str(self.settings["callsign"]).upper()
        passcode = self._passcode
        aprs_filter = str(self.settings.get("filter") or "")

        reader, writer = await asyncio.open_connection(
            server,
            port,
            family=socket.AF_UNSPEC,
        )
        self.connected_at = datetime.now(UTC)
        await self._on_status("connecting", f"Connected TCP to {server}:{port}")

        login = f"user {callsign} pass {passcode} vers TOCALL-Census 1.0"
        if aprs_filter:
            login += f" filter {aprs_filter}"
        writer.write((login + "\n").encode("ascii", errors="ignore"))
        await writer.drain()
        await self._on_status("running", f"Logged in as {callsign}")

        try:
            while not self._stop_event.is_set():
                try:
                    line = await asyncio.wait_for(reader.readline(), timeout=READ_TIMEOUT_SECONDS)
                except (OSError, TimeoutError, UnicodeDecodeError) as exc:
                    raise AprsIsConnectionDropped(f"APRS-IS connection dropped ({type(exc).__name__}: {exc})") from exc
                if not line:
                    raise AprsIsConnectionDropped("APRS-IS server closed the connection")
                text = line.decode("utf-8", errors="replace").strip()
                packet = parse_packet(text)
                if packet:
                    self.last_packet_at = packet.heard_at
                    await self._on_packet(packet)
                elif text.startswith("#"):
                    state, message = server_comment_status(text)
                    await self._on_status(state, message)
                    if state == "rejected":
                        raise LoginRejectedError(message)
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()
