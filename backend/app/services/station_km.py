"""Границы километража станций (до полной перегонной модели)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.stations import normalize_station_name


@dataclass(frozen=True)
class StationKmBounds:
    km_from: int
    km_to: int


# Расширяется по мере уточнения перегонной модели.
STATION_KM_BOUNDS: dict[str, StationKmBounds] = {
    "Магнетиты": StationKmBounds(km_from=1408, km_to=1412),
}


def _parse_km_int(km: str | None) -> int | None:
    if not km:
        return None
    try:
        return int(float(km.replace(",", ".").strip()))
    except ValueError:
        return None


def km_in_station_bounds(value: int, bounds: StationKmBounds) -> bool:
    return bounds.km_from <= value <= bounds.km_to


def sanitize_station_km(
    km: str | None,
    station: str | None,
) -> tuple[str | None, bool]:
    """
    Отбрасывает км вне границ станции (в т.ч. ASR-шум «1400» у уширения колеи).
    Возвращает (km, was_cleared).
    """
    if not km or not station:
        return km, False

    canonical = normalize_station_name(station)
    if not canonical:
        return km, False

    bounds = STATION_KM_BOUNDS.get(canonical)
    if not bounds:
        return km, False

    value = _parse_km_int(km)
    if value is None:
        return km, False

    if km_in_station_bounds(value, bounds):
        return str(value), False

    return None, True
