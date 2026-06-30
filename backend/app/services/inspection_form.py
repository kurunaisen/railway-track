"""Официальная форма таблицы обхода (столбцы из шаблона Excel)."""

from __future__ import annotations

import re
from typing import Protocol

from app.services.locations import format_location_for_table

FORM_COLUMNS: tuple[str, ...] = (
    "Nп/п",
    "Местонахождение (перегон, станция)",
    "№ пути, стрелочного перевода",
    "Привязка (км,пк,м)",
    "Выявленная неисправность",
    "Ограничение скорости",
    "Примечание",
)


class FormRowSource(Protocol):
    peregon: str | None
    uchastok: str | None
    put: str | None
    obekt: str | None
    km: str | None
    piket: str | None
    parameter: str | None
    defect: str | None
    value: str | None
    unit: str | None
    comment: str | None
    speed_limit: str | None
    raw_text: str | None


# Явные фразы: «путь номер 4», «стрелочный перевод 2».
_PATH_EXPLICIT_RE = re.compile(
    r"(?:главн\w*\s+)?путь\s*(?:№|номер|n\.?)?\s*(\d+)",
    re.IGNORECASE,
)
_SWITCH_EXPLICIT_RE = re.compile(
    r"стрелочн(?:ый|ого|ом|ая)?\s+перевод(?:а|е|у|ом)?\s*(?:№|номер|n\.?)?\s*(\d+)",
    re.IGNORECASE,
)
_MAIN_PATH_EXPLICIT_RE = re.compile(
    r"главн\w*\s+путь|\bгл\.?\s*п\.?",
    re.IGNORECASE,
)
_PEREGON_WORD_RE = re.compile(r"\bперегон\b", re.IGNORECASE)
_HAUL_NAME_RE = re.compile(r"[-–—]")


def _normalize_track_text(text: str) -> str:
    return text.replace("ё", "е").replace("Ё", "Е")


def _explicit_path_number(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _PATH_EXPLICIT_RE.search(_normalize_track_text(text))
        if match:
            return match.group(1)
    return None


def _explicit_switch_number(*texts: str | None) -> str | None:
    for text in texts:
        if not text:
            continue
        match = _SWITCH_EXPLICIT_RE.search(_normalize_track_text(text))
        if match:
            return match.group(1)
    return None


def _main_path_explicit(*texts: str | None) -> bool:
    for text in texts:
        if not text:
            continue
        if _MAIN_PATH_EXPLICIT_RE.search(_normalize_track_text(text)):
            return True
    return False


def _is_peregon_context(rec: FormRowSource, *texts: str | None) -> bool:
    for text in texts:
        if text and _PEREGON_WORD_RE.search(_normalize_track_text(text)):
            return True
    if rec.peregon and _HAUL_NAME_RE.search(rec.peregon.strip()):
        return True
    return False


def _format_path_number(num: str, rec: FormRowSource, *texts: str | None) -> str:
    """На перегоне — всегда гл.п.; на станции — только номер, если не сказали «главный путь»."""
    if _is_peregon_context(rec, *texts) or _main_path_explicit(*texts):
        return f"{num} гл.п."
    return num


def format_location(rec: FormRowSource) -> str:
    return format_location_for_table(
        peregon=rec.peregon,
        uchastok=rec.uchastok,
        raw_text=rec.raw_text,
        comment=rec.comment,
    )


def format_track(rec: FormRowSource) -> str:
    sources = (rec.raw_text, rec.comment)
    path_num = _explicit_path_number(*sources)
    switch_num = _explicit_switch_number(*sources)
    put = (rec.put or "").strip()

    parts: list[str] = []
    if path_num:
        parts.append(_format_path_number(path_num, rec, *sources))
    elif switch_num is None and put.isdigit():
        parts.append(_format_path_number(put, rec, *sources))

    if switch_num:
        parts.append(f"стр.п. {switch_num}")

    if parts:
        return ", ".join(parts)
    return put


def format_binding(rec: FormRowSource) -> str:
    parts: list[str] = []
    km = (rec.km or "").strip()
    piket = (rec.piket or "").strip()
    if km:
        parts.append(f"{km} км")
    if piket:
        piket_norm = piket.replace(",", ".")
        if "+" in piket_norm:
            pk, meters = piket_norm.split("+", 1)
            parts.append(f"пк {pk.strip()}")
            meters = meters.strip()
            if meters:
                parts.append(f"м {meters}")
        else:
            parts.append(f"пк {piket}")
    return ", ".join(parts)


def format_defect(rec: FormRowSource) -> str:
    defect = (rec.defect or "").strip()
    parameter = (rec.parameter or "").strip()
    value = (rec.value or "").strip()
    unit = (rec.unit or "").strip()

    if defect and len(defect) > 20 and not value:
        return defect

    chunks: list[str] = []
    if defect:
        chunks.append(defect)
    elif parameter:
        chunks.append(parameter)

    if value:
        val = f"{value} {unit}".strip() if unit else value
        if chunks and val.lower() not in chunks[-1].lower():
            chunks.append(val)
        elif not chunks:
            chunks.append(val)

    if chunks:
        return " ".join(chunks)

    raw = (rec.raw_text or "").strip()
    if raw and len(raw) < 500:
        return raw
    return ""


def record_to_form_row(rec: FormRowSource, index: int) -> dict[str, str | int | None]:
    return {
        FORM_COLUMNS[0]: index,
        FORM_COLUMNS[1]: format_location(rec) or None,
        FORM_COLUMNS[2]: format_track(rec) or None,
        FORM_COLUMNS[3]: format_binding(rec) or None,
        FORM_COLUMNS[4]: format_defect(rec) or None,
        FORM_COLUMNS[5]: (rec.speed_limit or "").strip() or None,
        FORM_COLUMNS[6]: (rec.comment or "").strip() or None,
    }


def build_form_rows(records: list[FormRowSource]) -> tuple[list[str], list[dict]]:
    rows = [record_to_form_row(rec, i) for i, rec in enumerate(records, start=1)]
    return list(FORM_COLUMNS), rows
