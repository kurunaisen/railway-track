"""Указатель стороны рельсовой нити (левая/правая по ходу километража)."""

from __future__ import annotations

import re

_RAIL_SIDE_PHRASE_RE = re.compile(
    r"(?:"
    r"(?:на\s+)?(?:лев(?:ой|ая|ую)|прав(?:ой|ая|ую))\s+"
    r"(?:"
    r"сторон(?:е|а|у)\s+"
    r")?"
    r"(?:"
    r"(?:рельсов(?:ой|ая|ую|ые)\s+)?(?:кол(?:еи|ьи|еи)\s+)?(?:нит(?:и|ь|ью|и))?"
    r"|"
    r"сторон(?:а|ы|у)\s+(?:рельсов(?:ой|ая)\s+)?нит(?:и|ь|и)\s+(?:лев(?:ая|ой|ую)|прав(?:ая|ой|ую))"
    r")"
    r"|"
    r"(?:рельсов(?:ой|ая)\s+)?нит(?:ь|и)\s+(?:лев(?:ая|ой|ую)|прав(?:ая|ой|ую))"
    r")",
    re.IGNORECASE,
)

_LEFT_RE = re.compile(r"\b(?:лев(?:ой|ая|ую)|слева)\b", re.IGNORECASE)
_RIGHT_RE = re.compile(r"\b(?:прав(?:ой|ая|ую)|справа)\b", re.IGNORECASE)
_RAIL_CONTEXT_RE = re.compile(r"\b(?:рельс|нит(?:ь|и)|коле(?:я|и)|сторон)\b", re.IGNORECASE)

_DEFECT_HINT_RE = re.compile(
    r"\b(?:"
    r"отсутств|неисправ|дефект|поврежд|трещин|износ|просад|отслоен|выбоин|"
    r"перекос|болт|стыков|шпал|слом|разруш|ослаб"
    r")\w*",
    re.IGNORECASE,
)


def extract_rail_side(text: str | None) -> str | None:
    """«на левой стороне рельсовой нити» → «левая нить»."""
    if not text:
        return None
    if not _RAIL_SIDE_PHRASE_RE.search(text) and not (
        _RAIL_CONTEXT_RE.search(text) and (_LEFT_RE.search(text) or _RIGHT_RE.search(text))
    ):
        return None
    if _LEFT_RE.search(text) and not _RIGHT_RE.search(text):
        return "левая нить"
    if _RIGHT_RE.search(text) and not _LEFT_RE.search(text):
        return "правая нить"
    return None


def strip_rail_side_phrases(text: str) -> str:
    cleaned = _RAIL_SIDE_PHRASE_RE.sub(" ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:-")
    return cleaned


def is_rail_side_only_fragment(text: str | None) -> bool:
    if not text or not text.strip():
        return False
    side = extract_rail_side(text)
    if not side:
        return False
    remainder = strip_rail_side_phrases(text)
    remainder = re.sub(
        r"\b(?:на|у|по|в|сторон(?:е|а|у)|рельсов(?:ой|ая)|кол(?:еи|ьи))\b",
        " ",
        remainder,
        flags=re.IGNORECASE,
    )
    remainder = re.sub(r"\s+", " ", remainder).strip(" ,.;:-")
    if not remainder:
        return True
    if len(remainder) < 4:
        return True
    return not bool(_DEFECT_HINT_RE.search(remainder))


def is_defect_continuation(text: str | None) -> bool:
    """Обрыв ASR вроде отдельного «Болт» после «стыковой»."""
    if not text:
        return False
    t = text.strip().lower()
    if len(t) > 30:
        return False
    if extract_rail_side(t):
        return False
    if _DEFECT_HINT_RE.search(t) and not re.search(r"\b(?:перегон|пикет|километр|км\.?)\b", t):
        return True
    return len(t.split()) <= 2 and bool(_DEFECT_HINT_RE.search(t))
