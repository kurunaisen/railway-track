"""Обязательная валидация ParsedRow после LLM — по тексту сегмента."""

from __future__ import annotations

import re
from typing import Any

from app.services.asr_fixes import normalize_asr_text

ParsedRow = dict[str, Any]

_TRACK_PREFIX_RE = re.compile(r"^путь\s+(\d+)", re.IGNORECASE)
_SWITCH_PREFIX_RE = re.compile(
    r"^стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)",
    re.IGNORECASE,
)
_EXPLICIT_SPEED_RE = re.compile(
    r"\b(?:ограничение скорости|скорость)\s*(\d+)\b",
    re.IGNORECASE,
)
_TIP_IN_DEFECT_RE = re.compile(r"остри[ея]\s+остряка", re.IGNORECASE)
_TIP_QUALIFIER_RE = re.compile(
    r"\b(?:в\s+|на\s+)?остри[ея]\s+остряка\b",
    re.IGNORECASE,
)
_TIP_STRIP_RE = re.compile(
    r"\b(?:в\s+|на\s+)?остри[ея]\s+остряка\b",
    re.IGNORECASE,
)
_TIP_SEGMENT_RE = _TIP_QUALIFIER_RE
_WS_RE = re.compile(r"\s+")


def _extract_qualifier(text: str) -> str:
    match = _TIP_QUALIFIER_RE.search(text)
    return match.group(0) if match else "уточнение места измерения"


def _fix_tip_in_defect(row: ParsedRow) -> None:
    defect = row.get("defect")
    if not defect or not _TIP_IN_DEFECT_RE.search(defect):
        return
    qualifier = _extract_qualifier(defect)
    note = (row.get("note") or "").strip()
    row["note"] = f"{note}; {qualifier}" if note else qualifier
    cleaned = _TIP_STRIP_RE.sub("", defect)
    cleaned = _WS_RE.sub(" ", cleaned).strip()
    row["defect"] = cleaned or None


def validate_rows_for_segment(segment: str, rows: list[ParsedRow]) -> list[ParsedRow]:
    normalized = normalize_asr_text(segment)

    track_match = _TRACK_PREFIX_RE.match(normalized)
    switch_match = _SWITCH_PREFIX_RE.match(normalized)
    explicit_speed = _EXPLICIT_SPEED_RE.search(normalized)

    result: list[ParsedRow] = []
    for row in rows:
        fixed = dict(row)

        if track_match:
            fixed["assetKind"] = "track"
            fixed["assetNumber"] = track_match.group(1)
        elif switch_match:
            fixed["assetKind"] = "switch"
            fixed["assetNumber"] = switch_match.group(1)

        if not explicit_speed:
            fixed["speedLimit"] = None
        elif fixed.get("speedLimit") is None and explicit_speed:
            try:
                fixed["speedLimit"] = int(explicit_speed.group(1))
            except (TypeError, ValueError):
                pass

        if _TIP_SEGMENT_RE.search(normalized):
            qual = _extract_qualifier(normalized)
            note = (fixed.get("note") or "").strip()
            if not note:
                fixed["note"] = qual
            elif qual.lower() not in note.lower():
                fixed["note"] = f"{note}; {qual}"

        _fix_tip_in_defect(fixed)
        result.append(fixed)

    return result
