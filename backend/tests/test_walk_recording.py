"""Обход с диктовкой: несколько неисправностей подряд без повторения перегона."""

from app.services.canonical_model import expand_blocks_to_canonical_rows
from app.services.inspection_form import format_binding, format_defect, format_location
from app.services.normalizer import normalize_all
from app.services.segmentation import segment_logical_blocks

WALK_TEXT = (
    "Перегон от никиты шомгу 1418 километр пикет 2 87 метр отсутствует 1 стыковой болт. "
    "На 1418 км пикет 4 Метр 22 отсутствует 2 закладных болта. "
    "На станции магнититы 5 путь 2 звено не закручен 1 стыковой болт "
    "И уширение колеи 1400 1543 мм."
)


def _rows(text: str = WALK_TEXT):
    blocks = segment_logical_blocks(text)
    return normalize_all(expand_blocks_to_canonical_rows(blocks))


def test_walk_recording_splits_into_four_rows():
    rows = _rows()
    assert len(rows) == 4


def test_walk_recording_peregon_inheritance():
    rows = _rows()
    peregon_rows = [r for r in rows if r.peregon]
    assert len(peregon_rows) == 2
    assert all("Шонгуй" in (r.peregon or "") for r in peregon_rows)
    assert rows[0].km == "1418"
    assert rows[0].piket == "2+87"
    assert rows[1].km == "1418"
    assert rows[1].piket == "4+22"


def test_walk_recording_station_context():
    rows = _rows()
    station_rows = rows[2:]
    assert all(r.peregon is None for r in station_rows)
    assert all(r.uchastok == "Магнетиты" for r in station_rows)
    assert rows[2].put == "5"
    assert "звено 2" in (rows[2].comment or "")


def test_walk_recording_defects():
    rows = _rows()
    defects = [format_defect(r) for r in rows]
    assert "отсутствует" in defects[0].lower()
    assert "стыков" in defects[0].lower()
    assert "закладн" in defects[1].lower()
    assert "закручен" in defects[2].lower()
    assert "уширение" in defects[3].lower()
    assert rows[3].value == "1543"
    assert rows[3].unit == "мм"
    assert rows[3].speed_limit == "60"


def test_walk_recording_location_and_binding():
    rows = _rows()
    assert format_location(rows[0]) == "Магнетиты-Шонгуй"
    assert format_binding(rows[0]) == "1418 км, пк 2, м 87"
    assert format_location(rows[2]) == "Магнетиты"
