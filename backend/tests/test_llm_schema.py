"""FR 15.2 — валидация и конвертация strict JSON rows[] от LLM."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.services.llm.extraction_schema import (
    RAILWAY_EXTRACTION_SCHEMA,
    openai_response_format,
)
from app.services.llm.json_schema import (
    parse_llm_json,
    structured_to_parsed_rows,
    validate_structured_payload,
)

SAMPLE = {
    "rows": [
        {
            "location": "А-Б",
            "assetKind": "track",
            "assetNumber": "2",
            "reference": "35 км, пк 5+20",
            "defect": "перекос 4 мм",
            "speedLimit": None,
            "note": None,
            "sourceText": "перегон А-Б 2 путь 35 км пикет 5+20 перекос 4 мм",
        },
        {
            "location": "В-Г",
            "assetKind": "track",
            "assetNumber": "1",
            "reference": "12 км, пк 3+40",
            "defect": "просадка 6 мм",
            "speedLimit": None,
            "note": None,
            "sourceText": "перегон В-Г 1 путь 12 км пикет 3+40 просадка 6 мм",
        },
    ]
}


def test_openai_response_format_uses_json_schema():
    fmt = openai_response_format()
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["name"] == "railway_rows"
    assert fmt["json_schema"]["strict"] is True
    assert "rows" in fmt["json_schema"]["schema"]["properties"]


def test_railway_extraction_schema_matches_contract():
    assert RAILWAY_EXTRACTION_SCHEMA["name"] == "railway_rows"
    item = RAILWAY_EXTRACTION_SCHEMA["schema"]["properties"]["rows"]["items"]
    assert set(item["required"]) == {
        "location",
        "assetKind",
        "assetNumber",
        "reference",
        "defect",
        "speedLimit",
        "note",
        "sourceText",
    }


def test_validate_structured_payload():
    assert len(validate_structured_payload(SAMPLE)["rows"]) == 2


def test_rejects_invalid_json():
    with pytest.raises(ValueError):
        validate_structured_payload({"records": []})


def test_rejects_missing_source_text():
    bad = {
        "rows": [
            {
                "location": None,
                "assetKind": None,
                "assetNumber": None,
                "reference": None,
                "defect": "x",
                "speedLimit": None,
                "note": None,
            }
        ]
    }
    with pytest.raises(ValueError):
        validate_structured_payload(bad)


def test_structured_to_parsed_rows():
    rows = structured_to_parsed_rows(SAMPLE)
    assert len(rows) == 2
    assert rows[0].peregon == "А-Б"
    assert rows[0].put == "2"
    assert rows[0].defect == "перекос 4 мм"
    assert rows[0].value == "4"
    assert rows[0].logical_record_index == 0
    assert rows[1].defect == "просадка 6 мм"


def test_structured_switch_row():
    data = {
        "rows": [
            {
                "location": "Мурманск",
                "assetKind": "switch",
                "assetNumber": "10",
                "reference": None,
                "defect": "износ рамного рельса 7 мм",
                "speedLimit": None,
                "note": "в острии остряка",
                "sourceText": "стрелочный перевод 10 износ рамного рельса 7 мм",
            }
        ]
    }
    rows = structured_to_parsed_rows(data)
    assert rows[0].switch == "10"
    assert rows[0].put is None
    assert rows[0].comment == "в острии остряка"


def test_parse_llm_json_strips_markdown_fence():
    raw = "```json\n" + json.dumps(SAMPLE, ensure_ascii=False) + "\n```"
    data = parse_llm_json(raw)
    assert len(data["rows"]) == 2
