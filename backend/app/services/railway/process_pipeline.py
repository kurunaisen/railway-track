"""Новый pipeline: SpeechKit → transcript → LLM → RailwayRow[] → Excel."""

from __future__ import annotations

from pathlib import Path

from app.services.llm.extract_railway_rows import extract_railway_rows
from app.services.parser import TranscriptSegment
from app.services.railway.export_railway_xlsx import export_railway_xlsx
from app.services.railway.types import RailwayRow
from app.services.speech.transcribe_with_yandex import transcribe_with_yandex


def transcribe_audio(audio_path: Path) -> tuple[str, list[TranscriptSegment]]:
    return transcribe_with_yandex(audio_path)


def rows_from_transcript(transcript: str) -> list[RailwayRow]:
    return extract_railway_rows(transcript)


def export_rows_to_xlsx(
    rows: list[RailwayRow],
    *,
    include_source_text: bool = False,
):
    return export_railway_xlsx(rows, include_source_text=include_source_text)
