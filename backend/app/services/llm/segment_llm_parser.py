"""
LLM: один ASR-сегмент → один вызов → ParsedRow.
"""

from __future__ import annotations

import json
import logging

from app.config import settings
from app.services.llm.extraction_schema import (
    RAILWAY_ROW_EXTRACTION_SCHEMA,
    openai_row_response_format,
)
from app.services.llm.json_schema import (
    build_llm_segment_system_rules,
    merge_segment_row,
    parse_llm_row_json,
    structured_to_parsed_rows,
)
from app.services.llm.row_segment_validation import validate_rows_for_segment
from app.services.parser import ParsedRecord, TranscriptSegment
from app.services.railway_segment import SegmentedBlock, segment_railway_text

logger = logging.getLogger(__name__)


def _segment_blocks(full_text: str) -> list[SegmentedBlock]:
    blocks = segment_railway_text(full_text)
    if blocks:
        return blocks
    text = full_text.strip()
    return [SegmentedBlock(location=None, segment=text)] if text else []


def _build_segment_payload(block: SegmentedBlock, index: int) -> dict:
    return {
        "task": "segment_to_row",
        "segment_index": index + 1,
        "location_hint": block.location,
        "segment": block.segment,
        "json_schema": RAILWAY_ROW_EXTRACTION_SCHEMA,
        "instruction": (
            "Извлеки ровно одну строку таблицы из segment. "
            "location: используй location_hint, если в segment не названо иное. "
            "sourceText: дословно segment (или его часть с неисправностью). "
            "Ответ — один объект ParsedRow по JSON Schema railway_row."
        ),
    }


def _parse_segment_openai(block: SegmentedBlock, index: int) -> dict:
    from openai import OpenAI

    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": build_llm_segment_system_rules()},
            {
                "role": "user",
                "content": json.dumps(_build_segment_payload(block, index), ensure_ascii=False),
            },
        ],
        temperature=0.0,
        response_format=openai_row_response_format(),
    )
    content = response.choices[0].message.content or "{}"
    return parse_llm_row_json(content)


def _parse_segment_claude(block: SegmentedBlock, index: int) -> dict:
    from anthropic import Anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY не задан")

    client = Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=build_llm_segment_system_rules(),
        messages=[
            {
                "role": "user",
                "content": json.dumps(_build_segment_payload(block, index), ensure_ascii=False),
            }
        ],
    )
    text = message.content[0].text if message.content else "{}"
    return parse_llm_row_json(text)


def parse_structured_by_segments(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> dict:
    """N сегментов → N вызовов LLM → {"rows": [...]}."""
    del segments, logical_blocks  # таймкоды пока не привязываем к сегментам
    blocks = _segment_blocks(full_text)
    parse_one = (
        _parse_segment_claude
        if settings.llm_primary_parser == "anthropic"
        else _parse_segment_openai
    )

    rows: list[dict] = []
    for index, block in enumerate(blocks):
        try:
            row = parse_one(block, index)
            row = merge_segment_row(row, block)
            validated = validate_rows_for_segment(block.segment, [row])
            rows.append(validated[0])
        except Exception as exc:
            logger.warning("LLM segment %d failed: %s", index + 1, exc)
            raise

    logger.info(
        "LLM (%s) by segments: %d calls → %d rows",
        settings.llm_primary_parser,
        len(blocks),
        len(rows),
    )
    return {"rows": rows}


def parse_with_segments_llm(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> tuple[list[ParsedRecord], dict]:
    structured = parse_structured_by_segments(full_text, segments, logical_blocks)
    return structured_to_parsed_rows(structured), structured
