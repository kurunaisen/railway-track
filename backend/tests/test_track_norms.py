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
