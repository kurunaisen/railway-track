from app.services.locations import (
    extract_single_location,
    format_location_for_table,
    is_peregon_haul,
)
from app.services.stations import normalize_blockpost, normalize_station_name


def test_op_equals_blockpost():
    assert normalize_blockpost("О.П. 1425 км") == "Блокпост 1425 км"
    assert normalize_blockpost("остановочный пункт 1381 км") == "Блокпост 1381 км"


def test_station_prefix_stripped():
    assert extract_single_location("станция Мурманск, путь 2") == "Мурманск"


def test_plain_station_name():
    assert extract_single_location("Мурманск, путь 2") == "Мурманск"


def test_blockpost_requires_km():
    assert extract_single_location("Блокпост 1381 км") == "Блокпост 1381 км"
    assert extract_single_location("блокпост, путь 1") is None


def test_peregon_display():
    assert is_peregon_haul("Кица — Блокпост 1381 км")
    assert is_peregon_haul("А-Б")
    assert not is_peregon_haul("Комсомольск-Мурманский")
    assert format_location_for_table(peregon="Кица — Блокпост 1381 км") == "Кица-Блокпост 1381 км"


def test_station_in_table():
    assert format_location_for_table(uchastok="станция Мурманск") == "Мурманск"
    assert format_location_for_table(raw_text="станция Мурманск, путь 5") == "Мурманск"


def test_blockpost_in_table():
    assert format_location_for_table(raw_text="Блокпост 1381 км, путь 2") == "Блокпост 1381 км"


def test_normalize_station():
    assert normalize_station_name("апатиты-1") == "Апатиты"
