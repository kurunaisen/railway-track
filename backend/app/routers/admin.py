from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, require_role
from app.database import get_db
from app.models import AuditLog
from app.schemas import AuditLogOut, UserOut

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit_logs(
    current: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
):
    return (
        db.query(AuditLog)
        .order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/users", response_model=list[UserOut])
def list_users(
    current: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: Session = Depends(get_db),
):
    from app.models import User

    return db.query(User).order_by(User.name).all()
