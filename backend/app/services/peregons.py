"""Справочник перегонов и синонимов (Мурманское направление)."""

from __future__ import annotations

import re

# Канонические названия перегонов
CANONICAL_PEREGONS: tuple[str, ...] = (
    "Лапландия — Пулозеро",
    "Пулозеро — Тайбола",
    "Тайбола — Блокпост 1381 км",
    "Блокпост 1381 км — Кица",
    "Кица — Блокпост 1391 км",
    "Блокпост 1391 км — Лопарская",
    "Лопарская — Магнетиты",
    "Магнетиты — Шонгуй",
    "Магнетиты — Блокпост 1425 км",
    "Блокпост 1425 км — Выходной",
    "Выходной — Кола",
    "Кола — Мурманск",
    "Мурманск — Комсомольск-Мурманский",
    "Комсомольск-Мурманский — Промышленная",
    "Комсомольск-Мурманский — Блокпост 15 км",
    "Блокпост 15 км — Ваенга",
    "Комсомольск-Мурманский — Ваенга",
)

# Синонимы → канон (ключи в нормализованном виде, см. _peregon_key)
PEREGON_ALIASES: dict[str, str] = {
    "тайбола — блокпост": "Тайбола — Блокпост 1381 км",
    "магнетиты — блокпост": "Магнетиты — Блокпост 1425 км",
    "комсомольск — промышленная": "Комсомольск-Мурманский — Промышленная",
    "комсомольск — ваенга": "Комсомольск-Мурманский — Ваенга",
    "комсомольск-мурманский — промышленная": "Комсомольск-Мурманский — Промышленная",
    "комсомольск-мурманский — ваенга": "Комсомольск-Мурманский — Ваенга",
}


def _peregon_key(value: str) -> str:
    s = value.strip().lower()
    s = s.replace("ё", "е")
    s = re.sub(r"\s*[-–—]\s*", " — ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


_CANONICAL_BY_KEY = {_peregon_key(c): c for c in CANONICAL_PEREGONS}


def _fix_asr_typos(value: str) -> str:
    """Типичные ошибки ASR для станции Комсомольск-Мурманский."""
    s = value
    s = re.sub(
        r"комсомольск\s*[-–—]?\s*м[уy][rр]?манск(?:ий|ий|ий)?",
        "Комсомольск-Мурманский",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"комсомольск\s*[-–—]\s*(?!мурманский)",
        "Комсомольск-Мурманский — ",
        s,
        flags=re.IGNORECASE,
    )
    return s


def normalize_peregon(value: str | None) -> str | None:
    if not value:
        return value

    fixed = _fix_asr_typos(value.strip())
    key = _peregon_key(fixed)

    if key in PEREGON_ALIASES:
        return PEREGON_ALIASES[key]

    if key in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[key]

    # «Комсомольск — …» без «Мурманский» в первой части
    if key.startswith("комсомольск — ") and "мурманский" not in key.split(" — ", 1)[0]:
        expanded = key.replace("комсомольск — ", "комсомольск-мурманский — ", 1)
        if expanded in PEREGON_ALIASES:
            return PEREGON_ALIASES[expanded]
        if expanded in _CANONICAL_BY_KEY:
            return _CANONICAL_BY_KEY[expanded]

    normalized = re.sub(r"\s*[-–—]\s*", " — ", fixed.strip())
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def peregon_names_for_prompt() -> str:
    return "; ".join(CANONICAL_PEREGONS)
