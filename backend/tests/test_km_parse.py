"""Тесты разбора километража с паузами в речи."""

from app.services.km_parse import (
    extract_binding_km,
    merge_hesitated_km_in_text,
    merge_hesitated_km_value,
    merge_split_km_numbers,
)
from app.services.normalizer import normalize_all
from app.services.parser import parse_chunk


def test_merge_thousand_pause():
    assert merge_split_km_numbers("1000", "385") == "1385"
    assert merge_split_km_numbers("1", "385") == "1385"


def test_merge_hesitated_km_in_text():
    assert "1385 км" in merge_hesitated_km_in_text("на 1000 385 км пикет 5")


def test_merge_hesitated_km_value():
    assert merge_hesitated_km_value("1000 385") == "1385"
    assert merge_hesitated_km_value("1385") == "1385"


def test_skip_blockpost_km_in_location_name():
    text = "перегон кица блокпост 1381 километр на 1000 385 км пикет 5"
    assert extract_binding_km(text) == "1385"


def test_user_asr_example():
    text = (
        "Перегон кица блокпост 1381 километр На 1000 385 км пикет 5 метр 82 "
        "На левой стороне рельсовой нити Отсутствует 1 стыковой Болт."
    )
    record = parse_chunk(text)
    rows = normalize_all([record])
    assert rows[0].km == "1385"
    assert rows[0].piket == "5"


def test_plain_km_still_works():
    assert extract_binding_km("путь 2, км 248, пикет 7") == "248"
