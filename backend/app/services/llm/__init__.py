"""Выбор LLM-парсера и стратегия FR 15.3."""

from __future__ import annotations

import logging

from app.config import settings
from app.services.llm.claude_parser import parse_structured_with_claude, parse_with_claude
from app.services.llm.claude_reviewer import review_all_disputed
from app.services.llm.json_schema import count_structured_records, structured_to_parsed_rows
from app.services.llm.openai_parser import parse_structured_with_openai, parse_with_openai
from app.services.parser import ParsedRecord, TranscriptSegment

logger = logging.getLogger(__name__)


def parse_with_primary_llm(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> tuple[list[ParsedRecord], dict | None]:
    """
    FR 15.3: основной парсер — OpenAI (ChatGPT) или Claude (для A/B).
    Возвращает (flat rows, structured JSON или None).
    """
    if settings.llm_primary_parser == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY не задан для llm_primary_parser=anthropic")
        structured = parse_structured_with_claude(full_text, segments, logical_blocks)
    else:
        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY не задан для llm_primary_parser=openai")
        structured = parse_structured_with_openai(full_text, segments, logical_blocks)

    rows = structured_to_parsed_rows(structured)
    return rows, structured
