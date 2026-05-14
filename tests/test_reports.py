from datetime import UTC, datetime

from app.aprs import ParsedPacket
from app.main import safe_filename_part
from app.pdf_report import build_pdf_report
from app.registry import TocallRegistry
from app.store import PacketStore


def make_packet(tocall: str = "APDW16") -> ParsedPacket:
    return ParsedPacket(
        raw=f"CALL>{tocall},WIDE1-1:!3401.00N/08901.00W>",
        source="CALL",
        tocall=tocall,
        path="WIDE1-1",
        body="!3401.00N/08901.00W>",
        heard_at=datetime.now(UTC),
        lat=34.016667,
        lon=-89.016667,
        transport="rf_path",
    )


def make_located_packet(raw: str, lat: float, lon: float, tocall: str = "APDW16") -> ParsedPacket:
    return ParsedPacket(
        raw=raw,
        source="CALL",
        tocall=tocall,
        path="WIDE1-1",
        body="!position",
        heard_at=datetime.now(UTC),
        lat=lat,
        lon=lon,
        transport="rf_path",
    )


def test_store_clear_removes_packets(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    registry = TocallRegistry()

    store.add_packet(make_packet())
    assert store.summary(registry)["top_tocalls"][0]["count"] == 1

    store.clear()
    assert store.summary(registry)["top_tocalls"] == []


def test_report_exports_rows_and_csv(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    registry = TocallRegistry()
    registry.entries = {"APDW??": "WB2OSZ DireWolf"}
    store.add_packet(make_packet())

    report = store.report(registry)
    csv_text = store.report_csv(registry)

    assert report["packets"][0]["tocall"] == "APDW16"
    assert report["packets"][0]["label"] == "WB2OSZ DireWolf"
    assert "heard_at,source,tocall,label,transport,path,lat,lon,raw" in csv_text
    assert "APDW16" in csv_text


def test_pdf_report_contains_pdf_header(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    registry = TocallRegistry()
    registry.entries = {"APDW??": "WB2OSZ DireWolf"}
    store.add_packet(make_packet())

    pdf = build_pdf_report(store.report(registry), "TOCALL Census", "v1.0.0")

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000
    assert b"Map Snapshot" not in pdf


def test_pdf_filename_sanitizes_tocall_identifier() -> None:
    assert safe_filename_part("APRSPV") == "APRSPV"
    assert safe_filename_part("AP/../PV") == "APPV"
    assert safe_filename_part("") == "ALL"


def test_location_summary_counts_unique_raw_packets(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    store.add_packet(make_located_packet("DUPLICATE", 34.0, -89.0))
    store.add_packet(make_located_packet("DUPLICATE", 34.0, -89.0))
    store.add_packet(make_located_packet("CANADA", 45.5, -75.7))

    locations = store.location_summary()

    assert locations["states"] == [{"name": "Mississippi", "count": 1}]
    assert {"name": "United States", "count": 1} in locations["countries"]
    assert {"name": "Canada", "count": 1} in locations["countries"]


def test_location_summary_counts_propview_packet_in_new_jersey(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    packet = make_located_packet(
        "KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#Alinco DR135 APRS PropView Digi/IGate",
        40.105667,
        -74.783667,
        "APRSPV",
    )
    store.add_packet(packet)
    store.add_packet(packet)

    locations = store.location_summary("APRSPV")

    assert locations["states"] == [{"name": "New Jersey", "count": 1}]
    assert locations["countries"] == [{"name": "United States", "count": 1}]


def test_export_rows_include_state_and_country(tmp_path) -> None:
    store = PacketStore(tmp_path / "packets.sqlite3")
    registry = TocallRegistry()
    store.add_packet(
        make_located_packet(
            "KD2FMW-1>APRSPV,TCPIP*,qAC,T2RDU:=4006.34N/07447.02W#Alinco DR135 APRS PropView Digi/IGate",
            40.105667,
            -74.783667,
            "APRSPV",
        )
    )

    row = store.export_rows(registry, "APRSPV")[0]

    assert row["us_state"] == "New Jersey"
    assert row["country"] == "United States"
