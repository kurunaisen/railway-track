"""Deterministic semantic repair for RailwayRow fields.

The LLM sometimes puts location, asset, reference, and note into the wrong
columns. This module only moves facts already present in the row text pool; it
does not infer defects, speeds, or normative decisions.
"""

from __future__ import annotations

import re

from app.services.railway.types import RailwayRow

_SPACE_RE = re.compile(r"\s+")
_LOCATION_FORBIDDEN_RE = re.compile(
    r"\b(?:км|километр\w*|пикет|пике|пк|метр\w*|путь|стрелоч\w*|звено)\b",
    re.IGNORECASE,
)

_REFERENCE_PATTERNS = [
    re.compile(
        r"(?P<km>\d{3,5})\s*(?:км|километр\w*)\s*"
        r"(?:пикет|пике|пк)\s*(?P<pk>\d+)\s*"
        r"(?P<m>\d+)\s*(?:м|метр\w*)?",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?P<km>\d{3,5})\s*(?:км|километр\w*)\s*"
        r"(?:пикет|пике|пк)\s*(?P<pk>\d+)\s*"
        r"(?:м|метр\w*)\s*(?P<m>\d+)",
        re.IGNORECASE,
    ),
]
_SWITCH_RE = re.compile(
    r"(?:стрелочн\w*\s+перевод(?:\s+номер)?|стр\.\s*п\.)\s*(?P<number>\d+[А-Яа-яA-Za-z-]*)",
    re.IGNORECASE,
)
_TRACK_AFTER_RE = re.compile(r"\bпуть\s*(?P<number>\d+[А-Яа-яA-Za-z-]*)\b", re.IGNORECASE)
_TRACK_BEFORE_RE = re.compile(r"\b(?P<number>\d+[А-Яа-яA-Za-z-]*)\s*путь\b", re.IGNORECASE)
_LINK_AFTER_RE = re.compile(r"\bзвено\s*(?P<number>\d+)\b", re.IGNORECASE)
_LINK_BEFORE_RE = re.compile(r"\b(?P<number>\d+)\s*звено\b", re.IGNORECASE)
_POINT_NOTE_RE = re.compile(r"\bв\s+остри[ие]\s+остряка\b", re.IGNORECASE)
_STATION_RE = re.compile(
    r"(?:^|[\s,])(?:на\s+)?станци[ия]\s+(?P<name>[А-Яа-яЁёA-Za-z -]+?)"
    r"(?=(?:\s+\d+\s*путь|\s+путь|\s+звено|\s+\d+\s*звено|,|$))",
    re.IGNORECASE,
)
_PEREGON_RE = re.compile(
    r"(?:^|[\s,])перегон\s+(?P<name>[А-Яа-яЁёA-Za-z -]+?)"
    r"(?=(?:\s+\d{3,5}\s*(?:км|километр)|,|$))",
    re.IGNORECASE,
)


def _trim(value: str | None) -> str | None:
    if value is None:
        return None
    text = _SPACE_RE.sub(" ", value).strip(" ,.;")
    return text or None


