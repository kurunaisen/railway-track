"""flatten_blocks_to_rows — наследование asset с блока на строки."""

from app.services.flatten_blocks_to_rows import build_row_source_text, flatten_blocks_to_rows


def test_inherits_switch_from_block():
    rows = flatten_blocks_to_rows(
        [
            {
                "location": "Мурманск",
                "assetKind": "switch",
                "assetNumber": "10",
                "rows": [
                    {
                        "defect": "износ рамного рельса 7 мм",
                        "note": "в острие остряка",
                    }
                ],
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0]["assetKind"] == "switch"
    assert rows[0]["assetNumber"] == "10"
    assert "стрелочный перевод номер 10" in rows[0]["sourceText"]


def test_row_asset_overrides_block():
    rows = flatten_blocks_to_rows(
        [
            {
                "location": "Мурманск",
                "assetKind": "switch",
                "assetNumber": "10",
                "rows": [{"assetKind": "track", "assetNumber": "15", "defect": "ширина колеи 1544 мм"}],
            }
        ]
    )
    assert rows[0]["assetKind"] == "track"
    assert rows[0]["assetNumber"] == "15"


def test_build_row_source_text_switch():
    text = build_row_source_text(
        location="Мурманск",
        asset_kind="switch",
        asset_number="10",
        defect="износ рамного рельса 7 мм",
        note="в острие остряка",
    )
    assert "станция Мурманск" in text
    assert "стрелочный перевод номер 10" in text
