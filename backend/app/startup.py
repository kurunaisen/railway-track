import logging

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.config import settings
from app.database import SessionLocal, engine
from app.models import User

logger = logging.getLogger(__name__)


def run_schema_migrations() -> None:
    """Lightweight migrations for columns added after initial deploy."""
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {col["name"] for col in inspector.get_columns("users")}
    if "avatar_id" in columns:
        return
    dialect = engine.dialect.name
    with engine.begin() as conn:
        if dialect == "sqlite":
            conn.execute(text("ALTER TABLE users ADD COLUMN avatar_id VARCHAR(32) DEFAULT 'star'"))
        else:
            conn.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_id VARCHAR(32) DEFAULT 'star'"))
    logger.info("Added users.avatar_id column")


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
