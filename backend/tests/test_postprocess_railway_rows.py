"""postprocessRailwayRows — жёсткая evidence-only постобработка."""

from app.services.postprocess_railway_rows import (
    count_asset_markers,
    format_asset_for_cell,
    sanitize_row_for_export,
    to_display_rows,
)

MURMANSK_SEGMENTS = [
    "станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка",
    "путь 15 ширина колеи 1544 мм",
    "путь 12 3 подряд куста из 3 шпал",
    "путь 11 куст из 5 негодных шпал",
]


def _row(source: str, **kwargs) -> dict:
    return {
        "location": None,
        "assetKind": None,
        "assetNumber": None,
        "reference": None,
        "defect": None,
        "speedLimit": None,
        "note": None,
        "sourceText": source,
        **kwargs,
    }


def test_qualifier_moved_from_defect_to_note():
    row = sanitize_row_for_export(
        _row(
            MURMANSK_SEGMENTS[0],
            defect="износ рамного рельса 7 мм в острие остряка",
        )
    )
    assert row["defect"] == "износ рамного рельса 7 мм"
    assert row["note"] == "в острие остряка"


def test_multi_asset_marker_warning():
    merged = " ".join(MURMANSK_SEGMENTS[:2])
    row = sanitize_row_for_export(_row(merged))
    warnings = row.get("warnings") or []
    assert any("несколько объектов" in w for w in warnings)


def test_count_asset_markers():
    assert count_asset_markers(MURMANSK_SEGMENTS[0]) == 1
    assert count_asset_markers(" ".join(MURMANSK_SEGMENTS[:2])) == 2


def test_detect_location_and_asset_from_source():
    row = sanitize_row_for_export(_row(MURMANSK_SEGMENTS[0]))
    assert row["location"] == "Мурманск"
    assert row["assetKind"] == "switch"
    assert row["assetNumber"] == "10"


def test_format_asset_for_cell():
    assert format_asset_for_cell("switch", "10") == "стр. п. 10"
    assert format_asset_for_cell("track", "15") == "15"


def test_normative_decision_always_null():
    row = sanitize_row_for_export(
        _row(MURMANSK_SEGMENTS[1], defect="уширение рельсовой колеи")
    )
    assert row["normativeDecision"] is None


def test_to_display_rows_murmansk():
    parsed = [_row(s) for s in MURMANSK_SEGMENTS]
    _, display = to_display_rows(parsed)
    assert len(display) == 4
    assert display[0]["№ пути, стрелочного перевода"] == "стр. п. 10"
    assert display[0]["Выявленная неисправность"] == "износ рамного рельса 7 мм"
    assert display[1]["Выявленная неисправность"] == "ширина колеи 1544 мм"
    assert display[1]["Ограничение скорости"] == "—"
