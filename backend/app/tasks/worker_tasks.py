from __future__ import annotations

import logging
from datetime import datetime

from app.database import SessionLocal
from app.models import AudioFile, ProcessingJob
from app.services.processing import run_session_processing
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="railway.process_session")
def process_session_task(self, session_id: int, job_id: int) -> dict:
    db = SessionLocal()
    try:
        count = run_session_processing(db, session_id, job_id)
        return {"session_id": session_id, "records": count, "status": "completed"}
    except Exception as exc:
        logger.exception("Processing failed for session %s", session_id)
        job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()
        audio = db.query(AudioFile).filter(AudioFile.id == session_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(exc)
            job.finished_at = datetime.utcnow()
        if audio:
            audio.updated_at = datetime.utcnow()
        db.commit()
        raise
    finally:
        db.close()
