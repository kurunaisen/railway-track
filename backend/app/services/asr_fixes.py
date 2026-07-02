"""Нормализация ASR-текста перед разбором (типовые ошибки Whisper)."""

from __future__ import annotations

import re

from app.services.user_asr_corrections import apply_user_corrections

_PUST_RE = re.compile(r"\bпусть\b", re.IGNORECASE)
_KOLI_RE = re.compile(r"\bколи\b", re.IGNORECASE)
_PIKE_RE = re.compile(r"\bпике\b", re.IGNORECASE)
_OSTRII_RE = re.compile(r"\bострии\s+остряка\b", re.IGNORECASE)
_STRP_RE = re.compile(r"\bстр[.\s]*п[.\s]?\b", re.IGNORECASE)
_LIZAT_RE = re.compile(r"\bлизат\b", re.IGNORECASE)
_MAGNETITY_SHONGUY_RE = re.compile(
    r"\b(?:от\s+)?никит\w*\s+ш[оа](?:н|нг|мг|м)\w*\b|"
    r"\bмагн[еи]т\w*\s*[-–—]?\s*ш[оа](?:н|нг|мг|м)\w*\b",
    re.IGNORECASE,
)
_KOLA_MURMANSK_ASR_RE = re.compile(
    r"\bперед\s+гонк(?:ой|а|у)?\s+мурманск(?:ом|а)?\b",
    re.IGNORECASE,
)
_WS_RE = re.compile(r"\s+")


def normalize_asr_text(text: str) -> str:
    if not text:
        return text
    fixed = _PUST_RE.sub("путь", text)
    fixed = _KOLI_RE.sub("колеи", fixed)
    fixed = _PIKE_RE.sub("пикет", fixed)
    fixed = _OSTRII_RE.sub("острие остряка", fixed)
    fixed = _STRP_RE.sub("стрелочный перевод ", fixed)
    fixed = _LIZAT_RE.sub("лежат", fixed)
    fixed = _MAGNETITY_SHONGUY_RE.sub("Магнетиты — Шонгуй", fixed)
    fixed = _KOLA_MURMANSK_ASR_RE.sub("перегон Кола — Мурманск", fixed)
    fixed = apply_user_corrections(fixed)
    return _WS_RE.sub(" ", fixed).strip()


def fix_asr_transcript(text: str) -> str:
    """Alias для совместимости с существующим конвейером."""
    return normalize_asr_text(text)
