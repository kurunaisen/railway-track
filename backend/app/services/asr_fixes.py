"""Нормализация ASR-текста перед разбором (типовые ошибки Whisper)."""

from __future__ import annotations

import re

_PUST_RE = re.compile(r"\bпусть\b", re.IGNORECASE)
_KOLI_RE = re.compile(r"\bколи\b", re.IGNORECASE)
_STRP_RE = re.compile(r"\bстр[.\s]*п[.\s]?\b", re.IGNORECASE)
_WS_RE = re.compile(r"\s+")


def normalize_asr_text(text: str) -> str:
    if not text:
        return text
    fixed = _PUST_RE.sub("путь", text)
    fixed = _KOLI_RE.sub("колеи", fixed)
    fixed = _STRP_RE.sub("стрелочный перевод ", fixed)
    return _WS_RE.sub(" ", fixed).strip()


def fix_asr_transcript(text: str) -> str:
    """Alias для совместимости с существующим конвейером."""
    return normalize_asr_text(text)
