"""OpenAI LLM — legacy segment parser entry."""

from __future__ import annotations

from app.services.llm.segment_llm_parser import parse_with_segments_llm
from app.services.parser import ParsedRecord, TranscriptSegment


def parse_with_primary_llm(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> tuple[list[ParsedRecord], dict | None]:
    from app.config import settings

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан")

    return parse_with_segments_llm(full_text, segments, logical_blocks)
