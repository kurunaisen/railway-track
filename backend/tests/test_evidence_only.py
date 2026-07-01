"""Режим evidenceOnly — таблица только из исходного ASR-сегмента."""

from app.services.asr_pipeline import asr_text_to_parsed_rows
from app.services.evidence_only import (
    defect_from_segment,
    is_evidence_only,
    note_from_segment,
    speed_from_segment,
)
from app.services.inspection_form import build_form_rows, record_to_form_row
from app.services.llm.json_schema import structured_to_parsed_rows
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord
from app.services.parsing_pipeline import run_parsing_pipeline

MURMANSK = (
    "Станция мурманск стрелочный перевод номер 10 износ рамного рельса 7 мм "
    "острие остряка пусть 15 ширина колеи 1544 мм путь 12 3 подряд куста из 3 шпал "
    "путь 11 куст из 5 негодных шпал"
)


def _murmansk_form_rows():
    parsed = asr_text_to_parsed_rows(MURMANSK, use_llm=False)
    records = structured_to_parsed_rows({"rows": parsed})
    return build_form_rows(records)[1]


def test_evidence_only_is_default():
    assert is_evidence_only() is True


def test_murmansk_evidence_only_four_rows():
    forms = _murmansk_form_rows()
    assert len(forms) == 4


def test_murmansk_switch_row_from_segment():
    row = _murmansk_form_rows()[0]
    assert row["Местонахождение (перегон, станция)"] == "Мурманск"
    assert row["№ пути, стрелочного перевода"] == "стр.п. 10"
    assert row["Выявленная неисправность"] == "износ рамного рельса 7 мм"
    assert row["Примечание"] == "в острие остряка"
    assert row["Ограничение скорости"] is None


def test_murmansk_gauge_keeps_asr_wording_not_norm_title():
    row = _murmansk_form_rows()[1]
    assert row["№ пути, стрелочного перевода"] == "15"
    assert "ширина колеи" in (row["Выявленная неисправность"] or "").lower()
    assert "уширение" not in (row["Выявленная неисправность"] or "").lower()
    assert row["Ограничение скорости"] is None


def test_norm_substituted_defect_rejected_when_segment_says_width():
    rec = ParsedRecord(
        uchastok="Мурманск",
        put="15",
        defect="уширение рельсовой колеи",
        value="1544",
        unit="мм",
        speed_limit="60",
        raw_text="путь 15 ширина колеи 1544 мм",
    )
    assert defect_from_segment(rec) == "ширина колеи 1544 мм"
    assert speed_from_segment(rec) is None


def test_note_only_from_segment_not_hallucination():
    rec = ParsedRecord(
        uchastok="Мурманск",
        switch="10",
        defect="износ рамного рельса 7 мм",
        raw_text="стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка",
        comment="левая нить",
    )
    assert note_from_segment(rec) == "в острие остряка"


def test_norm_closure_comment_not_exported():
    rec = ParsedRecord(
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
    assert not form.get("Примечание")


def test_explicit_speed_in_segment_exported():
    rec = ParsedRecord(
        put="2",
        defect="уширение колеи",
        value="1543",
        unit="мм",
        speed_limit="60",
        raw_text="путь 2 уширение колеи 1543 мм ограничение скорости 60",
    )
    form = record_to_form_row(rec, 1)
    assert form["Ограничение скорости"] == "60 км/ч"


def test_norms_enriched_mode_shows_computed_speed(monkeypatch):
    monkeypatch.setattr("app.services.evidence_only.settings.table_export_mode", "normsEnriched")
    rows = normalize_all(
        run_parsing_pipeline(MURMANSK).records,
        source_text=MURMANSK,
        apply_track_norms=True,
    )
    gauge = next(r for r in rows if r.defect and "коле" in r.defect.lower())
    form = record_to_form_row(gauge, 2, evidence_only=False)
    assert form["Ограничение скорости"] == "60 км/ч"
