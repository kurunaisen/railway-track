import json

import logging

import shutil

import uuid

from pathlib import Path

from typing import Annotated, Union



from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status

from fastapi.responses import FileResponse, StreamingResponse

from sqlalchemy.orm import Session



from app.auth.deps import CurrentUser, get_current_user, require_role

from app.config import settings

from app.database import get_db

from app.models import AudioFile, InspectionItem, InspectionRecord, ProcessingJob

from app.schemas import (

    AudioSessionOut,

    JobOut,

    ProcessQueuedResponse,

    ProcessResponse,

    SessionSummaryOut,

    StructuredRecordsOut,
    TrackRecordCreate,

    TrackRecordOut,

    TrackRecordUpdate,

)

from app.services.audit import log_action

from app.services.excel_export import export_session_to_excel, export_sessions_batch_to_excel

from app.services.inspection_repository import (
    apply_flat_update,
    flat_row_from_item,
    get_item_with_record,
    load_flat_rows,
    load_latest_done_job,
    load_structured_records,
)

from app.services.session_cleanup import delete_audio_session

from app.services.session_adapter import _flat_to_track_out, audio_file_to_session_out, audio_file_to_summary

from app.services.storage import get_storage



router = APIRouter(prefix="/api", tags=["railway"])

logger = logging.getLogger(__name__)



ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".webm"}

MIME_MAP = {

    ".wav": "audio/wav",

    ".mp3": "audio/mpeg",

    ".m4a": "audio/mp4",

    ".flac": "audio/flac",

    ".webm": "audio/webm",

}


def _audio_content_type(filename: str, mime_type: str | None) -> str:
    if mime_type:
        return mime_type
    ext = Path(filename).suffix.lower()
    return MIME_MAP.get(ext, "application/octet-stream")


def _attachment_filename(name: str) -> str:
    from urllib.parse import quote

    safe = name.replace('"', "'")
    return f"attachment; filename=\"{safe}\"; filename*=UTF-8''{quote(name)}"





def _check_audio_access(audio: AudioFile, current: CurrentUser, write: bool = False) -> None:

    if current.has_role("admin"):

        return

    if write and not current.has_role("operator"):

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Только для операторов")

    if not write and current.has_role("viewer"):

        return

    if audio.uploaded_by and current.id and audio.uploaded_by != current.id:

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нет доступа к сессии")





def _audio_or_404(db: Session, session_id: int, current: CurrentUser, write: bool = False) -> AudioFile:

    audio = db.query(AudioFile).filter(AudioFile.id == session_id).first()

    if not audio:

        raise HTTPException(status_code=404, detail="Сессия не найдена")

    _check_audio_access(audio, current, write=write)

    return audio





def _latest_job_for_write(db: Session, audio_file_id: int) -> ProcessingJob:

    job = load_latest_done_job(db, audio_file_id)

    if not job:

        raise HTTPException(status_code=400, detail="Сначала выполните обработку аудио")

    return job





@router.post("/upload", response_model=AudioSessionOut)

