from __future__ import annotations

import json
from typing import Any

from fastapi import Request
from sqlalchemy.orm import Session

from app.auth.deps import CurrentUser, get_client_ip
from app.models import AuditLog


def log_action(
    db: Session,
    *,
    action: str,
    current: CurrentUser,
    request: Request | None = None,
    resource_type: str | None = None,
    resource_id: str | int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    entry = AuditLog(
        user_id=current.id,
        username=current.username,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        ip_address=get_client_ip(request) if request else None,
        user_agent=request.headers.get("user-agent") if request else None,
        details_json=json.dumps(details, ensure_ascii=False) if details else None,
    )
    db.add(entry)
    db.commit()
