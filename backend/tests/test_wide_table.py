"""Сводная (wide) таблица: путь, стр.п. и вид объекта."""

from dataclasses import dataclass, field

from app.services.inspection_form import format_object_kind, format_path, format_switch
from app.services.wide_table import build_wide_rows


@dataclass
class Rec:
    record_date: str | None = None
    uchastok: str | None = None
    peregon: str | None = None
    put: str | None = None
    km: str | None = None
    piket: str | None = None
    obekt: str | None = None
    parameter: str | None = None
    defect: str | None = None
    value: str | None = None
    unit: str | None = None
    comment: str | None = None
    speed_limit: str | None = None
    raw_text: str | None = None
    disputed_fields: list[str] = field(default_factory=list)


def test_path_column_on_peregon():
    rec = Rec(peregon="Кица — Блокпост 1381 км", put="2", km="1384", piket="4")
    assert format_path(rec) == "2 гл.п."
    assert format_switch(rec) is None
    assert format_object_kind(rec) == "путь"


def test_switch_column_and_object_kind():
    rec = Rec(
        put="3",
        obekt="рельс",
        raw_text="стрелочный перевод номер 3, износ 12 миллиметров",
    )
    assert format_path(rec) is None
    assert format_switch(rec) == "стр.п. 3"
    assert format_object_kind(rec) == "стрелочный перевод"


def test_path_and_switch_together():
    rec = Rec(
        put="4",
        raw_text="Перегон Кица-Блокпост, путь номер 4, стрелочный перевод 2, километр 1384",
    )
    assert format_path(rec) == "4 гл.п."
    assert format_switch(rec) == "стр.п. 2"
    assert format_object_kind(rec) == "путь, стрелочный перевод"


def test_wide_table_columns():
    rec = Rec(
        peregon="Кица — Блокпост 1381 км",
        put="2",
        km="1384",
        defect="износ",
        value="12",
        unit="мм",
    )
    cols, rows = build_wide_rows([rec])
    assert cols[:8] == [
        "Дата", "Участок", "Перегон", "Путь", "Стрелочный перевод", "Км", "Пикет", "Объект"
    ]
    assert rows[0]["Путь"] == "2 гл.п."
    assert rows[0]["Стрелочный перевод"] is None
    assert rows[0]["Объект"] == "путь"
