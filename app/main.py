from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.aprs import AprsIsClient, ParsedPacket
from app.geography import country, us_state
from app.paths import static_dir
from app.pdf_report import build_pdf_report
from app.privacy import mask_path, mask_raw_packet, masked_station
from app.registry import REGISTRY_MASTER_URL, REGISTRY_WEB_URL, TocallRegistry
from app.settings import AppSettings
from app.store import PacketStore


STATIC_DIR = static_dir()
APP_NAME = "TOCALL Census"
APP_VERSION = "v1.0.1"
APP_STARTED_AT = datetime.now(UTC)
GITHUB_REPO = "RF-YVY/TOCALL-Census"
GITHUB_REPO_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_RELEASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_TAGS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/tags"


@asynccontextmanager
async def lifespan(_: FastAPI):
    registry.load_cached()
    if not registry.entries:
        try:
            await registry.refresh()
        except Exception as exc:  # noqa: BLE001
            status.update({"state": "warning", "message": f"Registry refresh failed: {exc}"})
    if app_settings.values.get("auto_connect"):
        await client.start(
            server=str(app_settings.values.get("server") or "rotate.aprs2.net"),
            port=int(app_settings.values.get("port") or 14580),
            callsign=str(app_settings.values.get("callsign") or "N0CALL"),
            passcode=str(app_settings.values.get("passcode") or "-1"),
            aprs_filter=str(app_settings.values.get("filter") or ""),
        )
    yield
    await client.stop()


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

store = PacketStore()
registry = TocallRegistry()
app_settings = AppSettings()
target_tocall: str | None = str(app_settings.values.get("target_tocall") or "").upper() or None
status: dict[str, Any] = {"state": "stopped", "message": "Ready"}
clients: set[WebSocket] = set()


class ConnectRequest(BaseModel):
    server: str = Field(default="rotate.aprs2.net", min_length=1)
    port: int = Field(default=14580, ge=1, le=65535)
    callsign: str = Field(default="N0CALL", min_length=1, max_length=12)
    passcode: str = Field(default="-1", min_length=1)
    aprs_filter: str = Field(default="r/0/0/9999", max_length=200)
    target_tocall: str = Field(default="", max_length=12)
    auto_connect: bool = False
    retention_days: int = Field(default=0, ge=0, le=3650)
    max_packets: int = Field(default=0, ge=0, le=1_000_000)


async def on_packet(packet: ParsedPacket) -> None:
    store.add_packet(packet)
    store.prune(
        retention_days=int(app_settings.values.get("retention_days") or 0),
        max_packets=int(app_settings.values.get("max_packets") or 0),
    )
    if target_tocall and packet.tocall != target_tocall:
        return
    await broadcast({"type": "packet", "packet": packet_to_event(packet)})
    await broadcast({"type": "summary", "summary": store.summary(registry, target_tocall)})


async def on_status(state: str, message: str) -> None:
    status.update({"state": state, "message": message})
    await broadcast({"type": "status", "status": status_payload()})


client = AprsIsClient(on_packet=on_packet, on_status=on_status)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.ico")
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "icons" / "favicon.ico")


@app.get("/site.webmanifest")
async def webmanifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "icons" / "site.webmanifest", media_type="application/manifest+json")


@app.post("/api/connect")
async def connect(request: ConnectRequest) -> dict[str, Any]:
    global target_tocall
    target_tocall = request.target_tocall.strip().upper() or None
    passcode = saved_passcode_if_masked(request.passcode)
    app_settings.update(
        {
            "server": request.server.strip(),
            "port": request.port,
            "callsign": request.callsign.strip().upper(),
            "passcode": passcode,
            "filter": request.aprs_filter.strip(),
            "target_tocall": target_tocall or "",
            "auto_connect": request.auto_connect,
            "retention_days": request.retention_days,
            "max_packets": request.max_packets,
        }
    )
    await client.start(
        server=request.server.strip(),
        port=request.port,
        callsign=request.callsign.strip().upper(),
        passcode=passcode,
        aprs_filter=request.aprs_filter.strip(),
    )
    return {"ok": True, "status": status_payload()}


