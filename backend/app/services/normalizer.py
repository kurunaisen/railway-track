"""Шаг 6: нормализация извлечённых значений."""

from __future__ import annotations

import re

from app.services.km_parse import merge_hesitated_km_value
from app.services.parser import ParsedRecord
from app.services.peregons import normalize_peregon
from app.services.locations import is_peregon_haul
from app.services.stations import normalize_station_name

ORDINAL_PUT = {
    "перв": "1",
    "втор": "2",
    "трет": "3",
    "четверт": "4",
    "пят": "5",
    "шест": "6",
    "седьм": "7",
    "восьм": "8",
    "девят": "9",
    "десят": "10",
}

UNIT_NORMALIZE = {
    "миллиметр": "мм",
    "миллиметров": "мм",
    "миллиметра": "мм",
    "мм": "мм",
    "сантиметр": "см",
    "сантиметров": "см",
    "см": "см",
    "километров в час": "км/ч",
    "км/ч": "км/ч",
    "км в час": "км/ч",
    "градус": "°",
    "градусов": "°",
    "промилле": "‰",
    "метр": "м",
    "м": "м",
}


def normalize_put(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    if v.isdigit():
        return v
    for stem, num in ORDINAL_PUT.items():
        if stem in v:
            return num
    m = re.search(r"(\d+)", v)
    return m.group(1) if m else value


def normalize_piket(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    v = re.sub(r"\s*плюс\s*", "+", v)
    v = re.sub(r"\s+", "", v)
    v = v.replace(",", ".")
    return v


def normalize_unit(value: str | None) -> str | None:
    if not value:
        return value
    v = value.strip().lower()
    for key, norm in UNIT_NORMALIZE.items():
        if key in v or v == key:
            return norm
    return value


def normalize_km(value: str | None) -> str | None:
    if not value:
        return value
    return merge_hesitated_km_value(value)


def normalize_speed(value: str | None) -> str | None:
    if not value:
        return value
    m = re.search(r"(\d+)", value)
    return m.group(1) if m else value


def normalize_record(record: ParsedRecord) -> ParsedRecord:
    if record.peregon and is_peregon_haul(record.peregon):
        record.peregon = normalize_peregon(record.peregon)
    elif record.peregon:
        record.uchastok = normalize_station_name(record.peregon) or record.uchastok
        record.peregon = None
    if record.uchastok:
        record.uchastok = normalize_station_name(record.uchastok)
    record.put = normalize_put(record.put)
    record.km = normalize_km(record.km)
    record.piket = normalize_piket(record.piket)
    record.unit = normalize_unit(record.unit)
    record.speed_limit = normalize_speed(record.speed_limit)
    if record.value:
        record.value = record.value.replace(",", ".").strip()
    return record


def normalize_all(records: list[ParsedRecord]) -> list[ParsedRecord]:
    return [normalize_record(r) for r in records]
