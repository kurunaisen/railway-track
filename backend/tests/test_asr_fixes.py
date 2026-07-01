"""ASR: «пусть N» → «путь N» в контексте обхода."""

from app.services.asr_fixes import fix_asr_transcript


def test_pust_after_switch_tip():
    text = "острие остряка пусть 15 ширина колеи 1544"
    assert "путь 15" in fix_asr_transcript(text).lower()
    assert "пусть" not in fix_asr_transcript(text).lower()


def test_pust_before_gauge():
    text = "пусть 15 ширина колеи 1544"
    assert fix_asr_transcript(text).lower().startswith("путь 15")
