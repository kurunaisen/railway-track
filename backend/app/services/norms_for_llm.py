"""
Выжимка норм 2288р / 436/р для промпта LLM — из тех же таблиц, что apply_track_norms.
"""

from __future__ import annotations

from app.config import settings
from app.services.gauge_norms import (
    GAUGE_SWITCH_1520,
    GAUGE_TRACK_1520,
    GaugeProfile,
    SpeedBand,
)
from app.services.instruction_refs import (
    INSTRUCTION_2288_REF,
    INSTRUCTION_436_GAUGE,
    INSTRUCTION_436_REF,
)
from app.services.track_norms import JOINT_GAP_RULE, TrackNormRule

_NORM_PRINCIPLES = (
    "Превышение допустимой нормы → defect_text (например «уширение рельсовой колеи»), не parameter.",
    "V огр. в JSON не заполняй — его рассчитывает бэкенд по нормам. Исключение: инспектор явно назвал скорость в тексте.",
    "Явная скорость в тексте («ограничение скорости 60», «скорость не более 40») → отдельный item с position_type speed_limit.",
    "Числа вроде «1400» рядом с шириной колеи — шум ASR, не km_value; ширина 1512–1548 мм.",
)


def _format_band(band: SpeedBand, *, unit: str = "мм") -> str:
    low = band.above
    high = band.up_to
    if band.closed and high is None:
        return f"св. {low:g} {unit} — движение закрывается"
    if band.speed_kmh is None:
        if low == 0 and high is not None:
            return f"до {high:g} {unit} — норма"
        if high is not None:
            return f"св. {low:g} до {high:g} {unit} — норма"
        return f"св. {low:g} {unit} — норма"
    if high is not None:
        return f"св. {low:g} до {high:g} {unit} — {band.speed_kmh} км/ч"
    return f"св. {low:g} {unit} — {band.speed_kmh} км/ч"


def _rule_bands_payload(rule: TrackNormRule) -> list[dict]:
    return [
        {
            "above": band.above,
            "up_to": band.up_to,
            "speed_kmh": band.speed_kmh,
            "closed": band.closed,
            "text": _format_band(band),
        }
        for band in rule.bands
    ]


def _gauge_profile_payload(profile: GaugeProfile, *, ref: str, context: str) -> dict:
    return {
        "id": profile.id,
        "context": context,
        "ref": ref,
        "nominal_mm": profile.nominal_mm,
        "normal_range_mm": [profile.min_normal_mm, profile.max_normal_mm],
        "absolute_range_mm": [profile.absolute_min_mm, profile.absolute_max_mm],
        "widen_bands": [_format_band(b) for b in profile.widen_bands],
        "narrow_bands": [_format_band(b) for b in profile.narrow_bands],
    }


def build_norms_reference() -> dict:
    """Структурированные нормы для user payload LLM."""
    line_max = settings.max_track_speed_kmh
    return {
        "sources": {
            "2288r": INSTRUCTION_2288_REF,
            "436r": INSTRUCTION_436_REF,
            "436r_gauge": INSTRUCTION_436_GAUGE,
        },
        "line_max_speed_kmh": line_max,
        "principles": list(_NORM_PRINCIPLES),
        "rules": [
            {
                "id": JOINT_GAP_RULE.id,
                "title": JOINT_GAP_RULE.title,
                "keywords": list(JOINT_GAP_RULE.keywords),
                "ref": "2288р, табл. 4.2",
                "unit": JOINT_GAP_RULE.unit,
                "bands": _rule_bands_payload(JOINT_GAP_RULE),
            },
            _gauge_profile_payload(
                GAUGE_TRACK_1520,
                ref="436/р прил. 2 табл. П.2.1; допуск содержания 2288р табл. 2.4",
                context="путь, перегон",
            ),
            _gauge_profile_payload(
                GAUGE_SWITCH_1520,
                ref="2288р п. 3.4.3, табл. 3.6; 436/р §5.7",
                context="стрелочный перевод, стрелка, крестовина",
            ),
        ],
        "examples": [
            {
                "measurement_mm": 1543,
                "context": "уширение колеи на пути",
                "defect": GAUGE_TRACK_1520.widen_title,
                "speed_limit_kmh": 60,
                "ref": "436/р П.2.1",
            },
            {
                "measurement_mm": 25,
                "context": "стыковой зазор",
                "defect": JOINT_GAP_RULE.title,
                "speed_limit_kmh": 100,
                "ref": "2288р табл. 4.2",
            },
        ],
    }


def build_norms_summary_for_llm() -> str:
    """Компактный текст норм для system prompt / payload."""
    ref = build_norms_reference()
    lines = [
        "Нормативная база (автогенерация из gauge_norms / track_norms):",
        f"- {ref['sources']['2288r']}",
        f"- {ref['sources']['436r']}; геометрия колеи: {ref['sources']['436r_gauge']}",
        f"- Макс. скорость на участке (лимит записи V огр.): {ref['line_max_speed_kmh']} км/ч",
        "",
        "Принципы:",
        *[f"- {p}" for p in ref["principles"]],
        "",
        f"Стыковой зазор ({JOINT_GAP_RULE.title}, 2288р табл. 4.2):",
        *[f"- {b['text']}" for b in ref["rules"][0]["bands"]],
        "",
        f"Ширина колеи на пути, номинал {GAUGE_TRACK_1520.nominal_mm} мм "
        f"(допуск {GAUGE_TRACK_1520.min_normal_mm}–{GAUGE_TRACK_1520.max_normal_mm}, 2288р табл. 2.4; "
        f"V огр. 436/р П.2.1):",
        *[f"- уширение: {b}" for b in ref["rules"][1]["widen_bands"]],
        *[f"- сужение: {b}" for b in ref["rules"][1]["narrow_bands"]],
        "",
        f"Ширина на стрелочном переводе, номинал {GAUGE_SWITCH_1520.nominal_mm} мм "
        f"(допуск {GAUGE_SWITCH_1520.min_normal_mm}–{GAUGE_SWITCH_1520.max_normal_mm}, 2288р; макс. {GAUGE_SWITCH_1520.absolute_max_mm}):",
        *[f"- уширение: {b}" for b in ref["rules"][2]["widen_bands"]],
        *[f"- сужение: {b}" for b in ref["rules"][2]["narrow_bands"]],
    ]
    for ex in ref["examples"]:
        lines.append(
            f"Пример классификации: {ex['measurement_mm']} мм ({ex['context']}) → "
            f"defect «{ex['defect']}» ({ex['ref']}). V огр. в JSON не указывай."
        )
    return "\n".join(lines)
