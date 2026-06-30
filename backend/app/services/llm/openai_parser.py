"""FR 15.2 / 15.3 — ChatGPT: основной парсер текст → строгий JSON."""

from __future__ import annotations

import json
import logging

from openai import OpenAI

from app.config import settings
from app.services.domain_terms import KNOWN_TERMS
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
        "output_format_example": STRUCTURED_JSON_EXAMPLE,
        "instruction": (
            "Верни JSON {\"records\": [...]} строго по формату output_format_example. "
            f"Минимум {len(logical_blocks or [])} records — по одному на каждый logical_block. "
            "Используй asr_segments для start_sec/end_sec."
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
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    data = parse_llm_json(content)
    n_rec, n_pos = len(data.get("records", [])), sum(len(r.get("items", [])) for r in data.get("records", []))
    logger.info("OpenAI structured: %d records, %d items", n_rec, n_pos)
    return data


def parse_with_openai(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> list[ParsedRecord]:
    """Текст → ParsedRecord[] через строгий JSON."""
    data = parse_structured_with_openai(full_text, segments, logical_blocks)
    return structured_to_parsed_rows(data)
