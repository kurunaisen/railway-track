"""FR 15.3 — Claude: сегмент → ParsedRow."""

from __future__ import annotations

import logging

from app.config import settings
from app.services.llm.segment_llm_parser import parse_structured_by_segments, parse_with_segments_llm
from app.services.parser import ParsedRecord, TranscriptSegment

logger = logging.getLogger(__name__)


def parse_structured_with_claude(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> dict:
    if settings.llm_primary_parser != "anthropic":
        logger.debug("Claude structured called while primary=%s", settings.llm_primary_parser)
    return parse_structured_by_segments(full_text, segments, logical_blocks)


def parse_with_claude(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[dict] | None = None,
) -> list[ParsedRecord]:
    rows, _ = parse_with_segments_llm(full_text, segments, logical_blocks)
    return rows
