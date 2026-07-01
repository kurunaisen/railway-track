"""Лёгкая deterministic-нормализация после LLM — без синтеза значений."""

from __future__ import annotations

import re

from app.services.railway.types import RailwayRow

_SPACE_RE = re.compile(r"\s+")


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    text = _SPACE_RE.sub(" ", value).strip()
    return text or None


def _sentence_case(value: str | None) -> str | None:
    text = _trim(value)
    if not text:
        return None
    return text[0].upper() + text[1:]


def _dedupe_note(note: str | None) -> str | None:
    text = _trim(note)
    if not text:
        return None
    parts = [p.strip() for p in re.split(r"[.;]+", text) if p.strip()]
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        key = part.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(part)
    return ". ".join(unique) if unique else None


def normalize_railway_row(row: RailwayRow) -> RailwayRow:
    warnings = [_trim(w) for w in row.warnings]
    warnings = [w for w in warnings if w]

    speed = row.speed_limit
    if speed is not None and speed <= 0:
        speed = None
        warnings.append("speedLimit ignored: non-positive value")

    return RailwayRow(
        location=_sentence_case(row.location),
        asset_kind=row.asset_kind,
        asset_number=_trim(row.asset_number),
        reference=_trim(row.reference),
        defect=_trim(row.defect),
        speed_limit=speed,
        note=_dedupe_note(row.note),
        source_text=_trim(row.source_text) or "",
        warnings=warnings,
    )


def normalize_railway_rows(rows: list[RailwayRow]) -> list[RailwayRow]:
    return [normalize_railway_row(row) for row in rows]
