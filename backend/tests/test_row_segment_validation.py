"""validate_rows_for_segment — пост-LLM правки по тексту сегмента."""

from app.services.llm.row_segment_validation import validate_rows_for_segment

BASE_ROW = {
    "location": "Мурманск",
    "assetKind": None,
    "assetNumber": None,
    "reference": None,
    "defect": "износ рамного рельса 7 мм",
    "speedLimit": 60,
    "note": None,
    "sourceText": "стрелочный перевод номер 10 износ рамного рельса 7 мм",
}


def test_switch_segment_fixes_asset_and_clears_speed():
    segment = "стрелочный перевод номер 10 износ рамного рельса 7 мм"
    row = validate_rows_for_segment(segment, [dict(BASE_ROW)])[0]
    assert row["assetKind"] == "switch"
    assert row["assetNumber"] == "10"
    assert row["speedLimit"] is None


def test_track_segment_fixes_asset():
    segment = "путь 15 ширина колеи 1544 мм"
    row = validate_rows_for_segment(
        segment,
        [{**BASE_ROW, "assetKind": "switch", "assetNumber": "10", "defect": "ширина колеи 1544 мм"}],
    )[0]
    assert row["assetKind"] == "track"
    assert row["assetNumber"] == "15"
    assert row["speedLimit"] is None


def test_explicit_speed_not_cleared_when_in_segment():
    segment = "путь 2 уширение колеи ограничение скорости 60"
    row = validate_rows_for_segment(
        segment,
        [{**BASE_ROW, "defect": "уширение колеи", "speedLimit": 60}],
    )[0]
    assert row["speedLimit"] == 60


def test_explicit_speed_from_llm_hallucination_cleared():
    segment = "путь 15 ширина колеи 1544 мм"
    row = validate_rows_for_segment(segment, [dict(BASE_ROW)])[0]
    assert row["speedLimit"] is None


def test_tip_moved_from_defect_to_note():
    segment = "стрелочный перевод 10 износ рамного рельса 7 мм в острие остряка"
    row = validate_rows_for_segment(
        segment,
        [{**BASE_ROW, "defect": "износ рамного рельса 7 мм в острие остряка", "note": None}],
    )[0]
    assert "остри" in (row["note"] or "").lower()
    assert row["defect"] == "износ рамного рельса 7 мм"
    assert "остри" not in (row["defect"] or "").lower()


def test_tip_appends_to_existing_note():
    segment = "стрелочный перевод 10 износ 7 мм на острие остряка"
    row = validate_rows_for_segment(
        segment,
        [{**BASE_ROW, "defect": "износ на острие остряка", "note": "левая нить"}],
    )[0]
    assert "левая нить" in row["note"]
    assert "остри" in row["note"].lower()


def test_source_text_forced_to_segment_not_full_asr():
    """LLM иногда кладёт весь обход в sourceText — validate перезаписывает сегментом."""
    segment = "путь 15 ширина колеи 1544 мм"
    full_asr = (
        "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
        "острие остряка путь 15 ширина колеи 1544 мм путь 12 куст"
    )
    row = validate_rows_for_segment(
        segment,
        [{**BASE_ROW, "sourceText": full_asr, "defect": "ширина колеи 1544 мм"}],
    )[0]
    assert row["sourceText"] == segment
    assert "путь 12" not in row["sourceText"]
    assert "стрелочный перевод" not in row["sourceText"]