def _title_ru(value: str) -> str:
    words = []
    for word in value.split():
        if word.lower() in {"от", "до", "на"}:
            words.append(word.lower())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _append_warning(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _text_pool(row: RailwayRow) -> str:
    return " ".join(
        part
        for part in [row.source_text, row.location, row.defect, row.note]
        if isinstance(part, str) and part.strip()
    )


def _extract_reference(text: str) -> str | None:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match:
            return f"{match.group('km')} км, пк {match.group('pk')}, {match.group('m')} м"
    return None


def _extract_asset(text: str) -> tuple[str, str] | None:
    match = _SWITCH_RE.search(text)
    if match:
        return "switch", match.group("number")
    match = _TRACK_BEFORE_RE.search(text) or _TRACK_AFTER_RE.search(text)
    if match:
        return "track", match.group("number")
    return None


def _extract_note(text: str) -> str | None:
    match = _LINK_AFTER_RE.search(text) or _LINK_BEFORE_RE.search(text)
    if match:
        return f"звено {match.group('number')}"
    match = _POINT_NOTE_RE.search(text)
    if match:
        return match.group(0).lower()
    return None


def _remove_semantic_noise(text: str) -> str:
    cleaned = text
    for pattern in _REFERENCE_PATTERNS:
        cleaned = pattern.sub(" ", cleaned)
    cleaned = _SWITCH_RE.sub(" ", cleaned)
    cleaned = _TRACK_AFTER_RE.sub(" ", cleaned)
    cleaned = _TRACK_BEFORE_RE.sub(" ", cleaned)
    cleaned = _LINK_AFTER_RE.sub(" ", cleaned)
    cleaned = _LINK_BEFORE_RE.sub(" ", cleaned)
    cleaned = _POINT_NOTE_RE.sub(" ", cleaned)
    return _trim(cleaned) or ""


def _extract_location(text: str, *, allow_plain_fallback: bool = False) -> str | None:
    match = _PEREGON_RE.search(text)
    if match:
        return f"Перегон {_title_ru(match.group('name'))}"

    match = _STATION_RE.search(text)
    if match:
        return _title_ru(match.group("name"))

    if not allow_plain_fallback:
        return None

    cleaned = _remove_semantic_noise(text)
    if not cleaned:
        return None
    first_part = _trim(cleaned.split(",", 1)[0])
    if first_part and not _LOCATION_FORBIDDEN_RE.search(first_part):
        return _title_ru(re.sub(r"^(?:на\s+)?станци[ия]\s+", "", first_part, flags=re.IGNORECASE))
    return None


def _repair_location(location: str | None, pool: str, warnings: list[str]) -> str | None:
    source = " ".join(part for part in [location, pool] if part)
    repaired = _extract_location(source)
    original = _trim(location)
    if repaired and repaired != original:
        _append_warning(warnings, "location repaired from mixed context")
        return repaired
    if original and _LOCATION_FORBIDDEN_RE.search(original):
        cleaned = _extract_location(original) or _extract_location(original, allow_plain_fallback=True)
        if cleaned and not _LOCATION_FORBIDDEN_RE.search(cleaned):
            _append_warning(warnings, "location cleaned from forbidden tokens")
            return _title_ru(cleaned)
        _append_warning(warnings, "location contains non-location tokens")
    return original


def _can_inherit_context(row: RailwayRow) -> bool:
    text = (row.source_text or "").strip().lower()
    return bool(re.match(r"^(?:и|а|также)\b", text))


def repair_railway_row(row: RailwayRow, previous: RailwayRow | None = None) -> RailwayRow:
    warnings = [w for w in row.warnings if w]
    pool = _text_pool(row)

    reference = _trim(row.reference)
    if not reference:
        extracted = _extract_reference(pool)
        if extracted:
            reference = extracted
            _append_warning(warnings, "reference repaired from row text")

    asset_kind = row.asset_kind
    asset_number = _trim(row.asset_number)
    if not asset_kind or not asset_number:
        asset = _extract_asset(pool)
        if asset:
            asset_kind, asset_number = asset
            _append_warning(warnings, "asset repaired from row text")

    note = _trim(row.note)
    if not note:
        extracted_note = _extract_note(pool)
        if extracted_note:
            note = extracted_note
            _append_warning(warnings, "note repaired from row text")

    location = _repair_location(row.location, pool, warnings)

    if previous and _can_inherit_context(row):
        if not location and previous.location:
            location = previous.location
            _append_warning(warnings, "location inherited from previous row context")
        if (not asset_kind or not asset_number) and previous.asset_kind and previous.asset_number:
            asset_kind = previous.asset_kind
            asset_number = previous.asset_number
            _append_warning(warnings, "asset inherited from previous row context")
        if not note and previous.note:
            note = previous.note
            _append_warning(warnings, "note inherited from previous row context")

    if location and _LOCATION_FORBIDDEN_RE.search(location):
        cleaned_location = _repair_location(location, "", warnings)
        if cleaned_location and not _LOCATION_FORBIDDEN_RE.search(cleaned_location):
            location = cleaned_location
        else:
            _append_warning(warnings, "location semantic validation failed")

    return RailwayRow(
        location=location,
        asset_kind=asset_kind,
        asset_number=asset_number,
        reference=reference,
        defect=row.defect,
        speed_limit=row.speed_limit,
        note=note,
        source_text=row.source_text,
        warnings=warnings,
    )


def repair_railway_rows(rows: list[RailwayRow]) -> list[RailwayRow]:
    repaired: list[RailwayRow] = []
    for row in rows:
        fixed = repair_railway_row(row, repaired[-1] if repaired else None)
        repaired.append(fixed)
    return repaired
