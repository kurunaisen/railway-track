"""Справочник станций и блок-постов Мурманского направления (ТР-4, участки Кандалaksha — Кола, Кола — Мурманск, Мурманск — Ваенга)."""

from __future__ import annotations

import re

# Станции и раздельные пункты (географический порядок: Кандalaksha → Ваенга)
CANONICAL_STATIONS: tuple[str, ...] = (
    "\u041a\u0430\u043d\u0434\u0430\u043b\u0430\u043a\u0448\u0430",
    "Алюминиевый Завод",
    "Плесозеро",
    "ГЭС-2",
    "Нивский",
    "Пинозеро",
    "Полярные Зори",
    "Восточная Губа",
    "Африканда",
    "Хабозеро",
    "Питкуль",
    "Апатиты",
    "Хибины",
    "Нефелиновые Пески",
    "Имандра",
    "Рудный",
    "Куна",
    "Ягельный Бор",
    "Оленегорск",
    "Лапландия",
    "Пулозеро",
    "Тайбола",
    "Кица",
    "Лопарская",
    "Магнетиты",
    "Тухта",
    "Шонгуй",
    "Выходной",
    "Молочный",
    "Кольский Острог",
    "Кола",
    "Мурманск",
    "Комсомольск-Мурманский",
    "Промышленная",
    "Сафоново-Мурманское",
    "Ваенга",
)

CANONICAL_BLOCKPOSTS: tuple[str, ...] = (
    "Блокпост 1268 км",
    "Блокпост 1297 км",
    "Блокпост 1303 км",
    "Блокпост 1381 км",
    "Блокпост 1391 км",
    "Блокпост 1425 км",
    "Блокпост 1439 км",
    "Блокпост 1441 км",
    "Блокпост 1443 км",
    "Блокпост 1446 км",
    "Блокпост 1448 км",
    "Блокпост 15 км",
)

CANONICAL_LOCATIONS: tuple[str, ...] = CANONICAL_STATIONS + CANONICAL_BLOCKPOSTS

LOCATION_ALIASES: dict[str, str] = {
    "апатиты 1": "Апатиты",
    "апатиты-1": "Апатиты",
    "апатиты i": "Апатиты",
    "комсомольск мурманский": "Комсомольск-Мурманский",
    "комсомольск-мурманский": "Комсомольск-Мурманский",
    "магнититы": "Магнетиты",
    "магнитит": "Магнетиты",
}

for _km in (1268, 1297, 1303, 1381, 1391, 1425, 1439, 1441, 1443, 1446, 1448, 15):
    canonical = f"Блокпост {_km} км"
    for prefix in (
        f"блокпост {_km}",
        f"блок-пост {_km}",
        f"блок пост {_km}",
        f"о.п. {_km}",
        f"оп {_km}",
        f"ост. пункт {_km}",
        f"остановочный пункт {_km}",
        f"ост пункт {_km}",
    ):
        LOCATION_ALIASES[prefix] = canonical

_LOCATION_KEY_RE = re.compile(r"\s*[-–—]\s*")


def _location_key(value: str) -> str:
    s = value.strip().lower()
    s = s.replace("ё", "е")
    s = _LOCATION_KEY_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


_CANONICAL_BY_KEY = {_location_key(name): name for name in CANONICAL_LOCATIONS}
for alias, canonical in LOCATION_ALIASES.items():
    _CANONICAL_BY_KEY.setdefault(_location_key(alias), canonical)

_LOCATIONS_BY_LENGTH = sorted(CANONICAL_LOCATIONS, key=len, reverse=True)


def normalize_station_name(value: str | None) -> str | None:
    if not value:
        return value

    raw = value.strip()
    if not raw:
        return None

    blockpost = normalize_blockpost(raw)
    if blockpost:
        return blockpost

    key = _location_key(raw)
    if key in _CANONICAL_BY_KEY:
        return _CANONICAL_BY_KEY[key]

    return raw


def normalize_blockpost(value: str) -> str | None:
    text = value.strip()
    if not text:
        return None

    key = _location_key(text)
    if key in _CANONICAL_BY_KEY:
        found = _CANONICAL_BY_KEY[key]
        if found.startswith("Блокпост"):
            return found

    m = re.search(
        r"(?:блок\s*[- ]?пост|блокпост|о\.?\s*п\.?|остановочн\w+\s+пункт|ост\.?\s*пункт)\s*(\d+)\s*(?:км\.?)?",
        text,
        re.IGNORECASE,
    )
    if m:
        return f"Блокпост {m.group(1)} км"

    return None


def match_location_in_text(text: str) -> str | None:
    if not text:
        return None
    norm = text.replace("ё", "е").replace("Ё", "Е")

    blockpost = normalize_blockpost(norm)
    if blockpost:
        return blockpost

    for name in _LOCATIONS_BY_LENGTH:
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.IGNORECASE)
        if pattern.search(norm):
            return name

    return None


def station_names_for_prompt() -> str:
    return "; ".join([*CANONICAL_STATIONS, *CANONICAL_BLOCKPOSTS])
