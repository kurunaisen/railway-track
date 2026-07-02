"""Reference data from station path and switch explication workbooks."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[1] / "data" / "railway_explications.json"

ROMAN_PATHS = {
    "I": "1",
    "II": "2",
    "III": "3",
    "IV": "4",
    "V": "5",
    "VI": "6",
    "VII": "7",
    "VIII": "8",
    "IX": "9",
    "X": "10",
}


def _key(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower().replace("ё", "е")
    text = re.sub(r"\s*[-–—]\s*", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_asset_number(value: str | None) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    roman = ROMAN_PATHS.get(text.upper())
    if roman:
        return roman
    if re.fullmatch(r"\d+/\d+", text):
        return text
    match = re.search(r"\b([IVX]+)\b\s*$", text, re.IGNORECASE)
    if match and match.group(1).upper() in ROMAN_PATHS:
        return ROMAN_PATHS[match.group(1).upper()]
    match = re.search(r"\d+", text)
    return match.group(0) if match else text


@lru_cache(maxsize=1)
def load_explications() -> dict[str, Any]:
    if not DATA_PATH.exists():
        return {
            "station_names": [],
            "station_paths": {},
            "switches": {},
        }
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _station_by_key() -> dict[str, str]:
    data = load_explications()
    return {_key(station): station for station in data.get("station_names", [])}


def explication_station_names() -> tuple[str, ...]:
    return tuple(load_explications().get("station_names", []))


def normalize_explication_station_name(value: str | None) -> str | None:
    if not value:
        return None
    return _station_by_key().get(_key(value))


def _station_payload(section: str, station: str | None) -> list[dict[str, Any]]:
    canonical = normalize_explication_station_name(station)
    if not canonical:
        return []
    data = load_explications()
    return list(data.get(section, {}).get(canonical, []))


def station_has_path(station: str | None, path_number: str | None) -> bool:
    number = normalize_asset_number(path_number)
    if not number:
        return False
    return any(row.get("number") == number for row in _station_payload("station_paths", station))


def station_has_paths(station: str | None) -> bool:
    return bool(_station_payload("station_paths", station))


def station_has_switch(station: str | None, switch_number: str | None) -> bool:
    number = normalize_asset_number(switch_number)
    if not number:
        return False
    return any(row.get("number") == number for row in _station_payload("switches", station))


def station_has_switches(station: str | None) -> bool:
    return bool(_station_payload("switches", station))


def path_for_station_switch(station: str | None, switch_number: str | None) -> str | None:
    number = normalize_asset_number(switch_number)
    if not number:
        return None
    paths = {
        row.get("path")
        for row in _station_payload("switches", station)
        if row.get("number") == number and row.get("path")
    }
    return next(iter(paths)) if len(paths) == 1 else None
