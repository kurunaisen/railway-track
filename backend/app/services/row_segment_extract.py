"""extractRowsFromSegment — одна строка ParsedRow из одного ASR-сегмента."""

from __future__ import annotations

import re

from app.services.asr_fixes import normalize_asr_text
from app.services.canonical_model import parse_position
from app.services.llm.row_segment_validation import ParsedRow
from app.services.railway_segment import SegmentedBlock
from app.services.rail_side import extract_rail_side_note

_TRACK_PREFIX_RE = re.compile(r"^путь\s+(\d+)", re.IGNORECASE)
_SWITCH_PREFIX_RE = re.compile(
    r"^стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)",
    re.IGNORECASE,
)
_TIP_SEGMENT_RE = re.compile(
    r"\b(?:в\s+|на\s+)?остри[ея]\s+остряка\b",
    re.IGNORECASE,
)


def _segment_asset(normalized: str) -> tuple[str | None, str | None]:
    track = _TRACK_PREFIX_RE.match(normalized)
    if track:
        return "track", track.group(1)
    switch = _SWITCH_PREFIX_RE.match(normalized)
    if switch:
        return "switch", switch.group(1)
    return None, None


def _format_defect(pos) -> str | None:
    if pos.defect:
        text = pos.defect.strip()
    elif pos.parameter:
        text = pos.parameter.strip()
    else:
        return None
    if pos.value:
        val = str(pos.value).strip()
        unit = (pos.unit or "мм").strip()
        if val not in text:
            text = f"{text} {val} {unit}".strip()
    return text or None


def _note_from_segment(segment: str, pos) -> str | None:
    notes: list[str] = []
    tip = _TIP_SEGMENT_RE.search(segment)
    if tip:
        notes.append(tip.group(0).strip())
    side = extract_rail_side_note(segment)
    if side:
        notes.append(side)
    if pos and getattr(pos, "comment", None):
        notes.append(str(pos.comment).strip())
    return "; ".join(n for n in notes if n) or None


def extract_row_from_segment_regex(block: SegmentedBlock) -> ParsedRow:
    """Детерминированное извлечение без LLM."""
    segment = block.segment
    normalized = normalize_asr_text(segment)
    pos = parse_position(segment, 0)
    asset_kind, asset_number = _segment_asset(normalized)

    return {
        "location": block.location,
        "assetKind": asset_kind,
        "assetNumber": asset_number,
        "reference": None,
        "defect": _format_defect(pos),
        "speedLimit": None,
        "note": _note_from_segment(segment, pos),
        "sourceText": segment,
    }


def extract_rows_from_segment(
    block: SegmentedBlock,
    *,
    use_llm: bool = False,
    index: int = 0,
) -> list[ParsedRow]:
    """Один сегмент → список из одной строки (ParsedRow)."""
    if use_llm:
        from app.services.llm.segment_llm_parser import extract_rows_from_segment_llm

        return extract_rows_from_segment_llm(block, index)

    return [extract_row_from_segment_regex(block)]
