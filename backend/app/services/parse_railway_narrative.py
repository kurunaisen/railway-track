"""parseRailwayNarrative — парсер диктовки с контекстом (порт TS)."""

from __future__ import annotations

import re
from typing import Any

from app.services.llm.row_segment_validation import ParsedRow

# Как в TS: \p{L} — только буквы (цифры не «слова»), иначе «2 1 звено» не нормализуется
_CYR_LETTER = r"a-zA-Z\u0400-\u04FF"
_CYR_BOUNDARY = rf"(?:^|[^{_CYR_LETTER}\d])"
_CYR_END = rf"(?=[^{_CYR_LETTER}\d]|$)"

DEFECT_RE = re.compile(
    rf"{_CYR_BOUNDARY}("
    r"отсутствует\s+\d+\s+(?:стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?|"
    r"не\s+закручен\s+\d+\s+(?:стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?|"
    r"(?:уширение|ширина)\s+колеи(?:\s+\d{3,4})*\s+\d{4}\s*мм"
    rf"){_CYR_END}",
    re.IGNORECASE,
)

_NARRATIVE_REPLACERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"{_CYR_BOUNDARY}пусть{_CYR_END}", re.I), " путь"),
    (re.compile(rf"{_CYR_BOUNDARY}километр(?:а|е|ов)?{_CYR_END}", re.I), " км"),
    (re.compile(rf"{_CYR_BOUNDARY}пикет{_CYR_END}", re.I), " пк"),
    (re.compile(rf"{_CYR_BOUNDARY}пике{_CYR_END}", re.I), " пк"),
    (re.compile(rf"{_CYR_BOUNDARY}на\s+станции{_CYR_END}", re.I), " станция"),
    (re.compile(rf"(\d+)\s+путь{_CYR_END}", re.I), r"путь \1"),
    (re.compile(rf"(?<![{_CYR_LETTER}]\s)(\d+)\s+звено{_CYR_END}", re.I), r"звено \1"),
    (re.compile(rf"(\d{{1,3}})\s+метр(?:а|ов)?{_CYR_END}", re.I), r"\1 м"),
)


def normalize_spaces(value: str) -> str:
    text = re.sub(r"\s+", " ", value)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    return text.strip()


def normalize_narrative_text(input_text: str) -> str:
    text = input_text
    for pattern, repl in _NARRATIVE_REPLACERS:
        text = pattern.sub(repl, text)
    return normalize_spaces(text)


def narrative_matches(raw_text: str) -> bool:
    return bool(DEFECT_RE.search(normalize_narrative_text(raw_text)))


def _sentence_case(value: str) -> str:
    trimmed = normalize_spaces(value)
    if not trimmed:
        return trimmed
    return trimmed[0].upper() + trimmed[1:]


def _extract_station_location(text: str) -> str | None:
    match = re.search(
        rf"{_CYR_BOUNDARY}станция\s+([^\d]+?)(?="
        r"\s+путь\s+\d+|\s+звено\s+\d+|\s+\d{{1,4}}\s*км|"
        r"\s+отсутствует|\s+не\s+закручен|\s+(?:уширение|ширина)\s+колеи|$)",
        text,
        re.I,
    )
    if not match or not match.group(1):
        return None
    return _sentence_case(match.group(1))


def _extract_peregon_location(text: str) -> str | None:
    match = re.search(
        rf"{_CYR_BOUNDARY}перегон\s+(.+?)(?=\s+\d{{1,4}}\s*км|\s+станция|$)",
        text,
        re.I,
    )
    if not match or not match.group(1):
        return None
    return _sentence_case(f"перегон {match.group(1)}")


def _extract_location(text: str) -> str | None:
    return _extract_station_location(text) or _extract_peregon_location(text)


def _extract_asset(text: str) -> tuple[str, str] | None:
    switch = re.search(
        rf"{_CYR_BOUNDARY}стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*(\d+){_CYR_END}",
        text,
        re.I,
    )
    if switch:
        return "switch", switch.group(1)
    track = re.search(rf"{_CYR_BOUNDARY}путь\s+(\d+){_CYR_END}", text, re.I)
    if track:
        return "track", track.group(1)
    return None


