"""FR 14 — несколько перегонов в одном аудио, порядок sequence_number / order_in_record."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.inspection_repository import build_structured_from_parsed
from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline

EXAMPLE_TEXT = (
    "Перегон А-Б, путь второй, км 35, пикет 5 плюс 20, перекос 4 миллиметра. "
    "Далее перегон В-Г, путь первый, км 12, пикет 3 плюс 40, просадка 6 миллиметров. "
    "Далее перегон А-Б, км 36, пикет 1 плюс 10, ограничение скорости 40."
)


def test_three_hauls_in_one_audio():
    result = run_parsing_pipeline(EXAMPLE_TEXT)
    rows = normalize_all(result.records)
    data = build_structured_from_parsed(rows)

    assert len(data["records"]) == 3


def test_sequence_numbers_start_at_one():
    rows = normalize_all(run_parsing_pipeline(EXAMPLE_TEXT).records)
    data = build_structured_from_parsed(rows)
    assert [r["sequence_number"] for r in data["records"]] == [1, 2, 3]


def test_first_record_fields():
    rows = normalize_all(run_parsing_pipeline(EXAMPLE_TEXT).records)
    r1 = build_structured_from_parsed(rows)["records"][0]
    assert r1["haul_name"] == "А-Б"
    assert r1["track_number"] == "2"
    assert r1["km_value"] == "35"
    assert r1["picket_value"] == "5+20"
    assert len(r1["items"]) == 1
    item = r1["items"][0]
    assert item["order_in_record"] == 1
    assert item["parameter_name"] == "Перекос"
    assert item["value_numeric"] == 4.0
    assert item["unit"] == "мм"


def test_second_record_haul():
    rows = normalize_all(run_parsing_pipeline(EXAMPLE_TEXT).records)
    r2 = build_structured_from_parsed(rows)["records"][1]
    assert r2["haul_name"] == "В-Г"
    assert r2["track_number"] == "1"
    assert r2["km_value"] == "12"
    assert r2["picket_value"] == "3+40"
    assert r2["items"][0]["parameter_name"] == "Просадка"
    assert r2["items"][0]["value_numeric"] == 6.0


def test_third_record_no_track_inherited():
    rows = normalize_all(run_parsing_pipeline(EXAMPLE_TEXT).records)
    r3 = build_structured_from_parsed(rows)["records"][2]
    assert r3["haul_name"] == "А-Б"
    assert r3["track_number"] is None
    assert r3["km_value"] == "36"
    assert r3["picket_value"] == "1+10"
    sp = r3["items"][0]
    assert sp["order_in_record"] == 1
    assert sp["parameter_name"] == "Ограничение скорости"
    assert sp["value_numeric"] == 40.0
    assert sp["unit"] == "км/ч"


def test_items_order_in_record():
    rows = normalize_all(run_parsing_pipeline(EXAMPLE_TEXT).records)
    for rec in build_structured_from_parsed(rows)["records"]:
        orders = [i["order_in_record"] for i in rec["items"]]
        assert orders == list(range(1, len(orders) + 1))
