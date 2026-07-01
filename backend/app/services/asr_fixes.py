"""Типовые ASR-ошибки в обходных записях."""

from __future__ import annotations

import re

# «острие остряка пусть 15» → «… путь 15» (Whisper путает «путь» и «пусть»)
_PUST_AFTER_SWITCH_TIP_RE = re.compile(
    r"(\bостри[ея]\s+остряк\w*\s+)пусть\s+(\d{1,2})\b",
    re.IGNORECASE,
)
# «пусть 15 ширина колеи» → «путь 15 ширина колеи»
_PUST_BEFORE_DEFECT_RE = re.compile(
    r"\bпусть\s+(\d{1,2})\b(?=\s+(?:ширина|уширен|сужен|износ|куст))",
    re.IGNORECASE,
)
# Whisper часто обрезает окончание: «ширина коли 1544»
_SHIRINA_KOLI_RE = re.compile(r"\bширина\s+коли\b", re.IGNORECASE)


def fix_asr_transcript(text: str) -> str:
    if not text:
        return text
    fixed = _PUST_AFTER_SWITCH_TIP_RE.sub(r"\1путь \2", text)
    fixed = _PUST_BEFORE_DEFECT_RE.sub(r"путь \1", fixed)
    fixed = _SHIRINA_KOLI_RE.sub("ширина колеи", fixed)
    return fixed
