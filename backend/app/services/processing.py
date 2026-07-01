"""Конвейер: Yandex SpeechKit → transcript (без LLM на этом шаге)."""

from __future__ import annotations

import logging
from datetime import datetime
from enum import IntEnum

from sqlalchemy.orm import Session

from app.config import settings
from app.models import AudioFile, ProcessingJob
from app.services.inspection_repository import save_transcript_only
from app.services.preprocessing import preprocess_audio
from app.services.railway.process_pipeline import transcribe_audio
from app.services.storage import get_storage
from app.services.transcript_crypto import encrypt_transcript_model

logger = logging.getLogger(__name__)


class PipelineStep(IntEnum):
    UPLOAD = 1
    PREPROCESS = 2
    ASR = 3
    DONE = 4


STEP_LABELS = {
    1: "Загрузка аудио",
    2: "Предобработка",
    3: "Yandex SpeechKit",
    4: "Транскript готов",
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
        job.asr_provider = "yandex"
        job.llm_provider = settings.llm_provider

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

        _log_step(job, PipelineStep.ASR, "yandex")
        full_text, asr_segments = transcribe_audio(converted)
        avg_conf = _avg_confidence(asr_segments)

        if not job:
            raise RuntimeError("Processing job not found")

        save_transcript_only(db, job, full_text, asr_segments, avg_conf, file_metadata)

        if job.transcript:
            encrypt_transcript_model(job.transcript)

        _log_step(job, PipelineStep.DONE, f"chars={len(full_text)}")
        job.status = "done"
        job.finished_at = datetime.utcnow()
        job.current_step = int(PipelineStep.DONE)
        audio.updated_at = datetime.utcnow()
        db.commit()
        logger.info("Transcribe-only pipeline done for audio %s", audio_file_id)
        return 0

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
