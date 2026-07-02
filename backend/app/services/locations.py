"""Извлечение и форматирование местоположения для таблицы обхода."""

from __future__ import annotations

import re

from app.services.peregons import normalize_peregon
from app.services.railway_explications import match_station_by_park
from app.services.stations import (
    CANONICAL_STATIONS,
    match_location_in_text,
    normalize_blockpost,
    normalize_station_name,
)

_DASH_RE = re.compile(r"[-–—]")
_HAUL_SEP_RE = re.compile(r"\s+[-–—]\s+")
_STATION_PREFIX_RE = re.compile(
    r"(?:^|\s)(?:на\s+)?станци[яи]\s+(.+?)(?:\s*,|\s+путь|\s+главн|\s+стрелоч|\s+блок|\s+км|\s+километр|\s+пикет|$)",
    re.IGNORECASE,
)
_PEREGON_PREFIX_RE = re.compile(r"\bперегон\b", re.IGNORECASE)


def _is_known_single_station(value: str) -> bool:
    """Станция с дефисом в названии (Комсомольск-Мурманский) — не перегон."""
    text = value.strip()
    if text in CANONICAL_STATIONS:
        return True
    norm = normalize_station_name(text)
    return bool(norm and norm == text and norm in CANONICAL_STATIONS)


def is_peregon_haul(value: str | None) -> bool:
    """Перегон — два пункта через тире или явное слово «перегон» в значении."""
    if not value:
        return False
    text = value.strip()
    if _PEREGON_PREFIX_RE.search(text):
        return True
    if not _DASH_RE.search(text):
        return False
    if _is_known_single_station(text):
        return False
    norm = normalize_peregon(text)
    if norm and _DASH_RE.search(norm):
        return True
    if _HAUL_SEP_RE.search(text):
        return True
    parts = _DASH_RE.split(text, maxsplit=1)
    return len(parts) == 2 and all(p.strip() for p in parts)


def _strip_station_prefix(value: str) -> str:
    text = value.strip()
    m = _STATION_PREFIX_RE.search(text)
    if m:
        return m.group(1).strip()
    return re.sub(r"^(?:на\s+)?станци[яи]\s+", "", text, flags=re.IGNORECASE).strip()


def extract_single_location(*texts: str | None) -> str | None:
    """
    Одна точка: станция или блок-пост с километром.
    «станция Мурманск» → Мурманск; «Блокпост 1381 км» → как есть.
    Блокпост без номера км не считается местоположением.
    """
    for text in texts:
        if not text:
            continue
        raw = text.strip()
        if not raw:
            continue

        if is_peregon_haul(raw):
            continue

        stripped = _strip_station_prefix(raw)
        park_match = match_station_by_park(stripped)
        if park_match:
            return park_match[0]

        blockpost = normalize_blockpost(stripped)
        if blockpost:
            return blockpost

        if stripped:
            head = re.split(r"[,]", stripped)[0].strip().split()[0]
            canon = normalize_station_name(head)
            if canon and canon != head:
                return canon
            if canon in CANONICAL_STATIONS:
                return canon

        matched = match_location_in_text(stripped)
        if matched:
            return matched

        park_match = match_station_by_park(raw)
        if park_match:
            return park_match[0]

        if re.search(r"^станци[яи]\s+", raw, re.IGNORECASE):
            name = _strip_station_prefix(raw)
            return normalize_station_name(name) or name

        matched = match_location_in_text(raw)
        if matched:
            return matched

    return None


def format_peregon_display(peregon: str) -> str:
    normalized = normalize_peregon(peregon) or peregon.strip()
    return normalized.replace(" — ", "-").replace(" – ", "-").replace("—", "-")


def format_location_for_table(
    *,
    peregon: str | None = None,
    uchastok: str | None = None,
    raw_text: str | None = None,
    comment: str | None = None,
) -> str:
    """
    Столбец «Местонахождение»:
    - перегон → «Кица-Блокпост 1381 км»
    - «станция Мурманск» / «Мурманск» → «Мурманск»
    - «Блокпост 1381 км» / «О.П. 1381 км» → «Блокпост 1381 км» (всегда с километром)
    """
    if peregon and is_peregon_haul(peregon):
        return format_peregon_display(peregon)

    for candidate in (uchastok, peregon):
        if not candidate:
            continue
        single = extract_single_location(candidate)
        if single:
            return single
        cleaned = _strip_station_prefix(candidate)
        normalized = normalize_station_name(cleaned)
        if normalized:
            return normalized

    from_text = extract_single_location(raw_text, comment)
    if from_text:
        return from_text

    if uchastok:
        return _strip_station_prefix(uchastok)
    if peregon:
        return format_peregon_display(peregon) if is_peregon_haul(peregon) else _strip_station_prefix(peregon)
    return ""
