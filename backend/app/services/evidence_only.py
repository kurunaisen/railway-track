"""
Режим evidenceOnly: в таблицу/экспорт попадает только то, что явно есть в исходном ASR-сегменте.

Без нормативных выводов (2288р/436/р), без подстановки названий неисправностей,
без рекомендаций и «улучшений» текста.
"""

from __future__ import annotations

import re
from typing import Literal, Protocol

from app.config import settings
from app.services.asr_fixes import normalize_asr_text
from app.services.locations import (
    extract_single_location,
    format_peregon_display,
    is_peregon_haul,
)
from app.services.rail_side import extract_rail_side_note
from app.services.sanitize_row_for_export import (
    normalize_spaces,
    parsed_row_from_record,
    sanitize_row_for_export,
)
from app.services.speed_limit import strip_speed_limit_phrases

TableExportMode = Literal["evidenceOnly", "normsEnriched"]

_PATH_N_PUT_RE = re.compile(r"(\d+)\s+путь\b", re.IGNORECASE)
_PATH_EXPLICIT_RE = re.compile(
    r"(?:главн\w*\s+)?путь\s*(?:№|номер|n\.?)?\s*(\d+)",
    re.IGNORECASE,
)
_SWITCH_EXPLICIT_RE = re.compile(
    r"стрелочн(?:ый|ного|ом|ая)?\s+перевод(?:а|е|у|ом)?\s*(?:№|номер|n\.?)?\s*(\d+)",
    re.IGNORECASE,
)
_MAIN_PATH_EXPLICIT_RE = re.compile(r"главн\w*\s+путь|\bгл\.?\s*п\.?", re.IGNORECASE)
_PEREGON_WORD_RE = re.compile(r"\bперегон\b", re.IGNORECASE)
_STATION_SEGMENT_RE = re.compile(r"\bстанц(?:ия|ии)\s+", re.IGNORECASE)
_SEGMENT_HEADER_RE = re.compile(
    r"^(?:станц(?:ия|ии)\s+\S+\s+)?"
    r"(?:стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+\s+|путь\s+\d+\s+)?",
    re.IGNORECASE,
)
_TIP_NOTE_RE = re.compile(r"\b(?:в\s+|на\s+)?остри[ея]\s+остряка\b", re.IGNORECASE)
_NORM_AUTO_COMMENT_RE = re.compile(
    r"движение\s+закрывается\s*\((?:2288р|436/р)\)",
    re.IGNORECASE,
)
_KM_IN_TEXT_RE = re.compile(
    r"(?:километр|км)\s*(\d+(?:[.,]\d+)?)|(\d+(?:[.,]\d+)?)\s*(?:километр|км)\b",
    re.IGNORECASE,
)
_PIKET_IN_TEXT_RE = re.compile(
    r"пикет\s*(\d+(?:\s*плюс\s*\d+(?:[.,]\d+)?|\+\d+(?:[.,]\d+)?)?)",
    re.IGNORECASE,
)
_NORM_DEFECT_TITLES = (
    "уширение рельсовой колеи",
    "сужение рельсовой колеи",
    "уширение колеи",
    "сужение колеи",
)


class EvidenceRowSource(Protocol):
    peregon: str | None
    uchastok: str | None
    put: str | None
    switch: str | None
    km: str | None
    piket: str | None
    parameter: str | None
    defect: str | None
    value: str | None
    unit: str | None
    comment: str | None
    speed_limit: str | None
    raw_text: str | None


def is_evidence_only(*, mode: bool | None = None) -> bool:
    if mode is not None:
        return mode
    return settings.table_export_mode == "evidenceOnly"


def segment_text(rec: EvidenceRowSource) -> str:
    return normalize_asr_text(rec.raw_text or "")


def _normalize_track_text(text: str) -> str:
    return text.replace("ё", "е").replace("Ё", "Е")


