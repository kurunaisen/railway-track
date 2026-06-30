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
    """Не меньше строк, чем даёт regex-разбор по смене км/пикета/станции."""
    if not blocks:
        return records

    expanded = enforce_single_position_per_row(expand_blocks_to_canonical_rows(blocks))
    if not expanded:
        return records

    if len(records) >= len(expanded):
        return enforce_single_position_per_row(records)

    return expanded