@app.post("/api/settings")
async def update_settings(request: ConnectRequest) -> dict[str, Any]:
    global target_tocall
    target_tocall = request.target_tocall.strip().upper() or None
    passcode = saved_passcode_if_masked(request.passcode)
    app_settings.update(
        {
            "server": request.server.strip(),
            "port": request.port,
            "callsign": request.callsign.strip().upper(),
            "passcode": passcode,
            "filter": request.aprs_filter.strip(),
            "target_tocall": target_tocall or "",
            "auto_connect": request.auto_connect,
            "retention_days": request.retention_days,
            "max_packets": request.max_packets,
        }
    )
    removed = store.prune(retention_days=request.retention_days, max_packets=request.max_packets)
    payload = snapshot_payload()
    await broadcast({"type": "snapshot", **payload})
    return {"ok": True, "removed": removed, **payload}


@app.post("/api/disconnect")
async def disconnect() -> dict[str, Any]:
    await client.stop()
    return {"ok": True, "status": status_payload()}


@app.post("/api/registry/refresh")
async def refresh_registry() -> dict[str, Any]:
    try:
        entries = await registry.refresh()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    await broadcast({"type": "registry", "count": len(entries)})
    return {"ok": True, "count": len(entries)}


@app.get("/api/registry/search")
async def search_registry(q: str = "") -> dict[str, Any]:
    return {
        "query": q,
        "count": len(registry.entries),
        "results": registry.search(q),
        "master_url": REGISTRY_MASTER_URL,
        "web_url": REGISTRY_WEB_URL,
    }


@app.post("/api/clear")
async def clear_session() -> dict[str, Any]:
    await client.stop()
    store.clear()
    status.update({"state": "cleared", "message": "Session cleared"})
    payload = snapshot_payload()
    await broadcast({"type": "cleared", **payload})
    return {"ok": True, **payload}


@app.get("/api/summary")
async def summary() -> dict[str, Any]:
    return snapshot_payload()


@app.get("/api/counts")
async def counts() -> dict[str, int]:
    return store.export_counts()


@app.get("/api/export/json")
async def export_json() -> JSONResponse:
    return JSONResponse(
        content={
            "generated_at": datetime.now(UTC).isoformat(),
            "app": APP_NAME,
            "version": APP_VERSION,
            **store.report(registry, target_tocall),
        },
        headers={"Content-Disposition": f'attachment; filename="{report_filename("json")}"'},
    )


@app.get("/api/export/csv")
async def export_csv() -> Response:
    return Response(
        content=store.report_csv(registry, target_tocall),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{report_filename("csv")}"'},
    )


@app.get("/api/export/pdf")
async def export_pdf() -> Response:
    return Response(
        content=build_pdf_report(store.report(registry, target_tocall), APP_NAME, APP_VERSION),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{report_filename("pdf")}"'},
    )


@app.get("/api/version")
async def version() -> dict[str, Any]:
    latest = await fetch_latest_version()
    return {
        "app": APP_NAME,
        "current_version": APP_VERSION,
        "latest_version": latest.get("version"),
        "update_available": is_newer_version(str(latest.get("version") or ""), APP_VERSION),
        "source": latest.get("source"),
        "release_url": latest.get("url") or GITHUB_REPO_URL,
        "checked_repo": GITHUB_REPO,
        "message": latest.get("message"),
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    clients.add(websocket)
    try:
        await websocket.send_json(
            {"type": "snapshot", **snapshot_payload()}
        )
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, ConnectionResetError, RuntimeError):
        pass
    finally:
        clients.discard(websocket)
        await broadcast({"type": "health", "health": health_payload()})


async def broadcast(payload: dict[str, Any]) -> None:
    if not clients:
        return
    dead: list[WebSocket] = []
    for websocket in clients:
        try:
            await websocket.send_json(payload)
        except (ConnectionResetError, RuntimeError, WebSocketDisconnect):
            dead.append(websocket)
    for websocket in dead:
        clients.discard(websocket)


def packet_to_event(packet: ParsedPacket) -> dict[str, Any]:
    state_name = None
    country_name = None
    if packet.lat is not None and packet.lon is not None:
        state_name = us_state(packet.lat, packet.lon)
        country_name = "United States" if state_name else country(packet.lat, packet.lon)

    return {
        "heard_at": packet.heard_at.isoformat(),
        "source": masked_station(packet.source),
        "tocall": packet.tocall,
        "label": registry.lookup(packet.tocall) or "Unknown",
        "path": mask_path(packet.path),
        "raw": mask_raw_packet(packet.raw, source=packet.source, tocall=packet.tocall, path=packet.path),
        "lat": packet.lat,
        "lon": packet.lon,
        "us_state": state_name,
        "country": country_name,
        "transport": packet.transport,
    }


