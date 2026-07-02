from app.services import user_asr_corrections as corr
from app.services.asr_fixes import normalize_asr_text


def test_learns_phrase_correction_from_record_update(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")

    learned = corr.learn_corrections_from_update(
        {"peregon": "Перед гонкой-мурманск"},
        {"peregon": "Кола — Мурманск"},
        created_by="operator",
    )

    assert learned >= 1
    assert corr.apply_user_corrections("Перед гонкой Мурманск 2 путь") == (
        "Кола — Мурманск 2 путь"
    )


def test_user_corrections_are_applied_by_asr_normalizer(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")
    corr.add_user_correction("гонкой мурманск", "Кола — Мурманск", field="peregon")

    fixed = normalize_asr_text("перед гонкой мурманск 2 путь")

    assert "Кола — Мурманск" in fixed


def test_does_not_learn_numeric_field_corrections(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")

    learned = corr.learn_corrections_from_update(
        {"value": "1400"},
        {"value": "1543"},
    )

    assert learned == 0
    assert corr.load_user_corrections() == []


def test_accumulates_sources_for_same_target(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")

    assert corr.add_user_correction("Кол", "Кола", field="uchastok")
    assert corr.add_user_correction("Кла", "Кола", field="uchastok")

    rows = corr.load_user_corrections()
    assert len(rows) == 1
    assert rows[0]["target"] == "Кола"
    assert set(rows[0]["sources"]) == {"Кол", "Кла"}
    assert corr.apply_user_corrections("станция Кол 5 путь") == "станция Кола 5 путь"
    assert corr.apply_user_corrections("станция Кла 5 путь") == "станция Кола 5 путь"


def test_short_source_correction_uses_word_boundaries(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")
    corr.add_user_correction("Кол", "Кола", field="uchastok")

    assert corr.apply_user_corrections("около станции Кол") == "около станции Кола"
    assert corr.apply_user_corrections("колея 1543") == "колея 1543"
