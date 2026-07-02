from __future__ import annotations

import json
from unittest.mock import patch

from app.services.llm.extract_railway_rows import extract_railway_rows
from app.services.railway.semantic_repair import repair_railway_rows
from app.services.railway.types import RailwayRow


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


def test_repair_switch_asset_and_point_note():
    rows = repair_railway_rows(
        [
            _row(
                sourceText="стрелочный перевод номер 10 износ рамного рельса 7 мм в острии остряка",
                defect="износ рамного рельса 7 мм",
            )
        ]
    )

    row = rows[0]
    assert row.location is None
    assert row.asset_kind == "switch"
    assert row.asset_number == "10"
    assert row.defect == "износ рамного рельса 7 мм"
    assert row.note == "в острии остряка"
    assert row.warnings


def test_repair_track_asset_from_path_phrase():
    rows = repair_railway_rows(
        [
            _row(
                sourceText="путь 15 ширина колеи 1544 мм",
                defect="ширина колеи 1544 мм",
            )
        ]
    )

    row = rows[0]
    assert row.asset_kind == "track"
    assert row.asset_number == "15"
    assert row.defect == "ширина колеи 1544 мм"


def test_repair_station_path_and_link_note_from_contaminated_location():
    rows = repair_railway_rows(
        [
            _row(
                location="Станция Магнетиты, 5 путь, звено 2",
                sourceText="На станции Магнетиты 5 путь 2 звено не закручен 1 стыковой болт",
                defect="не закручен 1 стыковой болт",
            ),
            _row(
                location="Станция Магнетиты, 5 путь, звено 2",
                sourceText="и уширение колеи 1543 мм",
                defect="уширение колеи 1543 мм",
            ),
        ]
    )

    assert len(rows) == 2
    for row in rows:
        assert row.location == "Магнетиты"
        assert row.asset_kind == "track"
        assert row.asset_number == "5"
        assert row.note == "звено 2"
        assert "путь" not in (row.location or "").lower()
        assert "звено" not in (row.location or "").lower()


def test_repair_peregon_reference_from_words():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон от Никиты Шонгуй 1418 километр пикет 2 87 метр",
                sourceText="Перегон от Никиты Шонгуй 1418 километр пикет 2 87 метр отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            )
        ]
    )

    row = rows[0]
    assert row.location == "Перегон Магнетиты - Шонгуй"
    assert row.reference == "1418 км, пк 2, 87 м"


def test_repair_known_magnetity_shonguy_aliases():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон от никиты шомгу",
                sourceText="Перегон от никиты шомгу 1418 километр пике 2 87 метр отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            ),
            _row(
                location="магнитит шон",
                sourceText="магнитит шон 249 км пикет 8 уширение рельсовой колеи 1543 мм",
                defect="уширение рельсовой колеи 1543 мм",
            ),
            _row(
                location="Перегон Магнетиты - шомгу",
                sourceText="Перегон Магнетиты - шомгу 1418 км пикет 4 отсутствует 2 закладных болта",
                defect="отсутствует 2 закладных болта",
            ),
        ]
    )

    assert rows[0].location == "Перегон Магнетиты - Шонгуй"
    assert rows[1].location == "Перегон Магнетиты - Шонгуй"
    assert rows[2].location == "Перегон Магнетиты - Шонгуй"


def test_repair_capitalizes_peregon_parts_around_dash():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон кола-мурманск",
                sourceText="Перегон кола-мурманск 1426 км пикет 2 отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            ),
            _row(
                location="Перегон Кола - мурманск",
                sourceText="Перегон Кола - мурманск 1426 км пикет 2 отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            ),
        ]
    )

    assert rows[0].location == "Перегон Кола-Мурманск"
    assert rows[1].location == "Перегон Кола - Мурманск"


def test_repair_keeps_km_pk_reference_without_meter():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон Магнетиты - Шонгуй",
                reference="249 км пикет 8",
                sourceText="Перегон Магнетиты - Шонгуй на 249 км пикет 8 уширение рельсовой колеи 1543 мм",
                defect="уширение рельсовой колеи 1543 мм",
            )
        ]
    )

    row = rows[0]
    assert row.location == "Перегон Магнетиты - Шонгуй"
    assert row.reference == "249 км, пк 8"


def test_repair_keeps_standalone_km_reference():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон Магнетиты - Шонгуй",
                reference="249 км",
                sourceText="Перегон Магнетиты - Шонгуй 249 км уширение рельсовой колеи 1543 мм",
                defect="уширение рельсовой колеи 1543 мм",
            )
        ]
    )

    assert rows[0].reference == "249 км"


