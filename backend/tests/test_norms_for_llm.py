"""Нормы для промпта LLM — синхронизация с gauge_norms / track_norms."""

from app.services.gauge_norms import evaluate_gauge_width, gauge_speed_limit_kmh
from app.services.norms_for_llm import build_norms_reference, build_norms_summary_for_llm
from app.services.track_norms import JOINT_GAP_RULE, evaluate_norm_band


def test_summary_contains_gauge_and_joint_bands():
    text = build_norms_summary_for_llm()
    assert "2288р" in text
    assert "436/р" in text
    assert "1512" in text and "1524" in text
    assert "1544" in text and "60 км/ч" in text
    assert JOINT_GAP_RULE.title in text
    assert "24" in text and "100 км/ч" in text


def test_summary_1543_example_matches_code():
    summary = build_norms_summary_for_llm()
    evaluation = evaluate_gauge_width(1543, "уширение колеи")
    speed = gauge_speed_limit_kmh(evaluation)
    assert "1543" in summary
    assert str(speed) in summary


def test_reference_bands_match_track_norms():
    ref = build_norms_reference()
    gap = ref["rules"][0]
    assert gap["id"] == "joint_gap"
    value = 25.0
    band = evaluate_norm_band(value, JOINT_GAP_RULE)
    assert band is not None
    assert band.speed_kmh == 100
    assert any("100" in b["text"] for b in gap["bands"])


def test_llm_system_rules_include_generated_norms():
    from app.services.llm.json_schema import build_llm_system_rules

    rules = build_llm_system_rules()
    assert "автогенерация из gauge_norms" in rules
    assert "1543" in rules
