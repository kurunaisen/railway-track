"""parseRailwayNarrative — парсер диктовки с контекстом."""

from app.services.parse_railway_narrative import (
    narrative_matches,
    normalize_narrative_text,
    parse_railway_narrative,
    parse_railway_narrative_to_records,
    prefer_narrative_parser,
)

NARRATIVE_SAMPLE = (
    "перегон апатиты оленья 1381 километр 385 пк 5 85 метр отсутствует 1 стыковой болт "
    "станция апатиты 2 путь 1 звено уширение колеи 1544 мм"
)

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка путь 15 ширина колеи 1544 мм"
)


def test_normalize_kilometr_to_km():
    assert "км" in normalize_narrative_text("1381 километр 385 пк")


def test_narrative_matches_bolt_and_gauge():
    assert narrative_matches(NARRATIVE_SAMPLE)


def test_parse_peregon_bolt_row():
    rows = parse_railway_narrative(NARRATIVE_SAMPLE)
    assert len(rows) == 2
    assert rows[0]["location"] == "Перегон апатиты оленья"
    assert rows[0]["defect"] == "отсутствует 1 стыковой болт"
    assert rows[0]["reference"] == "1381 км, пк 385, 85 м"


def test_parse_station_gauge_row():
    rows = parse_railway_narrative(NARRATIVE_SAMPLE)
    assert rows[1]["location"] == "Апатиты"
    assert rows[1]["assetKind"] == "track"
    assert rows[1]["assetNumber"] == "2"
    assert rows[1]["defect"] == "уширение колеи 1544 мм"
    assert rows[1]["note"] == "звено 1"


def test_prefer_narrative_not_murmansk():
    assert not prefer_narrative_parser(MURMANSK)


def test_prefer_narrative_peregon_bolt():
    assert prefer_narrative_parser(NARRATIVE_SAMPLE)


def test_to_records_has_switch_fields():
    records = parse_railway_narrative_to_records(NARRATIVE_SAMPLE)
    assert len(records) == 2
    assert records[1].put == "2"
