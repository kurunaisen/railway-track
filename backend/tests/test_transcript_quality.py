from app.services import user_asr_corrections as corr
from app.services import user_domain_terms as terms
from app.services.transcript_quality import check_transcript_text
from app.services.parser import detect_unknown_terms


def test_transcript_quality_reports_safe_fixes(tmp_path, monkeypatch):
    monkeypatch.setattr(corr, "CORRECTIONS_FILE", tmp_path / "asr_corrections.json")
    result = check_transcript_text("Перед гонкой Мурманск Лизат шпалы")

    titles = {issue["title"] for issue in result["issues"]}
    assert "Похоже на перегон Кола - Мурманск" in titles
    assert "Похоже на слово «лежат»" in titles
    assert "перегон Кола — Мурманск" in result["normalized_text"]
    assert "лежат" in result["normalized_text"]


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
