"""Шаг 6: нормализация извлечённых значений."""

from __future__ import annotations

import re

from app.services.km_parse import merge_hesitated_km_value
from app.services.parser import ParsedRecord, _extract_switch, _normalize_text
from app.services.speed_limit import reconcile_speed_limit_rows, drop_orphan_speed_rows
from app.services.rail_side import (
    extract_rail_side,
    extract_rail_side_note,
    is_defect_continuation,
    is_rail_side_only_fragment,
    merge_comment,
    strip_rail_side_phrases,
    strip_ungrounded_rail_side_comment,
)
from app.services.peregon_km import correct_km_for_peregon
from app.services.peregons import normalize_peregon
from app.services.locations import is_peregon_haul
from app.services.stations import normalize_station_name, CANONICAL_STATIONS
from app.services.station_km import sanitize_station_km
from app.services.station_context import propagate_station_context
from app.services.gauge_norms import is_gauge_context
from app.services.asr_fixes import fix_asr_transcript
from app.services.switch_context import propagate_switch_context
from app.services.switch_measurement import apply_switch_measurement_context
from app.services.track_norms import apply_track_norms_all
from app.services.canonical_model import _location_only_fragment

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
    if record.uchastok and record.peregon and is_peregon_haul(record.peregon):
        # На станции не тащим перегон с предыдущих строк (ASR-блоки).
        station = normalize_station_name(record.uchastok)
        if record.put and station in CANONICAL_STATIONS:
            record.peregon = None
    record.put = normalize_put(record.put)
    if not record.switch and record.raw_text:
        record.switch = _extract_switch(_normalize_text(record.raw_text))
    record.km = normalize_km(record.km)
    if record.uchastok and not record.peregon:
        cleared_km, was_cleared = sanitize_station_km(record.km, record.uchastok)
        if was_cleared:
            record.km = cleared_km
            if "km" not in record.disputed_fields:
                record.disputed_fields.append("km")
    if record.peregon and is_peregon_haul(record.peregon):
        corrected_km, km_fixed = correct_km_for_peregon(record.km, record.peregon)
        if km_fixed and corrected_km:
            record.km = corrected_km
            if "km" not in record.disputed_fields:
                record.disputed_fields.append("km")
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


def _resolve_peregon_asr_alias(record: ParsedRecord) -> None:
    """ASR «магнитит и шон» → «Магнетиты — Шонгуй» до reconcile."""
    if not record.peregon:
        return
    resolved = normalize_peregon(record.peregon)
    if resolved and is_peregon_haul(resolved):
        record.peregon = resolved


def _merge_speed_within_logical_records(records: list[ParsedRecord]) -> list[ParsedRecord]:
    """V огр. с отдельной позиции → на строку с неисправностью того же места."""
    groups: dict[tuple, list[ParsedRecord]] = {}
    for record in records:
        key = (
            record.logical_record_index,
            record.km or "",
            record.piket or "",
            record.peregon or "",
        )
        groups.setdefault(key, []).append(record)

    result: list[ParsedRecord] = []
    for group in groups.values():
        speed = next((r.speed_limit for r in group if r.speed_limit), None)
        has_defect = any(r.defect for r in group)
        for record in group:
            if record.defect and not record.speed_limit and speed:
                record.speed_limit = speed
            if (
                has_defect
                and not record.defect
                and not (record.parameter and record.parameter.strip())
                and record.speed_limit
            ):
                continue
            result.append(record)
    return result


def _strip_hallucinated_rail_side(records: list[ParsedRecord], source_text: str | None) -> None:
    """LLM иногда подставляет «левая нить» из примера промпта — убираем без ASR."""
    for record in records:
        record.comment = strip_ungrounded_rail_side_comment(
            record.comment,
            source_text,
            record.raw_text,
        )


_DEFECT_HINT_RE = re.compile(
    r"болт|закладн|закручен|отсutств|уширен|просадк|износ|перекос",
    re.IGNORECASE,
)


def _drop_location_only_rows(records: list[ParsedRecord]) -> list[ParsedRecord]:
    return [
        r
        for r in records
        if not (
            r.position_type == "parameter"
            and not r.defect
            and not r.value
            and not r.speed_limit
            and "parameter" in r.disputed_fields
            and not _DEFECT_HINT_RE.search(r.raw_text or "")
        )
        and not (
            _location_only_fragment(r.raw_text or "")
            and not r.defect
            and not r.value
            and not r.speed_limit
        )
    ]


def _clear_ungrounded_speed_limit(record: ParsedRecord) -> None:
    """LLM иногда ставит V огр. от колеи на строку с износом."""
    if not record.speed_limit or record.position_type == "speed_limit":
        return
    blob = f"{record.defect or ''} {record.raw_text or ''}".lower()
    if re.search(r"скорост|ограничен", blob):
        return
    if is_gauge_context(blob):
        return
    defect = (record.defect or "").lower()
    if "износ" in defect and "рамн" in defect:
        record.speed_limit = None


def normalize_all(
    records: list[ParsedRecord],
    source_text: str | None = None,
) -> list[ParsedRecord]:
    if source_text:
        source_text = fix_asr_transcript(source_text)
    for record in records:
        _resolve_peregon_asr_alias(record)
    records = reconcile_speed_limit_rows(records)
    records = reconcile_rail_side_rows(records)
    if source_text:
        _strip_hallucinated_rail_side(records, source_text)
    records = _drop_location_only_rows(records)
    records = _merge_speed_within_logical_records(records)
    records = propagate_station_context(records)
    if source_text:
        records = propagate_switch_context(records, source_text)
    records = apply_switch_measurement_context(records)
    records = [normalize_record(r) for r in records]
    records = apply_track_norms_all(records)
    for record in records:
        _clear_ungrounded_speed_limit(record)
    return drop_orphan_speed_rows(records)
