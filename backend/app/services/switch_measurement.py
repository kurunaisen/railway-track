"""
Контрольные точки промера на стрелочном переводе (2288р §3.4).

«Острие остряка» — указатель места промера → колонка «Примечание», не отдельная строка.
"""

from __future__ import annotations

import re

from app.services.parser import ParsedRecord, _normalize_text
from app.services.rail_side import merge_comment

_SWITCH_TIP_RE = re.compile(
    r"остри[ея]\s+остряк(?:а|ов|е|ом)?",
    re.IGNORECASE,
)
_RAM_RAIL_WEAR_RE = re.compile(
    r"износ\s+рамн(?:ого|ом|ые)?\s+рельс(?:а|ов|е|ом)?",
    re.IGNORECASE,
)
_TIP_ONLY_ROW_RE = re.compile(
    r"^(?:остри[ея]\s+остряк(?:а|ов|е|ом)?|остряк(?:а|ов|е|ом)?)\s*(?:пусть|путь)?\s*\d*\s*(?:мм)?\.?$",
    re.IGNORECASE,
)
_SWITCH_PATH_KEEP_RE = re.compile(
    r"колеи|крестовин|остряк|сердечник|износ|стрелоч",
    re.IGNORECASE,
)
_SLEEPER_CLUSTER_RE = re.compile(r"куст|шпал", re.IGNORECASE)

SWITCH_TIP_NOTE = "в острии остряка"


def has_switch_tip_measurement(text: str) -> bool:
    return bool(_SWITCH_TIP_RE.search(text or ""))


def has_ram_rail_wear(text: str) -> bool:
    return bool(_RAM_RAIL_WEAR_RE.search(text or ""))


def path_block_keeps_switch_context(text: str) -> bool:
    """Путь 15 у стрелки — стр.п. сохраняем; путь 12 с кустом шпал — нет."""
    normalized = _normalize_text(text)
    if _SLEEPER_CLUSTER_RE.search(normalized) and not _SWITCH_PATH_KEEP_RE.search(normalized):
        return False
    return True


def _enrich_wear_at_switch_tip(record: ParsedRecord) -> None:
    raw = record.raw_text or ""
    if not has_switch_tip_measurement(raw) or not has_ram_rail_wear(raw):
        return
    record.comment = merge_comment(record.comment, SWITCH_TIP_NOTE)
    record.obekt = None
    record.parameter = None
    record.position_type = "defect"


def _is_spurious_switch_tip_row(record: ParsedRecord) -> bool:
    raw = (record.raw_text or "").strip()
    if not raw or not has_switch_tip_measurement(raw):
        return False
    if has_ram_rail_wear(raw):
        return False
    if record.defect and record.defect.lower().startswith("износ"):
        return False
    normalized = re.sub(r"\s+", " ", raw).strip()
    if _TIP_ONLY_ROW_RE.match(normalized):
        return True
    if record.defect and "остри" in record.defect.lower() and not record.obekt:
        val = record.value
        if val:
            try:
                if float(val.replace(",", ".")) < 30:
                    return True
            except ValueError:
                pass
    return False


def apply_switch_measurement_context(records: list[ParsedRecord]) -> list[ParsedRecord]:
    """Точка промера → примечание только у износа; ложные строки отбрасываем."""
    result: list[ParsedRecord] = []
    for record in records:
        if _is_spurious_switch_tip_row(record):
            continue
        _enrich_wear_at_switch_tip(record)
        if record.comment and SWITCH_TIP_NOTE in record.comment.lower():
            if not has_ram_rail_wear(record.raw_text or "") and not (
                record.defect and "рамн" in record.defect.lower()
            ):
                parts = [p.strip() for p in record.comment.split(";") if p.strip().lower() != SWITCH_TIP_NOTE]
                record.comment = "; ".join(parts) if parts else None
        result.append(record)
    return result
