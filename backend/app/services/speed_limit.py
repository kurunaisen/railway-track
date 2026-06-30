"""Ограничение скорости — следствие неисправности, не отдельная неисправность."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.parser import ParsedRecord

_SPEED_EXTRACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ограничени[ея]\s+скорост(?:и|ь)?\s*(?:до\s*)?(\d+)", re.IGNORECASE),
    re.compile(
        r"скорост(?:ь|и)\s*(?:не\s*более|до|ограничена|ограничено)\s*(\d+)",
        re.IGNORECASE,
    ),
    re.compile(
        r"скорост(?:ь|и)\s+(\d+)\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час)?",
        re.IGNORECASE,
    ),
    re.compile(r"(\d+)\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час)\b", re.IGNORECASE),
)

_SPEED_PHRASE_RE = re.compile(
    r"(?:"
    r"ограничени[ея]\s+скорост(?:и|ь)?(?:\s+до\s*)?\s*\d+(?:\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час))?"
    r"|"
    r"скорост(?:ь|и)\s+(?:не\s+более|не\s+выше|до|ограничена|ограничено)?\s*\d+(?:\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час))?"
    r"|"
    r"\d+\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час)\b"
    r")",
    re.IGNORECASE,
)

_SPEED_PARAM_RE = re.compile(r"ограничени[ея]\s+скорост(?:и|ь)?|\bскорост(?:ь|и)\b", re.IGNORECASE)


def extract_speed_limit(text: str | None) -> str | None:
    if not text:
        return None
    for pat in _SPEED_EXTRACT_PATTERNS:
        match = pat.search(text)
        if match:
            return match.group(1)
    return None


def strip_speed_limit_phrases(text: str | None) -> str:
    if not text:
        return ""
    cleaned = _SPEED_PHRASE_RE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")


def is_speed_parameter(name: str | None) -> bool:
    if not name:
        return False
    lowered = name.strip().lower()
    if "огранич" in lowered and "скорост" in lowered:
        return True
    return lowered in {"скорость", "ограничение скорости", "v огр.", "v огр"}


def apply_speed_limit_fields(record: ParsedRecord) -> None:
    """Извлекает скорость из текста в speed_limit и убирает её из неисправности."""
    for source in (record.raw_text, record.defect, record.parameter):
        speed = extract_speed_limit(source)
        if speed:
            record.speed_limit = record.speed_limit or speed
            break

    if record.defect:
        cleaned = strip_speed_limit_phrases(record.defect).strip()
        if is_speed_parameter(record.defect) or not cleaned:
            record.defect = cleaned or None

    if record.parameter and is_speed_parameter(record.parameter):
        record.parameter = None
        record.value = None
        if not record.speed_limit:
            record.unit = None

    if record.position_type == "speed_limit" and (record.defect or record.parameter):
        record.position_type = "defect" if record.defect else "parameter"
    elif record.position_type == "speed_limit":
        record.position_type = None


def _same_record_context(a: ParsedRecord, b: ParsedRecord) -> bool:
    return (
        a.logical_record_index == b.logical_record_index
        and (a.km or "") == (b.km or "")
        and (a.piket or "") == (b.piket or "")
        and (a.peregon or "") == (b.peregon or "")
    )


def _has_real_issue(record: ParsedRecord) -> bool:
    if record.parameter and not is_speed_parameter(record.parameter):
        return True
    if record.defect and strip_speed_limit_phrases(record.defect).strip():
        if not is_speed_parameter(record.defect):
            return True
    return False


def is_speed_limit_only_record(record: ParsedRecord) -> bool:
    apply_speed_limit_fields(record)
    if not record.speed_limit:
        return False
    if _has_real_issue(record):
        return False
    return record.position_type == "speed_limit" or not record.defect


def _merge_pending_speed(
    result: list[ParsedRecord],
    pending_speed: str | None,
    context: ParsedRecord,
) -> str | None:
    if not pending_speed or not result:
        return pending_speed
    for row in reversed(result):
        if _same_record_context(row, context) and _has_real_issue(row):
            if not row.speed_limit:
                row.speed_limit = pending_speed
            return None
    for row in reversed(result):
        if _same_record_context(row, context):
            if not row.speed_limit:
                row.speed_limit = pending_speed
            return None
    return pending_speed


def reconcile_speed_limit_rows(records: list[ParsedRecord]) -> list[ParsedRecord]:
    """Скорость — в столбец ограничения, при необходимости на строку с неисправностью."""
    if not records:
        return records

    result: list[ParsedRecord] = []
    pending_speed: str | None = None

    for record in records:
        apply_speed_limit_fields(record)

        if is_speed_limit_only_record(record):
            if result and _same_record_context(result[-1], record):
                pending_speed = record.speed_limit or pending_speed
                continue
            record.defect = None
            record.parameter = None
            record.value = None
            record.unit = None
            record.position_type = None
            result.append(record)
            continue

        if pending_speed and not record.speed_limit:
            record.speed_limit = pending_speed
            pending_speed = None

        if record.position_type == "speed_limit":
            record.position_type = "defect" if record.defect else ("parameter" if record.parameter else None)

        if (
            not _has_real_issue(record)
            and not record.speed_limit
            and record.position_type == "parameter"
            and "parameter" in record.disputed_fields
        ):
            continue

        result.append(record)

    pending_speed = _merge_pending_speed(result, pending_speed, records[-1])

    return result
