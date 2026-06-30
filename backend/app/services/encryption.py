from __future__ import annotations

import json
import logging

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.orm import Session

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet | None:
    global _fernet
    if not settings.encrypt_transcripts or not settings.data_encryption_key:
        return None
    if _fernet is None:
        try:
            _fernet = Fernet(settings.data_encryption_key.encode())
        except Exception as exc:
            raise RuntimeError(
                "Неверный DATA_ENCRYPTION_KEY. Сгенерируйте ключ Fernet: "
                'python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"'
            ) from exc
    return _fernet


def encrypt_text(plain: str) -> tuple[str, bool]:
    f = _get_fernet()
    if not f or not plain:
        return plain, False
    return f.encrypt(plain.encode()).decode(), True


def decrypt_text(stored: str, encrypted: bool) -> str:
    if not stored:
        return stored
    if not encrypted:
        return stored
    f = _get_fernet()
    if not f:
        logger.warning("Transcript marked encrypted but no encryption key configured")
        return stored
    try:
        return f.decrypt(stored.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt transcript")
        return "[decryption error]"


def encrypt_session_transcript(session) -> None:
    if session.full_transcript and settings.encrypt_transcripts:
        session.full_transcript, session.transcript_encrypted = encrypt_text(session.full_transcript)


def decrypt_session_transcript(session) -> str | None:
    if session.full_transcript is None:
        return None
    return decrypt_text(session.full_transcript, session.transcript_encrypted)
