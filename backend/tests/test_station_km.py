"""Тесты границ км станций."""

from app.services.station_km import sanitize_station_km


def test_magnetites_rejects_1400_asr_noise():
    cleared, was_cleared = sanitize_station_km("1400", "Магнетиты")
    assert was_cleared
    assert cleared is None


def test_magnetites_accepts_in_bounds_km():
    km, was_cleared = sanitize_station_km("1410", "Магнетиты")
    assert not was_cleared
    assert km == "1410"
