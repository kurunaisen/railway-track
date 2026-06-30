"""Доменный словарь для фильтрации ложных unknown_terms."""

from app.services.domain_terms import is_known_domain_word
from app.services.parser import detect_unknown_terms


def test_railway_inflections_not_unknown():
    text = (
        "Перегон лапландия пулозеро путь 2 главный километр 1353 пикет 2 "
        "неисправность уширение рельсовой колеи 1543 мм ограничение скорости 60."
    )
    terms = {t["term"] for t in detect_unknown_terms(text)}
    for word in ("главный", "уширение", "рельсовой", "колеи", "скорости"):
        assert word not in terms, f"{word} не должно быть вне словаря"


def test_is_known_domain_word_stems():
    assert is_known_domain_word("колеи")
    assert is_known_domain_word("скорости")
    assert is_known_domain_word("рельсовой")
    assert is_known_domain_word("уширение")
    assert is_known_domain_word("главный")
    assert not is_known_domain_word("абракадабра")
