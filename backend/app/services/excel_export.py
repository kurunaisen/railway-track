"""Excel export from v2 RailwayRow[] stored in job metadata."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO

from sqlalchemy.orm import Session

from app.models import AudioFile, Export
from app.services.inspection_repository import load_latest_done_job
from app.services.railway.export_railway_xlsx import export_railway_xlsx
from app.services.railway.process_pipeline import railway_rows_from_job
from app.services.railway.types import RailwayRow


def export_session_to_excel(db: Session, session_id: int) -> BytesIO:
    """session_id = audio_files.id."""
    return export_sessions_batch_to_excel(db, [session_id])


def export_sessions_batch_to_excel(db: Session, session_ids: list[int]) -> BytesIO:
    if not session_ids:
        raise ValueError("Не указаны сессии для экспорта")

    all_rows: list[RailwayRow] = []
    export_job_id: int | None = None

    for session_id in session_ids:
        audio = db.query(AudioFile).filter(AudioFile.id == session_id).first()
        if not audio:
            continue
        job = load_latest_done_job(db, session_id)
        if not job:
            continue
        export_job_id = export_job_id or job.id
        all_rows.extend(railway_rows_from_job(job))

    if not all_rows:
        raise ValueError("Нет строк таблицы для экспорта. Сначала сформируйте таблицу из расшифровки.")

    buffer = export_railway_xlsx(all_rows)

    if export_job_id:
        label = (
            f"railway_session_{session_ids[0]}.xlsx"
            if len(session_ids) == 1
            else f"railway_batch_{len(session_ids)}_sessions.xlsx"
        )
        db.add(
            Export(
                job_id=export_job_id,
                file_path=label,
                format="xlsx",
                created_at=datetime.utcnow(),
            )
        )
        db.commit()

    return buffer
