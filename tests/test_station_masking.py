from datetime import UTC, datetime

from app.aprs import ParsedPacket
from app.privacy import mask_path, mask_raw_packet, masked_station
from app.registry import TocallRegistry
from app.store import PacketStore


def test_station_mask_removes_callsign_and_ssid() -> None:
    first = masked_station("KD2FMW-1")
    second = masked_station("KD2FMW-1")

    assert first == second
    assert first.startswith("STN-")
    assert "KD2FMW" not in first
    assert "-1" not in first


def test_path_and_raw_packet_mask_station_addresses() -> None:
    path = "TCPIP*,qAC,T2RDU"
    raw = "KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#PropView"

    masked_path = mask_path(path)
    masked_raw = mask_raw_packet(raw, source="KD2FMW-1", tocall="APRSPV", path=path)

    assert "KD2FMW" not in masked_raw
    assert "T2RDU" not in masked_raw
    assert "-1" not in masked_raw
    assert "APRSPV" in masked_raw
    assert masked_path.startswith("TCPIP*,QAC,STN-")


def test_store_outputs_masked_station_data(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    registry = TocallRegistry()
    packet = ParsedPacket(
        raw="KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#PropView",
        source="KD2FMW-1",
        tocall="APRSPV",
        path="TCPIP*,qAC,T2RDU",
        body="=4006.34N/07447.02W#PropView",
        heard_at=datetime.now(UTC),
        lat=40.105667,
        lon=-74.783667,
        transport="aprs_is",
    )

    store.add_packet(packet)
    row = store.export_rows(registry)[0]

    assert row["source"].startswith("STN-")
    assert "KD2FMW" not in row["source"]
    assert "KD2FMW" not in row["raw"]
    assert "T2RDU" not in row["raw"]
    assert "APRSPV" in row["raw"]


def test_store_masks_existing_packet_rows_on_startup(tmp_path) -> None:
    db_path = tmp_path / "packets.sqlite3"
    store = PacketStore(db_path)
    store.conn.execute(
        """
        INSERT INTO packets
        (heard_at, source, tocall, path, body, raw, lat, lon, transport)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(UTC).isoformat(),
            "KD2FMW-1",
            "APRSPV",
            "TCPIP*,qAC,T2RDU",
            "=4006.34N/07447.02W#PropView",
            "KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#PropView",
            40.105667,
            -74.783667,
            "aprs_is",
        ),
    )
    store.conn.commit()
    store.conn.close()

    migrated = PacketStore(db_path)
    row = migrated.conn.execute("SELECT source, path, raw FROM packets").fetchone()

    assert row["source"].startswith("STN-")
    assert "KD2FMW" not in row["raw"]
    assert "T2RDU" not in row["raw"]
