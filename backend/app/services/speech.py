"""Обратная совместимость — используйте app.services.asr."""

from app.services.asr import segments_to_json, transcribe as transcribe_audio
from app.services.parser import TranscriptSegment

__all__ = ["transcribe_audio", "segments_to_json", "TranscriptSegment"]
