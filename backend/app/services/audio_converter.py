"""Конвертация аудио в рабочий формат: mono, 16 kHz, WAV."""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


def _find_ffmpeg() -> str:
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise RuntimeError(
        "ffmpeg не найден. Установите ffmpeg и добавьте в PATH: "
        "https://ffmpeg.org/download.html"
    )


def convert_to_working_wav(source: Path, dest: Path | None = None) -> Path:
    """
    Конвертирует аудиофайл в mono 16 kHz WAV.
    Возвращает путь к результирующему файлу.
    """
    if dest is None:
        dest = source.with_suffix(".working.wav")

    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg,
        "-y",
        "-i",
        str(source),
        "-ac",
        str(TARGET_CHANNELS),
        "-ar",
        str(TARGET_SAMPLE_RATE),
        "-c:a",
        "pcm_s16le",
        str(dest),
    ]
    logger.info("Converting audio: %s -> %s", source.name, dest.name)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Ошибка ffmpeg: {result.stderr[-500:]}")

    if not dest.exists():
        raise RuntimeError("Конвертация не создала выходной файл")

    return dest


def is_wav_16k_mono(path: Path) -> bool:
    """Проверяет, соответствует ли WAV уже рабочему формату (упрощённо по имени/расширению)."""
    return path.suffix.lower() == ".wav" and ".working." in path.name
