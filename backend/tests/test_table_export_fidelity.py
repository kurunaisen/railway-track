"""Таблица обхода: без подстановки V огр. и «движение закрывается» по нормам."""

from app.services.inspection_form import build_form_rows, record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord
from app.services.parsing_pipeline import run_parsing_pipeline

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина колеи 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def test_normalize_all_default_skips_track_norms():
    rows = normalize_all(run_parsing_pipeline(MURMANSK).records, source_text=MURMANSK)
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    assert gauge.speed_limit is None
    assert "уширение" not in (gauge.defect or "").lower() or "ширина" in (gauge.defect or "").lower()


def test_form_table_no_computed_speed_for_gauge():
    rows = normalize_all(run_parsing_pipeline(MURMANSK).records, source_text=MURMANSK)
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    form = record_to_form_row(gauge, 2)
    assert form["Ограничение скорости"] is None


def test_form_table_strips_norm_closure_comment():
    rec = ParsedRecord(
        uchastok="Тест",
        put="1",
        defect="стыковой зазор",
        value="35",
        unit="мм",
        speed_limit="25",
        comment="движение закрывается (2288р)",
        raw_text="стыковой зазор 35 мм",
    )
    form = record_to_form_row(rec, 1)
    assert form["Ограничение скорости"] is None
    assert not form.get("Примечание") or "закрывается" not in (form["Примечание"] or "").lower()


def test_apply_track_norms_opt_in():
    rows = normalize_all(
        run_parsing_pipeline(MURMANSK).records,
        source_text=MURMANSK,
        apply_track_norms=True,
    )
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    assert gauge.speed_limit == "60"


def test_build_form_rows_all_murmansk_without_speed():
    rows = normalize_all(run_parsing_pipeline(MURMANSK).records, source_text=MURMANSK)
    _, forms = build_form_rows(rows)
    assert len(forms) == 4
    assert all(f["Ограничение скорости"] is None for f in forms)
