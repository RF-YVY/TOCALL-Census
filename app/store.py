from __future__ import annotations

import csv
import io
import sqlite3
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.aprs import ParsedPacket
from app.geography import country, us_state
from app.paths import data_dir
from app.privacy import mask_path, mask_raw_packet, masked_station


DATA_DIR = data_dir()
DB_PATH = DATA_DIR / "tocall_monitor.sqlite3"


class PacketStore:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS packets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                heard_at TEXT NOT NULL,
                source TEXT NOT NULL,
                tocall TEXT NOT NULL,
                path TEXT NOT NULL,
                body TEXT NOT NULL,
                raw TEXT NOT NULL,
                lat REAL,
                lon REAL,
                transport TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_packets_tocall ON packets(tocall);
            CREATE INDEX IF NOT EXISTS idx_packets_heard_at ON packets(heard_at);
            CREATE INDEX IF NOT EXISTS idx_packets_source ON packets(source);
            """
        )
        self.conn.commit()
        self.mask_existing_packet_identifiers()

    def mask_existing_packet_identifiers(self) -> None:
        rows = self.conn.execute("SELECT id, source, tocall, path, raw FROM packets").fetchall()
        updates: list[tuple[str, str, str, int]] = []
        for row in rows:
            masked_source = masked_station(row["source"])
            masked_path = mask_path(row["path"])
            masked_raw = mask_raw_packet(row["raw"], source=row["source"], tocall=row["tocall"], path=row["path"])
            if (masked_source, masked_path, masked_raw) != (row["source"], row["path"], row["raw"]):
                updates.append((masked_source, masked_path, masked_raw, row["id"]))
        if not updates:
            return
        self.conn.executemany(
            "UPDATE packets SET source = ?, path = ?, raw = ? WHERE id = ?",
            updates,
        )
        self.conn.commit()

    def add_packet(self, packet: ParsedPacket) -> None:
        masked_source = masked_station(packet.source)
        masked_path = mask_path(packet.path)
        masked_raw = mask_raw_packet(packet.raw, source=packet.source, tocall=packet.tocall, path=packet.path)
        self.conn.execute(
            """
            INSERT INTO packets
            (heard_at, source, tocall, path, body, raw, lat, lon, transport)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                packet.heard_at.isoformat(),
                masked_source,
                packet.tocall,
                masked_path,
                packet.body,
                masked_raw,
                packet.lat,
                packet.lon,
                packet.transport,
            ),
        )
        self.conn.commit()

    def prune(self, *, retention_days: int = 0, max_packets: int = 0) -> int:
        removed = 0
        if retention_days > 0:
            cutoff = datetime.now(UTC) - timedelta(days=retention_days)
            cursor = self.conn.execute("DELETE FROM packets WHERE heard_at < ?", (cutoff.isoformat(),))
            removed += cursor.rowcount if cursor.rowcount != -1 else 0
        if max_packets > 0:
            cursor = self.conn.execute(
                """
                DELETE FROM packets
                WHERE id NOT IN (
                    SELECT id FROM packets ORDER BY id DESC LIMIT ?
                )
                """,
                (max_packets,),
            )
            removed += cursor.rowcount if cursor.rowcount != -1 else 0
        if removed:
            self.conn.commit()
        return removed

    def summary(self, registry: Any, target_tocall: str | None = None) -> dict[str, Any]:
        params: list[Any] = []
        where = ""
        if target_tocall:
            where = "WHERE tocall = ?"
            params.append(target_tocall.upper())

        totals = self.conn.execute(
            f"""
            SELECT tocall, COUNT(*) AS count, MAX(heard_at) AS last_heard
            FROM packets
            {where}
            GROUP BY tocall
            ORDER BY count DESC, tocall ASC
            LIMIT 50
            """,
            params,
        ).fetchall()

        transport_rows = self.conn.execute(
            f"SELECT transport, COUNT(*) AS count FROM packets {where} GROUP BY transport",
            params,
        ).fetchall()

        unique_sources = self.conn.execute(
            f"SELECT COUNT(DISTINCT source) AS count FROM packets {where}",
            params,
        ).fetchone()["count"]

        recent = self.recent_packets(registry, target_tocall=target_tocall, limit=25)
        return {
            "top_tocalls": [
                {
                    "tocall": row["tocall"],
                    "count": row["count"],
                    "last_heard": row["last_heard"],
                    "label": registry.lookup(row["tocall"]) or "Unknown",
                }
                for row in totals
            ],
            "transport": {row["transport"]: row["count"] for row in transport_rows},
            "unique_sources": unique_sources,
            "locations": self.location_summary(target_tocall),
            "recent": recent,
        }

    def recent_packets(
        self,
        registry: Any,
        *,
        target_tocall: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if target_tocall:
            where = "WHERE tocall = ?"
            params.append(target_tocall.upper())
        params.append(limit)

        rows = self.conn.execute(
            f"""
            SELECT heard_at, source, tocall, path, raw, lat, lon, transport
            FROM packets
            {where}
            ORDER BY id DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        return [row_to_event(row, registry) for row in rows]

    def map_points(self, registry: Any, target_tocall: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = "WHERE lat IS NOT NULL AND lon IS NOT NULL"
        if target_tocall:
            where += " AND tocall = ?"
            params.append(target_tocall.upper())

        rows = self.conn.execute(
            f"""
            SELECT source, tocall, path, lat, lon, transport, MAX(heard_at) AS heard_at
            FROM packets
            {where}
            GROUP BY source, tocall
            ORDER BY heard_at DESC
            LIMIT 500
            """,
            params,
        ).fetchall()
        return [row_to_event(row, registry) for row in rows]

    def export_counts(self) -> dict[str, int]:
        rows = self.conn.execute("SELECT tocall, COUNT(*) AS count FROM packets GROUP BY tocall").fetchall()
        return dict(Counter({row["tocall"]: row["count"] for row in rows}))

    def clear(self) -> None:
        self.conn.execute("DELETE FROM packets")
        self.conn.commit()

    def export_rows(self, registry: Any, target_tocall: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if target_tocall:
            where = "WHERE tocall = ?"
            params.append(target_tocall.upper())

        rows = self.conn.execute(
            f"""
            SELECT heard_at, source, tocall, path, raw, lat, lon, transport
            FROM packets
            {where}
            ORDER BY id ASC
            """,
            params,
        ).fetchall()
        return [row_to_event(row, registry) for row in rows]

    def report(self, registry: Any, target_tocall: str | None = None) -> dict[str, Any]:
        return {
            "target_tocall": target_tocall,
            "summary": self.summary(registry, target_tocall),
            "map_points": self.map_points(registry, target_tocall),
            "packets": self.export_rows(registry, target_tocall),
        }

    def report_csv(self, registry: Any, target_tocall: str | None = None) -> str:
        rows = self.export_rows(registry, target_tocall)
        output = io.StringIO()
        fieldnames = ["heard_at", "source", "tocall", "label", "transport", "path", "lat", "lon", "raw"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def daily_summary_csv(self, registry: Any, target_tocall: str | None = None) -> str:
        rows = self.daily_summary(registry, target_tocall)
        output = io.StringIO()
        fieldnames = ["date", "tocall", "label", "packet_count", "unique_sources", "last_heard"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        return output.getvalue()

    def daily_summary(self, registry: Any, target_tocall: str | None = None) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if target_tocall:
            where = "WHERE tocall = ?"
            params.append(target_tocall.upper())
        rows = self.conn.execute(
            f"""
            SELECT substr(heard_at, 1, 10) AS date,
                   tocall,
                   COUNT(*) AS packet_count,
                   COUNT(DISTINCT source) AS unique_sources,
                   MAX(heard_at) AS last_heard
            FROM packets
            {where}
            GROUP BY date, tocall
            ORDER BY date DESC, packet_count DESC, tocall ASC
            """,
            params,
        ).fetchall()
        return [
            {
                "date": row["date"],
                "tocall": row["tocall"],
                "label": registry.lookup(row["tocall"]) or "Unknown",
                "packet_count": row["packet_count"],
                "unique_sources": row["unique_sources"],
                "last_heard": row["last_heard"],
            }
            for row in rows
        ]

    def location_summary(self, target_tocall: str | None = None) -> dict[str, list[dict[str, Any]]]:
        params: list[Any] = []
        where = "WHERE lat IS NOT NULL AND lon IS NOT NULL"
        if target_tocall:
            where += " AND tocall = ?"
            params.append(target_tocall.upper())

        rows = self.conn.execute(
            f"""
            SELECT raw, MAX(lat) AS lat, MAX(lon) AS lon
            FROM packets
            {where}
            GROUP BY raw
            """,
            params,
        ).fetchall()

        state_counts: Counter[str] = Counter()
        country_counts: Counter[str] = Counter()
        for row in rows:
            lat = row["lat"]
            lon = row["lon"]
            state = us_state(lat, lon)
            if state:
                state_counts[state] += 1
                country_counts["United States"] += 1
            else:
                country_counts[country(lat, lon)] += 1

        return {
            "states": counter_rows(state_counts),
            "countries": counter_rows(country_counts),
        }


def counter_rows(counter: Counter[str]) -> list[dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common()]


def row_to_event(row: sqlite3.Row, registry: Any) -> dict[str, Any]:
    heard_at = row["heard_at"]
    if isinstance(heard_at, datetime):
        heard_at = heard_at.isoformat()
    lat = row["lat"]
    lon = row["lon"]
    state_name = None
    country_name = None
    if lat is not None and lon is not None:
        state_name = us_state(lat, lon)
        country_name = "United States" if state_name else country(lat, lon)

    source = row["source"]
    path = row["path"]
    raw = row["raw"] if "raw" in row.keys() else ""

    return {
        "heard_at": heard_at,
        "source": masked_station(source),
        "tocall": row["tocall"],
        "label": registry.lookup(row["tocall"]) or "Unknown",
        "path": mask_path(path),
        "raw": mask_raw_packet(raw, source=source, tocall=row["tocall"], path=path),
        "lat": lat,
        "lon": lon,
        "us_state": state_name,
        "country": country_name,
        "transport": row["transport"],
    }
