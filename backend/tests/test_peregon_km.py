"""Границы км перегонов и исправление ошибок ASR."""

from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.peregons import normalize_peregon
from app.services.peregon_km import correct_km_for_peregon

MAGNETITES_TEXT = (
    "Перегон магнитит и шон 2419 км пикет 8 уширение рельсовой колеи 1543 мм."
)


def test_peregon_asr_alias():
    assert normalize_peregon("магнитит и шон") == "Магнетиты — Шонгуй"
    assert normalize_peregon("магнитит и шон 2419") == "Магнетиты — Шонгуй"


def test_km_2419_corrected_to_1419():
    km, fixed = correct_km_for_peregon("2419", "Магнетиты — Шонгуй")
    assert fixed is True
    assert km == "1419"


def test_km_1419_unchanged():
    km, fixed = correct_km_for_peregon("1419", "Магнетиты — Шонгуй")
    assert fixed is False
    assert km == "1419"


def test_magnetites_shonguy_transcript():
    rows = normalize_all(run_parsing_pipeline(MAGNETITES_TEXT).records)
    assert len(rows) >= 1
    row = rows[0]
    assert row.peregon == "Магнетиты — Шонгуй"
    assert row.km == "1419"
    assert row.piket == "8"
    assert "km" in row.disputed_fields
