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


def test_kola_switch_terms_not_unknown():
    text = (
        "Станция кола 5 путь стрелочный перевод 15 износ сердечника крестовины 8 мм "
        "6 путь стрелочный перевод 18 ширина колеи в хвосте крестовины 1524"
    )
    terms = {t["term"] for t in detect_unknown_terms(text)}
    for word in ("крестовины", "сердечника", "хвосте"):
        assert word not in terms, f"{word} не должно попадать в unknown_terms"


def test_switch_glossary_terms_known():
    for word in (
        "крестовина",
        "крестовины",
        "сердечник",
        "сердечника",
        "хвосте",
        "усовик",
        "остряк",
        "контррельс",
    ):
        assert is_known_domain_word(word), word


def test_binding_meter_not_unknown():
    text = "1418 километр пикет 4 метр 22 отсутствует стыковой болт"
    terms = {t["term"] for t in detect_unknown_terms(text)}
    for word in ("метр", "метра", "метре", "метров"):
        assert is_known_domain_word(word)
    assert "метр" not in terms


def test_is_known_domain_word_stems():
    assert is_known_domain_word("колеи")
    assert is_known_domain_word("скорости")
    assert is_known_domain_word("рельсовой")
    assert is_known_domain_word("уширение")
    assert is_known_domain_word("главный")
    assert not is_known_domain_word("абракадабра")
