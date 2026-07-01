"""Адаптер audio_files + jobs → AudioSessionOut (обратная совместимость API)."""

from __future__ import annotations

import logging
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models import AudioFile, Export, ProcessingJob
from app.schemas import (
    AudioSessionOut,
    JobOut,
    LogicalBlockOut,
    LogicalRecordOut,
    SessionSummaryOut,
    StructuredRecordsOut,
    RailwayRowOut,
    TrackRecordOut,
    TranscriptSegmentOut,
    WideTableOut,
)
from app.services.inspection_repository import load_structured_records
from app.services.transcript_crypto import decrypt_transcript_text
from app.services.inspection_repository import FlatInspectionRow, load_active_job, load_flat_rows, load_latest_done_job
from app.services.inspection_form import build_form_rows
from app.services.parser import ParsedRecord
from app.services.switch_context import propagate_switch_context
from app.services.pipeline_issues import normalize_pipeline_issues
from app.services.wide_table import build_wide_rows

logger = logging.getLogger(__name__)


def _derive_status(audio: AudioFile, active: ProcessingJob | None, done: ProcessingJob | None) -> str:
    if active:
        return "queued" if active.status == "queued" else "processing"
    if done:
        meta = done.get_pipeline_metadata()
        if meta.get("confirmed"):
            return "confirmed"
        if meta.get("saved"):
            return "saved"
        return "processed"
    return "uploaded"


def _enrich_switch_from_transcript(
    rows: list[FlatInspectionRow],
    full_transcript: str | None,
) -> None:
    """Старые записи без switch_number в БД — восстановить из ASR."""
    if not full_transcript or not rows or all(r.switch for r in rows):
        return
    tmp = [
        ParsedRecord(
            logical_record_index=r.logical_record_index,
            put=r.put,
            switch=r.switch,
        )
        for r in rows
    ]
    propagate_switch_context(tmp, full_transcript)
    by_idx = {t.logical_record_index: t for t in tmp}
    for row in rows:
        if row.switch:
            continue
        src = by_idx.get(row.logical_record_index)
        if src and src.switch:
            row.switch = src.switch


def _flat_to_track_out(row: FlatInspectionRow) -> TrackRecordOut:
    return TrackRecordOut(
        id=row.id,
        session_id=row.session_id,
        row_order=row.row_order,
        record_date=row.record_date,
        uchastok=row.uchastok,
        peregon=row.peregon,
        put=row.put,
        switch=row.switch,
        km=row.km,
        piket=row.piket,
        obekt=row.obekt,
        parameter=row.parameter,
        value=row.value,
        unit=row.unit,
        defect=row.defect,
        comment=row.comment,
        speed_limit=row.speed_limit,
        raw_text=row.raw_text,
        segment_start=row.segment_start,
        segment_end=row.segment_end,
        disputed_fields=row.disputed_fields,
        validation_errors=row.validation_errors,
        logical_record_index=row.logical_record_index,
        logical_block_index=row.logical_block_index,
        position_index=row.position_index,
        position_type=row.position_type,
    )


def _build_logical_records(rows: list[FlatInspectionRow]) -> list[LogicalRecordOut]:
    grouped: dict[int, list[FlatInspectionRow]] = {}
    for row in rows:
        key = row.logical_record_index if row.logical_record_index is not None else 0
        grouped.setdefault(key, []).append(row)

    result: list[LogicalRecordOut] = []
    for idx in sorted(grouped.keys()):
        group = grouped[idx]
        first = group[0]
        result.append(
            LogicalRecordOut(
                index=idx,
                peregon=first.peregon,
                put=first.put,
                km=first.km,
                piket=first.piket,
                comment=first.comment,
                segment_start=first.segment_start,
                segment_end=first.segment_end,
                positions_count=len(group),
            )
        )
    return result


def _job_to_out(job: ProcessingJob) -> JobOut:
    return JobOut(
        id=job.id,
        session_id=job.audio_file_id,
        celery_task_id=job.celery_task_id,
        status=_api_job_status(job.status),
        current_step=job.current_step,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.finished_at,
    )


def _api_job_status(status: str) -> str:
    return {
        "queued": "queued",
        "processing": "running",
        "done": "completed",
        "failed": "failed",
    }.get(status, status)


