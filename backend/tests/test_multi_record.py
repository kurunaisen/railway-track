"""Каноническая модель FR 10.1–10.3."""

import pytest

from app.services.canonical_model import (
    expand_blocks_to_canonical_rows,
    parse_position,
    split_into_position_fragments,
)
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.record_expander import count_blocks_and_rows, expand_blocks_to_rows
from app.services.segmentation import segment_logical_blocks


THREE_PEREGON_TEXT = (
    "Перегon А — Б, путь 1, км 10, пикет 2, износ 5 мм. "
    "Далее перегon Б — В, путь 2, километр 15, пикет 4, просадка 20 мм. "
    "Следующий перегon В — Г, путь 1, км 20, пикет 1, трещина, уровень 15 мм."
).replace("перегon", "перегон")


def test_one_parameter_per_row():
    text = "Путь 1, км 248, пикет 7, просадка 25 мм; трещина на рельсе."
    fragments = split_into_position_fragments(text)
    assert len(fragments) >= 2
    for frag in fragments:
        pos = parse_position(frag, 0)
        kinds = sum(bool(x) for x in (pos.parameter, pos.defect, pos.speed_limit))
        assert kinds <= 1


def test_multiple_positions_same_logical_record():
    text = "Путь 1, км 248, piket 7, просадка 25 мм; трещина на рельсе.".replace("piket", "пикет")
    blocks = segment_logical_blocks(text)
    rows = expand_blocks_to_rows(blocks)
    assert len(rows) >= 2
    assert all(r.logical_record_index == 0 for r in rows)
    assert {r.position_index for r in rows} >= {0, 1}


def test_speed_limit_merged_with_defect():
    text = "Перегon А — Б, путь 1, км 10, износ 5 мм, ограничение скорости 40.".replace("перегon", "перегон")
    from app.services.normalizer import normalize_all

    rows = normalize_all(expand_blocks_to_canonical_rows(segment_logical_blocks(text)))
    defect_rows = [r for r in rows if r.defect]
    assert len(defect_rows) == 1
    assert defect_rows[0].speed_limit == "40"
    assert len(rows) == 1


def test_one_audio_three_peregons_n_rows():
    blocks = segment_logical_blocks(THREE_PEREGON_TEXT)
    assert len(blocks) >= 3
    rows = expand_blocks_to_rows(blocks)
    assert len(rows) >= len(blocks)
    assert all(r.logical_record_index is not None for r in rows)


def test_blocks_count_le_records_count():
    text = "Перегon один. Далее перегon два. Затем перегon три.".replace("перегon", "перегон")
    result = run_parsing_pipeline(text)
    blocks = segment_logical_blocks(text)
    stats = count_blocks_and_rows(blocks, result.records)
    assert stats["logical_records"] >= 3
    if stats["positions"]:
        assert stats["positions"] >= stats["logical_records"]


def test_third_block_two_positions():
    blocks = segment_logical_blocks(THREE_PEREGON_TEXT)
    rows = expand_blocks_to_rows(blocks)
    last_record_rows = [r for r in rows if r.logical_record_index == len(blocks) - 1]
    assert len(last_record_rows) >= 2
