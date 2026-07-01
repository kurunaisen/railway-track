"""Мурманск: стр.п. 10; «пусть 15» → путь 15; острие остряка → примечание."""

from app.services.asr_fixes import fix_asr_transcript
from app.services.canonical_model import _split_by_location
from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parsing_pipeline import run_parsing_pipeline

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина колеи 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def _rows():
    return normalize_all(run_parsing_pipeline(MURMANSK).records, source_text=MURMANSK)


def test_asr_pust_to_path():
    fixed = fix_asr_transcript(MURMANSK)
    assert "пусть 15" not in fixed.lower()
    assert "путь 15" in fixed.lower()


def test_split_path_15_before_path_12():
    parts = _split_by_location(fix_asr_transcript(MURMANSK))
    assert len(parts) == 4
    assert "стрелочный перевод" in parts[0].lower()
    assert "путь 15" in parts[1].lower()
    assert "путь 12" in parts[2].lower()
    assert "путь 11" in parts[3].lower()


def test_wear_switch_only_tip_in_note():
    rows = _rows()
    wear = next(r for r in rows if r.defect and "рамн" in r.defect.lower())
    f = record_to_form_row(wear, 1)
    assert wear.put is None
    assert wear.switch == "10"
    assert wear.value == "7"
    assert "остри" not in (wear.defect or "").lower()
    assert f["№ пути, стрелочного перевода"] == "стр.п. 10"
    assert f["Примечание"] and "остри" in f["Примечание"].lower()


def test_gauge_on_path_15_with_switch():
    rows = _rows()
    gauge = next(r for r in rows if r.defect and "колеи" in r.defect.lower())
    f = record_to_form_row(gauge, 2)
    assert gauge.put == "15"
    assert gauge.switch == "10"
    assert gauge.speed_limit == "60"
    assert "15" in (f["№ пути, стрелочного перевода"] or "")
    assert "стр.п. 10" in (f["№ пути, стрелочного перевода"] or "")


def test_path_12_and_11_sleeper_clusters():
    rows = _rows()
    p12 = next(r for r in rows if r.put == "12")
    p11 = next(r for r in rows if r.put == "11")
    assert p12.switch is None
    assert p11.switch is None
    assert "шпал" in (p12.defect or p12.raw_text or "").lower()
    assert "шпал" in (p11.defect or p11.raw_text or "").lower()


def test_four_table_rows():
    assert len(_rows()) == 4
