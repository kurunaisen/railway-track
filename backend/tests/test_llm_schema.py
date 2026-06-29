"""FR 15.2 — валидация и конвертация строгого JSON от LLM."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.llm.json_schema import (
    parse_llm_json,
    structured_to_parsed_rows,
    validate_structured_payload,
)


SAMPLE = {
    "records": [
        {
            "sequence_number": 1,
            "haul_name": "А-Б",
            "track_number": "2",
            "km_value": "35",
            "picket_value": "5+20",
            "items": [
                {
                    "order_in_record": 1,
                    "parameter_name": "Перекос",
                    "value_numeric": 4,
                    "unit": "мм",
                    "position_type": "parameter",
                }
            ],
        },
        {
            "sequence_number": 2,
            "haul_name": "В-Г",
            "track_number": "1",
            "km_value": "12",
            "picket_value": "3+40",
            "items": [
                {
                    "order_in_record": 1,
                    "parameter_name": "Просадка",
                    "value_numeric": 6,
                    "unit": "мм",
                    "position_type": "defect",
                    "defect_text": "просадка",
                }
            ],
        },
    ]
}


def test_validate_structured_payload():
    assert validate_structured_payload(SAMPLE)["records"][0]["sequence_number"] == 1


def test_rejects_invalid_json():
    with pytest.raises(ValueError):
        validate_structured_payload({"items": []})


def test_structured_to_parsed_rows():
    rows = structured_to_parsed_rows(SAMPLE)
    assert len(rows) == 2
    assert rows[0].peregon == "А-Б"
    assert rows[0].put == "2"
    assert rows[0].parameter == "перекос"
    assert rows[0].logical_record_index == 0
    assert rows[0].position_index == 0
    assert rows[1].defect == "просадка"


def test_parse_llm_json_strips_markdown_fence():
    raw = '```json\n' + __import__("json").dumps(SAMPLE, ensure_ascii=False) + '\n```'
    data = parse_llm_json(raw)
    assert len(data["records"]) == 2
