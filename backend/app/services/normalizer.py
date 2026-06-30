"""Шаг 6: нормализация извлечённых значений."""

from __future__ import annotations

import re

from app.services.km_parse import merge_hesitated_km_value
from app.services.parser import ParsedRecord
from app.services.speed_limit import reconcile_speed_limit_rows
from app.services.rail_side import (
    extract_rail_side,
    extract_rail_side_note,
    is_defect_continuation,
    is_rail_side_only_fragment,
    merge_comment,
    strip_rail_side_phrases,
)
from app.services.peregons import normalize_peregon
from app.services.locations import is_peregon_haul
from app.services.stations import normalize_station_name

ORDINAL_PUT = {
    "перв": "1",
    "втор": "2",
    "трет": "3",
    "четверт": "4",
    "пят": "5",
    "шест": "6",
    "седьм": "7",
    "восьм": "8",
    "девят": "9",
    "десят": "10",
}

UNIT_NORMALIZE = {
    "миллиметр": "мм",
    "миллиметров": "мм",
    "миллиметра": "мм",
    "мм": "мм",
    "сантиметр": "см",
    "сантиметров": "см",
    "см": "см",
    "километров в час": "км/ч",
    "км/ч": "км/ч",
    "км в час": "км/ч",
    "градус": "°",
    "градусов": "°",
    "промилле": "‰",
    "метр": "м",
    "м": "м",
}


def normalize_put(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    if v.isdigit():
        return v
    for stem, num in ORDINAL_PUT.items():
        if stem in v:
            return num
    m = re.search(r"(\d+)", v)
    return m.group(1) if m else value


def normalize_piket(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    v = re.sub(r"\s*плюс\s*", "+", v)
    v = re.sub(r"\s+", "", v)
    v = v.replace(",", ".")
    return v


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    for key, norm in UNIT_NORMALIZE.items():
        if key in v or v == key:
            return norm
    return value


def normalize_km(value: str | None) -> str | None:
    if not value:
        return value
    return merge_hesitated_km_value(value)


def normalize_speed(value: str | None) -> str | None:
    if not value:
        return value
    m = re.search(r"(\d+)", value)
    return m.group(1) if m else value


def _same_record_context(a: ParsedRecord, b: ParsedRecord) -> bool:
    return (
        a.logical_record_index == b.logical_record_index
        and (a.km or "") == (b.km or "")
        and (a.piket or "") == (b.piket or "")
        and (a.peregon or "") == (b.peregon or "")
    )


def _append_defect_text(record: ParsedRecord, extra: str) -> None:
    extra = extra.strip()
    if not extra:
        return
    if record.defect:
        if extra.lower() not in record.defect.lower():
            record.defect = f"{record.defect} {extra}".strip()
    else:
        record.defect = extra
    record.position_type = "defect"


def _apply_rail_side_note(record: ParsedRecord) -> None:
    note = extract_rail_side_note(record.raw_text) or extract_rail_side_note(record.defect or "")
    if note:
        record.comment = merge_comment(record.comment, note)
    if record.obekt in ("левая нить", "правая нить"):
        record.obekt = None


def reconcile_rail_side_rows(records: list[ParsedRecord]) -> list[ParsedRecord]:
    """Сторона нити — в примечание; не отдельная неисправность."""
    if not records:
        return records

    result: list[ParsedRecord] = []
    pending_note: str | None = None

    for record in records:
        note = extract_rail_side_note(record.raw_text) or extract_rail_side_note(record.defect or "")
        if note:
            if record.defect and extract_rail_side(record.defect):
                record.defect = None
                record.parameter = None
                record.value = None
                record.unit = None
                record.position_type = None

        if is_rail_side_only_fragment(record.raw_text) or (
            note and not record.defect and not record.parameter and not record.value
        ):
            pending_note = note or pending_note
            continue

        if pending_note:
            record.comment = merge_comment(record.comment, pending_note)
            pending_note = None

        if result and is_defect_continuation(record.raw_text) and _same_record_context(result[-1], record):
            _append_defect_text(result[-1], record.raw_text or "")
            if record.comment and not result[-1].comment:
                result[-1].comment = record.comment
            continue

        if note:
            record.comment = merge_comment(record.comment, note)

        cleaned_raw = strip_rail_side_phrases(record.raw_text or "")
        if cleaned_raw and cleaned_raw != record.raw_text:
            record.raw_text = cleaned_raw

        _apply_rail_side_note(record)
        result.append(record)

    return result


def normalize_record(record: ParsedRecord) -> ParsedRecord:
    if record.peregon and is_peregon_haul(record.peregon):
        record.peregon = normalize_peregon(record.peregon)
    elif record.peregon:
        record.uchastok = normalize_station_name(record.peregon) or record.uchastok
        record.peregon = None
    if record.uchastok:
        record.uchastok = normalize_station_name(record.uchastok)
    record.put = normalize_put(record.put)
    record.km = normalize_km(record.km)
    record.piket = normalize_piket(record.piket)
    record.unit = normalize_unit(record.unit)
    record.speed_limit = normalize_speed(record.speed_limit)
    if record.speed_limit and not record.unit:
        record.unit = "км/ч"
    if record.comment:
        record.comment = record.comment.strip().lower()
    if record.value:
        record.value = record.value.replace(",", ".").strip()
    return record


def normalize_all(records: list[ParsedRecord]) -> list[ParsedRecord]:
    records = reconcile_speed_limit_rows(records)
    records = reconcile_rail_side_rows(records)
    return [normalize_record(r) for r in records]
