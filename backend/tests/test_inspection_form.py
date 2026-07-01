"""Тесты формата официальной таблицы обхода."""

from dataclasses import dataclass

from app.services.inspection_form import (
    FORM_COLUMNS,
    build_form_rows,
    format_binding,
    format_defect,
    format_location,
    format_track,
)


@dataclass
class Rec:
    peregon: str | None = None
    uchastok: str | None = None
    put: str | None = None
    switch: str | None = None
    obekt: str | None = None
    km: str | None = None
    piket: str | None = None
    parameter: str | None = None
    defect: str | None = None
    value: str | None = None
    unit: str | None = None
    comment: str | None = None
    speed_limit: str | None = None
    raw_text: str | None = None


def test_form_columns_match_template():
    assert len(FORM_COLUMNS) == 7
    assert FORM_COLUMNS[0] == "Nп/п"
    assert "Местонахождение" in FORM_COLUMNS[1]
    assert "неисправность" in FORM_COLUMNS[4].lower()


def test_example_row_from_user_template():
    rec = Rec(
        peregon="Кица — Блокпост 1381 км",
        put="2",
        km="1384",
        piket="4+33",
        defect="Отсутствие одного стыкового болта по левой рельсовой нити",
    )
    assert format_location(rec) == "Кица-Блокпост 1381 км"
    assert format_track(rec) == "2 гл.п."
    assert format_binding(rec) == "1384 км, пк 4, м 33"
    assert format_defect(rec) == rec.defect

    cols, rows = build_form_rows([rec], evidence_only=False)
    assert cols == list(FORM_COLUMNS)
    row = rows[0]
    assert row["Nп/п"] == 1
    assert row["Местонахождение (перегон, станция)"] == "Кица-Блокпост 1381 км"
    assert row["№ пути, стрелочного перевода"] == "2 гл.п."
    assert row["Привязка (км,пк,м)"] == "1384 км, пк 4, м 33"
    assert "стыкового болта" in row["Выявленная неисправность"]
    assert row["Ограничение скорости"] is None
    assert row["Примечание"] is None


def test_switch_track_abbreviation():
    rec = Rec(
        put="3",
        obekt="стрелочный перевод",
        raw_text="Перегон Кица-Блокпост, стрелочный перевод номер 3, километр 1384",
    )
    assert format_track(rec) == "3 гл.п., стр.п. 3"


def test_switch_not_inferred_from_obekt_only():
    rec = Rec(put="3", obekt="стрелочный перевод")
    assert format_track(rec) == "3"


def test_station_path_number_without_main_path():
    rec = Rec(
        put="5",
        raw_text="станция Мурманск, путь номер 5",
    )
    assert format_track(rec) == "5"


def test_station_main_path_explicit():
    rec = Rec(
        put="5",
        raw_text="станция Мурманск, главный путь номер 5",
    )
    assert format_track(rec) == "5 гл.п."


def test_peregon_implies_main_path():
    rec = Rec(
        peregon="Кица — Блокпост 1391 км",
        put="2",
    )
    assert format_track(rec) == "2 гл.п."


def test_path_and_switch_together():
    rec = Rec(
        put="4",
        raw_text="Перегон Кица-Блокпост, путь номер 4, стрелочный перевод 2, километр 1384",
    )
    assert format_track(rec) == "4 гл.п., стр.п. 2"


def test_path_and_switch_from_record_fields():
    """LLM: put/switch в полях записи, в raw_text только дефект."""
    rec = Rec(
        put="5",
        switch="15",
        uchastok="Кола",
        raw_text="износ сердечника крестовины 8 мм",
    )
    assert format_track(rec) == "5, стр.п. 15"


def test_path_and_switch_same_number_both_shown():
    """Путь и стр.п. — разные объекты, даже при совпадении номера."""
    rec = Rec(
        put="3",
        raw_text="стрелочный перевод номер 3, дефект на стыке",
    )
    assert format_track(rec) == "3, стр.п. 3"
