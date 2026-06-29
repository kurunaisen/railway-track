from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.config import settings
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_LEVEL = {"viewer": 1, "operator": 2, "admin": 3}


class CurrentUser:
    def __init__(self, user: User | None, is_anonymous: bool = False):
        self.user = user
        self.is_anonymous = is_anonymous

    @property
    def id(self) -> int | None:
        return self.user.id if self.user else None

    @property
    def username(self) -> str:
        return self.user.username if self.user else "anonymous"

    @property
    def role(self) -> str:
        return self.user.role if self.user else "operator"

    def has_role(self, minimum: str) -> bool:
        return ROLE_LEVEL.get(self.role, 0) >= ROLE_LEVEL.get(minimum, 99)


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Session = Depends(get_db),
) -> CurrentUser:
    if not settings.auth_required:
        if credentials:
            try:
                payload = decode_access_token(credentials.credentials)
                user = db.query(User).filter(User.id == payload["uid"], User.is_active).first()
                if user:
                    return CurrentUser(user)
            except ValueError:
                pass
        return CurrentUser(None, is_anonymous=True)

    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Требуется авторизация")

    try:
        payload = decode_access_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Недействительный токен") from exc

    user = db.query(User).filter(User.id == payload["uid"], User.is_active).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")
    return CurrentUser(user)


def require_role(minimum: str):
    def dependency(current: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if not current.has_role(minimum):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
        return current

    return dependency


def get_client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"
