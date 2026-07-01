"""Наследование номера стрелочного перевода из полного текста (LLM не всегда заполняет switch)."""

from __future__ import annotations

import re

from app.services.parser import ParsedRecord, _extract_put, _extract_switch, _normalize_text

_PATH_MARK_RE = re.compile(r"(?:^|\s)(\d+\s+путь\b)", re.IGNORECASE)


def _path_context_segments(source_text: str) -> list[tuple[str | None, str | None]]:
    """Фрагменты «…N путь … стрелочный перевод M» — по одному на каждый путь."""
    normalized = _normalize_text(source_text)
    matches = list(_PATH_MARK_RE.finditer(normalized))
    if not matches:
        return [(_extract_put(normalized), _extract_switch(normalized))]

    split_starts = [0] + [m.start() for m in matches[1:]]
    segments: list[tuple[str | None, str | None]] = []
    for i, start in enumerate(split_starts):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(normalized)
        part = normalized[start:end].strip(" ,.;")
        if part:
            segments.append((_extract_put(part), _extract_switch(part)))
    return segments or [(_extract_put(normalized), _extract_switch(normalized))]


def propagate_switch_context(
    records: list[ParsedRecord],
    source_text: str | None,
) -> list[ParsedRecord]:
    """
    Заполняет put/switch из полного ASR-текста по порядку логических записей.
    «…5 путь стрелочный перевод 15 … 6 путь стрелочный перевод 18 …»
    """
    if not source_text or not records:
        return records

    segments = _path_context_segments(source_text)
    if not segments:
        return records

    indices = sorted(
        {r.logical_record_index for r in records if r.logical_record_index is not None}
    )
    active_put: str | None = None
    active_switch: str | None = None

    for i, idx in enumerate(indices):
        seg_put, seg_switch = segments[min(i, len(segments) - 1)]
        if seg_put:
            active_put = seg_put
        if seg_switch:
            active_switch = seg_switch

        for record in records:
            if record.logical_record_index != idx:
                continue
            if active_put and not record.put:
                record.put = active_put
            if active_switch and not record.switch:
                record.switch = active_switch

    return records
