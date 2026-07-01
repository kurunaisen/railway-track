"""
Ширина рельсовой колеи — Инструкция 436/р (оценка ГРК, ред. 09.11.2020).

§5.7 — номинал 1520 мм, абсолют 1512–1548 мм, стрелки макс. 1546 мм.
Табл. 6.1 — степени I–IV по отклонению от номинала (зависит от V уст.).
Прил. 2, табл. П.2.1 — V огр. по фактической ширине (участки ≤140 км/ч).

Допуск содержания +4/−8 мм (1512–1524) — 2288р, табл. 2.4 (не перенесена в 436/р).
Стрелочный перевод ±3 мм — 2288р, п. 3.4.3, табл. 3.6.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum

from app.config import settings

from app.services.instruction_refs import (
    INSTRUCTION_2288_FULL_URL,
    INSTRUCTION_436_REF,
)

INSTRUCTION_REF = INSTRUCTION_436_REF
INSTRUCTION_SOURCE_URL = INSTRUCTION_2288_FULL_URL

GAUGE_ABSOLUTE_MIN_MM = 1512
GAUGE_ABSOLUTE_MAX_MM = 1548
GAUGE_SWITCH_MAX_MM = 1546


class DeviationDegree(IntEnum):
    """Степень отступления по табл. 6.1 436/р."""

    WITHIN = 0
    I = 1
    II = 2
    III = 3
    IV = 4


@dataclass(frozen=True)
class SpeedBand:
    """Диапазон (above, up_to] мм → скорость км/ч; closed = движение закрывается."""

    above: float
    up_to: float | None
    speed_kmh: int | None = None
    closed: bool = False


def effective_norm_speed_kmh(regulation_speed: int | None) -> int | None:
    """Лимит по 436/р с учётом фактической макс. скорости на участке."""
    if regulation_speed is None:
        return None
    line_max = settings.max_track_speed_kmh
    if regulation_speed >= line_max:
        return None
    return regulation_speed


@dataclass(frozen=True)
class GaugeProfile:
    id: str
    nominal_mm: int
    max_normal_mm: int
    min_normal_mm: int
    absolute_max_mm: int
    absolute_min_mm: int
    widen_title: str
    narrow_title: str
    widen_bands: tuple[SpeedBand, ...]
    narrow_bands: tuple[SpeedBand, ...] = ()


# Табл. П.2.1 (436/р), номинал 1520, V уст. 61–100/61–80 км/ч.
GAUGE_TRACK_1520 = GaugeProfile(
    id="gauge_track_1520",
    nominal_mm=1520,
    max_normal_mm=1524,
    min_normal_mm=1512,
    absolute_max_mm=GAUGE_ABSOLUTE_MAX_MM,
    absolute_min_mm=GAUGE_ABSOLUTE_MIN_MM,
    widen_title="уширение рельсовой колеи",
    narrow_title="сужение рельсовой колеи",
    widen_bands=(
        SpeedBand(1524, 1544, 60),
        SpeedBand(1544, 1548, 25),
        SpeedBand(1548, None, None, closed=True),
    ),
    narrow_bands=(
        SpeedBand(0, 1512, None, closed=True),
    ),
)

# Стрелочный перевод: ±3 мм (2288р п. 3.4.3), макс. 1546 мм (436/р §5.7 п. 3, 2288р табл. 3.6).
GAUGE_SWITCH_1520 = GaugeProfile(
    id="gauge_switch_1520",
    nominal_mm=1520,
    max_normal_mm=1523,
    min_normal_mm=1517,
    absolute_max_mm=GAUGE_SWITCH_MAX_MM,
    absolute_min_mm=GAUGE_ABSOLUTE_MIN_MM,
    widen_title="уширение рельсовой колеи",
    narrow_title="сужение рельсовой колеи",
    widen_bands=(
        SpeedBand(1523, 1540, 60),
        SpeedBand(1540, 1546, 25),
        SpeedBand(1546, None, None, closed=True),
    ),
    narrow_bands=(
        SpeedBand(0, 1512, None, closed=True),
        SpeedBand(1512, 1517, 60),
    ),
)

GAUGE_PROFILES: tuple[GaugeProfile, ...] = (GAUGE_TRACK_1520, GAUGE_SWITCH_1520)

# Табл. 6.1 (436/р): макс. уширение/сужение от номинала, мм → степень (V уст. 61–100).
_WIDEN_DEGREE_LIMITS_1520: tuple[tuple[int, DeviationDegree], ...] = (
    (18, DeviationDegree.I),
    (20, DeviationDegree.II),
    (24, DeviationDegree.III),
)

_GAUGE_KEYWORDS = (
    "уширение",
    "сужение",
    "ширина колеи",
    "рельсовой колеи",
    "колеи",
)
_SWITCH_KEYWORDS = (
    "стрелоч",
    "перевод",
    "крестовин",
    "остряк",
    "сердечник",
    "хвост",
    "усовик",
)


def is_plausible_gauge_width_mm(value: int | float) -> bool:
    return GAUGE_ABSOLUTE_MIN_MM <= float(value) <= GAUGE_ABSOLUTE_MAX_MM


def is_gauge_context(text: str) -> bool:
    normalized = text.lower()
    return any(kw in normalized for kw in _GAUGE_KEYWORDS)


def is_switch_gauge_context(text: str) -> bool:
    normalized = text.lower()
    return any(kw in normalized for kw in _SWITCH_KEYWORDS)


def select_gauge_profile(text: str) -> GaugeProfile:
    if is_switch_gauge_context(text):
        return GAUGE_SWITCH_1520
    return GAUGE_TRACK_1520


def gauge_deviation_degree(
    width_mm: float,
    *,
    nominal_mm: int = 1520,
    widen: bool = True,
) -> DeviationDegree:
    """Степень отступления по табл. 6.1 436/р (номинал 1520, V уст. 61–100)."""
    if nominal_mm != 1520:
        return DeviationDegree.WITHIN

    if widen:
        deviation = width_mm - nominal_mm
        if deviation <= 0:
            return DeviationDegree.WITHIN
        for limit_mm, degree in _WIDEN_DEGREE_LIMITS_1520:
            if deviation <= limit_mm:
                return degree
        return DeviationDegree.IV

    deviation = nominal_mm - width_mm
    if deviation <= 0:
        return DeviationDegree.WITHIN
    narrow_limits = (6, 7, 8)
    for limit_mm, degree in zip(narrow_limits, (DeviationDegree.I, DeviationDegree.II, DeviationDegree.III)):
        if deviation <= limit_mm:
            return degree
    return DeviationDegree.IV


def _pick_band(width: float, bands: tuple[SpeedBand, ...]) -> SpeedBand | None:
    for band in bands:
        upper = band.up_to if band.up_to is not None else float("inf")
        if band.above < width <= upper:
            return band
    return None


@dataclass(frozen=True)
class GaugeEvaluation:
    profile: GaugeProfile
    width_mm: float
    defect_title: str | None
    band: SpeedBand | None
    within_tolerance: bool
    degree: DeviationDegree = DeviationDegree.WITHIN


def evaluate_gauge_width(width: float, text: str) -> GaugeEvaluation:
    profile = select_gauge_profile(text)

    # 2288р табл. 2.4: допуск содержания 1512–1524 мм — без V огр. (в т.ч. хвост крестовины).
    if GAUGE_TRACK_1520.min_normal_mm <= width <= GAUGE_TRACK_1520.max_normal_mm:
        return GaugeEvaluation(
            profile=profile,
            width_mm=width,
            defect_title=None,
            band=None,
            within_tolerance=True,
            degree=DeviationDegree.WITHIN,
        )

    if width >= profile.absolute_max_mm:
        return GaugeEvaluation(
            profile=profile,
            width_mm=width,
            defect_title=profile.widen_title,
            band=SpeedBand(profile.absolute_max_mm - 1, None, None, closed=True),
            within_tolerance=False,
            degree=DeviationDegree.IV,
        )
    if width <= profile.absolute_min_mm:
        return GaugeEvaluation(
            profile=profile,
            width_mm=width,
            defect_title=profile.narrow_title,
            band=SpeedBand(0, profile.absolute_min_mm, None, closed=True),
            within_tolerance=False,
            degree=DeviationDegree.IV,
        )

    if width > profile.max_normal_mm:
        band = _pick_band(width, profile.widen_bands)
        return GaugeEvaluation(
            profile=profile,
            width_mm=width,
            defect_title=profile.widen_title,
            band=band,
            within_tolerance=False,
            degree=gauge_deviation_degree(width, nominal_mm=profile.nominal_mm, widen=True),
        )

    if width < profile.min_normal_mm:
        band = _pick_band(width, profile.narrow_bands)
        return GaugeEvaluation(
            profile=profile,
            width_mm=width,
            defect_title=profile.narrow_title,
            band=band,
            within_tolerance=band is None,
            degree=gauge_deviation_degree(width, nominal_mm=profile.nominal_mm, widen=False),
        )

    return GaugeEvaluation(
        profile=profile,
        width_mm=width,
        defect_title=None,
        band=None,
        within_tolerance=True,
        degree=DeviationDegree.WITHIN,
    )


def gauge_speed_limit_kmh(evaluation: GaugeEvaluation) -> int | None:
    band = evaluation.band
    if not band or band.closed or band.speed_kmh is None:
        return None
    return effective_norm_speed_kmh(band.speed_kmh)
