"""Yandex SpeechKit — облачное распознавание русской речи."""

from __future__ import annotations

import logging
import wave
from pathlib import Path

import httpx

from app.config import settings
from app.services.parser import TranscriptSegment

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"
SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
# Синхронный API Yandex: лимит ~1 МБ LPCM (~32 с). Берём запас.
MAX_LPCM_BYTES = 960_000
MAX_CHUNK_SEC = 30.0


def _auth_headers() -> dict[str, str]:
    """IAM-токен (авторизованный ключ) надёжнее API-key для сервисного аккаунта."""
    if settings.yandex_sa_authorized_key.strip():
        from app.services.asr.yandex_iam import get_iam_token

        return {"Authorization": f"Bearer {get_iam_token()}"}
    api_key = settings.yandex_speech_api_key.strip()
    if not api_key:
        raise RuntimeError(
            "Задайте YANDEX_SA_AUTHORIZED_KEY (рекомендуется) или YANDEX_SPEECH_API_KEY"
        )
    return {"Authorization": f"Api-Key {api_key}"}


def _wav_to_lpcm(wav_path: Path) -> bytes:
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != SAMPLE_WIDTH:
            raise ValueError("Ожидается mono 16-bit WAV (конвертируйте через ffmpeg)")
        if wf.getframerate() != SAMPLE_RATE:
            raise ValueError(f"Ожидается {SAMPLE_RATE} Hz WAV (конвертируйте через ffmpeg)")
        return wf.readframes(wf.getnframes())


def _recognize_lpcm(lpcm: bytes) -> str:
    headers = _auth_headers()
    params: dict[str, str | int] = {
        "lang": "ru-RU",
        "format": "lpcm",
        "sampleRateHertz": SAMPLE_RATE,
        "topic": "general",
    }

    try:
        with httpx.Client(timeout=120.0) as client:
            resp = client.post(STT_URL, headers=headers, params=params, content=lpcm)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        body = exc.response.text[:400] if exc.response is not None else ""
        if exc.response is not None and exc.response.status_code == 401:
            raise RuntimeError(
                "Yandex SpeechKit: доступ запрещён (401). "
                "Рекомендуется YANDEX_SA_AUTHORIZED_KEY (авторизованный ключ SA). "
                "У speechkit-railway должна быть роль ai.speechkit-stt.user на каталоге. "
                f"Ответ: {body or exc}"
            ) from exc
        raise RuntimeError(
            f"Yandex SpeechKit HTTP {exc.response.status_code}: {body or exc}"
        ) from exc
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Yandex SpeechKit: {exc}") from exc

    return str(data.get("result", "")).strip()


def _split_lpcm(lpcm: bytes) -> list[bytes]:
    if len(lpcm) <= MAX_LPCM_BYTES:
        return [lpcm]

    frame_bytes = SAMPLE_WIDTH
    chunk_frames = int(MAX_CHUNK_SEC * SAMPLE_RATE)
    chunk_bytes = chunk_frames * frame_bytes
    chunks: list[bytes] = []
    offset = 0
    while offset < len(lpcm):
        end = min(offset + chunk_bytes, len(lpcm))
        piece = lpcm[offset:end]
        piece = piece[: len(piece) - (len(piece) % frame_bytes)]
        if piece:
            chunks.append(piece)
        offset = end
    return chunks or [lpcm]


def transcribe_yandex(file_path: Path) -> tuple[str, list[TranscriptSegment]]:
    if not settings.yandex_sa_authorized_key.strip() and not settings.yandex_speech_api_key.strip():
        raise RuntimeError("YANDEX_SA_AUTHORIZED_KEY или YANDEX_SPEECH_API_KEY не задан")

    lpcm = _wav_to_lpcm(file_path)
    chunks = _split_lpcm(lpcm)
    texts: list[str] = []
    segments: list[TranscriptSegment] = []
    offset_sec = 0.0

    for i, chunk in enumerate(chunks):
        text = _recognize_lpcm(chunk)
        if text:
            texts.append(text)
        chunk_sec = len(chunk) / (SAMPLE_RATE * SAMPLE_WIDTH)
        if text:
            segments.append(
                TranscriptSegment(offset_sec, offset_sec + chunk_sec, text, confidence=0.9)
            )
        offset_sec += chunk_sec
        if len(chunks) > 1:
            logger.info("Yandex STT chunk %d/%d: %.1fs", i + 1, len(chunks), chunk_sec)

    full_text = " ".join(texts).strip()
    if not full_text:
        raise RuntimeError("Yandex SpeechKit вернул пустой результат")

    duration = len(lpcm) / (SAMPLE_RATE * SAMPLE_WIDTH)
    if not segments:
        segments = [TranscriptSegment(0.0, duration, full_text, confidence=0.9)]

    logger.info("Yandex STT: %s, %.1fs, %d chunk(s)", file_path.name, duration, len(chunks))
    return full_text, segments
