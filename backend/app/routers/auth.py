import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from sqlalchemy import or_

from app.auth.deps import CurrentUser, get_current_user, require_role
from app.auth.security import create_access_token, verify_password
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, TokenResponse, UserOut
from app.services.audit import log_action

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(
            User.is_active,
            or_(User.name == payload.username, User.email == payload.username),
        )
        .first()
    )
    if not user or not verify_password(payload.password, user.password_hash):
        log_action(
            db,
            action="login_failed",
            current=CurrentUser(None, is_anonymous=True),
            request=request,
            details={"username": payload.username},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")

    token = create_access_token(user.name, user.role, user.id)
    current = CurrentUser(user)
    log_action(db, action="login", current=current, request=request)
    return TokenResponse(access_token=token, role=user.role, username=user.name)


@router.get("/me", response_model=UserOut)
def me(current: CurrentUser = Depends(get_current_user)):
    if not current.user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован")
    return current.user
