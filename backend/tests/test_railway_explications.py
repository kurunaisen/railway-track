from app.services.normalizer import normalize_all, normalize_put
from app.services.parser import ParsedRecord
from app.services.railway_explications import (
    explication_station_names,
    path_for_station_switch,
    station_has_path,
    station_has_switch,
)
from app.services.stations import normalize_station_name


def test_explication_stations_extend_station_dictionary():
    assert "Заполярная" in explication_station_names()
    assert normalize_station_name("заполярная") == "Заполярная"


def test_station_paths_from_explication_normalize_roman_numbers():
    assert normalize_put("II") == "2"
    assert station_has_path("Кола", "I")
    assert station_has_path("Кола", "1")


def test_switches_from_explication_are_available():
    assert station_has_switch("Лапландия", "1")
    assert path_for_station_switch("Лапландия", "1") == "2"


def test_explication_context_marks_unknown_station_path():
    rows = normalize_all(
        [
            ParsedRecord(
                uchastok="Лапландия",
                put="999",
                defect="просадка",
                value="12",
                unit="мм",
            )
        ],
        apply_track_norms=False,
    )
    assert rows[0].uchastok == "Лапландия"
    assert "put" in rows[0].disputed_fields
