"""ASR: normalize_asrText — пусть, коли, стр.п."""

from app.services.asr_fixes import fix_asr_transcript, normalize_asr_text


def test_pust_to_put_globally():
    text = "острие остряка пусть 15 ширина колеи 1544"
    assert normalize_asr_text(text).lower() == fix_asr_transcript(text).lower()
    assert "путь 15" in normalize_asr_text(text).lower()
    assert "пусть" not in normalize_asr_text(text).lower()


def test_pust_before_gauge():
    text = "пусть 15 ширина колеи 1544"
    assert normalize_asr_text(text).lower().startswith("путь 15")


def test_koli_to_kolei():
    text = "путь 15 ширина коли 1544"
    assert "ширина колеи" in normalize_asr_text(text).lower()
    assert " коли " not in normalize_asr_text(text).lower()


def test_strp_to_switch_phrase():
    assert normalize_asr_text("стр.п. 10").lower().startswith("стрелочный перевод")
    assert "стрелочный перевод 10" in normalize_asr_text("стр п 10").lower()
    assert "стр.п" not in normalize_asr_text("стр.п. 10").lower()


def test_collapses_whitespace():
    assert normalize_asr_text("  пусть   15   коли  ") == "путь 15 колеи"


def test_ostrii_to_ostrie():
    assert "острие остряка" in normalize_asr_text("в острии остряка").lower()
    assert "острии" not in normalize_asr_text("в острии остряка").lower()
