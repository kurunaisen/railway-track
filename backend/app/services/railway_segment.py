"""Извлечение местонахождения и разбиение ASR-текста на сегменты по пути/стрелке."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.asr_fixes import normalize_asr_text

_STATION_RE = re.compile(
    r"\bстанц(?:ия|ии)\s+([А-ЯЁA-Z][А-ЯЁA-Zа-яёa-z0-9-]*)",
    re.IGNORECASE,
)
_MARKER_RE = re.compile(
    r"(?:стрелоч(?:ный|ного)\s+перевод(?:\s*(?:№|номер))?\s*\d+|путь\s+\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SegmentedBlock:
    location: str | None
    segment: str


def _capitalize_name(value: str) -> str:
    if not value:
        return value
    return value[0].upper() + value[1:].lower()


def segment_railway_text(input_text: str) -> list[SegmentedBlock]:
    text = normalize_asr_text(input_text)

    station_match = _STATION_RE.search(text)
    location = _capitalize_name(station_match.group(1)) if station_match else None

    body = (
        text[station_match.end() :].strip()
        if station_match
        else text
    )

    matches = list(_MARKER_RE.finditer(body))
    if not matches:
        return [SegmentedBlock(location=location, segment=body)] if body else []

    result: list[SegmentedBlock] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        segment = body[start:end].strip()
        if segment:
            result.append(SegmentedBlock(location=location, segment=segment))
    return result
