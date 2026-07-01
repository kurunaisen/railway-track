"""Наследование номера стрелочного перевода из полного текста (LLM не всегда заполняет switch)."""

from __future__ import annotations

from app.services.asr_fixes import fix_asr_transcript
from app.services.canonical_model import _split_by_location
from app.services.switch_measurement import path_block_keeps_switch_context
from app.services.parser import (
    ParsedRecord,
    _extract_put,
    _extract_switch,
    _normalize_text,
    has_path_binding,
)


def _segment_put_switch(part: str) -> tuple[str | None, str | None]:
    """Путь — только если в фрагменте явно «N путь»; стр.п. — из любого упоминания."""
    normalized = _normalize_text(part)
    put = _extract_put(normalized) if has_path_binding(normalized) else None
    return put, _extract_switch(normalized)


def propagate_switch_context(
    records: list[ParsedRecord],
    source_text: str | None,
) -> list[ParsedRecord]:
    """
    Заполняет put/switch из полного ASR-текста по порядку логических записей.
    Сегменты совпадают с _split_by_location: блок «стр.п. 10» без «N путь» не получает put.
    """
    if not source_text or not records:
        return records

    source_text = fix_asr_transcript(source_text)
    parts = _split_by_location(source_text)
    segments = [_segment_put_switch(part) for part in parts]
    if not segments:
        segments = [_segment_put_switch(source_text)]

    indices = sorted(
        {r.logical_record_index for r in records if r.logical_record_index is not None}
    )
    active_put: str | None = None
    active_switch: str | None = None

    for i, idx in enumerate(indices):
        seg_put, seg_switch = segments[min(i, len(segments) - 1)]
        part = parts[min(i, len(parts) - 1)]
        if seg_put is not None:
            active_put = seg_put
            if not seg_switch and not path_block_keeps_switch_context(part):
                active_switch = None
        elif seg_switch:
            active_put = None
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
