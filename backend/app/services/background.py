"""Фоновая обработка без Celery (для Railway без Redis)."""

from __future__ import annotations

import logging
import threading

from app.database import SessionLocal
from app.services.processing import run_session_processing

logger = logging.getLogger(__name__)


def spawn_session_processing(session_id: int, job_id: int) -> None:
    """Запускает конвейер в отдельном потоке, чтобы HTTP не упирался в таймаут прокси."""

    def _worker() -> None:
        db = SessionLocal()
        try:
            run_session_processing(db, session_id, job_id)
        except Exception:
            logger.exception("Background processing failed for session %s", session_id)
        finally:
            db.close()

    threading.Thread(
        target=_worker,
        name=f"process-session-{session_id}",
        daemon=True,
    ).start()
