"""Разбор километража: паузы в речи и км в названии блок-поста."""

from __future__ import annotations

import re

_SPLIT_KM_RE = re.compile(
    r"\b(\d{1,4})\s+(\d{2,3})\s*(км\.?|километр(?:а|ов)?)\b",
    re.IGNORECASE,
)

_KM_VALUE_PATTERNS = (
    re.compile(r"(?:километр|км\.?)\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:километр|км\.?)\b", re.IGNORECASE),
)

_LOCATION_KM_BEFORE_RE = re.compile(
    r"(?:"
    r"блок\s*[- ]?пост|блокпост|о\.?\s*п\.?|"
    r"ост(?:\.|\s)?\s*пункт|остановочный\s+пункт"
    r")\s*\d*\s*$",
    re.IGNORECASE,
)


def merge_split_km_numbers(first: str, second: str) -> str | None:
    """
    «1000 385» → «1385»: сначала сказали «тысяча», затем «385 км».
    """
    try:
        a, b = int(first), int(second)
    except ValueError:
        return None
    if not (1 <= b <= 999):
        return None

    candidates: list[int] = []
    if a in (1, 10, 100, 1000):
        candidates.append(int(str(a)[0] + second))
    if a % 1000 == 0 and a >= 1000:
        candidates.append((a // 1000) * 1000 + b)

    for value in candidates:
        if 100 <= value <= 9999:
            return str(value)
    return None


def merge_hesitated_km_in_text(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        merged = merge_split_km_numbers(match.group(1), match.group(2))
        if merged:
            return f"{merged} {match.group(3)}"
        return match.group(0)

    return _SPLIT_KM_RE.sub(repl, text)


def merge_hesitated_km_value(value: str | None) -> str | None:
    if not value:
        return value
    cleaned = value.replace(",", ".").strip()
    parts = cleaned.split()
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        merged = merge_split_km_numbers(parts[0], parts[1])
        if merged:
            return merged
    m = _SPLIT_KM_RE.search(cleaned)
    if m:
        merged = merge_split_km_numbers(m.group(1), m.group(2))
        if merged:
            return merged
    return cleaned


def _is_location_km_context(text: str, match_start: int) -> bool:
    before = text[max(0, match_start - 50):match_start]
    return bool(_LOCATION_KM_BEFORE_RE.search(before))


def extract_binding_km(text: str) -> str | None:
    """Км привязки дефекта; км в названии блок-поста не считается."""
    normalized = merge_hesitated_km_in_text(text)
    candidates: list[tuple[int, str]] = []
    for pattern in _KM_VALUE_PATTERNS:
        for match in pattern.finditer(normalized):
            if _is_location_km_context(normalized, match.start()):
                continue
            candidates.append((match.start(), match.group(1).replace(",", ".")))
    if not candidates:
        return None
    return candidates[-1][1]
