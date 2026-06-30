from app.services.stations import CANONICAL_BLOCKPOSTS, CANONICAL_STATIONS, station_names_for_prompt


def test_murmansk_line_stations_present():
    assert "Апатиты" in CANONICAL_STATIONS
    assert "Оленегорск" in CANONICAL_STATIONS
    assert "Мурманск" in CANONICAL_STATIONS
    assert "Комсомольск-Мурманский" in CANONICAL_STATIONS
    assert "Ваенга" in CANONICAL_STATIONS
    assert len(CANONICAL_STATIONS) >= 30


def test_blockposts_include_1381():
    assert "Блокпост 1381 км" in CANONICAL_BLOCKPOSTS
    assert "Блокпост 1425 км" in CANONICAL_BLOCKPOSTS


def test_prompt_lists_stations():
    prompt = station_names_for_prompt()
    assert "Мурманск" in prompt
    assert "Блокпост 1381 км" in prompt
