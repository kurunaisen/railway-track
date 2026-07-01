"""Yandex SpeechKit — единственный ASR в новом pipeline."""

from __future__ import annotations

from pathlib import Path

from app.services.asr.yandex import transcribe_yandex
from app.services.parser import TranscriptSegment


def transcribe_with_yandex(audio_path: Path) -> tuple[str, list[TranscriptSegment]]:
    return transcribe_yandex(audio_path)