def status_payload() -> dict[str, Any]:
    return {
        **status,
        "running": client.running,
        "settings": public_settings(),
        "health": health_payload(),
    }


def snapshot_payload() -> dict[str, Any]:
    return {
        "status": status_payload(),
        "summary": store.summary(registry, target_tocall),
        "map_points": store.map_points(registry, target_tocall),
        "target_tocall": target_tocall,
        "registry_count": len(registry.entries),
        "settings": app_settings.public(),
        "health": health_payload(),
        "registry_links": {
            "master": REGISTRY_MASTER_URL,
            "web": REGISTRY_WEB_URL,
        },
    }


def report_filename(extension: str) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    target = target_tocall or "all"
    if extension == "pdf":
        return f"{safe_filename_part(target.upper())}-{stamp}.pdf"
    return f"tocall-census-{target.lower()}-{stamp}.{extension}"


def safe_filename_part(value: str) -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in {"-", "_"})
    return cleaned or "ALL"


def saved_passcode_if_masked(value: str) -> str:
    cleaned = value.strip()
    if cleaned == "masked":
        return str(app_settings.values.get("passcode") or "")
    return cleaned


def public_settings() -> dict[str, str | int | bool]:
    return {
        "server": client.settings.get("server", ""),
        "port": client.settings.get("port", ""),
        "callsign": client.settings.get("callsign", ""),
        "filter": client.settings.get("filter", ""),
        "passcode": "masked" if client.settings else "",
        "auto_connect": bool(app_settings.values.get("auto_connect")),
        "retention_days": int(app_settings.values.get("retention_days") or 0),
        "max_packets": int(app_settings.values.get("max_packets") or 0),
    }


def health_payload() -> dict[str, Any]:
    now = datetime.now(UTC)
    uptime_seconds = int((now - APP_STARTED_AT).total_seconds())
    connected_seconds = int((now - client.connected_at).total_seconds()) if client.connected_at else 0
    return {
        "app_uptime_seconds": uptime_seconds,
        "aprs_connected_seconds": connected_seconds,
        "last_packet_at": client.last_packet_at.isoformat() if client.last_packet_at else None,
        "reconnect_count": client.reconnect_count,
        "last_reconnect_reason": client.last_reconnect_reason,
        "web_clients": len(clients),
    }


async def fetch_latest_version() -> dict[str, str | None]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": f"{APP_NAME}/{APP_VERSION}",
    }
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=headers) as http:
        release_response = await http.get(GITHUB_RELEASE_URL)
        if release_response.status_code == 200:
            release = release_response.json()
            return {
                "version": normalize_version(release.get("tag_name") or release.get("name") or ""),
                "url": release.get("html_url") or GITHUB_REPO_URL,
                "source": "latest release",
                "message": None,
            }
        if release_response.status_code not in {404, 403}:
            release_response.raise_for_status()

        tags_response = await http.get(GITHUB_TAGS_URL)
        if tags_response.status_code == 200:
            tags = tags_response.json()
            if tags:
                first_tag = tags[0]
                return {
                    "version": normalize_version(first_tag.get("name") or ""),
                    "url": GITHUB_REPO_URL,
                    "source": "latest tag",
                    "message": "No GitHub release was found, so the latest tag was used.",
                }
            return {
                "version": None,
                "url": GITHUB_REPO_URL,
                "source": "repository",
                "message": "No releases or tags were found in the GitHub repository.",
            }
        if tags_response.status_code in {403, 404}:
            return {
                "version": None,
                "url": GITHUB_REPO_URL,
                "source": "repository",
                "message": "The GitHub repository is reachable only without release metadata right now.",
            }
        tags_response.raise_for_status()

    return {
        "version": None,
        "url": GITHUB_REPO_URL,
        "source": None,
        "message": "Unable to check GitHub for updates.",
    }


def normalize_version(value: str) -> str:
    return value.strip().lstrip("vV")


def is_newer_version(candidate: str, current: str) -> bool:
    if not candidate:
        return False
    candidate_parts = version_parts(candidate)
    current_parts = version_parts(current)
    if candidate_parts and current_parts:
        max_len = max(len(candidate_parts), len(current_parts))
        candidate_parts += [0] * (max_len - len(candidate_parts))
        current_parts += [0] * (max_len - len(current_parts))
        return candidate_parts > current_parts
    return candidate != current


def version_parts(value: str) -> list[int]:
    parts: list[int] = []
    for chunk in normalize_version(value).split("."):
        if not chunk.isdigit():
            return []
        parts.append(int(chunk))
    return parts
