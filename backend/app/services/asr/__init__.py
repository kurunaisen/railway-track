from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.services.parser import TranscriptSegment

logger = logging.getLogger(__name__)


def transcribe(audio_path: Path) -> tuple[str, list[TranscriptSegment]]:
    """Фабрика ASR: faster-whisper (локально) или Yandex SpeechKit."""
    provider = settings.asr_provider
    if provider == "yandex":
        if not settings.yandex_speech_api_key and not settings.yandex_sa_authorized_key:
            raise RuntimeError(
                "Задайте YANDEX_SA_AUTHORIZED_KEY (рекомендуется) или YANDEX_SPEECH_API_KEY "
                "в переменных окружения Railway."
            )
        from app.services.asr.yandex import transcribe_yandex

        return transcribe_yandex(audio_path)
    from app.services.asr.whisper import transcribe_whisper

    return transcribe_whisper(audio_path)


def segments_to_json(segments: list[TranscriptSegment]) -> str:
    import json

    return json.dumps(
        [
            {
                "start": s.start,
                "end": s.end,
                "text": s.text,
                "confidence": s.confidence,
            }
            for s in segments
        ],
        ensure_ascii=False,
    )
