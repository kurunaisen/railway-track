"""Наследование контекста станции на следующие строки (LLM иногда возвращает перегон)."""

from __future__ import annotations

import re

from app.services.locations import is_peregon_haul
from app.services.parser import ParsedRecord
from app.services.stations import CANONICAL_STATIONS, normalize_station_name

_PEREGON_WORD_RE = re.compile(r"\bперегон\b", re.IGNORECASE)


def _is_peregon_binding_row(record: ParsedRecord) -> bool:
    return bool(
        record.peregon
        and is_peregon_haul(record.peregon)
        and (record.km or record.piket)
    )


def _station_from_record(record: ParsedRecord) -> str | None:
    if not record.uchastok:
        return None
    station = normalize_station_name(record.uchastok)
    if station in CANONICAL_STATIONS and not (record.peregon and is_peregon_haul(record.peregon)):
        return station
    if station in CANONICAL_STATIONS and record.put:
        return station
    return None


def propagate_station_context(records: list[ParsedRecord]) -> list[ParsedRecord]:
    """
    После «на станции … N путь» строки без км/пк не должны тащить перегон с LLM.
    «… болт И уширение колеи 1543» → та же станция и путь.
    """
    active_station: str | None = None
    active_put: str | None = None

    for record in records:
        if _is_peregon_binding_row(record):
            active_station = None
            active_put = None

        station = _station_from_record(record)
        if station:
            active_station = station
            if record.put:
                active_put = record.put

        if not active_station:
            continue

        if not (record.peregon and is_peregon_haul(record.peregon)):
            continue
        if record.km or record.piket:
            continue
        raw = record.raw_text or ""
        if _PEREGON_WORD_RE.search(raw):
            continue

        record.uchastok = active_station
        record.put = record.put or active_put
        record.peregon = None
        record.km = None
        record.piket = None

    return records
