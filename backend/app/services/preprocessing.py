"""Шаг 2: предобработка аудио — нормализация, нарезка по тишине, метаданные."""

from __future__ import annotations

import json
import logging
import re
import shutil
import subprocess
import wave
from dataclasses import dataclass, field
from pathlib import Path

from app.config import settings
from app.services.audio_converter import convert_to_working_wav

logger = logging.getLogger(__name__)


@dataclass
class AudioMetadata:
    duration_sec: float = 0.0
    sample_rate: int = 0
    channels: int = 0
    bit_depth: int = 0
    file_size_bytes: int = 0
    format: str = ""
    chunks: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "duration_sec": self.duration_sec,
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "bit_depth": self.bit_depth,
            "file_size_bytes": self.file_size_bytes,
            "format": self.format,
            "chunks": self.chunks,
        }


def preprocess_audio(source: Path, session_id: int) -> tuple[Path, AudioMetadata]:
    """
    Нормализует в mono 16 kHz WAV, при необходимости режет по тишине,
    извлекает метаданные.
    """
    working = settings.upload_dir / f"session_{session_id}.working.wav"
    converted = convert_to_working_wav(source, working)
    metadata = extract_metadata(converted, source)

    if settings.split_on_silence and metadata.duration_sec > settings.silence_split_min_duration:
        chunks = detect_silence_chunks(converted)
        metadata.chunks = chunks
        logger.info("Silence chunks detected: %d", len(chunks))

    return converted, metadata


def extract_metadata(wav_path: Path, original: Path) -> AudioMetadata:
    meta = AudioMetadata(file_size_bytes=original.stat().st_size if original.exists() else 0)
    meta.format = wav_path.suffix.lower().lstrip(".")
    try:
        with wave.open(str(wav_path), "rb") as wf:
            meta.channels = wf.getnchannels()
            meta.sample_rate = wf.getframerate()
            meta.bit_depth = wf.getsampwidth() * 8
            meta.duration_sec = wf.getnframes() / float(wf.getframerate())
    except Exception as exc:
        logger.warning("wave metadata failed: %s", exc)
    return meta


def detect_silence_chunks(wav_path: Path, noise_db: int = -35, min_silence: float = 1.2) -> list[dict]:
    """Определяет границы фрагментов между паузами через ffmpeg silencedetect."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return []

    cmd = [
        ffmpeg, "-i", str(wav_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    output = result.stderr

    silence_starts = [float(x) for x in re.findall(r"silence_start:\s*([\d.]+)", output)]
    silence_ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", output)]

    chunks: list[dict] = []
    prev_end = 0.0
    for i, s_start in enumerate(silence_starts):
        if s_start > prev_end + 0.3:
            chunks.append({"start": round(prev_end, 2), "end": round(s_start, 2)})
        if i < len(silence_ends):
            prev_end = silence_ends[i]

    duration = extract_metadata(wav_path, wav_path).duration_sec
    if duration and prev_end < duration - 0.3:
        chunks.append({"start": round(prev_end, 2), "end": round(duration, 2)})

    return chunks
