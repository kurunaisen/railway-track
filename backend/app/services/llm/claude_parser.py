"""FR 15.3 — Claude как альтернативный основной парсер (A/B тесты)."""

from __future__ import annotations

import json
import logging

from anthropic import Anthropic

from app.config import settings
from app.services.llm.json_schema import (
    build_llm_system_rules,
    parse_llm_json,
    structured_to_parsed_rows,
)
from app.services.llm.openai_parser import _build_user_payload
from app.services.parser import ParsedRecord, TranscriptSegment

logger = logging.getLogger(__name__)


def parse_structured_with_claude(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> dict:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан")

    client = Anthropic(api_key=settings.anthropic_api_key)
    payload = _build_user_payload(full_text, segments, logical_blocks)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=build_llm_system_rules(),
        messages=[
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False),
            }
        ],
    )
    text = message.content[0].text if message.content else "{}"
    data = parse_llm_json(text)
    logger.info("Claude structured: %d records", len(data.get("records", [])))
    return data


def parse_with_claude(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> list[ParsedRecord]:
    data = parse_structured_with_claude(full_text, segments, logical_blocks)
    return structured_to_parsed_rows(data)
