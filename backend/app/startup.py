import logging

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.config import settings
from app.database import SessionLocal
from app.models import User

logger = logging.getLogger(__name__)


def seed_default_admin() -> None:
    db: Session = SessionLocal()
    try:
        if settings.admin_password_reset:
            admin = (
                db.query(User)
                .filter(User.name == settings.default_admin_username)
                .first()
            )
            if admin:
                admin.password_hash = hash_password(settings.admin_password_reset)
                db.commit()
                logger.warning(
                    "Admin password reset for user %s (ADMIN_PASSWORD_RESET was set)",
                    settings.default_admin_username,
                )
                return

        existing = db.query(User).count()
        if existing > 0:
            return
        admin = User(
            name=settings.default_admin_username,
            email="admin@local",
            password_hash=hash_password(settings.default_admin_password),
            role="admin",
        )
        operator = User(
            name="operator",
            email="operator@local",
            password_hash=hash_password("operator"),
            role="operator",
        )
        viewer = User(
            name="viewer",
            email="viewer@local",
            password_hash=hash_password("viewer"),
            role="viewer",
        )
        db.add_all([admin, operator, viewer])
        db.commit()
        logger.info(
            "Created default users: %s (admin), operator, viewer — change passwords in production!",
            settings.default_admin_username,
        )
    finally:
        db.close()
