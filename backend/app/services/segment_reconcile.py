"""Сверка строк таблицы с сегментами ASR-текста (путь K → дефект в том же фрагменте)."""

from __future__ import annotations

import re

from app.services.asr_fixes import fix_asr_transcript
from app.services.canonical_model import (
    LogicalRecordContext,
    PositionItem,
    _inherit_location_fields,
    _is_station_block,
    _split_by_location,
    extract_logical_record_context,
    parse_position,
    position_to_row,
)
from app.services.parser import ParsedRecord, _normalize_text
from app.services.rail_side import extract_rail_side_note, strip_rail_side_phrases

_PATH_LEAD_RE = re.compile(
    r"^(?:\d+\s+)?(?:главн\w*\s+)?путь\s*(?:№|номер|n\.?)?\s*\d+\s+",
    re.IGNORECASE,
)
_RAM_WEAR_VALUE_RE = re.compile(
    r"износ\s+рамн\w*\s+рельс\w*\s+(\d+(?:[.,]\d+)?)\s*мм",
    re.IGNORECASE,
)


def _parse_numeric(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", value.replace(",", "."))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_segment_position(loc_text: str) -> PositionItem:
    side_note = extract_rail_side_note(loc_text)
    text = strip_rail_side_phrases(loc_text) if side_note else loc_text
    pos = parse_position(text, 0)
    if pos.defect or pos.parameter or pos.value:
        return pos
    stripped = _PATH_LEAD_RE.sub("", _normalize_text(text), count=1).strip()
    if stripped and stripped != _normalize_text(text):
        return parse_position(stripped, 0)
    return pos


def build_records_from_asr_segments(source_text: str) -> list[ParsedRecord]:
    """Одна строка таблицы на каждый фрагмент «путь K …» / стрелку из _split_by_location."""
    source_text = fix_asr_transcript(source_text)
    parts = _split_by_location(source_text)
    if not parts:
        return []

    inherited = LogicalRecordContext(logical_record_index=0)
    rows: list[ParsedRecord] = []

    for i, loc_text in enumerate(parts):
        ctx = extract_logical_record_context(loc_text, i, None, None)
        _inherit_location_fields(ctx, inherited, loc_text)

        if _is_station_block(loc_text):
            ctx.peregon = None
            ctx.km = None
            ctx.piket = None
            ctx.station_active = True
            inherited.peregon = None
            inherited.km = None
            inherited.piket = None
            inherited.station_active = True

        pos = _parse_segment_position(loc_text)
        row = position_to_row(ctx, pos)
        rows.append(row)

        for field in ("record_date", "uchastok", "peregon", "put", "switch", "km", "piket", "comment"):
            val = getattr(ctx, field)
            if val:
                setattr(inherited, field, val)
        inherited.station_active = ctx.station_active or inherited.station_active

    return rows


def _segment_rows_preferred(
    records: list[ParsedRecord],
    segment_rows: list[ParsedRecord],
) -> bool:
    if not segment_rows:
        return False
    if len(records) != len(segment_rows):
        return True
    for rec, seg in zip(records, segment_rows):
        if (seg.put or "") != (rec.put or ""):
            return True
        if (seg.switch or "") != (rec.switch or ""):
            return True
        if rec.defect and "рамн" in rec.defect.lower():
            val = _parse_numeric(rec.value)
            if val is not None and val > 500:
                return True
        seg_gauge = seg.defect and "коле" in (seg.defect or "").lower()
        rec_gauge = rec.defect and "коле" in (rec.defect or "").lower()
        if seg_gauge and not rec_gauge and (seg.put or seg.switch):
            return True
    return False


def fix_ram_rail_wear_gauge_value(record: ParsedRecord) -> None:
    """LLM/ASR иногда подставляет 1544 мм в строку износа рамного рельса."""
    if not record.defect or "рамн" not in record.defect.lower():
        return
    val = _parse_numeric(record.value)
    if val is None or val < 500:
        return
    m = _RAM_WEAR_VALUE_RE.search(record.raw_text or "")
    if m:
        record.value = m.group(1).replace(",", ".")
        record.unit = "мм"
    else:
        record.value = None
        record.unit = None


def reconcile_records_by_asr_segments(
    records: list[ParsedRecord],
    source_text: str | None,
) -> list[ParsedRecord]:
    if not source_text or not records:
        return records

    segment_rows = build_records_from_asr_segments(source_text)
    if not segment_rows or not _segment_rows_preferred(records, segment_rows):
        for record in records:
            fix_ram_rail_wear_gauge_value(record)
        return records

    for i, row in enumerate(segment_rows):
        if i < len(records):
            row.segment_start = records[i].segment_start
            row.segment_end = records[i].segment_end
            if not row.uchastok and records[i].uchastok:
                row.uchastok = records[i].uchastok
        row.logical_record_index = i
        row.position_index = 0

    return segment_rows
