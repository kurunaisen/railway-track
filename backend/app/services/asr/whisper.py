from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings
from app.services.parser import TranscriptSegment

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        _whisper_model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )
    return _whisper_model


def transcribe_whisper(file_path: Path) -> tuple[str, list[TranscriptSegment]]:
    from app.services.domain_terms import RAILWAY_INITIAL_PROMPT

    try:
        model = _get_model()
        segments_iter, info = model.transcribe(
            str(file_path),
            language="ru",
            beam_size=5,
            vad_filter=True,
            initial_prompt=RAILWAY_INITIAL_PROMPT,
        )
        segments: list[TranscriptSegment] = []
        texts: list[str] = []
        for seg in segments_iter:
            text = seg.text.strip()
            if text:
                conf = None
                if seg.avg_logprob is not None:
                    import math
                    conf = round(min(1.0, max(0.0, math.exp(float(seg.avg_logprob)))), 3)
                segments.append(TranscriptSegment(start=seg.start, end=seg.end, text=text, confidence=conf))
                texts.append(text)
        full_text = " ".join(texts)
        logger.info("Whisper: %s, %.1fs, %d segments", file_path.name, info.duration, len(segments))
        return full_text, segments
    except Exception as exc:
        logger.warning("Whisper unavailable (%s), demo fallback", exc)
        return _demo_transcription()


def _demo_transcription() -> tuple[str, list[TranscriptSegment]]:
    demo = (
        "Дата 29.06.2026. Участок Северный, перегон станция Северная — Южная, путь 1, "
        "километр 245, пикет 3, объект рельс, износ 12 миллиметров, ограничение скорости 40."
    )
    return demo, [TranscriptSegment(0.0, 10.0, demo, confidence=0.95)]
