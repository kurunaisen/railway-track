"""
1 аудио → N логических записей → M позиций = M строк long-таблицы.

См. canonical_model.py (FR 10.1–10.3).
"""

from __future__ import annotations

from app.services.canonical_model import (
    count_logical_records_and_positions,
    enforce_single_position_per_row,
    expand_blocks_to_canonical_rows,
)
from app.services.parser import ParsedRecord
from app.services.segmentation import LogicalBlock

expand_blocks_to_rows = expand_blocks_to_canonical_rows
count_blocks_and_rows = count_logical_records_and_positions


def ensure_minimum_rows(
    records: list[ParsedRecord],
    blocks: list[LogicalBlock],
) -> list[ParsedRecord]:
    """Гарантирует M ≥ N логических записей."""
    if not blocks:
        return records

    expanded = expand_blocks_to_canonical_rows(blocks)
    n_records = len({r.logical_record_index for r in expanded if r.logical_record_index is not None})
    if not n_records:
        n_records = len(blocks)

    if len(records) >= n_records:
        return enforce_single_position_per_row(records)

    if len(expanded) >= n_records:
        return expanded

    return records if records else expanded
