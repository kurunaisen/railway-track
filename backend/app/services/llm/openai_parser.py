"""FR 15.2 / 15.3 — ChatGPT: основной парсер текст → строгий JSON."""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.config import settings
from app.services.domain_terms import KNOWN_TERMS
from app.services.llm.extraction_schema import RAILWAY_EXTRACTION_SCHEMA, openai_response_format
from app.services.llm.json_schema import (
    STRUCTURED_JSON_EXAMPLE,
    build_llm_system_rules,
    parse_llm_json,
    structured_to_parsed_rows,
)
from app.services.norms_for_llm import build_norms_reference
from app.services.parser import ParsedRecord, TranscriptSegment

logger = logging.getLogger(__name__)


def _build_user_payload(
    full_text: str,
    segments: list[TranscriptSegment] | None,
    logical_blocks: list[dict] | None,
) -> dict:
    return {
        "task": "text_to_structure",
        "transcript": full_text,
        "asr_segments": [
            {"start": s.start, "end": s.end, "text": s.text, "confidence": s.confidence}
            for s in (segments or [])
        ],
        "logical_blocks": logical_blocks or [],
        "domain_terms_sample": sorted(KNOWN_TERMS)[:60],
        "norms_reference": build_norms_reference(),
        "json_schema": RAILWAY_EXTRACTION_SCHEMA,
        "output_format_example": STRUCTURED_JSON_EXAMPLE,
        "instruction": (
            'Верни JSON {"rows": [...]} строго по JSON Schema railway_rows (structured output). '
            f"Минимум {len(logical_blocks or [])} rows — по одной неисправности на логический фрагмент. "
            "Используй asr_segments для контекста таймкодов в sourceText."
        ),
    }


def parse_structured_with_openai(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY не задан")

    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": build_llm_system_rules()},
            {"role": "user", "content": json.dumps(_build_user_payload(full_text, segments, logical_blocks), ensure_ascii=False)},
        ],
        temperature=0.0,
        response_format=openai_response_format(),
    )
    content = response.choices[0].message.content or "{}"
    data = parse_llm_json(content)
    n_rows = len(data.get("rows", []))
    logger.info("OpenAI structured: %d rows", n_rows)
    return data


def parse_with_openai(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> list[ParsedRecord]:
    """Текст → ParsedRecord[] через строгий JSON."""
    data = parse_structured_with_openai(full_text, segments, logical_blocks)
    return structured_to_parsed_rows(data)
