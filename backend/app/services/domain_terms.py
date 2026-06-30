"""Железнодорожная терминология для подсказки Whisper и проверки распознавания."""

from __future__ import annotations

from app.services.peregons import CANONICAL_PEREGONS, peregon_names_for_prompt
from app.services.stations import CANONICAL_LOCATIONS, station_names_for_prompt

RAILWAY_INITIAL_PROMPT = (
    "Обход пути. Перегон, станция, блокпост, остановочный пункт, участок, путь, главный, километр, пикет, "
    "рельс, рельсовой, шпала, стык, стрелочный перевод, колея, ширина колеи, уровень, износ, просадка, "
    "трещина, уширение, сужение, отслоение, выбоина, балласт, уклон, кривая, неисправность, дефект, "
    "ограничение скорости, километр в час, миллиметр, пикетаж, объект, "
    "стрелочная гарнитура, бесстыковой путь, температурный зазор. "
    f"Перегоны: {peregon_names_for_prompt()}. "
    f"Станции: {station_names_for_prompt()}."
)

# Объекты инфраструктуры
OBJECT_KEYWORDS = [
    "рельс",
    "шпала",
    "стык",
    "перевод",
    "стрелочный перевод",
    "стрелка",
    "мост",
    "виадук",
    "насыпь",
    "выемка",
    "балласт",
    "платформа",
    "стрелочная гарнитура",
    "объект",
]

# Параметры измерения
PARAMETER_KEYWORDS = [
    "уровень",
    "ширина колеи",
    "колея",
    "уклон",
    "зазор",
    "высота",
    "положение",
    "отклонение",
    "отступление",
    "температурный зазор",
    "перекос",
    "рихтовка",
    "выправка",
]

# Неисправности / дефекты
DEFECT_KEYWORDS = [
    "износ",
    "просадка",
    "трещина",
    "уширение",
    "сужение",
    "отслоение",
    "выбоина",
    "неисправность",
    "дефект",
    "повреждение",
    "отсутствует",
    "отсутствуют",
]

# Базовые термины + топонимы (нижний регистр)
KNOWN_TERMS_BASE: set[str] = {
    "перегон",
    "участок",
    "путь",
    "километр",
    "км",
    "пикет",
    "пикетаж",
    "рельс",
    "шпала",
    "стык",
    "балласт",
    "колея",
    "перевод",
    "стрелочный перевод",
    "стрелка",
    "износ",
    "просадка",
    "трещина",
    "отслоение",
    "выбоина",
    "уровень",
    "уклон",
    "кривая",
    "неисправность",
    "дефект",
    "ограничение",
    "скорость",
    "объект",
    "мост",
    "виадук",
    "насыпь",
    "выемка",
    "ширина колеи",
    "зазор",
    "гарнитура",
    "бесстыковой",
    "миллиметр",
    "мм",
    "сантиметр",
    "промилле",
    "комментарий",
    "примечание",
    "далее",
    "следующий",
    "затем",
    "станция",
    "платформа",
    "стрелочная",
    "температурный",
    "выправка",
    "отступление",
    "отклонение",
    "повреждение",
    "положение",
    "высота",
    "лапландия",
    "пулозеро",
    "тайбола",
    "блокпост",
    "кица",
    "лопарская",
    "магнетиты",
    "шонгуй",
    "выходной",
    "кола",
    "мурманск",
    "комсомольск",
    "промышленная",
    "ваенга",
    "левой",
    "левый",
    "левая",
    "правой",
    "правый",
    "правая",
    "нити",
    "нить",
    "стороне",
    "сторона",
    "стыковой",
    "болт",
    "отсутствует",
}

# Частые падежные формы и производные, которых нет в списках ключевых слов
DOMAIN_INFLECTIONS: set[str] = {
    "главный",
    "главная",
    "главное",
    "главного",
    "главной",
    "главные",
    "главных",
    "уширение",
    "уширения",
    "уширении",
    "сужение",
    "сужения",
    "рельсовой",
    "рельсовая",
    "рельсовое",
    "рельсовых",
    "рельсовую",
    "колеи",
    "колею",
    "колеей",
    "скорости",
    "скоростью",
    "скоростей",
    "ограничения",
    "ограничении",
    "ширина",
    "ширины",
    "неисправности",
    "перекос",
    "рихтовка",
    "бесстыковой",
    "температурный",
    "температурного",
    "зазора",
    "уровня",
    "износа",
    "просадки",
    "трещины",
    "дефекты",
    "объекта",
    "пути",
    "путей",
    "пикета",
    "километра",
    "участка",
    "перегона",
    "станции",
}


def _normalize_token(token: str) -> str:
    return token.lower().replace("ё", "е").strip()


def _tokens_from_phrase(phrase: str) -> list[str]:
    return [_normalize_token(part) for part in phrase.split() if part.strip()]


def _location_tokens() -> set[str]:
    tokens: set[str] = set()
    for name in (*CANONICAL_PEREGONS, *CANONICAL_LOCATIONS):
        normalized = _normalize_token(name.replace("—", " ").replace("-", " "))
        tokens.add(normalized)
        tokens.update(_tokens_from_phrase(normalized))
    return tokens


def _build_known_terms() -> set[str]:
    terms = set(KNOWN_TERMS_BASE)
    terms.update(DOMAIN_INFLECTIONS)
    terms.update(_location_tokens())
    for phrase in (*OBJECT_KEYWORDS, *PARAMETER_KEYWORDS, *DEFECT_KEYWORDS):
        terms.add(_normalize_token(phrase))
        terms.update(_tokens_from_phrase(phrase))
    return terms


def _collect_stems(terms: set[str]) -> frozenset[str]:
    stems: set[str] = set()
    for term in terms:
        for token in _tokens_from_phrase(term) if " " in term else [term]:
            if len(token) < 4:
                continue
            stems.add(token[:4])
            if len(token) >= 5:
                stems.add(token[:5])
            if len(token) >= 6:
                stems.add(token[:-1])
                stems.add(token[:-2])
    return frozenset(stem for stem in stems if len(stem) >= 4)


KNOWN_TERMS: set[str] = _build_known_terms()
KNOWN_STEMS: frozenset[str] = _collect_stems(KNOWN_TERMS)


def is_known_domain_word(word: str) -> bool:
    """Слово из домена: точное совпадение или общая основа (колеи → колея)."""
    normalized = _normalize_token(word)
    if not normalized or normalized.isdigit():
        return True
    if normalized in KNOWN_TERMS:
        return True
    return any(normalized.startswith(stem) for stem in KNOWN_STEMS)
