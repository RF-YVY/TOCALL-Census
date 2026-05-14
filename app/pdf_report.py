from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.geography import location_bucket


def build_pdf_report(report: dict[str, Any], app_name: str, version: str) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    story: list[Any] = []
    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    target = report.get("target_tocall") or "All TOCALLs"
    packets = report.get("packets", [])
    top_tocalls = report.get("summary", {}).get("top_tocalls", [])

    story.append(Paragraph(f"{app_name} Report", styles["Title"]))
    story.append(Paragraph(f"Target: {target}", styles["Normal"]))
    story.append(Paragraph(f"Generated: {generated_at} | Version: {version}", styles["Normal"]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("TOCALL Identified Counts", styles["Heading2"]))
    story.append(make_table([["TOCALL", "Device or Software", "Count", "Last Heard"]] + [
        [row["tocall"], row["label"], str(row["count"]), row.get("last_heard") or ""]
        for row in top_tocalls[:30]
    ]))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Locations Heard", styles["Heading2"]))
    story.append(make_table([["Location Type", "Location", "Packets"]] + location_rows(packets)))
    story.append(Spacer(1, 14))

    story.append(Paragraph("Report Notes", styles["Heading2"]))
    story.append(
        Paragraph(
            "Locations are derived from unique APRS packets containing coordinates. US state and country placement uses "
            "offline geographic bounds and should be treated as a practical reporting aid, not a legal boundary survey.",
            styles["BodyText"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def location_rows(packets: list[dict[str, Any]]) -> list[list[str]]:
    counts: Counter[tuple[str, str]] = Counter()
    seen_raw: set[str] = set()
    for packet in packets:
        raw = packet.get("raw") or f"{packet.get('source')}:{packet.get('tocall')}:{packet.get('lat')}:{packet.get('lon')}"
        if raw in seen_raw:
            continue
        seen_raw.add(raw)
        bucket_type, bucket = location_bucket(packet.get("lat"), packet.get("lon"))
        counts[(bucket_type, bucket)] += 1
    if not counts:
        return [["Unknown", "No located packets", "0"]]
    return [[bucket_type, bucket, str(count)] for (bucket_type, bucket), count in counts.most_common()]


def make_table(rows: list[list[str]]) -> Table:
    if len(rows) == 1:
        rows.append(["", "No data collected", "", ""][: len(rows[0])])
    table = Table(rows, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5dd")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f7f8")]),
            ]
        )
    )
    return table
