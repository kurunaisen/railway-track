"""Нормы Распоряжения № 2288р — неисправность и V огр. по измерению."""

from app.services.inspection_form import record_to_form_row
from app.services.normalizer import normalize_all
from app.services.parser import ParsedRecord
from app.services.parsing_pipeline import run_parsing_pipeline
from app.services.track_norms import (
    apply_track_norms,
    evaluate_norm_band,
    match_track_norm_rule,
    JOINT_GAP_RULE,
)


def test_match_joint_gap_rule():
    assert match_track_norm_rule("стыковой зазор 28 мм") is JOINT_GAP_RULE
    assert match_track_norm_rule("зазор в стыке 30") is JOINT_GAP_RULE
    assert match_track_norm_rule("температурный зазор 20") is None


def test_joint_gap_bands():
    assert evaluate_norm_band(22, JOINT_GAP_RULE).speed_kmh is None
    assert evaluate_norm_band(25, JOINT_GAP_RULE).speed_kmh == 100
    assert evaluate_norm_band(28, JOINT_GAP_RULE).speed_kmh == 60
    assert evaluate_norm_band(32, JOINT_GAP_RULE).speed_kmh == 25
    assert evaluate_norm_band(40, JOINT_GAP_RULE).closed is True


def test_auto_speed_60_when_gap_over_26():
    rec = ParsedRecord(
        parameter="зазор",
        value="28",
        unit="мм",
        raw_text="стыковой зазор 28 мм",
    )
    apply_track_norms(rec)
    assert rec.defect == "стыковой зазор"
    assert rec.speed_limit == "60"
    form = record_to_form_row(rec, 1)
    assert form["Ограничение скорости"] == "60 км/ч"


def test_normal_gap_no_speed_limit():
    rec = ParsedRecord(
        parameter="зазор",
        value="22",
        unit="мм",
        raw_text="стыковой зазор 22 мм",
    )
    apply_track_norms(rec)
    assert rec.speed_limit is None


def test_spoken_speed_not_overwritten():
    rec = ParsedRecord(
        parameter="зазор",
        value="28",
        unit="мм",
        speed_limit="40",
        raw_text="стыковой зазор 28 мм ограничение 40",
    )
    apply_track_norms(rec)
    assert rec.speed_limit == "40"


def test_gap_24_26_no_speed_when_line_max_80():
    """По 2288р — 100 км/ч, но на участке макс. 80 → V огр. не записываем."""
    rec = ParsedRecord(
        parameter="зазор",
        value="25",
        unit="мм",
        raw_text="стыковой зазор 25 мм",
    )
    apply_track_norms(rec)
    assert rec.defect == "стыковой зазор"
    assert rec.speed_limit is None


def test_joint_gap_from_transcript():
    text = "Перегон А — Б, путь 1, км 10, пикет 2, стыковой зазор 28 мм."
    rows = normalize_all(run_parsing_pipeline(text).records)
    row = rows[0]
    assert row.speed_limit == "60"
    assert row.defect == "стыковой зазор"


def test_gauge_within_tolerance_no_defect():
    rec = ParsedRecord(
        defect="уширение рельсовой колеи",
        value="1524",
        unit="мм",
        raw_text="уширение рельсовой колеи 1524 мм",
    )
    apply_track_norms(rec)
    assert rec.speed_limit is None


def test_gauge_widen_1543_speed_60():
    """436/р прил. 2 табл. П.2.1: 1524 < ширина ≤ 1544 мм → 60 км/ч (V уст. 61–100)."""
    rec = ParsedRecord(
        defect="уширение рельсовой колеи",
        value="1543",
        unit="мм",
        raw_text="уширение рельсовой колеи 1543 мм",
    )
    apply_track_norms(rec)
    assert rec.defect == "уширение рельсовой колеи"
    assert rec.speed_limit == "60"


def test_gauge_1543_is_third_degree():
    from app.services.gauge_norms import DeviationDegree, evaluate_gauge_width

    evaluation = evaluate_gauge_width(1543, "уширение рельсовой колеи")
    assert evaluation.degree == DeviationDegree.III


def test_gauge_widen_1545_speed_25():
    rec = ParsedRecord(
        defect="уширение рельсовой колеи",
        value="1545",
        unit="мм",
        raw_text="уширение рельсовой колеи 1545 мм",
    )
    apply_track_norms(rec)
    assert rec.speed_limit == "25"


def test_gauge_closed_above_1548():
    rec = ParsedRecord(
        defect="уширение рельсовой колеи",
        value="1549",
        unit="мм",
        raw_text="уширение рельсовой колеи 1549 мм",
    )
    apply_track_norms(rec)
    assert "закрывается" in (rec.comment or "")


def test_gauge_switch_1524_within_content_tolerance():
    """2288р табл. 2.4: 1524 мм — верхняя граница допуска, без V огр. даже у крестовины."""
    from app.services.gauge_norms import evaluate_gauge_width

    evaluation = evaluate_gauge_width(1524, "стрелочный перевод ширина колеи в хвосте крестовины")
    assert evaluation.within_tolerance
    rec = ParsedRecord(
        defect="ширина рельсовой колеи",
        value="1524",
        unit="мм",
        raw_text="ширина колеи в хвосте крестовины 1524",
    )
    apply_track_norms(rec)
    assert rec.speed_limit is None


def test_gauge_switch_1525_over_switch_tolerance():
    from app.services.gauge_norms import evaluate_gauge_width

    evaluation = evaluate_gauge_width(1525, "стрелочный перевод уширение колеи")
    assert not evaluation.within_tolerance


def test_gauge_from_walk_transcript():
    text = (
        "На станции магнититы 5 путь 2 звено не закручен 1 стыковой болт "
        "И уширение колеи 1400 1543 мм."
    )
    rows = normalize_all(run_parsing_pipeline(text).records)
    gauge_row = [r for r in rows if r.defect and "уширен" in r.defect][0]
    assert gauge_row.value == "1543"
    assert gauge_row.speed_limit == "60"
