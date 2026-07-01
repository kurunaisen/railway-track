"""
Пайплайн ASR → табличные строки (4 этапа):

1. normalize_asr_text
2. segment_railway_text
3. extract_rows_from_segment
4. validate_rows_for_segment
"""

from __future__ import annotations

from app.services.asr_fixes import normalize_asr_text
from app.services.llm.row_segment_validation import ParsedRow, validate_rows_for_segment
from app.services.parser import ParsedRecord
from app.services.railway_segment import SegmentedBlock, segment_railway_text
from app.services.row_segment_extract import extract_rows_from_segment
from app.services.sanitize_row_for_export import sanitize_row_for_export

# Явные алиасы этапов (соответствие TS API)
normalizeAsrText = normalize_asr_text
segmentRailwayText = segment_railway_text
validateRowsForSegment = validate_rows_for_segment
sanitizeRowForExport = sanitize_row_for_export


def extractRowsFromSegment(
    block: SegmentedBlock,
    *,
    use_llm: bool = False,
    index: int = 0,
) -> list[ParsedRow]:
    return extract_rows_from_segment(block, use_llm=use_llm, index=index)


def asr_text_to_parsed_rows(
    text: str,
    *,
    use_llm: bool = False,
) -> list[ParsedRow]:
    """Полный 4-этапный конвейер → список ParsedRow."""
    blocks = segment_railway_text(text)
    if not blocks:
        return []

    rows: list[ParsedRow] = []
    for index, block in enumerate(blocks):
        extracted = extract_rows_from_segment(block, use_llm=use_llm, index=index)
        validated = validate_rows_for_segment(block.segment, extracted)
        rows.extend(sanitize_row_for_export(row) for row in validated)
    return rows


def asr_text_to_records(
    text: str,
    *,
    use_llm: bool = False,
) -> list[ParsedRecord]:
    from app.services.llm.json_schema import structured_to_parsed_rows

    parsed_rows = asr_text_to_parsed_rows(text, use_llm=use_llm)
    return structured_to_parsed_rows({"rows": parsed_rows})
