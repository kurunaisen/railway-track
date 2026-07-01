"""4-этапный ASR-пайплайн: кейс Мурманск (без LLM)."""

from app.services.asr_pipeline import asr_text_to_parsed_rows

MURMANSK_CANONICAL = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка путь 15 ширина колеи 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def _rows():
    return asr_text_to_parsed_rows(MURMANSK_CANONICAL, use_llm=False)


def test_murmansk_four_segments_four_rows():
    rows = _rows()
    assert len(rows) == 4


def test_murmansk_switch_wear_with_tip_note():
    row = _rows()[0]
    assert row["location"] == "Мурманск"
    assert row["assetKind"] == "switch"
    assert row["assetNumber"] == "10"
    assert row["defect"] == "износ рамного рельса 7 мм"
    assert row["note"] and "остри" in row["note"].lower()
    assert "остри" not in (row["defect"] or "").lower()
    assert row["speedLimit"] is None


def test_murmansk_path_15_gauge():
    row = _rows()[1]
    assert row["location"] == "Мурманск"
    assert row["assetKind"] == "track"
    assert row["assetNumber"] == "15"
    assert "коле" in (row["defect"] or "").lower()
    assert "1544" in (row["defect"] or "")
    assert row["speedLimit"] is None


def test_murmansk_path_12_sleeper_cluster():
    row = _rows()[2]
    assert row["assetKind"] == "track"
    assert row["assetNumber"] == "12"
    assert "подряд" in (row["defect"] or "").lower() or "3" in (row["defect"] or "")
    assert row["speedLimit"] is None


def test_murmansk_path_11_bad_sleepers():
    row = _rows()[3]
    assert row["assetKind"] == "track"
    assert row["assetNumber"] == "11"
    assert "негодн" in (row["defect"] or "").lower()
    assert row["speedLimit"] is None


def test_murmansk_no_mixed_track_and_switch():
    for row in _rows():
        kind = row.get("assetKind")
        assert kind in ("track", "switch")
        assert row.get("assetNumber")


def test_each_row_source_text_is_own_segment_only():
    from app.services.railway_segment import segment_railway_text

    blocks = segment_railway_text(MURMANSK_CANONICAL)
    rows = _rows()
    assert len(rows) == len(blocks) == 4
    for row, block in zip(rows, blocks):
        assert row["sourceText"] == block.segment
        assert "путь 12" not in row["sourceText"] or block.segment.startswith("путь 12")
