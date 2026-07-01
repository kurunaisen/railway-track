"""Конвейер разбора: N блоков → M строк таблицы."""

from __future__ import annotations

import logging

from app.config import settings
from app.services.asr_fixes import fix_asr_transcript
from app.services.canonical_model import enforce_single_position_per_row
from app.services.llm import parse_with_primary_llm
from app.services.llm.claude_reviewer import review_all_disputed
from app.services.llm.json_schema import count_structured_records
from app.services.parser import ParseResult, TranscriptSegment, detect_unknown_terms
from app.services.record_expander import ensure_minimum_rows, expand_blocks_to_rows
from app.services.segmentation import LogicalBlock, segment_logical_blocks

logger = logging.getLogger(__name__)


def _llm_available() -> bool:
    if settings.parser_mode not in ("openai", "hybrid"):
        return False
    if settings.llm_primary_parser == "anthropic":
        return bool(settings.anthropic_api_key)
    return bool(settings.openai_api_key)


def run_parsing_pipeline(
    full_text: str,
    segments: list[TranscriptSegment] | None = None,
    logical_blocks: list[LogicalBlock] | None = None,
) -> ParseResult:
    errors: list[dict] = []
    full_text = fix_asr_transcript(full_text)

    blocks = logical_blocks or segment_logical_blocks(full_text, segments)
    n_blocks = len(blocks)
    blocks_payload = [b.to_dict() for b in blocks]

    # Базовый путь без LLM (regex / canonical)
    regex_baseline = enforce_single_position_per_row(expand_blocks_to_rows(blocks))
    records = regex_baseline

    if _llm_available():
        try:
            llm_records, structured = parse_with_primary_llm(full_text, segments, blocks_payload)
            n_llm_logical, n_llm_pos = count_structured_records(structured or {"records": []})
            llm_rows = enforce_single_position_per_row(llm_records)

            llm_ok = (
                n_llm_logical >= n_blocks
                and n_llm_pos >= n_llm_logical
                and len(llm_rows) >= len(regex_baseline)
            )
            if llm_ok:
                records = llm_rows
                logger.info(
                    "LLM (%s): %d records, %d items from %d blocks",
                    settings.llm_primary_parser,
                    n_llm_logical,
                    n_llm_pos,
                    n_blocks,
                )
            else:
                errors.append({
                    "row": -1,
                    "error": (
                        f"LLM ({settings.llm_primary_parser}): {n_llm_logical} records / {n_llm_pos} items "
                        f"при {n_blocks} блоках и {len(regex_baseline)} regex-строках — fallback на regex"
                    ),
                    "severity": "warning",
                })
                records = regex_baseline
        except Exception as exc:
            logger.warning("LLM parser failed: %s", exc)
            errors.append({
                "row": -1,
                "error": f"LLM ({settings.llm_primary_parser}): {exc}",
                "text": full_text[:200],
                "severity": "error",
            })

    records = ensure_minimum_rows(records, blocks)
    records = enforce_single_position_per_row(records)

    n_logical = len({r.logical_record_index for r in records if r.logical_record_index is not None}) or n_blocks

    if n_logical > 1 and len(records) < n_logical:
        errors.append({
            "row": -1,
            "error": f"Ожидалось ≥{n_logical} строк, получено {len(records)} — принудительный разбор",
            "severity": "error",
        })
        records = enforce_single_position_per_row(expand_blocks_to_rows(blocks))

    # FR 15.3: Claude ревью спорных (если основной — OpenAI; или наоборот при A/B)
    if settings.llm_review_disputed and settings.anthropic_api_key and settings.llm_primary_parser == "openai":
        try:
            records = review_all_disputed(records, full_text)
        except Exception as exc:
            logger.warning("Claude review failed: %s", exc)
            errors.append({"row": -1, "error": f"Claude review: {exc}", "severity": "warning"})

    logger.info(
        "Pipeline: %d blocks → %d logical → %d positions | ASR=%s LLM=%s",
        n_blocks,
        n_logical,
        len(records),
        settings.asr_provider,
        settings.llm_primary_parser if _llm_available() else "regex",
    )

    return ParseResult(
        records=records,
        unknown_terms=detect_unknown_terms(full_text),
        errors=errors,
    )
