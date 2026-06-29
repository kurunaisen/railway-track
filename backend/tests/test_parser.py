import pytest

from app.services.parser import parse_transcript, split_into_logical_chunks


def test_single_record_extraction():
    text = (
        "Дата 29.06.2026. Участок Северный, перегон станция Северная — Южная, путь 1, "
        "километр 245, пикет 3, объект рельс, износ 12 миллиметров, ограничение скорости 40"
    )
    result = parse_transcript(text)
    assert len(result.records) >= 1
    r = result.records[0]
    assert r.record_date == "29.06.2026"
    assert r.uchastok is not None
    assert r.peregon is not None
    assert r.put == "1"
    assert r.km == "245"
    assert r.piket == "3"
    assert r.obekt == "рельс"
    assert r.defect == "износ"
    assert r.value == "12"
    assert r.unit == "мм"
    speed_rows = [x for x in result.records if x.speed_limit]
    assert len(speed_rows) >= 1
    assert speed_rows[0].speed_limit == "40"
    assert speed_rows[0].position_type == "speed_limit"


def test_multiple_records_long_audio():
    text = (
        "Перегон А — Б, путь 1, км 10, пикет 2, износ 5 мм. "
        "Далее перегон Б — В, путь 2, километр 15, пикет 4, просадка 20 мм. "
        "Также путь 1, км 15, пикет 4, трещина, уровень 15 мм, скорость не более 25 км/ч"
    )
    result = parse_transcript(text)
    assert len(result.records) >= 2
    assert result.records[0].peregon is not None


def test_split_preserves_order():
    text = "Перегон один. Далее перегон два. Затем перегон три."
    chunks = split_into_logical_chunks(text)
    assert len(chunks) >= 3
    assert "один" in chunks[0][0]
    assert "два" in chunks[1][0]


def test_multiple_defects_same_location():
    text = "Путь 1, км 248, пикет 7, просадка 25 мм; трещина на рельсе."
    result = parse_transcript(text)
    assert len(result.records) >= 2


def test_unknown_terms_detection():
    text = "Перегон тестовый, xyzzzzword абракадабра, путь 1"
    result = parse_transcript(text)
    terms = {t["term"] for t in result.unknown_terms}
    assert "xyzzzzword" in terms or "абракадабра" in terms
