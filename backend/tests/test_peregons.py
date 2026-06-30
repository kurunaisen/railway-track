from app.services.peregons import normalize_peregon


def test_peregon_synonyms():
    assert normalize_peregon("Тайбола - Блокпост") == "Тайбола — Блокпост 1381 км"
    assert normalize_peregon("Магнетиты - Блокпост") == "Магнетиты — Блокпост 1425 км"
    assert normalize_peregon("Комсомольск - Промышленная") == "Комсомольск-Мурманский — Промышленная"
    assert normalize_peregon("Комсомольск - Ваенга") == "Комсомольск-Мурманский — Ваенга"


def test_canonical_peregon():
    assert normalize_peregon("Лапландия — Пулозеро") == "Лапландия — Пулозеро"
    assert normalize_peregon("Блокпост 15 км - Ваенга") == "Блокпост 15 км — Ваенга"