def explicit_path_number(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        norm = _normalize_track_text(text)
        match = _PATH_N_PUT_RE.search(norm)
        if match:
            return match.group(1)
        for match in _PATH_EXPLICIT_RE.finditer(norm):
            tail = norm[match.end() : match.end() + 12]
            if re.match(r"\s+звен", tail, re.IGNORECASE):
                continue
            before = norm[max(0, match.start() - 12) : match.start()]
            if re.search(r"\d+\s+путь\s*$", before, re.IGNORECASE):
                continue
            return match.group(1)
    return None


def explicit_switch_number(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _SWITCH_EXPLICIT_RE.search(_normalize_track_text(text))
        if match:
            return match.group(1)
    return None


def _main_path_explicit(*texts: str | None) -> bool:
    for text in texts:
        if text and _MAIN_PATH_EXPLICIT_RE.search(_normalize_track_text(text)):
            return True
    return False


def _is_peregon_segment(segment: str) -> bool:
    return bool(_PEREGON_WORD_RE.search(_normalize_track_text(segment)))


def _phrase_in_segment(phrase: str | None, segment: str) -> bool:
    if not phrase or not segment:
        return False
    return phrase.strip().lower() in segment.lower()


def _note_evidence_in_segment(phrase: str | None, segment: str) -> bool:
    if not phrase or not segment:
        return False
    if _phrase_in_segment(phrase, segment):
        return True
    core = re.sub(r"^(?:в|на)\s+", "", phrase.strip().lower()).strip()
    return bool(core and core in segment.lower())


def _is_norm_substituted_defect(defect: str | None, segment: str) -> bool:
    if not defect:
        return False
    lowered = defect.strip().lower()
    if lowered not in _NORM_DEFECT_TITLES:
        return False
    if any(token in segment.lower() for token in ("ширина колеи", "ширина коли", "колеи", "коли")):
        return True
    return lowered not in segment.lower()


def _sanitized_row(rec: EvidenceRowSource) -> dict:
    return sanitize_row_for_export(parsed_row_from_record(rec))


def defect_from_segment(rec: EvidenceRowSource) -> str:
    """Неисправность — sanitizeRowForExport + fallback по телу сегмента."""
    sanitized = _sanitized_row(rec)
    if sanitized.get("defect"):
        return str(sanitized["defect"])

    segment = segment_text(rec)
    if not segment:
        return ""

    body = _SEGMENT_HEADER_RE.sub("", segment).strip()
    tip = _TIP_NOTE_RE.search(body)
    if tip:
        body = f"{body[: tip.start()]} {body[tip.end() :]}".strip()
    body = strip_speed_limit_phrases(body).strip(" ,.;:-")

    if body:
        return body

    defect = strip_speed_limit_phrases(rec.defect or "").strip()
    if defect and not _is_norm_substituted_defect(defect, segment):
        if _phrase_in_segment(defect, segment):
            return defect
        if rec.value and rec.value in segment:
            chunks = [defect]
            val = f"{rec.value} {(rec.unit or '').strip()}".strip()
            if val.lower() not in defect.lower():
                chunks.append(val)
            return " ".join(chunks)

    parameter = (rec.parameter or "").strip()
    if parameter and _phrase_in_segment(parameter, segment):
        val = (rec.value or "").strip()
        unit = (rec.unit or "").strip()
        if val:
            composed = f"{parameter} {val} {unit}".strip()
            if _phrase_in_segment(composed, segment) or val in segment:
                return composed
        return parameter

    return segment


def note_from_segment(rec: EvidenceRowSource) -> str:
    """Примечание — sanitizeRowForExport + фразы из сегмента."""
    segment = segment_text(rec)
    sanitized = _sanitized_row(rec)
    if sanitized.get("note"):
        parts = [
            normalize_spaces(p)
            for p in re.split(r"[.;]+", str(sanitized["note"]))
            if normalize_spaces(p)
        ]
        kept = [p for p in parts if _note_evidence_in_segment(p, segment)]
        if kept:
            return ". ".join(kept)

    if not segment:
        return ""

    notes: list[str] = []
    tip = _TIP_NOTE_RE.search(segment)
    if tip:
        notes.append("в острие остряка")
    side = extract_rail_side_note(segment)
    if side:
        notes.append(side)

    comment = (rec.comment or "").strip()
    if comment:
        cleaned = _NORM_AUTO_COMMENT_RE.sub("", comment).strip(" ,;")
        if cleaned and _phrase_in_segment(cleaned, segment):
            if cleaned.lower() not in {n.lower() for n in notes}:
                notes.append(cleaned.lower())

    return "; ".join(n for n in notes if n)


def speed_from_segment(rec: EvidenceRowSource) -> str | None:
    sanitized = _sanitized_row(rec)
    speed = sanitized.get("speedLimit")
    if speed is None:
        return None
    return str(speed)


def location_from_segment(rec: EvidenceRowSource) -> str:
    segment = segment_text(rec)
    from_text = extract_single_location(segment)
    if from_text:
        return from_text

    if rec.peregon and is_peregon_haul(rec.peregon):
        peregon_norm = format_peregon_display(rec.peregon).lower()
        if _is_peregon_segment(segment) or peregon_norm.replace("-", " ") in segment.lower():
            return format_peregon_display(rec.peregon)

    if rec.uchastok:
        station = rec.uchastok.strip()
        if _phrase_in_segment(station, segment) or _STATION_SEGMENT_RE.search(segment):
            return station
        if explicit_path_number(segment) or explicit_switch_number(segment):
            return station

    return ""


def binding_from_segment(rec: EvidenceRowSource) -> str:
    segment = segment_text(rec)
    if not segment:
        return ""

    parts: list[str] = []
    km_match = _KM_IN_TEXT_RE.search(segment)
    if km_match:
        km_val = (km_match.group(1) or km_match.group(2) or "").replace(",", ".")
        if km_val:
            parts.append(f"{km_val} км")
    elif rec.km and re.search(rf"\b{re.escape(rec.km)}\b", segment):
        parts.append(f"{rec.km} км")

    pk_match = _PIKET_IN_TEXT_RE.search(segment)
    if pk_match:
        pk_raw = pk_match.group(1).replace(" плюс ", "+").replace(",", ".")
        if "+" in pk_raw:
            pk, meters = pk_raw.split("+", 1)
            parts.append(f"пк {pk.strip()}")
            if meters.strip():
                parts.append(f"м {meters.strip()}")
        else:
            parts.append(f"пк {pk_raw.strip()}")
    elif rec.piket and rec.piket.replace("+", " плюс ") in segment.lower():
        piket_norm = rec.piket.replace(",", ".")
        if "+" in piket_norm:
            pk, meters = piket_norm.split("+", 1)
            parts.append(f"пк {pk.strip()}")
            if meters.strip():
                parts.append(f"м {meters.strip()}")
        else:
            parts.append(f"пк {piket_norm}")

    return ", ".join(parts)


def track_parts_from_segment(rec: EvidenceRowSource) -> tuple[str | None, str | None]:
    segment = segment_text(rec)
    path_num = explicit_path_number(segment)
    switch_num = explicit_switch_number(segment)

    if not path_num:
        put = getattr(rec, "put", None)
        if put and str(put).strip():
            path_num = str(put).strip()

    if not switch_num:
        switch = getattr(rec, "switch", None)
        if switch and str(switch).strip():
            switch_num = str(switch).strip()

    path_display: str | None = None
    if path_num:
        if _main_path_explicit(segment) or _is_peregon_segment(segment):
            path_display = f"{path_num} гл.п."
        else:
            path_display = path_num

    switch_display = f"стр.п. {switch_num}" if switch_num else None
    return path_display, switch_display


def format_track_from_segment(rec: EvidenceRowSource) -> str:
    path, switch = track_parts_from_segment(rec)
    parts = [p for p in (path, switch) if p]
    return ", ".join(parts)
