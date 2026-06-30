"""10-шаговый конвейер обработки одного аудио (схема FR 11)."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import IntEnum

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AudioFile, ProcessingJob
from app.services.asr import transcribe
from app.services.inspection_repository import save_job_results
from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.preprocessing import preprocess_audio
from app.services.segmentation import segment_logical_blocks
from app.services.storage import get_storage
from app.services.transcript_crypto import encrypt_transcript_model
from app.services.validator import validate_all

logger = logging.getLogger(__name__)


class PipelineStep(IntEnum):
    UPLOAD = 1
    PREPROCESS = 2
    ASR = 3
    SEGMENT = 4
    LLM_PARSE = 5
    NORMALIZE = 6
    VALIDATE = 7
    SAVE = 8
    DISPLAY = 9
    EXPORT = 10


STEP_LABELS = {
    1: "Загрузка аудио",
    2: "Предобработка",
    3: "ASR",
    4: "Сегментация",
    5: "LLM-разбор",
    6: "Нормализация",
    7: "Валидация",
    8: "Сохранение в БД",
    9: "Готово к отображению",
    10: "Экспорт Excel",
}


def _log_step(job: ProcessingJob | None, step: PipelineStep, detail: str = "") -> None:
    if not job:
        return
    job.current_step = int(step)
    log = job.get_steps_log()
    log.append({
        "step": int(step),
        "label": STEP_LABELS.get(int(step), ""),
        "detail": detail,
        "at": datetime.utcnow().isoformat(),
    })
    job.set_steps_log(log)


def run_session_processing(db: Session, session_id: int, job_id: int | None = None) -> int:
    """session_id = audio_files.id (обратная совместимость API)."""
    return run_audio_processing(db, session_id, job_id)


def run_audio_processing(db: Session, audio_file_id: int, job_id: int | None = None) -> int:
    audio = db.query(AudioFile).filter(AudioFile.id == audio_file_id).first()
    if not audio:
        raise ValueError(f"Audio file {audio_file_id} not found")

    job: ProcessingJob | None = None
    if job_id:
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
    if not job:
        job = (
            db.query(ProcessingJob)
            .filter(ProcessingJob.audio_file_id == audio_file_id)
            .order_by(ProcessingJob.created_at.desc())
            .first()
        )

    if job:
        job.status = "processing"
        job.started_at = datetime.utcnow()
        job.error_message = None
        job.asr_provider = settings.asr_provider
        job.llm_provider = (
            settings.llm_primary_parser
            if settings.parser_mode in ("openai", "hybrid")
            else "regex"
        )

    db.commit()

    try:
        _log_step(job, PipelineStep.UPLOAD, audio.original_filename)

        storage = get_storage()
        local_path = storage.resolve_local_path(audio.stored_path)
        if not local_path.exists():
            raise FileNotFoundError("Аудиофайл не найден")

        _log_step(job, PipelineStep.PREPROCESS)
        converted, metadata = preprocess_audio(local_path, audio_file_id)
        audio.converted_path = str(converted)
        audio.duration_sec = metadata.duration_sec if hasattr(metadata, "duration_sec") else None
        file_metadata = metadata.to_dict()
        db.commit()

        _log_step(job, PipelineStep.ASR, settings.asr_provider)
        full_text, asr_segments = transcribe(converted)
        avg_conf = _avg_confidence(asr_segments)

        _log_step(job, PipelineStep.SEGMENT)
        blocks = segment_logical_blocks(full_text, asr_segments)
        blocks_payload = [b.to_dict() for b in blocks]

        _log_step(job, PipelineStep.LLM_PARSE, settings.parser_mode)
        parse_result = run_parsing_pipeline(full_text, asr_segments, blocks)

        _log_step(job, PipelineStep.NORMALIZE)
        records = normalize_all(parse_result.records, source_text=full_text)

        _log_step(job, PipelineStep.VALIDATE)
        validation = validate_all(records)
        all_errors = parse_result.errors + validation.to_dicts()

        _log_step(job, PipelineStep.SAVE)
        if not job:
            raise RuntimeError("Processing job not found")

        count = save_job_results(
            db,
            job,
            full_text,
            asr_segments,
            records,
            avg_conf,
            parse_result.unknown_terms,
            all_errors,
            validation.record_errors,
            blocks_payload,
            file_metadata,
        )

        if job.transcript:
            encrypt_transcript_model(job.transcript)

        _log_step(job, PipelineStep.DISPLAY, f"blocks={len(blocks)} positions={count}")
        job.status = "done"
        job.finished_at = datetime.utcnow()
        job.current_step = int(PipelineStep.DISPLAY)
        audio.updated_at = datetime.utcnow()
        db.commit()
        return count

    except Exception as exc:
        logger.exception("Pipeline failed audio_file %s", audio_file_id)
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
        db.commit()
        raise


def _avg_confidence(segments) -> float | None:
    confs = [s.confidence for s in segments if s.confidence is not None]
    if not confs:
        return None
    return round(sum(confs) / len(confs), 3)