async def upload_audio(

    request: Request,

    file: UploadFile = File(...),

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    if not file.filename:

        raise HTTPException(status_code=400, detail="Файл не указан")



    ext = Path(file.filename).suffix.lower()

    if ext not in ALLOWED_EXTENSIONS:

        raise HTTPException(

            status_code=400,

            detail=f"Формат {ext} не поддерживается. Допустимы: .wav, .mp3, .m4a, .flac",

        )



    content = await file.read()

    max_bytes = settings.max_upload_mb * 1024 * 1024

    if len(content) > max_bytes:

        raise HTTPException(status_code=413, detail=f"Файл превышает {settings.max_upload_mb} МБ")



    stored_name = f"{uuid.uuid4().hex}{ext}"

    storage = get_storage()

    try:

        uri = storage.save(content, stored_name)

    except Exception as exc:

        raise HTTPException(status_code=422, detail=f"Ошибка сохранения файла: {exc}") from exc



    audio = AudioFile(

        original_filename=file.filename,

        stored_path=uri,

        mime_type=MIME_MAP.get(ext),

        uploaded_by=current.id,

    )

    db.add(audio)

    db.commit()

    db.refresh(audio)



    log_action(

        db,

        action="upload",

        current=current,

        request=request,

        resource_type="session",

        resource_id=audio.id,

        details={"filename": file.filename, "size": len(content)},

    )

    return audio_file_to_session_out(db, audio)





@router.post(

    "/sessions/{session_id}/process",

    response_model=Union[ProcessResponse, ProcessQueuedResponse],

)

def process_session(

    session_id: int,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    audio = _audio_or_404(db, session_id, current, write=True)

    storage = get_storage()

    local_path = storage.resolve_local_path(audio.stored_path)

    if not local_path.exists():

        raise HTTPException(status_code=404, detail="Аудиофайл не найден на диске")



    job = (

        db.query(ProcessingJob)

        .filter(

            ProcessingJob.audio_file_id == session_id,

            ProcessingJob.status.in_(("queued", "failed")),

        )

        .order_by(ProcessingJob.created_at.desc())

        .first()

    )

    if not job:

        job = ProcessingJob(audio_file_id=session_id, status="queued", current_step=1)

        db.add(job)

        db.flush()



    log_action(

        db,

        action="process_start",

        current=current,

        request=request,

        resource_type="session",

        resource_id=session_id,

    )



    if settings.use_task_queue:

        job.status = "queued"

        db.commit()

        db.refresh(job)



        from app.tasks.worker_tasks import process_session_task



        task = process_session_task.delay(session_id, job.id)

        job.celery_task_id = task.id

        db.commit()



        from app.services.session_adapter import _job_to_out



        return ProcessQueuedResponse(

            job=_job_to_out(job),

            message="Задача поставлена в очередь (шаги 2–9)",

        )



    job.status = "queued"

    db.commit()

    db.refresh(job)



    from app.services.background import spawn_session_processing

    from app.services.session_adapter import _job_to_out



    spawn_session_processing(session_id, job.id)



    return ProcessQueuedResponse(

        job=_job_to_out(job),

        message="Обработка запущена (шаги 2–9)",

    )





@router.get("/jobs/{job_id}", response_model=JobOut)

def get_job(

    job_id: int,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    job = db.query(ProcessingJob).filter(ProcessingJob.id == job_id).first()

    if not job:

        raise HTTPException(status_code=404, detail="Задача не найдена")

    _audio_or_404(db, job.audio_file_id, current)

    from app.services.session_adapter import _job_to_out



    return _job_to_out(job)





@router.get("/sessions/{session_id}/jobs", response_model=list[JobOut])

def list_session_jobs(

    session_id: int,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    _audio_or_404(db, session_id, current)

    jobs = (

        db.query(ProcessingJob)

        .filter(ProcessingJob.audio_file_id == session_id)

        .order_by(ProcessingJob.created_at.desc())

        .all()

    )

    from app.services.session_adapter import _job_to_out



    return [_job_to_out(j) for j in jobs]





@router.get("/sessions/summary", response_model=list[SessionSummaryOut])

def list_session_summaries(

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    q = db.query(AudioFile)

    if not current.has_role("admin"):

        if current.id:

            q = q.filter(

                (AudioFile.uploaded_by == current.id) | (AudioFile.uploaded_by.is_(None))

            )

    files = q.order_by(AudioFile.created_at.desc()).limit(100).all()

    return [audio_file_to_summary(db, f) for f in files]





@router.get("/sessions/{session_id}", response_model=AudioSessionOut)

def get_session(

    session_id: int,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    return audio_file_to_session_out(db, _audio_or_404(db, session_id, current))





@router.get("/sessions", response_model=list[AudioSessionOut])

def list_sessions(

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    q = db.query(AudioFile)

    if not current.has_role("admin"):

        if current.id:

            q = q.filter(

                (AudioFile.uploaded_by == current.id) | (AudioFile.uploaded_by.is_(None))

            )

    files = q.order_by(AudioFile.created_at.desc()).limit(50).all()

    return [audio_file_to_session_out(db, f) for f in files]





@router.get("/sessions/{session_id}/records/structured", response_model=StructuredRecordsOut)
def get_structured_records(
    session_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    """FR 14.2 — перегоны и позиции с sequence_number / order_in_record."""
    _audio_or_404(db, session_id, current)
    job = load_latest_done_job(db, session_id)
    if not job:
        return StructuredRecordsOut(records=[])
    return StructuredRecordsOut(**load_structured_records(job))


@router.put("/records/{record_id}", response_model=TrackRecordOut)

def update_record(

    record_id: int,

    payload: TrackRecordUpdate,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    pair = get_item_with_record(db, record_id)

    if not pair:

        raise HTTPException(status_code=404, detail="Запись не найдена")

    item, insp_rec = pair

    _audio_or_404(db, insp_rec.job.audio_file_id, current, write=True)



    data = payload.model_dump(exclude_unset=True)

    data.pop("row_order", None)

    apply_flat_update(item, insp_rec, data)

    insp_rec.status = "review"



    job = insp_rec.job

    meta = job.get_pipeline_metadata()

    meta["confirmed"] = False

    job.set_pipeline_metadata(meta)



    db.commit()

    db.refresh(item)

    log_action(

        db,

        action="record_update",

        current=current,

        request=request,

        resource_type="record",

        resource_id=record_id,

    )

    rows = load_flat_rows(job, job.audio_file_id)

    row_order = next((r.row_order for r in rows if r.id == item.id), 0)

    return _flat_to_track_out(flat_row_from_item(item, insp_rec, job.audio_file_id, row_order))





@router.post("/sessions/{session_id}/records", response_model=TrackRecordOut)

def create_record(

    session_id: int,

    payload: TrackRecordCreate,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    _audio_or_404(db, session_id, current, write=True)

    job = _latest_job_for_write(db, session_id)



    data = payload.model_dump()

    seq = data.get("logical_record_index") or data.get("logical_block_index") or 0



    insp_rec = (

        db.query(InspectionRecord)

        .filter(InspectionRecord.job_id == job.id, InspectionRecord.sequence_number == seq)

        .first()

    )

    if not insp_rec:

        insp_rec = InspectionRecord(

            job_id=job.id,

            sequence_number=seq,

            status="draft",

        )

        db.add(insp_rec)

        db.flush()



    max_order = (

        db.query(InspectionItem.order_in_record)

        .filter(InspectionItem.record_id == insp_rec.id)

        .order_by(InspectionItem.order_in_record.desc())

        .first()

    )

    order = (max_order[0] + 1) if max_order else 0



    item = InspectionItem(record_id=insp_rec.id, order_in_record=order, position_type="parameter")

    db.add(item)

    db.flush()

    apply_flat_update(item, insp_rec, data)



    db.commit()

    db.refresh(item)

    log_action(db, action="record_create", current=current, request=request, resource_type="record", resource_id=item.id)

    rows = load_flat_rows(job, session_id)

    row_order = len(rows)

    return _flat_to_track_out(flat_row_from_item(item, insp_rec, session_id, row_order))





@router.delete("/records/{record_id}")

def delete_record(

    record_id: int,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    pair = get_item_with_record(db, record_id)

    if not pair:

        raise HTTPException(status_code=404, detail="Запись не найдена")

    item, insp_rec = pair

    _audio_or_404(db, insp_rec.job.audio_file_id, current, write=True)

    db.delete(item)

    db.commit()

    log_action(db, action="record_delete", current=current, request=request, resource_type="record", resource_id=record_id)

    return {"ok": True}





@router.post("/sessions/{session_id}/save")

def save_session(

    session_id: int,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    _audio_or_404(db, session_id, current, write=True)

    job = _latest_job_for_write(db, session_id)

    meta = job.get_pipeline_metadata()

    meta["saved"] = True

    meta["confirmed"] = False

    job.set_pipeline_metadata(meta)

    db.commit()

    log_action(db, action="session_save", current=current, request=request, resource_type="session", resource_id=session_id)

    return {"ok": True, "message": "Данные сохранены"}





@router.post("/sessions/{session_id}/confirm")

def confirm_session(

    session_id: int,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(require_role("operator")),

):

    _audio_or_404(db, session_id, current, write=True)

    job = _latest_job_for_write(db, session_id)

    for rec in job.inspection_records:

        rec.status = "approved"

    meta = job.get_pipeline_metadata()

    meta["confirmed"] = True

    job.set_pipeline_metadata(meta)

    db.commit()

    log_action(db, action="session_confirm", current=current, request=request, resource_type="session", resource_id=session_id)

    return {"ok": True, "message": "Результат подтверждён"}





@router.get("/sessions/export-batch")

def export_excel_batch(

    request: Request,

    session_ids: str = Query(..., description="ID сессий через запятую"),

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    ids = [int(part.strip()) for part in session_ids.split(",") if part.strip().isdigit()]

    if not ids:

        raise HTTPException(status_code=400, detail="Укажите session_ids")

    for session_id in ids:

        _audio_or_404(db, session_id, current)

    try:

        buffer = export_sessions_batch_to_excel(db, ids)

    except ValueError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:

        logger.exception("Excel batch export failed for sessions %s", ids)

        raise HTTPException(status_code=422, detail=f"Ошибка экспорта Excel: {exc}") from exc



    log_action(

        db,

        action="export_excel",

        current=current,

        request=request,

        resource_type="session_batch",

        resource_id=",".join(str(i) for i in ids),

    )

    filename = f"railway_batch_{len(ids)}_sessions.xlsx" if len(ids) > 1 else f"railway_session_{ids[0]}.xlsx"

    return StreamingResponse(

        buffer,

        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        headers={"Content-Disposition": f'attachment; filename="{filename}"'},

    )





@router.get("/sessions/{session_id}/export")

def export_excel(

    session_id: int,

    request: Request,

    db: Session = Depends(get_db),

    current: CurrentUser = Depends(get_current_user),

):

    _audio_or_404(db, session_id, current)

    try:

        buffer = export_session_to_excel(db, session_id)

    except ValueError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except Exception as exc:

        logger.exception("Excel export failed for session %s", session_id)

        raise HTTPException(status_code=422, detail=f"Ошибка экспорта Excel: {exc}") from exc



    log_action(db, action="export_excel", current=current, request=request, resource_type="session", resource_id=session_id)

    return StreamingResponse(

        buffer,

        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",

        headers={"Content-Disposition": f'attachment; filename="railway_session_{session_id}.xlsx"'},

    )


@router.get("/sessions/{session_id}/audio")
def download_session_audio(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    audio = _audio_or_404(db, session_id, current)
    storage = get_storage()
    try:
        local_path = storage.resolve_local_path(audio.stored_path)
    except Exception as exc:
        logger.exception("Audio resolve failed for session %s", session_id)
        raise HTTPException(status_code=404, detail="Аудиофайл недоступен") from exc
    if not local_path.is_file():
        raise HTTPException(status_code=404, detail="Аудиофайл не найден")

    log_action(
        db,
        action="download_audio",
        current=current,
        request=request,
        resource_type="session",
        resource_id=session_id,
    )
    return FileResponse(
        path=local_path,
        media_type=_audio_content_type(audio.original_filename, audio.mime_type),
        filename=audio.original_filename,
        headers={"Content-Disposition": _attachment_filename(audio.original_filename)},
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(
    session_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    audio = _audio_or_404(db, session_id, current, write=True)
    try:
        delete_audio_session(db, audio)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    db.commit()
    log_action(
        db,
        action="session_delete",
        current=current,
        request=request,
        resource_type="session",
        resource_id=session_id,
    )


@router.delete("/sessions/batch", status_code=status.HTTP_204_NO_CONTENT)
def delete_sessions_batch(
    request: Request,
    session_ids: str = Query(..., description="ID сессий через запятую"),
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(get_current_user),
):
    ids = [int(part.strip()) for part in session_ids.split(",") if part.strip().isdigit()]
    if not ids:
        raise HTTPException(status_code=400, detail="Укажите session_ids")

    for session_id in ids:
        audio = _audio_or_404(db, session_id, current, write=True)
        try:
            delete_audio_session(db, audio)
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    db.commit()
    log_action(
        db,
        action="session_delete_batch",
        current=current,
        request=request,
        resource_type="session_batch",
        resource_id=",".join(str(i) for i in ids),
    )