def audio_file_to_session_out(db: Session, audio: AudioFile) -> AudioSessionOut:
    active = load_active_job(db, audio.id)
    done = load_latest_done_job(db, audio.id)
    job = active or done

    rows: list[FlatInspectionRow] = []
    full_transcript: str | None = None
    segments: list[TranscriptSegmentOut] = []
    logical_blocks: list[LogicalBlockOut] = []
    unknown_terms: list[dict] = []
    parse_errors: list[dict] = []
    validation_warnings: list[dict] = []
    file_metadata: dict = {}
    asr_avg: float | None = None
    confirmed = False

    if done:
        rows = load_flat_rows(done, audio.id)
        if done.transcript:
            full_transcript = decrypt_transcript_text(
                done.transcript.full_text, done.transcript.text_encrypted
            )
            _enrich_switch_from_transcript(rows, full_transcript)
            asr_avg = done.transcript.confidence_avg
            segments = [
                TranscriptSegmentOut(
                    start=s.start_sec or 0,
                    end=s.end_sec or 0,
                    text=s.text,
                    confidence=s.confidence,
                )
                for s in sorted(done.transcript.segments, key=lambda x: x.segment_index)
            ]
        meta = done.get_pipeline_metadata()
        logical_blocks = []
        for block in meta.get("logical_blocks", []):
            try:
                logical_blocks.append(LogicalBlockOut(**block))
            except (ValidationError, TypeError) as exc:
                logger.warning("Skip invalid logical block for job %s: %s", done.id, exc)
        file_metadata = meta.get("file_metadata", {})
        parse_errors, validation_warnings = normalize_pipeline_issues(meta.get("parse_errors", []))
        confirmed = bool(meta.get("confirmed"))
        unknown_terms = [
            {"term": t.term_text, "count": 1, "context": t.context_text}
            for t in done.unknown_terms
        ]

    flat_for_wide = rows
    cols, wide_rows = build_wide_rows(flat_for_wide)
    form_cols, form_rows = build_form_rows(flat_for_wide)

    structured = None
    if done and done.inspection_records:
        try:
            structured = StructuredRecordsOut(**load_structured_records(done))
        except ValidationError as exc:
            logger.warning("Skip invalid structured records for job %s: %s", done.id, exc)

    railway_rows: list[RailwayRowOut] = []
    if done:
        meta = done.get_pipeline_metadata() or {}
        for raw in meta.get("railway_rows", []):
            try:
                railway_rows.append(RailwayRowOut.model_validate(raw))
            except ValidationError as exc:
                logger.warning("Skip invalid railway row in job %s: %s", done.id, exc)

    return AudioSessionOut(
        id=audio.id,
        filename=audio.stored_path,
        original_name=audio.original_filename,
        status=_derive_status(audio, active, done),
        full_transcript=full_transcript,
        confirmed=confirmed,
        asr_avg_confidence=asr_avg,
        created_at=audio.created_at,
        updated_at=audio.updated_at,
        records=[_flat_to_track_out(r) for r in rows],
        transcript_segments=segments,
        logical_blocks=logical_blocks,
        logical_records=_build_logical_records(rows),
        unknown_terms=unknown_terms,
        parse_errors=parse_errors,
        validation_warnings=validation_warnings,
        file_metadata=file_metadata,
        records_wide=WideTableOut(columns=cols, rows=wide_rows) if wide_rows else None,
        records_form=WideTableOut(columns=form_cols, rows=form_rows) if form_rows else None,
        active_job=_job_to_out(active) if active else None,
        logical_blocks_count=len(logical_blocks),
        records_count=len(rows),
        logical_records_count=len(_build_logical_records(rows)),
        positions_count=len(rows),
        structured_records=structured,
        railway_rows=railway_rows,
    )


def _count_positions(job: ProcessingJob | None) -> int:
    if not job:
        return 0
    return sum(len(rec.items) for rec in job.inspection_records)


def _export_stats(db: Session, audio_file_id: int) -> tuple[int, datetime | None]:
    rows = (
        db.query(Export.created_at)
        .join(ProcessingJob)
        .filter(ProcessingJob.audio_file_id == audio_file_id)
        .order_by(Export.created_at.desc())
        .all()
    )
    if not rows:
        return 0, None
    last: datetime = rows[0][0]
    return len(rows), last


def audio_file_to_summary(db: Session, audio: AudioFile) -> SessionSummaryOut:
    active = load_active_job(db, audio.id)
    done = load_latest_done_job(db, audio.id)
    status = _derive_status(audio, active, done)
    confirmed = False
    positions_count = 0
    if done:
        meta = done.get_pipeline_metadata()
        confirmed = bool(meta.get("confirmed"))
        positions_count = _count_positions(done)
    export_count, last_export_at = _export_stats(db, audio.id)
    return SessionSummaryOut(
        id=audio.id,
        original_name=audio.original_filename,
        status=status,
        created_at=audio.created_at,
        updated_at=audio.updated_at,
        positions_count=positions_count,
        confirmed=confirmed,
        has_table=positions_count > 0,
        export_count=export_count,
        last_export_at=last_export_at,
    )


def get_audio_file_or_404(db: Session, audio_file_id: int) -> AudioFile:
    audio = db.query(AudioFile).filter(AudioFile.id == audio_file_id).first()
    if not audio:
        raise ValueError("not found")
    return audio
