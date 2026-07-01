"""
postprocessRailwayRows — жёсткая evidence-only постобработка ParsedRow → таблица.

Порт frontend/postprocessRailwayRows.ts
"""

from __future__ import annotations

import re
from typing import Any, Literal, TypedDict

from app.services.asr_fixes import normalize_asr_text

AssetKind = Literal["track", "switch"]
ParsedRow = dict[str, Any]

DASH = "—"

SYNTHETIC_NOTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"2288\s*р", re.IGNORECASE),
    re.compile(r"движение\s+закрыва(?:ется|ть|ют)", re.IGNORECASE),
    re.compile(r"закрытие\s+движения", re.IGNORECASE),
    re.compile(r"запрещается\s+движение", re.IGNORECASE),
    re.compile(r"ограничение\s+скорости", re.IGNORECASE),
)

QUALIFIER_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(?:в|на)?\s*остри[ея]\s+остряка\b", re.IGNORECASE), "в острие остряка"),
    (re.compile(r"\bпо\s+прямому\s+направлению\b", re.IGNORECASE), "по прямому направлению"),
    (re.compile(r"\bпо\s+боковому\s+направлению\b", re.IGNORECASE), "по боковому направлению"),
    (re.compile(r"\bна\s+крестовине\b", re.IGNORECASE), "на крестовине"),
    (re.compile(r"\bна\s+усовике\b", re.IGNORECASE), "на усовике"),
)

_ASSET_MARKER_RE = re.compile(
    r"\b(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)\b",
    re.IGNORECASE,
)
_STATION_LOCATION_RE = re.compile(
    r"\bстанц(?:ия|ии)\s+(.+?)(?=\s+(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)|$)",
    re.IGNORECASE,
)
_SWITCH_ASSET_RE = re.compile(
    r"\bстрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+)\b",
    re.IGNORECASE,
)
_TRACK_ASSET_RE = re.compile(r"\bпуть\s+(\d+)\b", re.IGNORECASE)
_SPEED_KMH_RE = re.compile(r"\b(\d+)\s*км\s*/?\s*ч\b", re.IGNORECASE)
_SPEED_PHRASE_RE = re.compile(
    r"\b(?:ограничени[ея]\s+скорост[ьи]|скорост[ьи])\s*(?:до|не\s+более)?\s*(\d+)\b",
    re.IGNORECASE,
)
_STRIP_CONTEXT_STATION_RE = re.compile(
    r"\bстанц(?:ия|ии)\s+.+?(?=\s+(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)|$)",
    re.IGNORECASE,
)
_STRIP_CONTEXT_ASSET_RE = re.compile(
    r"\b(?:путь\s+\d+|стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+)\b",
    re.IGNORECASE,
)
_GAUGE_DEFECT_RE = re.compile(r"ширин[аы]\s+коле[иы]\s+(\d+)\s*мм", re.IGNORECASE)
_MM_ON_SLEEPERS_RE = re.compile(r"\s+\d+\s*мм\b", re.IGNORECASE)

_WEAR_RE = re.compile(r"износ\s+рамного\s+рельса\s+(\d+)\s*мм", re.IGNORECASE)
_CLUSTER_RE = re.compile(r"(\d+)\s+подряд\s+куста\s+из\s+(\d+)\s+шпал", re.IGNORECASE)
_BAD_SLEEPERS_RE = re.compile(r"куст(?:\s+из)?\s+(\d+)\s+негодных\s+шпал", re.IGNORECASE)
_TIP_IN_SOURCE_RE = re.compile(r"\bостри[ея]\s+остряка\b", re.IGNORECASE)

MULTI_OBJECT_WARNING = (
    "sourceText содержит несколько объектов; "
    "для корректной постобработки нужен сегмент одной строки"
)


class RailwayDisplayRow(TypedDict, total=False):
    Nп_п: int  # not used — keys are Russian column names in runtime dicts


