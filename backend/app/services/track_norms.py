"""
Нормы Инструкции по текущему содержанию железнодорожного пути
(Распоряжение ОАО «РЖД» от 14.11.2016 № 2288р, табл. 4.2 и др.).

Неисправность — превышение допустимых норм. Ограничение скорости — следствие
неисправности по таблицам инструкции, если инспектор не назвал V огр. явно.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.services.rail_side import merge_comment
from app.config import settings

if TYPE_CHECKING:
    from app.services.parser import ParsedRecord

INSTRUCTION_REF = "Распоряжение ОАО «РЖД» от 14.11.2016 № 2288р"


@dataclass(frozen=True)
class SpeedBand:
    """Диапазон (above, up_to] мм → скорость км/ч; closed = движение закрывается."""

    above: float
    up_to: float | None
    speed_kmh: int | None = None
    closed: bool = False


@dataclass(frozen=True)
class TrackNormRule:
    id: str
    title: str
    keywords: tuple[str, ...]
    all_keywords: tuple[str, ...] = ()
    unit: str = "мм"
    bands: tuple[SpeedBand, ...] = ()


# Табл. 4.2 — стыковой зазор (рельсы 25 м, ø отверстия 36 мм).
JOINT_GAP_RULE = TrackNormRule(
    id="joint_gap",
    title="стыковой зазор",
    keywords=("зазор",),
    all_keywords=("стыков", "стыке", "стык"),
    bands=(
        SpeedBand(0, 24, None),
        SpeedBand(24, 26, 100),
        SpeedBand(26, 30, 60),
        SpeedBand(30, 35, 25),
        SpeedBand(35, None, None, closed=True),
    ),
)

TRACK_NORM_RULES: tuple[TrackNormRule, ...] = (JOINT_GAP_RULE,)


def _record_text(record: ParsedRecord) -> str:
    parts = [record.parameter, record.defect, record.raw_text]
    return " ".join(p.strip() for p in parts if p and p.strip()).lower()


def _parse_numeric(value: str | None) -> float | None:
    if not value:
        return None
    match = re.search(r"(\d+(?:[.,]\d+)?)", value.replace(",", "."))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _unit_matches(record_unit: str | None, expected: str) -> bool:
    if not record_unit:
        return expected == "мм"
    unit = record_unit.strip().lower()
    if expected == "мм":
        return unit in {"мм", "mm", "миллиметр", "миллиметров", "миллиметра"}
    return unit == expected


def match_track_norm_rule(text: str) -> TrackNormRule | None:
    normalized = text.lower()
    for rule in TRACK_NORM_RULES:
        if not all(kw in normalized for kw in rule.keywords):
            continue
        if rule.all_keywords and not any(kw in normalized for kw in rule.all_keywords):
            continue
        return rule
    return None


def evaluate_norm_band(value: float, rule: TrackNormRule) -> SpeedBand | None:
    for band in rule.bands:
        upper = band.up_to if band.up_to is not None else float("inf")
        if band.above < value <= upper:
            return band
    return None


def effective_norm_speed_kmh(regulation_speed: int | None) -> int | None:
    """Лимит по 2288р с учётом фактической макс. скорости на участке."""
    if regulation_speed is None:
        return None
    line_max = settings.max_track_speed_kmh
    if regulation_speed >= line_max:
        return None
    return regulation_speed


def apply_track_norms(record: ParsedRecord) -> ParsedRecord:
    """Применяет нормы 2288р: превышение → неисправность + V огр. (если не сказано устно)."""
    text = _record_text(record)
    rule = match_track_norm_rule(text)
    if not rule:
        return record

    value = _parse_numeric(record.value)
    if value is None:
        value = _parse_numeric(record.defect) or _parse_numeric(record.raw_text)
    if value is None or not _unit_matches(record.unit, rule.unit):
        return record

    band = evaluate_norm_band(value, rule)
    if band is None or (band.speed_kmh is None and not band.closed):
        return record

    if not record.defect:
        record.defect = rule.title
    if record.parameter and record.parameter.lower() in {rule.title, *rule.keywords}:
        record.parameter = None

    record.position_type = "defect"

    if band.closed:
        record.comment = merge_comment(record.comment, "движение закрывается (2288р)")
    elif not record.speed_limit and band.speed_kmh is not None:
        effective = effective_norm_speed_kmh(band.speed_kmh)
        if effective is not None:
            record.speed_limit = str(effective)

    return record


def apply_track_norms_all(records: list[ParsedRecord]) -> list[ParsedRecord]:
    return [apply_track_norms(r) for r in records]
