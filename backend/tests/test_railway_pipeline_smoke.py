"""Smoke tests for railway v2 pipeline (normalize + schema; LLM mocked)."""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from app.services.railway.normalize_railway_rows import normalize_railway_row
from app.services.railway.schema import parse_llm_rows_payload
from app.services.railway.types import RailwayRow
from app.services.llm.extract_railway_rows import extract_railway_rows as extract_rows_from_transcript


def _row(**kwargs) -> RailwayRow:
    base = {
        "location": None,
        "assetKind": None,
        "assetNumber": None,
        "reference": None,
        "defect": None,
        "speedLimit": None,
        "note": None,
        "sourceText": "test",
        "warnings": [],
    }
    base.update(kwargs)
    return RailwayRow.model_validate(base)


def test_schema_parses_rows_array():
    payload = {
        "rows": [
            {
                "location": "Мурманск",
                "assetKind": "switch",
                "assetNumber": "10",
                "reference": None,
                "defect": "износ рамного рельса 7 мм",
                "speedLimit": None,
                "note": "в острие остряка",
                "sourceText": "стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка",
                "warnings": [],
            }
        ]
    }
    rows = parse_llm_rows_payload(payload)
    assert len(rows) == 1
    assert rows[0].asset_number == "10"


def test_normalize_dedupes_note():
    row = normalize_railway_row(
        _row(note="в острие остряка; в острие остряка", sourceText="x")
    )
    assert row.note == "в острие остряка"


@pytest.mark.parametrize(
    "llm_json,checks",
    [
        (
            {
                "rows": [
                    {
                        "location": "Мурманск",
                        "assetKind": "switch",
                        "assetNumber": "10",
                        "reference": None,
                        "defect": "износ рамного рельса 7 мм",
                        "speedLimit": None,
                        "note": "в острие остряка",
                        "sourceText": "стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка",
                        "warnings": [],
                    }
                ],
                "warnings": [],
            },
            lambda rows: (
                len(rows) == 1
                and rows[0].asset_kind == "switch"
                and rows[0].asset_number == "10"
                and rows[0].defect == "износ рамного рельса 7 мм"
                and rows[0].note == "в острие остряка"
            ),
        ),
        (
            {
                "rows": [
                    {
                        "location": None,
                        "assetKind": "track",
                        "assetNumber": "15",
                        "reference": None,
                        "defect": "ширина колеи 1544 мм",
                        "speedLimit": None,
                        "note": None,
                        "sourceText": "путь 15 ширина колеи 1544 мм",
                        "warnings": [],
                    }
                ],
                "warnings": [],
            },
            lambda rows: (
                len(rows) == 1
                and rows[0].asset_kind == "track"
                and rows[0].asset_number == "15"
                and rows[0].defect == "ширина колеи 1544 мм"
            ),
        ),
        (
            {
                "rows": [
                    {
                        "location": "Магнетиты",
                        "assetKind": "track",
                        "assetNumber": "5",
                        "reference": None,
                        "defect": "не закручен 1 стыковой болт",
                        "speedLimit": None,
                        "note": "звено 2",
                        "sourceText": "на станции магнетиты 5 путь 2 звено не закручен 1 стыковой болт",
                        "warnings": [],
                    },
                    {
                        "location": "Магнетиты",
                        "assetKind": "track",
                        "assetNumber": "5",
                        "reference": None,
                        "defect": "уширение колеи 1543 мм",
                        "speedLimit": None,
                        "note": "звено 2",
                        "sourceText": "и уширение колеи 1543 мм",
                        "warnings": [],
                    },
                ],
                "warnings": [],
            },
            lambda rows: (
                len(rows) == 2
                and all(r.asset_number == "5" for r in rows)
                and all(r.note == "звено 2" for r in rows)
            ),
        ),
        (
            {
                "rows": [
                    {
                        "location": "Перегон Апатиты Оленья",
                        "assetKind": None,
                        "assetNumber": None,
                        "reference": "1418 км, пк 2, 87 м",
                        "defect": "отсутствует 1 стыковой болт",
                        "speedLimit": None,
                        "note": None,
                        "sourceText": "перегон апатиты оленья 1418 километр пикет 2 87 метр отсутствует 1 стыковой болт",
                        "warnings": [],
                    }
                ],
                "warnings": [],
            },
            lambda rows: (
                len(rows) == 1
                and "перегон" in (rows[0].location or "").lower()
                and rows[0].reference == "1418 км, пк 2, 87 м"
            ),
        ),
    ],
)
def test_extract_railway_rows_mocked(llm_json, checks):
    with patch("app.services.llm.extract_railway_rows.get_llm_provider") as mock_provider:
        mock_provider.return_value.complete_json.return_value = json.dumps(llm_json, ensure_ascii=False)
        rows = extract_rows_from_transcript("dummy transcript")
        mock_provider.return_value.complete_json.assert_called_once()
        call_kwargs = mock_provider.return_value.complete_json.call_args.kwargs
        assert call_kwargs["user"] == "Transcript:\ndummy transcript"
    assert checks(rows)
