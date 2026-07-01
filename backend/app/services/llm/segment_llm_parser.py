"""
LLM: extractRowsFromSegment для одного ASR-сегмента → ParsedRow.
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
from app.services.llm.row_segment_validation import ParsedRow, validate_rows_for_segment
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
            "location: location_hint, если в segment не названо иное. "
            "assetKind/assetNumber — только объект этого segment (track XOR switch). "
            "note: «острие остряка» и аналоги; не defect. "
            "speedLimit: null, если скорость не названа в segment. "
            "sourceText: дословно segment."
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
    return parse_llm_row_json(response.choices[0].message.content or "{}")


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
    return parse_llm_row_json(message.content[0].text if message.content else "{}")


def extract_rows_from_segment_llm(block: SegmentedBlock, index: int = 0) -> list[ParsedRow]:
    parse_one = (
        _parse_segment_claude
        if settings.llm_primary_parser == "anthropic"
        else _parse_segment_openai
    )
    row = parse_one(block, index)
    row = merge_segment_row(row, block)
    return validate_rows_for_segment(block.segment, [row])


def parse_structured_by_segments(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> dict:
    """N сегментов → N вызовов LLM → {"rows": [...]}."""
    del segments, logical_blocks
    blocks = _segment_blocks(full_text)
    rows: list[ParsedRow] = []

    for index, block in enumerate(blocks):
        try:
            rows.extend(extract_rows_from_segment_llm(block, index))
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
