"""Выбор LLM-парсера и стратегия FR 15.3."""

from __future__ import annotations

from app.services.llm.segment_llm_parser import parse_with_segments_llm
from app.services.parser import ParsedRecord, TranscriptSegment


def parse_with_primary_llm(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> tuple[list[ParsedRecord], dict | None]:
    """
    FR 15.3: сегментация → N вызовов LLM (один ParsedRow на сегмент).
    """
    from app.config import settings

    if settings.llm_primary_parser == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY не задан для llm_primary_parser=anthropic")
    else:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY не задан для llm_primary_parser=openai")

    return parse_with_segments_llm(full_text, segments, logical_blocks)
