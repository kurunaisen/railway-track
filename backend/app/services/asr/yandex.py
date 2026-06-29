"""Yandex SpeechKit — облачное распознавание русской речи."""

from __future__ import annotations

import logging
import struct
import wave
from pathlib import Path

import httpx

from app.config import settings
from app.services.parser import TranscriptSegment

logger = logging.getLogger(__name__)

STT_URL = "https://stt.api.cloud.yandex.net/speech/v1/stt:recognize"


def _wav_to_lpcm(wav_path: Path) -> bytes:
    with wave.open(str(wav_path), "rb") as wf:
        if wf.getnchannels() != 1 or wf.getsampwidth() != 2:
            raise ValueError("Ожидается mono 16-bit WAV (конвертируйте через ffmpeg)")
        return wf.readframes(wf.getnframes())


def transcribe_yandex(file_path: Path) -> tuple[str, list[TranscriptSegment]]:
    if not settings.yandex_speech_api_key:
        raise RuntimeError("YANDEX_SPEECH_API_KEY не задан")

    lpcm = _wav_to_lpcm(file_path)
    headers = {"Authorization": f"Api-Key {settings.yandex_speech_api_key}"}
    params: dict[str, str | int] = {
        "lang": "ru-RU",
        "format": "lpcm",
        "sampleRateHertz": 16000,
        "topic": "general",
    }
    if settings.yandex_speech_folder_id:
        headers["x-folder-id"] = settings.yandex_speech_folder_id

    with httpx.Client(timeout=120.0) as client:
        resp = client.post(STT_URL, headers=headers, params=params, content=lpcm)
        resp.raise_for_status()
        data = resp.json()

    full_text = data.get("result", "").strip()
    if not full_text:
        raise RuntimeError("Yandex SpeechKit вернул пустой результат")

    duration = len(lpcm) / (16000 * 2)
    segments = [TranscriptSegment(0.0, duration, full_text, confidence=0.9)]
    logger.info("Yandex STT: %s, %.1fs", file_path.name, duration)
    return full_text, segments
