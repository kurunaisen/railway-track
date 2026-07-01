"""
sanitizeRowForExport — evidence-only очистка ParsedRow перед таблицей/экспортом.

Порт TypeScript-патча: только явное содержимое sourceText, без нормативных подстановок.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.asr_fixes import normalize_asr_text
from app.services.llm.row_segment_validation import ParsedRow

_WS_RE = re.compile(r"\s+")
_EXPLICIT_SPEED_RE = re.compile(
    r"\b\d+\s*км\s*/?\s*ч\b|\bограничени[ея]\s+скорост[ьи]\b",
    re.IGNORECASE,
)
_SYNTHETIC_NOTE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"2288\s*р", re.IGNORECASE),
    re.compile(r"движение\s+закрыва(?:ется|ть)", re.IGNORECASE),
    re.compile(r"закрытие\s+движения", re.IGNORECASE),
    re.compile(r"ограничение\s+скорости", re.IGNORECASE),
)
_MM_ON_SLEEPERS_RE = re.compile(r"\s+\d+\s*мм\b", re.IGNORECASE)
_TIP_IN_SOURCE_RE = re.compile(r"остри[ея]\s+остряка", re.IGNORECASE)
_WIDTH_IN_SOURCE_RE = re.compile(r"ширин[аы]\s+коле[иы]\s+(\d+)\s*мм", re.IGNORECASE)

# Детерминированные паттерны дефектов (как в TS extractDeterministicDefect)
_WEAR_RE = re.compile(r"износ\s+рамного\s+рельса\s+(\d+)\s*мм", re.IGNORECASE)
_GAUGE_RE = re.compile(r"ширин[аы]\s+коле[иы]\s+(\d+)\s*мм", re.IGNORECASE)
_CLUSTER_RE = re.compile(r"(\d+)\s+подряд\s+куста\s+из\s+(\d+)\s+шпал", re.IGNORECASE)
_BAD_SLEEPERS_RE = re.compile(r"куст(?:\s+из)?\s+(\d+)\s+негодных\s+шпал", re.IGNORECASE)


def normalize_spaces(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()


def dash_if_empty(value: str | None) -> str:
    if not value:
        return "—"
    v = normalize_spaces(value)
    return v if v else "—"


def remove_duplicate_note_phrases(note: str | None) -> str | None:
    if not note:
        return None

    normalized = normalize_asr_text(note.lower())
    normalized = re.sub(r"[.;,]+", ".", normalized)
    parts = [normalize_spaces(part) for part in normalized.split(".") if normalize_spaces(part)]

    seen: set[str] = set()
    result: list[str] = []
    for part in parts:
        key = re.sub(r"\bв\s+остри[ея]\s+остряка\b", "в острие остряка", part)
        if key not in seen:
            seen.add(key)
            result.append(key)

    if not result:
        return None
    return ". ".join(result)


def contains_explicit_speed(source: str) -> bool:
    return bool(_EXPLICIT_SPEED_RE.search(source))


def remove_synthetic_note(note: str | None, source: str) -> str | None:
    if not note:
        return None
    note_has = any(p.search(note) for p in _SYNTHETIC_NOTE_PATTERNS)
    source_has = any(p.search(source) for p in _SYNTHETIC_NOTE_PATTERNS)
    if note_has and not source_has:
        return None
    return note


def extract_deterministic_defect(source: str) -> tuple[str | None, str | None]:
    text = normalize_asr_text(source)

    match = _WEAR_RE.search(text)
    if match:
        note = "в острие остряка" if _TIP_IN_SOURCE_RE.search(text) else None
        return f"износ рамного рельса {match.group(1)} мм", note

    match = _GAUGE_RE.search(text)
    if match:
        return f"ширина колеи {match.group(1)} мм", None

    match = _CLUSTER_RE.search(text)
    if match:
        return f"{match.group(1)} подряд куста из {match.group(2)} шпал", None

    match = _BAD_SLEEPERS_RE.search(text)
    if match:
        return f"куст из {match.group(1)} негодных шпал", None

    return None, None


def sanitize_row_for_export(row: ParsedRow) -> ParsedRow:
    source = normalize_asr_text(str(row.get("sourceText") or ""))
    out: ParsedRow = dict(row)

    if not contains_explicit_speed(source):
        out["speedLimit"] = None

    note = remove_synthetic_note(out.get("note"), source)
    out["note"] = note

    defect, det_note = extract_deterministic_defect(source)
    if defect:
        out["defect"] = defect
    if det_note:
        out["note"] = det_note

    defect_val = out.get("defect")
    if isinstance(defect_val, str) and re.search(r"шпал", defect_val, re.IGNORECASE):
        out["defect"] = _MM_ON_SLEEPERS_RE.sub("", defect_val).strip() or None

    if out.get("defect") and not re.search(
        r"сужение|уширение|движение\s+закрыва", source, re.IGNORECASE
    ):
        width_match = _WIDTH_IN_SOURCE_RE.search(source)
        if width_match:
            out["defect"] = f"ширина колеи {width_match.group(1)} мм"

    out["note"] = remove_duplicate_note_phrases(
        str(out["note"]).strip() if out.get("note") else None
    )

    if out.get("defect"):
        out["defect"] = normalize_spaces(str(out["defect"]))
    if out.get("note"):
        out["note"] = normalize_spaces(str(out["note"]))

    return out


def parsed_row_from_record(rec: Any) -> ParsedRow:
    """ParsedRecord / FlatInspectionRow → ParsedRow для sanitize."""
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
    }


# TS API alias
sanitizeRowForExport = sanitize_row_for_export
