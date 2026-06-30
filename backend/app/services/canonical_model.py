"""
Каноническая модель данных (FR 10):

10.1 Логическая запись — блок контекста: перегон, путь, км, пикет, комментарий, таймкод, №.
10.2 Позиция — один параметр или дефект внутри записи.
10.3 Один параметр/неисправность = одна строка long-таблицы.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.domain_terms import DEFECT_KEYWORDS, PARAMETER_KEYWORDS
from app.services.parser import (
    DEFECT_LABEL_PREFIXES,
    ParsedRecord,
    _extract_comment,
    _extract_compound_defect,
    _extract_date,
    _extract_defect,
    _extract_km,
    _extract_obekt,
    _extract_parameter,
    _extract_peregon,
    _extract_piket,
    _extract_put,
    _extract_speed_limit,
    _extract_uchastok,
    _extract_value_unit,
    _find_all_mentions,
    _normalize_text,
    _split_multi_defects,
)
from app.services.rail_side import (
    extract_rail_side_note,
    is_rail_side_only_fragment,
    merge_comment,
    strip_rail_side_phrases,
)
from app.services.speed_limit import (
    extract_speed_limit,
    is_speed_parameter,
    strip_speed_limit_phrases,
)
from app.services.segmentation import LogicalBlock

POSITION_TYPES = ("parameter", "defect", "speed_limit")

# Параметры и дефекты для разбиения на позиции (п. 10.2)
POSITION_ANCHOR_KEYWORDS: tuple[str, ...] = tuple(
    dict.fromkeys(
        [
            *PARAMETER_KEYWORDS,
            *DEFECT_KEYWORDS,
            "перекос",
            "рихтовка",
            "выправка",
        ]
    )
)

SPEED_LIMIT_MARKERS = (
    "ограничение скорости",
    "скорость не более",
    "скорость не выше",
    "скорость ограничена",
)

_SPEED_LIMIT_ANCHOR_RE = re.compile(
    r"(?:"
    r"ограничени[ея]\s+скорост(?:и|ь)?(?:\s+до\s*)?\s*\d+(?:\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час))?"
    r"|"
    r"ограничени[ея]\s+\d+(?:\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час))?"
    r"|"
    r"скорост(?:ь|и)\s+(?:не\s+более|не\s+выше|до|ограничена|ограничено)?\s*\d+(?:\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час))?"
    r"|"
    r"скорост(?:ь|и)\s+\d+\s*(?:км\s*/?\s*ч|километр(?:ов)?\s*в\s*час)?"
    r"|"
    r"\d+\s*км\s*/?\s*ч"
    r")",
    re.IGNORECASE,
)

KM_SPLIT_RE = re.compile(
    r"(?<=[.;])\s*(?=(?:километр|км\.?)\s*\d)",
    re.IGNORECASE,
)
PIKET_SPLIT_RE = re.compile(
    r"(?<=[.;])\s*(?=пикет\s*\d)",
    re.IGNORECASE,
)


@dataclass
class LogicalRecordContext:
    """10.1 — блок контекста (логическая запись)."""

    logical_record_index: int
    record_date: str | None = None
    uchastok: str | None = None
    peregon: str | None = None
    put: str | None = None
    km: str | None = None
    piket: str | None = None
    obekt: str | None = None
    comment: str | None = None
    segment_start: float | None = None
    segment_end: float | None = None


@dataclass
class PositionItem:
    """10.2 — одна позиция (параметр или дефект)."""

    position_index: int
    position_type: str
    parameter: str | None = None
    defect: str | None = None
    value: str | None = None
    unit: str | None = None
    obekt: str | None = None
    speed_limit: str | None = None
    raw_text: str = ""
    disputed_fields: list[str] = field(default_factory=list)


def _is_new_haul_block(text: str) -> bool:
    normalized = _normalize_text(text)
    return bool(re.search(r"\b(?:перегон|далее|следующ)", normalized))


def _inherit_location_fields(
    ctx: LogicalRecordContext, inherited: LogicalRecordContext, loc_text: str
) -> None:
    """При новом перегоне не наследуем путь/км/пикет — только из текущего фрагмента."""
    always = ("record_date", "uchastok")
    location = () if _is_new_haul_block(loc_text) else ("peregon", "put", "km", "piket")
    for field in (*always, *location):
        if not getattr(ctx, field) and getattr(inherited, field):
            setattr(ctx, field, getattr(inherited, field))


def _split_by_location(text: str) -> list[str]:
    """Смена км/пикета внутри блока → отдельные логические записи."""
    normalized = _normalize_text(text)
    km_count = len(re.findall(r"(?:километр|км\.?)\s*\d", normalized))
    piket_count = len(re.findall(r"пикет\s*\d", normalized))

    parts = [text]
    if km_count > 1:
        parts = KM_SPLIT_RE.split(text)
        parts = [p.strip(" ,.;") for p in parts if p.strip(" ,.;")]
    if piket_count > 1 and len(parts) == 1:
        parts = PIKET_SPLIT_RE.split(text)
        parts = [p.strip(" ,.;") for p in parts if p.strip(" ,.;")]

    return parts if parts else [text]


def extract_logical_record_context(
    text: str,
    logical_record_index: int,
    segment_start: float | None,
    segment_end: float | None,
) -> LogicalRecordContext:
    normalized = _normalize_text(text)
    dummy = ParsedRecord()
    return LogicalRecordContext(
        logical_record_index=logical_record_index,
        record_date=_extract_date(normalized),
        uchastok=_extract_uchastok(normalized),
        peregon=_extract_peregon(normalized),
        put=_extract_put(normalized),
        km=_extract_km(normalized),
        piket=_extract_piket(normalized),
        comment=_extract_comment(normalized, dummy),
        segment_start=segment_start,
        segment_end=segment_end,
    )


def _speed_limit_positions(text: str) -> list[tuple[int, int]]:
    normalized = _normalize_text(text)
    spans: list[tuple[int, int]] = []
    for marker in SPEED_LIMIT_MARKERS:
        start = 0
        while True:
            pos = normalized.find(marker, start)
            if pos < 0:
                break
            end = len(text)
            for kw in POSITION_ANCHOR_KEYWORDS:
                kw_pos = normalized.find(kw, pos + len(marker))
                if kw_pos > pos and kw_pos < end:
                    end = kw_pos
            spans.append((pos, end))
            start = pos + 1
    for match in _SPEED_LIMIT_ANCHOR_RE.finditer(normalized):
        spans.append((match.start(), match.end()))
    if not spans:
        return spans
    spans.sort(key=lambda x: x[0])
    merged: list[tuple[int, int]] = [spans[0]]
    for start, end in spans[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _anchor_is_defect_label_before_real_defect(normalized: str, pos: int, kw: str) -> bool:
    """«неисправность уширение…» — одна позиция, метка не якорь."""
    if kw not in DEFECT_LABEL_PREFIXES:
        return False
    tail = normalized[pos + len(kw):].lstrip(" :-")
    if _extract_compound_defect(tail):
        return True
    return any(
        dk in tail for dk in DEFECT_KEYWORDS if dk not in DEFECT_LABEL_PREFIXES
    )


def split_into_position_fragments(text: str) -> list[str]:
    """Разбивает текст логической записи на фрагменты — по одному на позицию."""
    normalized = _normalize_text(text)
    anchors: list[tuple[int, str]] = []

    for kw in sorted(POSITION_ANCHOR_KEYWORDS, key=len, reverse=True):
        start = 0
        while True:
            pos = normalized.find(kw, start)
            if pos < 0:
                break
            occupied = any(a <= pos < b for a, b in _speed_limit_positions(text))
            if not occupied and not _anchor_is_defect_label_before_real_defect(normalized, pos, kw):
                anchors.append((pos, kw))
            start = pos + len(kw)

    for pos, end in _speed_limit_positions(text):
        anchors.append((pos, "__speed_limit__"))

    if not anchors:
        return [text.strip()] if text.strip() else []

    anchors.sort(key=lambda x: x[0])
    unique: list[tuple[int, str]] = []
    seen: set[int] = set()
    for pos, kw in anchors:
        if pos not in seen:
            seen.add(pos)
            unique.append((pos, kw))

    fragments: list[str] = []
    for i, (pos, _) in enumerate(unique):
        end_pos = unique[i + 1][0] if i + 1 < len(unique) else len(text)
        frag = text[pos:end_pos].strip(" ,.;")
        if not frag:
            continue
        if i == 0 and pos > 0:
            prefix = text[:pos].strip(" ,.;")
            if prefix and not _extract_parameter(_normalize_text(prefix)):
                frag = f"{prefix} {frag}".strip()
        fragments.append(frag)

    if not fragments:
        return _split_multi_defects(text) or [text.strip()]
    return fragments


def parse_position(fragment: str, position_index: int) -> PositionItem:
    """Извлекает ровно одну позицию из фрагмента (правило 10.3)."""
    normalized = _normalize_text(fragment)
    raw = fragment.strip()
    obekt = _extract_obekt(normalized)

    for marker in SPEED_LIMIT_MARKERS:
        if marker in normalized:
            sp = extract_speed_limit(normalized)
            if sp:
                return PositionItem(
                    position_index=position_index,
                    position_type="speed_limit",
                    parameter="ограничение скорости",
                    value=sp,
                    unit="км/ч",
                    speed_limit=sp,
                    raw_text=raw,
                )

    sp = extract_speed_limit(normalized)
    if sp and (
        re.search(r"\bскорост(?:ь|и)\s+\d+", normalized, re.IGNORECASE)
        or re.search(r"ограничени[ея]\s+\d+", normalized, re.IGNORECASE)
    ):
        if not _extract_defect(normalized) and not _extract_parameter(normalized):
            return PositionItem(
                position_index=position_index,
                position_type="speed_limit",
                parameter="ограничение скорости",
                value=sp,
                unit="км/ч",
                speed_limit=sp,
                raw_text=raw,
            )

    param = _extract_parameter(normalized)
    defect = _extract_defect(normalized)

    if param and defect:
        if _extract_compound_defect(normalized):
            param = None
            defect = _extract_compound_defect(normalized)
        elif normalized.find(param) <= normalized.find(defect):
            defect = None
        else:
            param = None

    if param:
        after = normalized.split(param, 1)[-1].strip(" ,:-")
        value, unit = _extract_value_unit(after)
        item = PositionItem(
            position_index=position_index,
            position_type="parameter",
            parameter=param,
            value=value,
            unit=unit,
            obekt=obekt,
            raw_text=raw,
        )
        if not value:
            item.disputed_fields.append("value")
        return item

    if defect:
        after = normalized.split(defect.split()[0], 1)[-1].strip(" ,:-")
        value, unit = _extract_value_unit(after)
        full_defect = defect
        if defect == "отсутствует" or defect.startswith("отсутств"):
            tail = normalized[normalized.find(defect.split()[0]):].strip(" ,.;")
            full_defect = tail[:120]
        item = PositionItem(
            position_index=position_index,
            position_type="defect",
            defect=full_defect,
            value=value,
            unit=unit,
            obekt=obekt,
            raw_text=raw,
        )
        speed = extract_speed_limit(normalized)
        if speed:
            item.speed_limit = speed
            cleaned = strip_speed_limit_phrases(full_defect).strip()
            if cleaned and not is_speed_parameter(cleaned):
                item.defect = cleaned
            elif is_speed_parameter(full_defect) or is_speed_parameter(cleaned):
                item.defect = None
        if not value and "трещина" not in defect:
            item.disputed_fields.append("value")
        return item

    mentions = _find_all_mentions(normalized, list(POSITION_ANCHOR_KEYWORDS))
    if mentions:
        kw, _ = mentions[0]
        after = normalized.split(kw, 1)[-1].strip(" ,:-")
        value, unit = _extract_value_unit(after)
        ptype = "defect" if kw in DEFECT_KEYWORDS else "parameter"
        return PositionItem(
            position_index=position_index,
            position_type=ptype,
            parameter=kw if ptype == "parameter" else None,
            defect=kw if ptype == "defect" else None,
            value=value,
            unit=unit,
            obekt=obekt,
            raw_text=raw,
        )

    return PositionItem(
        position_index=position_index,
        position_type="parameter",
        raw_text=raw,
        disputed_fields=["parameter"],
    )


def position_to_row(ctx: LogicalRecordContext, pos: PositionItem) -> ParsedRecord:
    """Long-строка = контекст логической записи + одна позиция."""
    side_note = extract_rail_side_note(pos.raw_text)
    row = ParsedRecord(
        record_date=ctx.record_date,
        uchastok=ctx.uchastok,
        peregon=ctx.peregon,
        put=ctx.put,
        km=ctx.km,
        piket=ctx.piket,
        comment=merge_comment(ctx.comment, side_note) if side_note else ctx.comment,
        segment_start=ctx.segment_start,
        segment_end=ctx.segment_end,
        logical_record_index=ctx.logical_record_index,
        logical_block_index=ctx.logical_record_index,
        position_index=pos.position_index,
        position_type=pos.position_type,
        parameter=pos.parameter,
        defect=pos.defect,
        value=pos.value,
        unit=pos.unit,
        obekt=pos.obekt,
        speed_limit=pos.speed_limit,
        raw_text=pos.raw_text,
        disputed_fields=list(pos.disputed_fields),
    )
    return row


def expand_blocks_to_canonical_rows(blocks: list[LogicalBlock]) -> list[ParsedRecord]:
    """
    1 аудио → N логических записей → M позиций = M строк long-таблицы (M ≥ N).
    """
    if not blocks:
        return []

    rows: list[ParsedRecord] = []
    logical_record_index = 0
    inherited = LogicalRecordContext(logical_record_index=0)

    for block in blocks:
        location_parts = _split_by_location(block.text)

        for loc_text in location_parts:
            side_note = extract_rail_side_note(loc_text)
            position_text = strip_rail_side_phrases(loc_text) if side_note else loc_text

            ctx = extract_logical_record_context(
                loc_text,
                logical_record_index,
                block.start,
                block.end,
            )
            if side_note:
                ctx.comment = merge_comment(ctx.comment, side_note)
            _inherit_location_fields(ctx, inherited, loc_text)

            fragments = split_into_position_fragments(position_text)
            fragments = [f for f in fragments if not is_rail_side_only_fragment(f)]
            if not fragments and not side_note:
                fragments = [loc_text]
            elif not fragments and side_note:
                fragments = [position_text] if position_text.strip() else []

            for pos_idx, frag in enumerate(fragments):
                pos = parse_position(frag, pos_idx)
                rows.append(position_to_row(ctx, pos))

            for field in ("record_date", "uchastok", "peregon", "put", "km", "piket", "comment"):
                val = getattr(ctx, field)
                if val:
                    setattr(inherited, field, val)

            logical_record_index += 1

    return rows


def count_logical_records_and_positions(
    blocks: list[LogicalBlock],
    rows: list[ParsedRecord],
) -> dict:
    n_records = len({r.logical_record_index for r in rows if r.logical_record_index is not None})
    if not n_records and blocks:
        n_records = len(blocks)
    return {
        "logical_records": n_records,
        "positions": len(rows),
        "logical_blocks": len(blocks),
        "table_rows": len(rows),
        "positions_per_record": round(len(rows) / n_records, 2) if n_records else 0,
    }


def enforce_single_position_per_row(rows: list[ParsedRecord]) -> list[ParsedRecord]:
    """10.3: если в строке несколько параметров/дефектов — разбить."""
    result: list[ParsedRecord] = []
    for row in rows:
        normalized = _normalize_text(row.raw_text or "")
        fragments = split_into_position_fragments(row.raw_text or "")
        if len(fragments) <= 1:
            result.append(row)
            continue

        ctx = LogicalRecordContext(
            logical_record_index=row.logical_record_index or row.logical_block_index or 0,
            record_date=row.record_date,
            uchastok=row.uchastok,
            peregon=row.peregon,
            put=row.put,
            km=row.km,
            piket=row.piket,
            obekt=row.obekt,
            comment=row.comment,
            segment_start=row.segment_start,
            segment_end=row.segment_end,
        )
        for pos_idx, frag in enumerate(fragments):
            pos = parse_position(frag, pos_idx)
            result.append(position_to_row(ctx, pos))
    return result
