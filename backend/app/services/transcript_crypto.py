from __future__ import annotations

from app.config import settings
from app.models import Transcript


def encrypt_transcript_text(plain: str) -> tuple[str, bool]:
    from app.services.encryption import encrypt_text

    return encrypt_text(plain)


def decrypt_transcript_text(stored: str | None, encrypted: bool) -> str | None:
    from app.services.encryption import decrypt_text

    if stored is None:
        return None
    return decrypt_text(stored, encrypted)


def encrypt_transcript_model(transcript: Transcript) -> None:
    if transcript.full_text and settings.encrypt_transcripts:
        transcript.full_text, transcript.text_encrypted = encrypt_transcript_text(transcript.full_text)


def decrypt_transcript_model(transcript: Transcript) -> str | None:
    if transcript.full_text is None:
        return None
    return decrypt_transcript_text(transcript.full_text, transcript.text_encrypted)