def test_repair_rejects_piket_or_meter_without_km():
    rows = repair_railway_rows(
        [
            _row(
                reference="пикет 8",
                sourceText="пикет 8 уширение рельсовой колеи 1543 мм",
                defect="уширение рельсовой колеи 1543 мм",
            ),
            _row(
                reference="87 метр",
                sourceText="87 метр отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            ),
        ]
    )

    assert rows[0].reference is None
    assert rows[1].reference is None
    assert all("reference cleared" in " ".join(row.warnings) for row in rows)


def test_repair_cleans_excel_observed_location_and_reference_leaks():
    rows = repair_railway_rows(
        [
            _row(
                location="Перегон Магнетиты - Шонгуй Перегон Магнетиты - Шонгуй",
                reference="1418 км пикет 2, 87 м",
                sourceText="Перегон Магнетиты - Шонгуй 1418 километр пике 2 87 метр отсутствует 1 стыковой болт",
                defect="отсутствует 1 стыковой болт",
            ),
            _row(
                location="Перегон Магнетиты - Шонгуй На",
                reference="1418 км пикет 4, 22 м",
                sourceText="На 1418 км пикет 4 Метр 22 отсутствует 2 закладных болта",
                defect="отсутствует 2 закладных болта",
            ),
            _row(
                location="Магнетиты На станции Магнетиты",
                reference="2 звено",
                sourceText="На станции Магнетиты 5 путь 2 звено не закручен 1 стыковой болт",
                defect="не закручен 1 стыковой болт",
            ),
        ]
    )

    assert rows[0].location == "Перегон Магнетиты - Шонгуй"
    assert rows[0].reference == "1418 км, пк 2, 87 м"
    assert rows[1].location == "Перегон Магнетиты - Шонгуй"
    assert rows[1].reference == "1418 км, пк 4, 22 м"
    assert rows[2].location == "Магнетиты"
    assert rows[2].reference is None
    assert rows[2].asset_kind == "track"
    assert rows[2].asset_number == "5"
    assert rows[2].note == "звено 2"


def test_extract_repairs_real_transcript_bad_llm_semantics():
    transcript = (
        "Перегон от никиты шомгу 1418 километр пике 2 87 метр отсутствует 1 стыковой болт "
        "На 1418 км пикет 4 метр 22 отсутствует 2 закладных болта "
        "На станции магнититы 5 путь 2 звено не закручен 1 стыковой болт "
        "И уширение колеи 1400 1543 мм"
    )
    bad_llm_json = {
        "rows": [
            {
                "location": "Перегон от никиты шомгу 1418 километр пике 2 87 метр",
                "assetKind": None,
                "assetNumber": None,
                "reference": None,
                "defect": "отсутствует 1 стыковой болт",
                "speedLimit": None,
                "note": None,
                "sourceText": "Перегон от никиты шомгу 1418 километр пике 2 87 метр отсутствует 1 стыковой болт",
                "warnings": [],
            },
            {
                "location": "1418 км пикет 4 метр 22",
                "assetKind": None,
                "assetNumber": None,
                "reference": None,
                "defect": "отсутствует 2 закладных болта",
                "speedLimit": None,
                "note": None,
                "sourceText": "На 1418 км пикет 4 метр 22 отсутствует 2 закладных болта",
                "warnings": [],
            },
            {
                "location": "Станция магнититы, 5 путь, 2 звено",
                "assetKind": None,
                "assetNumber": None,
                "reference": None,
                "defect": "не закручен 1 стыковой болт",
                "speedLimit": None,
                "note": None,
                "sourceText": "На станции магнититы 5 путь 2 звено не закручен 1 стыковой болт",
                "warnings": [],
            },
            {
                "location": None,
                "assetKind": None,
                "assetNumber": None,
                "reference": None,
                "defect": "уширение колеи 1543 мм",
                "speedLimit": None,
                "note": None,
                "sourceText": "И уширение колеи 1400 1543 мм",
                "warnings": [],
            },
        ],
        "warnings": [],
    }

    with patch("app.services.llm.extract_railway_rows.get_llm_provider") as mock_provider:
        mock_provider.return_value.complete_json.return_value = json.dumps(bad_llm_json, ensure_ascii=False)
        rows = extract_railway_rows(transcript)
        call_kwargs = mock_provider.return_value.complete_json.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4.1"

    assert len(rows) == 4
    assert rows[0].reference is not None
    assert rows[1].reference is not None
    assert rows[2].asset_number == "5"
    assert rows[2].note and "звено 2" in rows[2].note
    assert rows[3].asset_number == "5"
    assert rows[3].asset_kind == "track"
