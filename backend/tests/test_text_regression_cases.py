from app.services.asr_fixes import normalize_asr_text
from app.services.parser import detect_unknown_terms
from app.services.transcript_quality import check_transcript_text


REGRESSION_TEXTS = [
    "Перед гонкой Мурманск 1441 километр Лизат 3 железобетонные шпалы",
    "ранжирный парк путь 8р разбросанность материалов ВСП",
    "3 железобетонные шпалы разбросанность материалов МВСП",
]


def test_regression_texts_have_known_safe_fixes_and_terms():
    combined = " ".join(REGRESSION_TEXTS)
    fixed = normalize_asr_text(combined)
    unknown = {item["term"] for item in detect_unknown_terms(fixed)}
    check = check_transcript_text(combined)

    assert "перегон Кола — Мурманск" in fixed
    assert "лежат" in fixed
    assert "всп" not in unknown
    assert "мвсп" not in unknown
    assert len(check["issues"]) >= 2
