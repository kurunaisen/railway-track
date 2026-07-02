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


def test_kola_murmansk_misheard_as_before_race():
    text = "Перед гонкой Мурманск 2 путь просадка 12 мм"
    fixed = normalize_asr_text(text)
    assert "перегон Кола — Мурманск" in fixed
    assert "перед гонкой" not in fixed.lower()


def test_lizat_to_lezhat():
    assert "лежат" in normalize_asr_text("Лизат железобетонные шпалы").lower()
    assert "лизат" not in normalize_asr_text("Лизат железобетонные шпалы").lower()


def test_pike_to_piket():
    fixed = normalize_asr_text("пике 8").lower()
    assert "пикет 8" in fixed
    assert " пике " not in f" {fixed} "


def test_nikity_shomgu_to_magnetity_shonguy():
    fixed = normalize_asr_text("Перегон от никиты шомгу 1418 километр")
    assert "Магнетиты — Шонгуй" in fixed
    assert "никиты" not in fixed.lower()
    assert "шомгу" not in fixed.lower()
