"""Границы километража перегонов (перегонная модель, Распоряжение 2288р / эксплуатация)."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.peregons import normalize_peregon


@dataclass(frozen=True)
class PeregonKmBounds:
    km_from: int
    km_to: int


# Расширяется по мере задания перегонной модели.
PEREGON_KM_BOUNDS: dict[str, PeregonKmBounds] = {
    "Магнетиты — Шонгуй": PeregonKmBounds(km_from=1412, km_to=1419),
}


def _parse_km_int(km: str | None) -> int | None:
    if not km:
        return None
    try:
        return int(float(km.replace(",", ".").strip()))
    except ValueError:
        return None


def km_in_bounds(value: int, bounds: PeregonKmBounds) -> bool:
    return bounds.km_from <= value <= bounds.km_to


def _correction_candidates(value: int) -> list[int]:
    """Типичные ошибки ASR: лишняя «2» в начале (2419 → 1419)."""
    candidates: list[int] = []
    text = str(value)

    if len(text) == 4 and text[0] == "2":
        candidates.append(int("1" + text[1:]))

    for delta in (1000, 2000):
        candidates.append(value - delta)

    if len(text) >= 3:
        candidates.append(int("14" + text[2:]))

    seen: set[int] = set()
    unique: list[int] = []
    for item in candidates:
        if item not in seen and item > 0:
            seen.add(item)
            unique.append(item)
    return unique


def correct_km_for_peregon(km: str | None, peregon: str | None) -> tuple[str | None, bool]:
    """
    Если км вне диапазона перегона — подобрать ближайшее значение внутри границ.
    Возвращает (km, was_corrected).
    """
    if not km or not peregon:
        return km, False

    canonical = normalize_peregon(peregon)
    if not canonical:
        return km, False

    bounds = PEREGON_KM_BOUNDS.get(canonical)
    if not bounds:
        return km, False

    value = _parse_km_int(km)
    if value is None:
        return km, False

    if km_in_bounds(value, bounds):
        return str(value), False

    for candidate in _correction_candidates(value):
        if km_in_bounds(candidate, bounds):
            return str(candidate), True

    return km, False


def peregon_km_hint_for_prompt() -> str:
    parts = [
        f"{name}: {b.km_from}–{b.km_to} км"
        for name, b in PEREGON_KM_BOUNDS.items()
    ]
    return "; ".join(parts)
