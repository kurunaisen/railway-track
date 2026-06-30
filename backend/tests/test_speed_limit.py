"""Ограничение скорости — не неисправность, столбец speed_limit."""

from app.services.inspection_form import build_form_rows, record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord, parse_transcript
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.record_expander import expand_blocks_to_rows
from app.services.segmentation import segment_logical_blocks
from app.services.speed_limit import extract_speed_limit, reconcile_speed_limit_rows


def test_extract_plain_speed_phrase():
    assert extract_speed_limit("скорость 60 км/ч") == "60"
    assert extract_speed_limit("скорость 60") == "60"
    assert extract_speed_limit("ограничение скорости 40") == "40"
    assert extract_speed_limit("ограничение 60") == "60"
    assert extract_speed_limit("ограничение 60 км/ч") == "60"
    assert extract_speed_limit("скорость не более 25 км/ч") == "25"


def test_speed_merged_with_defect_row():
    text = (
        "Перегон А — Б, путь 1, км 10, пикет 2, износ 5 мм, ограничение скорости 40."
    )
    blocks = segment_logical_blocks(text)
    rows = normalize_all(expand_blocks_to_rows(blocks))
    defect_rows = [r for r in rows if r.defect]
    assert len(defect_rows) == 1
    assert defect_rows[0].defect == "износ"
    assert defect_rows[0].speed_limit == "40"
    assert not any(r.position_type == "speed_limit" for r in rows)


def test_plain_speed_phrase_in_column():
    text = "Перегон А — Б, путь 1, км 10, износ 5 мм, скорость 60 км/ч."
    rows = normalize_all(run_parsing_pipeline(text).records)
    row = next(r for r in rows if r.defect)
    assert row.speed_limit == "60"
    form = record_to_form_row(row, 1)
    assert form["Выявленная неисправность"] == "износ 5 мм"
    assert form["Ограничение скорости"] == "60 км/ч"


def test_speed_only_not_in_defect_column():
    rec = ParsedRecord(
        raw_text="ограничение скорости 60",
        position_type="speed_limit",
        speed_limit="60",
        parameter="ограничение скорости",
    )
    rows = reconcile_speed_limit_rows([rec])
    assert len(rows) == 1
    assert rows[0].defect is None
    assert rows[0].speed_limit == "60"

    rec2 = ParsedRecord(
        raw_text="износ 5 мм",
        defect="износ",
        value="5",
        unit="мм",
        logical_record_index=0,
    )
    rec3 = ParsedRecord(
        raw_text="скорость 60 км/ч",
        position_type="speed_limit",
        speed_limit="60",
        logical_record_index=0,
    )
    merged = reconcile_speed_limit_rows([rec2, rec3])
    assert len(merged) == 1
    assert merged[0].defect == "износ"
    assert merged[0].speed_limit == "60"

    _, form_rows = build_form_rows(merged)
    assert form_rows[0]["Выявленная неисправность"] == "износ 5 мм"
    assert form_rows[0]["Ограничение скорости"] == "60 км/ч"


LAPLANDIA_TEXT = (
    "Перегон лапландия пулозеро путь 2 главный километр 1353 пикет 2 "
    "неисправность уширение рельсовой колеи 1543 мм ограничение скорости 60."
)

LAPLANDIA_TEXT_SHORT = (
    "Перегон лапландия пулозеро путь 2 главный километр 1353 пикет 2 "
    "неисправность уширение рельсовой колеи 1543 мм ограничение 60."
)


def test_parsed_to_item_keeps_speed_on_defect_row():
    from app.models import InspectionRecord
    from app.services.inspection_repository import _parsed_to_item
    from app.services.parser import ParsedRecord

    record = InspectionRecord(job_id=1, sequence_number=1)
    parsed = ParsedRecord(
        defect="уширение",
        value="1543",
        unit="мм",
        speed_limit="60",
        position_type="defect",
        raw_text="уширение рельсовой колеи 1543 мм",
    )
    item = _parsed_to_item(record, parsed, 1)
    assert item.speed_limit == "60"
    assert item.defect_text == "уширение"


def test_flat_row_form_shows_speed_limit():
    from app.services.inspection_repository import FlatInspectionRow

    row = FlatInspectionRow(
        id=1,
        session_id=1,
        record_id=1,
        row_order=0,
        peregon="Лапландия — Пулозеро",
        put="2",
        km="1353",
        piket="2",
        defect="уширение",
        value="1543",
        unit="мм",
        speed_limit="60",
        raw_text="уширение рельсовой колеи 1543 мм",
    )
    form = record_to_form_row(row, 1)
    assert form["Ограничение скорости"] == "60 км/ч"
    assert form["Выявленная неисправность"] == "уширение 1543 мм"


def test_laplandia_speed_in_column():
    rows = normalize_all(run_parsing_pipeline(LAPLANDIA_TEXT).records)
    row = next(r for r in rows if r.defect or r.speed_limit)
    assert row.speed_limit == "60"
    form = record_to_form_row(row, 1)
    assert form["Ограничение скорости"] == "60 км/ч"
    assert "огранич" not in (form["Выявленная неисправность"] or "").lower()


def test_laplandia_short_limit_phrase():
    rows = normalize_all(run_parsing_pipeline(LAPLANDIA_TEXT_SHORT).records)
    row = next(r for r in rows if r.defect or r.speed_limit)
    assert row.speed_limit == "60"
    form = record_to_form_row(row, 1)
    assert form["Ограничение скорости"] == "60 км/ч"


def test_llm_defect_with_embedded_speed():
    from app.services.llm.json_schema import structured_to_parsed_rows

    data = {
        "records": [
            {
                "sequence_number": 1,
                "haul_name": "Лапландия-Пулозеро",
                "track_number": "2",
                "km_value": "1353",
                "picket_value": "2",
                "items": [
                    {
                        "order_in_record": 1,
                        "position_type": "defect",
                        "defect_text": "уширение рельсовой колеи 1543 мм ограничение скорости 60",
                    }
                ],
            }
        ]
    }
    rows = normalize_all(structured_to_parsed_rows(data))
    assert rows[0].speed_limit == "60"
    form = record_to_form_row(rows[0], 1)
    assert form["Ограничение скорости"] == "60 км/ч"
    assert "огранич" not in (form["Выявленная неисправность"] or "").lower()


def test_speed_not_duplicated_as_defect():
    rec = ParsedRecord(
        defect="ограничение скорости 60",
        raw_text="ограничение скорости 60",
        position_type="defect",
    )
    rows = normalize_all([rec])
    assert rows[0].defect is None
    assert rows[0].speed_limit == "60"


def test_parser_single_record_speed():
    text = (
        "Дата 29.06.2026. Участок Северный, перегон станция Северная — Южная, путь 1, "
        "километр 245, пикет 3, объект рельс, износ 12 миллиметров, ограничение скорости 40"
    )
    result = parse_transcript(text)
    rows = normalize_all(result.records)
    defect_row = next(r for r in rows if r.defect)
    assert defect_row.speed_limit == "40"
