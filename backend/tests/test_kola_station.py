"""Станция Кола: путь + стрелочный перевод, ширина колеи 1524 без V огр."""

from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.inspection_form import record_to_form_row

KOLA_TEXT = (
    "Станция кола 5 путь стрелочный перевод 15 износ сердечника крестовины 8 мм "
    "6 путь стрелочный перевод 18 ширина колеи в хвосте крестовины 1524"
)


def test_kola_two_rows_path_and_switch():
    rows = normalize_all(run_parsing_pipeline(KOLA_TEXT).records, source_text=KOLA_TEXT)
    assert len(rows) == 2, [(r.put, r.switch, r.defect) for r in rows]
    f1 = record_to_form_row(rows[0], 1)
    f2 = record_to_form_row(rows[1], 2)
    assert f1["Местонахождение (перегон, станция)"] == "Кола"
    assert "5" in (f1["№ пути, стрелочного перевода"] or "")
    assert "стр.п. 15" in (f1["№ пути, стрелочного перевода"] or "")
    assert rows[0].switch == "15"
    assert f2["Местонахождение (перегон, станция)"] == "Кола"
    assert "6" in (f2["№ пути, стрелочного перевода"] or "")
    assert "стр.п. 18" in (f2["№ пути, стрелочного перевода"] or "")
    assert rows[1].switch == "18"


def test_kola_gauge_1524_no_speed_limit():
    rows = normalize_all(run_parsing_pipeline(KOLA_TEXT).records, source_text=KOLA_TEXT)
    gauge = rows[1]
    f = record_to_form_row(gauge, 2)
    assert gauge.value == "1524" or "1524" in (f["Выявленная неисправность"] or "")
    assert f["Ограничение скорости"] is None
