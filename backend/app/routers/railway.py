"""Railway v2 API: extract rows + export xlsx."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_role
from app.database import get_db
from app.schemas import (
    ExtractRailwayRequest,
    ExtractRailwayResponse,
    ExportRailwayRequest,
    RailwayRowOut,
    TranscriptReviewRequest,
    TranscriptReviewResponse,
)
from app.services.audit import log_action
from app.services.inspection_repository import load_latest_done_job, save_railway_rows_metadata
from app.services.llm.review_transcript import review_transcript_with_ai
from app.services.railway.process_pipeline import export_rows_to_xlsx, rows_from_transcript
from app.services.railway.types import RailwayRow
from app.services.session_adapter import audio_file_to_session_out

router = APIRouter(prefix="/railway", tags=["railway"])


def _rows_to_out(rows: list[RailwayRow]) -> list[RailwayRowOut]:
    return [RailwayRowOut.model_validate(row.to_api_dict()) for row in rows]


def _rows_from_out(rows: list[RailwayRowOut]) -> list[RailwayRow]:
    return [RailwayRow.model_validate(row.model_dump(by_alias=True)) for row in rows]


@router.post("/transcript-review", response_model=TranscriptReviewResponse)
def review_transcript(
    body: TranscriptReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("operator")),
):
    try:
        issues = review_transcript_with_ai(body.transcript)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    log_action(
        db,
        action="railway_transcript_review",
        current=current,
        request=request,
        resource_type="railway",
        resource_id=0,
        details={"issues": len(issues)},
    )
    return TranscriptReviewResponse(issues=[issue.model_dump() for issue in issues])


@router.post("/extract", response_model=ExtractRailwayResponse)
def extract_railway(
    body: ExtractRailwayRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("operator")),
):
    try:
        rows = rows_from_transcript(body.transcript)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    log_action(
        db,
        action="railway_extract",
        current=current,
        request=request,
        resource_type="railway",
        resource_id=0,
        details={"rows": len(rows)},
    )
    return ExtractRailwayResponse(rows=_rows_to_out(rows))


@router.post("/sessions/{session_id}/extract", response_model=ExtractRailwayResponse)
def extract_railway_for_session(
    session_id: int,
    body: ExtractRailwayRequest,
    request: Request,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("operator")),
):
    from app.routers.api import _audio_or_404

    _audio_or_404(db, session_id, current, write=True)
    try:
        rows = rows_from_transcript(body.transcript)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    job = load_latest_done_job(db, session_id)
    if job:
        save_railway_rows_metadata(db, job, [row.to_api_dict() for row in rows])

    log_action(
        db,
        action="railway_extract_session",
        current=current,
        request=request,
        resource_type="session",
        resource_id=session_id,
        details={"rows": len(rows)},
    )
    return ExtractRailwayResponse(rows=_rows_to_out(rows))


@router.post("/export")
def export_railway(
    body: ExportRailwayRequest,
    current: CurrentUser = Depends(require_role("operator")),
):
    if not body.rows:
        raise HTTPException(status_code=400, detail="Нет строк для экспорта")

    rows = _rows_from_out(body.rows)
    buffer = export_rows_to_xlsx(rows, include_source_text=body.include_source_text)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="railway_table.xlsx"'},
    )


@router.get("/sessions/{session_id}/rows", response_model=ExtractRailwayResponse)
def get_session_railway_rows(
    session_id: int,
    db: Session = Depends(get_db),
    current: CurrentUser = Depends(require_role("viewer")),
):
    from app.routers.api import _audio_or_404

    audio = _audio_or_404(db, session_id, current, write=False)
    session = audio_file_to_session_out(db, audio)
    return ExtractRailwayResponse(rows=session.railway_rows)
