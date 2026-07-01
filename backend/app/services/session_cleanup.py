"""Удаление сессий (audio_files) и файлов в хранилище."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import AudioFile, ProcessingJob
from app.services.storage import get_storage

logger = logging.getLogger(__name__)


def _active_job(db: Session, audio_file_id: int) -> ProcessingJob | None:
    return (
        db.query(ProcessingJob)
        .filter(
            ProcessingJob.audio_file_id == audio_file_id,
            ProcessingJob.status.in_(("queued", "processing")),
        )
        .first()
    )


def delete_audio_session(db: Session, audio: AudioFile) -> None:
    """Удаляет сессию, все jobs и файлы в storage."""
    if _active_job(db, audio.id):
        raise ValueError("Запись обрабатывается — дождитесь завершения или отмените задачу")

    storage = get_storage()
    paths = {p for p in (audio.stored_path, audio.converted_path) if p}
    db.delete(audio)
    db.flush()
    for path in paths:
        try:
            storage.delete(path)
        except Exception as exc:
            logger.warning("Could not delete storage file %s: %s", path, exc)