def normalize_spaces(input_text: str) -> str:
    text = re.sub(r"\s+", " ", input_text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def dash_if_empty(value: str | None) -> str:
    if not value:
        return DASH
    normalized = normalize_spaces(value)
    return normalized if normalized else DASH


def _to_title_case_ru(value: str) -> str:
    words: list[str] = []
    for word in value.split():
        parts = []
        for part in word.split("-"):
            if part:
                parts.append(part[0].upper() + part[1:].lower())
            else:
                parts.append(part)
        words.append("-".join(parts))
    return " ".join(words)


def count_asset_markers(source_text: str) -> int:
    text = normalize_asr_text(source_text)
    return len(_ASSET_MARKER_RE.findall(text))


def detect_location_from_source(source_text: str) -> str | None:
    text = normalize_asr_text(source_text)
    match = _STATION_LOCATION_RE.search(text)
    if not match or not match.group(1):
        return None
    location = normalize_spaces(match.group(1))
    location = re.sub(r"[.,;:]+$", "", location).strip()
    return _to_title_case_ru(location) if location else None


def detect_asset_from_source(source_text: str) -> dict[str, str] | None:
    text = normalize_asr_text(source_text)
    switch_match = _SWITCH_ASSET_RE.search(text)
    if switch_match:
        return {"kind": "switch", "number": switch_match.group(1)}
    track_match = _TRACK_ASSET_RE.search(text)
    if track_match:
        return {"kind": "track", "number": track_match.group(1)}
    return None


def format_asset_for_cell(asset_kind: AssetKind | str | None, asset_number: str | None) -> str:
    if not asset_kind or not asset_number:
        return DASH
    if asset_kind == "switch":
        return f"стр. п. {asset_number}"
    return str(asset_number)


def parse_explicit_speed(source_text: str) -> int | None:
    text = normalize_asr_text(source_text)
    match = _SPEED_KMH_RE.search(text)
    if match:
        return int(match.group(1))
    match = _SPEED_PHRASE_RE.search(text)
    if match:
        return int(match.group(1))
    return None


def contains_explicit_speed(source_text: str) -> bool:
    return parse_explicit_speed(source_text) is not None


def _split_note_parts(note: str) -> list[str]:
    normalized = note.replace(";", ".")
    return [normalize_spaces(part) for part in normalized.split(".") if normalize_spaces(part)]


def _canonicalize_note_part(part: str) -> str:
    value = normalize_asr_text(part.lower())
    value = re.sub(r"[.,;:]+$", "", value).strip()
    value = re.sub(r"\bострие\s+остряка\b", "в острие остряка", value)
    value = re.sub(r"\bв\s+в\s+", "в ", value)
    value = re.sub(r"\bна\s+острие\s+остряка\b", "в острие остряка", value)
    value = re.sub(r"\bв\s+острии\s+остряка\b", "в острие остряка", value)
    return normalize_spaces(value)


def _dedupe_note_parts(parts: list[str]) -> str | None:
    result: list[str] = []
    seen: set[str] = set()
    for part in parts:
        canonical = _canonicalize_note_part(part)
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        result.append(canonical)
    return ". ".join(result) if result else None


def _remove_synthetic_note_parts(note: str | None, source_text: str) -> str | None:
    if not note:
        return None
    source = normalize_asr_text(source_text)
    source_contains = any(p.search(source) for p in SYNTHETIC_NOTE_PATTERNS)
    filtered = [
        part
        for part in _split_note_parts(note)
        if source_contains or not any(p.search(part) for p in SYNTHETIC_NOTE_PATTERNS)
    ]
    return _dedupe_note_parts(filtered)


def _extract_qualifiers_from_text(text: str) -> tuple[str, list[str]]:
    clean = normalize_spaces(text)
    qualifiers: list[str] = []
    for pattern, canonical in QUALIFIER_RULES:
        if pattern.search(clean):
            qualifiers.append(canonical)
            clean = normalize_spaces(pattern.sub(" ", clean))
    clean = re.sub(r"\s+[.,;:]", "", clean)
    clean = re.sub(r"[.,;:]+$", "", clean).strip()
    return normalize_spaces(clean), qualifiers


def _strip_leading_context(defect: str) -> str:
    value = _STRIP_CONTEXT_STATION_RE.sub(" ", defect)
    value = _STRIP_CONTEXT_ASSET_RE.sub(" ", value)
    return normalize_spaces(value)


def _normalize_defect_punctuation(value: str) -> str:
    text = value.replace(";", " ")
    text = re.sub(r"\s+[.,:]", "", text)
    text = re.sub(r"[.,:]+$", "", text)
    return normalize_spaces(text)


def _normalize_sleeper_defect_leak(defect: str) -> str:
    if not re.search(r"шпал", defect, re.IGNORECASE):
        return defect
    return normalize_spaces(_MM_ON_SLEEPERS_RE.sub("", defect))


def _normalize_location_value(explicit_location: str | None, source_text: str) -> str | None:
    if explicit_location and normalize_spaces(explicit_location):
        return _to_title_case_ru(normalize_spaces(explicit_location))
    return detect_location_from_source(source_text)


def _normalize_reference_value(reference: str | None) -> str | None:
    if not reference:
        return None
    normalized = normalize_spaces(reference)
    return normalized or None


def extract_deterministic_defect(source_text: str) -> tuple[str | None, str | None]:
    text = normalize_asr_text(source_text)

    match = _WEAR_RE.search(text)
    if match:
        note = "в острие остряка" if _TIP_IN_SOURCE_RE.search(text) else None
        return f"износ рамного рельса {match.group(1)} мм", note

    match = _GAUGE_DEFECT_RE.search(text)
    if match:
        return f"ширина колеи {match.group(1)} мм", None

    match = _CLUSTER_RE.search(text)
    if match:
        return f"{match.group(1)} подряд куста из {match.group(2)} шпал", None

    match = _BAD_SLEEPERS_RE.search(text)
    if match:
        return f"куст из {match.group(1)} негодных шпал", None

    return None, None


def _format_speed_for_cell(speed_limit: int | str | None) -> str:
    if speed_limit is None or speed_limit == "":
        return DASH
    if isinstance(speed_limit, int):
        return f"{speed_limit} км/ч"
    normalized = normalize_spaces(str(speed_limit))
    if not normalized:
        return DASH
    if re.fullmatch(r"\d+", normalized):
        return f"{normalized} км/ч"
    return normalized


def sanitize_row_for_export(row: ParsedRow) -> ParsedRow:
    source = normalize_asr_text(str(row.get("sourceText") or ""))
    asset_marker_count = count_asset_markers(source)

    warnings: list[str] = list(row.get("warnings") or [])
    if asset_marker_count > 1 and MULTI_OBJECT_WARNING not in warnings:
        warnings.append(MULTI_OBJECT_WARNING)

    source_single = asset_marker_count <= 1

    detected = detect_asset_from_source(source) if source_single else None
    asset_kind = detected["kind"] if detected else row.get("assetKind")
    asset_number = detected["number"] if detected else row.get("assetNumber")

    location = _normalize_location_value(row.get("location"), source)
    reference = _normalize_reference_value(row.get("reference"))

    explicit_speed = parse_explicit_speed(source) if source_single else None
    speed_limit = explicit_speed if explicit_speed is not None else None

    note_parts: list[str] = []
    initial_note = _remove_synthetic_note_parts(
        str(row["note"]).strip() if row.get("note") else None,
        source,
    )
    if initial_note:
        note_parts.extend(_split_note_parts(initial_note))

    defect_from_row: str | None = None
    if row.get("defect"):
        defect_from_row = _normalize_defect_punctuation(_strip_leading_context(str(row["defect"])))
        extracted_clean, qualifiers = _extract_qualifiers_from_text(defect_from_row)
        defect_from_row = extracted_clean or None
        note_parts.extend(qualifiers)

    final_defect = defect_from_row

    if source_single:
        det_defect, det_note = extract_deterministic_defect(source)
        if det_defect:
            final_defect = det_defect
        if det_note:
            note_parts.append(det_note)
        gauge_match = _GAUGE_DEFECT_RE.search(source)
        if gauge_match:
            final_defect = f"ширина колеи {gauge_match.group(1)} мм"

    if final_defect:
        final_defect = _normalize_defect_punctuation(final_defect)
        final_defect = _normalize_sleeper_defect_leak(final_defect)

    final_note = _dedupe_note_parts(note_parts)

    return {
        **row,
        "location": location,
        "assetKind": asset_kind,
        "assetNumber": asset_number,
        "reference": reference,
        "defect": final_defect or None,
        "speedLimit": speed_limit,
        "note": final_note,
        "sourceText": source,
        "rawDefect": row.get("rawDefect") if row.get("rawDefect") is not None else row.get("defect"),
        "canonicalDefect": final_defect or None,
        "normativeDecision": None,
        "warnings": warnings,
    }


def sanitize_rows_for_export(rows: list[ParsedRow]) -> list[ParsedRow]:
    return [sanitize_row_for_export(row) for row in rows]


FORM_COLUMNS = (
    "Nп/п",
    "Местонахождение (перегон, станция)",
    "№ пути, стрелочного перевода",
    "Привязка (км,пк,м)",
    "Выявленная неисправность",
    "Ограничение скорости",
    "Примечание",
)


def to_display_rows(
    rows: list[ParsedRow],
    *,
    include_source_text: bool = False,
) -> tuple[list[str], list[dict[str, Any]]]:
    sanitized = sanitize_rows_for_export(rows)
    display: list[dict[str, Any]] = []
    for index, row in enumerate(sanitized, start=1):
        item: dict[str, Any] = {
            FORM_COLUMNS[0]: index,
            FORM_COLUMNS[1]: dash_if_empty(row.get("location")),
            FORM_COLUMNS[2]: format_asset_for_cell(row.get("assetKind"), row.get("assetNumber")),
            FORM_COLUMNS[3]: dash_if_empty(row.get("reference")),
            FORM_COLUMNS[4]: dash_if_empty(row.get("defect")),
            FORM_COLUMNS[5]: _format_speed_for_cell(row.get("speedLimit")),
            FORM_COLUMNS[6]: dash_if_empty(row.get("note")),
        }
        if include_source_text:
            item["Исходный текст"] = dash_if_empty(row.get("sourceText"))
        display.append(item)
    return list(FORM_COLUMNS), display


def parsed_row_from_record(rec: Any) -> ParsedRow:
    """ParsedRecord / FlatInspectionRow → ParsedRow."""
    asset_kind: str | None = None
    asset_number: str | None = None
    put = getattr(rec, "put", None)
    switch = getattr(rec, "switch", None)
    if put:
        asset_kind = "track"
        asset_number = str(put).strip()
    elif switch:
        asset_kind = "switch"
        asset_number = str(switch).strip()

    reference_parts: list[str] = []
    km = getattr(rec, "km", None)
    piket = getattr(rec, "piket", None)
    if km:
        reference_parts.append(f"{km} км")
    if piket:
        reference_parts.append(f"пк {piket}")

    speed = getattr(rec, "speed_limit", None)
    speed_limit: int | str | None = None
    if speed is not None and str(speed).strip():
        try:
            speed_limit = int(str(speed).strip())
        except ValueError:
            speed_limit = str(speed).strip()

    return {
        "location": getattr(rec, "uchastok", None) or getattr(rec, "peregon", None),
        "assetKind": asset_kind,
        "assetNumber": asset_number,
        "reference": ", ".join(reference_parts) or None,
        "defect": getattr(rec, "defect", None),
        "speedLimit": speed_limit,
        "note": getattr(rec, "comment", None),
        "sourceText": getattr(rec, "raw_text", None) or "",
        "warnings": [],
    }


# TS API aliases
sanitizeRowForExport = sanitize_row_for_export
sanitizeRowsForExport = sanitize_rows_for_export
toDisplayRows = to_display_rows
