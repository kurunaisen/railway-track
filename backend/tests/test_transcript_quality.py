from app.services import user_asr_corrections as corr
from app.services import user_domain_terms as terms
from app.services.transcript_quality import check_transcript_text
from app.services.parser import detect_unknown_terms


def test_transcript_quality_reports_safe_fixes(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")
    result = check_transcript_text("Перед гонкой Мурманск Лизат шпалы пике 8 никиты шомгу")

    titles = {issue["title"] for issue in result["issues"]}
    assert "Похоже на перегон Кола - Мурманск" in titles
    assert "Похоже на слово «лежат»" in titles
    assert "Похоже на слово «пикет»" in titles
    assert "Похоже на перегон Магнетиты - Шонгуй" in titles
    assert "перегон Кола — Мурманск" in result["normalized_text"]
    assert "лежат" in result["normalized_text"]
    assert "пикет 8" in result["normalized_text"]
    assert "Магнетиты — Шонгуй" in result["normalized_text"]


def test_transcript_quality_includes_user_dictionary_rule(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")
    corr.add_user_correction("Кла", "Кола", field="uchastok")

    result = check_transcript_text("станция Кла")

    assert any(issue["source"] == "user_dictionary" for issue in result["issues"])


def test_user_domain_terms_remove_unknown_term(tmp_path, monkeypatch):
    monkeypatch.setattr(terms, "TERMS_FILE", tmp_path / "domain_terms.json")

    assert "новотерм" in {item["term"] for item in detect_unknown_terms("новотерм")}
    terms.add_user_domain_term("новотерм")
    assert "новотерм" not in {item["term"] for item in detect_unknown_terms("новотерм")}


def test_transcript_quality_flags_extra_gauge_number():
    result = check_transcript_text("уширение колеи 1400 1543 мм")
    issue = next(
        item for item in result["issues"]
        if item["title"] == "Подозрительное число перед измерением колеи"
    )

    assert issue["safeFix"]["replacement"] == ""
    assert "1400" in issue["safeFix"]["label"]


def test_transcript_quality_flags_split_km():
    result = check_transcript_text("на 1000 385 км пикет 5")
    issue = next(
        item for item in result["issues"]
        if item["title"] == "Похоже на раздельно распознанный километр"
    )

    assert issue["safeFix"]["replacement"] == "1385 км"
    assert "1385 км" in result["normalized_text"]