def _extract_reference(text: str) -> str | None:
    km = re.search(r"(\d{1,4})\s*км", text, re.I)
    if not km:
        return None
    parts = [f"{km.group(1)} км"]

    pk_chain = re.search(r"(\d{1,3})\s*пк\s+(\d{1,2})(?:\s+(\d{1,3})\s*м)?", text, re.I)
    if pk_chain:
        parts.append(f"пк {pk_chain.group(1)}")
        if pk_chain.group(3):
            parts.append(f"{pk_chain.group(3)} м")
        elif pk_chain.group(2):
            parts.append(f"{pk_chain.group(2)} м")
        return ", ".join(parts)

    pk_short = re.search(rf"{_CYR_BOUNDARY}пк\s*(\d{{1,2}}){_CYR_END}", text, re.I)
    if pk_short:
        parts.append(f"пк {pk_short.group(1)}")

    meters = list(re.finditer(rf"(\d{{1,3}})\s*м{_CYR_END}", text, re.I))
    if meters:
        last = meters[-1].group(1)
        if last and not any(f"{last} м" in p for p in parts):
            parts.append(f"{last} м")

    return ", ".join(parts) if len(parts) > 1 else parts[0]


def _extract_note(text: str) -> str | None:
    match = re.search(rf"{_CYR_BOUNDARY}звено\s+(\d+){_CYR_END}", text, re.I)
    return f"звено {match.group(1)}" if match else None


def _normalize_defect(defect: str) -> str:
    text = normalize_spaces(defect.lower())

    match = re.match(
        r"^отсутствует\s+(\d+)\s+(стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?$",
        text,
        re.I,
    )
    if match:
        n = match.group(1)
        return f"отсутствует {n} {match.group(2)} болт{'' if n == '1' else 'а'}"

    match = re.match(
        r"^не\s+закручен\s+(\d+)\s+(стыков(?:ой|ых)|закладн(?:ой|ых))\s+болт(?:а|ов)?$",
        text,
        re.I,
    )
    if match:
        n = match.group(1)
        return f"не закручен {n} {match.group(2)} болт{'' if n == '1' else 'а'}"

    match = re.match(r"^(уширение|ширина)\s+колеи(?:\s+\d{3,4})*\s+(\d{4})\s*мм$", text, re.I)
    if match:
        return f"{match.group(1).lower()} колеи {match.group(2)} мм"

    return normalize_spaces(defect)


def _apply_context(prev: dict[str, Any], chunk: str) -> dict[str, Any]:
    text = normalize_narrative_text(chunk)
    next_state = dict(prev)

    location = _extract_location(text)
    if location:
        next_state = {
            "location": location,
            "assetKind": None,
            "assetNumber": None,
            "reference": None,
            "note": None,
        }

    reference = _extract_reference(text)
    if reference:
        next_state["reference"] = reference
        next_state["assetKind"] = None
        next_state["assetNumber"] = None

    asset = _extract_asset(text)
    if asset:
        next_state["assetKind"] = asset[0]
        next_state["assetNumber"] = asset[1]
        next_state["reference"] = None

    note = _extract_note(text)
    if note:
        next_state["note"] = note

    return next_state


def parse_railway_narrative(raw_text: str) -> list[ParsedRow]:
    text = normalize_narrative_text(raw_text)
    matches = list(DEFECT_RE.finditer(text))
    if not matches:
        return []

    rows: list[ParsedRow] = []
    state: dict[str, Any] = {
        "location": None,
        "assetKind": None,
        "assetNumber": None,
        "reference": None,
        "note": None,
    }
    cursor = 0

    for match in matches:
        defect_raw = match.group(1)
        context_chunk = text[cursor : match.start()]
        state = _apply_context(state, context_chunk)
        source_text = normalize_spaces(f"{context_chunk} {defect_raw}")

        rows.append(
            {
                "location": state.get("location"),
                "assetKind": state.get("assetKind"),
                "assetNumber": state.get("assetNumber"),
                "reference": state.get("reference"),
                "defect": _normalize_defect(defect_raw),
                "speedLimit": None,
                "note": state.get("note"),
                "sourceText": source_text,
                "warnings": [],
            }
        )
        cursor = match.end()

    return rows


def parse_railway_narrative_to_records(raw_text: str) -> list[Any]:
    """ParsedRow → ParsedRecord через sanitize + structured_to_parsed_rows."""
    from app.services.llm.json_schema import structured_to_parsed_rows
    from app.services.sanitize_row_for_export import sanitize_row_for_export

    parsed = parse_railway_narrative(raw_text)
    if not parsed:
        return []
    sanitized = [sanitize_row_for_export(row) for row in parsed]
    return structured_to_parsed_rows({"rows": sanitized})


def prefer_narrative_parser(full_text: str) -> bool:
    """Hybrid: narrative для перегон + болты; segment — для станционных обходов."""
    from app.config import settings

    if settings.parser_mode == "narrative":
        return narrative_matches(full_text)
    if settings.parser_mode != "hybrid":
        return False
    if not narrative_matches(full_text):
        return False
    norm = normalize_narrative_text(full_text)
    has_peregon = bool(re.search(r"перегон", norm, re.I))
    has_bolt = bool(re.search(r"отсутствует|не\s+закручен", norm, re.I))
    return has_peregon and has_bolt
