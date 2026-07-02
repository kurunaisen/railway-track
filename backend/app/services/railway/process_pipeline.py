"""Новый pipeline: SpeechKit → transcript → LLM → RailwayRow[] → Excel."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from app.models import ProcessingJob
from app.services.llm.extract_railway_rows import extract_railway_rows
from app.services.parser import TranscriptSegment
from app.services.railway.export_railway_xlsx import export_railway_xlsx
from app.services.railway.types import RailwayRow
from app.services.asr_fixes import normalize_asr_text
from app.services.speech.transcribe_with_yandex import transcribe_with_yandex


def transcribe_audio(audio_path: Path) -> tuple[str, list[TranscriptSegment]]:
    return transcribe_with_yandex(audio_path)


def rows_from_transcript(transcript: str) -> list[RailwayRow]:
    return extract_railway_rows(normalize_asr_text(transcript))


def railway_rows_from_job(job: ProcessingJob) -> list[RailwayRow]:
    meta = job.get_pipeline_metadata() or {}
    rows: list[RailwayRow] = []
    for raw in meta.get("railway_rows", []):
        try:
            rows.append(RailwayRow.model_validate(raw))
        except ValidationError:
            continue
    return rows


def export_rows_to_xlsx(
    rows: list[RailwayRow],
    *,
    include_source_text: bool = False,
):
    return export_railway_xlsx(rows, include_source_text=include_source_text)
