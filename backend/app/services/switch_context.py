"""Наследование и сверка put/switch по сегментам ASR-текста (перебивает ошибки LLM)."""

from __future__ import annotations

from app.services.asr_fixes import fix_asr_transcript
from app.services.railway_segment import segment_railway_text
from app.services.parser import (
    ParsedRecord,
    _extract_put,
    _extract_switch,
    _normalize_text,
    has_path_binding,
)


def _segment_put_switch(part: str) -> tuple[str | None, str | None]:
    normalized = _normalize_text(part)
    put = _extract_put(normalized) if has_path_binding(normalized) else None
    return put, _extract_switch(normalized)


def _resolve_segment_location(
    part: str,
    inherited_switch: str | None,
) -> tuple[str | None, str | None, str | None]:
    """
    (put, switch, inherited_switch после сегмента).
    Стр.п. не наследуем на новый «N путь» — только если назван в том же фрагменте.
    """
    seg_put, seg_switch = _segment_put_switch(part)

    if seg_put is not None:
        return seg_put, seg_switch, seg_switch

    if seg_switch:
        return None, seg_switch, seg_switch

    return None, inherited_switch, inherited_switch


def _apply_segment_to_record(
    record: ParsedRecord,
    part: str,
    inherited_switch: str | None,
) -> str | None:
    seg_put, seg_switch, inherited_switch = _resolve_segment_location(part, inherited_switch)
    record.put = seg_put
    record.switch = seg_switch
    return inherited_switch


def propagate_switch_context(
    records: list[ParsedRecord],
    source_text: str | None,
) -> list[ParsedRecord]:
    """
    Сверяет put/switch с сегментами segment_railway_text и перезаписывает поля.
    """
    if not source_text or not records:
        return records

    source_text = fix_asr_transcript(source_text)
    parts = [b.segment for b in segment_railway_text(source_text)]
    if not parts:
        parts = [source_text]

    ordered = sorted(
        records,
        key=lambda r: (r.logical_record_index if r.logical_record_index is not None else 0, r.position_index or 0),
    )

    if len(ordered) == len(parts):
        inherited: str | None = None
        for record, part in zip(ordered, parts):
            inherited = _apply_segment_to_record(record, part, inherited)
        return records

    indices = sorted(
        {r.logical_record_index for r in records if r.logical_record_index is not None}
    )
    inherited = None
    for i, idx in enumerate(indices):
        part = parts[min(i, len(parts) - 1)]
        seg_put, seg_switch, inherited = _resolve_segment_location(part, inherited)
        for record in records:
            if record.logical_record_index != idx:
                continue
            record.put = seg_put
            record.switch = seg_switch

    return records
