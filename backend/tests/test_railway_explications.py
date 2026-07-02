from app.services.normalizer import normalize_all, normalize_put
from app.services.parser import ParsedRecord
from app.services.railway_explications import (
    explication_station_names,
    match_station_by_park,
    path_for_station_switch,
    station_has_path,
    station_has_switch,
)
from app.services.inspection_form import record_to_form_row
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


def test_murmansk_park_aliases_resolve_station():
    assert match_station_by_park("ранжирный парк") == ("Мурманск", "РП")
    assert match_station_by_park("парк ПОП") == ("Мурманск", "ПОП")

    row = record_to_form_row(
        ParsedRecord(raw_text="ранжирный парк путь 8р просадка 12 мм"),
        1,
        evidence_only=False,
    )
    assert row["Местонахождение (перегон, станция)"] == "Мурманск"
