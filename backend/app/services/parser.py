from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.services.domain_terms import (
    DEFECT_KEYWORDS,
    KNOWN_TERMS,
    OBJECT_KEYWORDS,
    PARAMETER_KEYWORDS,
)
from app.services.locations import extract_single_location, is_peregon_haul


@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    confidence: float | None = None


@dataclass
class ParsedRecord:
    record_date: str | None = None
    uchastok: str | None = None
    peregon: str | None = None
    put: str | None = None
    km: str | None = None
    piket: str | None = None
    obekt: str | None = None
    parameter: str | None = None
    value: str | None = None
    unit: str | None = None
    defect: str | None = None
    comment: str | None = None
    speed_limit: str | None = None
    raw_text: str = ""
    segment_start: float | None = None
    segment_end: float | None = None
    disputed_fields: list[str] = field(default_factory=list)
    logical_record_index: int | None = None
    logical_block_index: int | None = None  # alias для БД / обратная совместимость
    position_index: int | None = None
    position_type: str | None = None  # parameter | defect | speed_limit


@dataclass
class ParseResult:
    records: list[ParsedRecord]
    unknown_terms: list[dict]
    errors: list[dict]


UNIT_PATTERNS = [
    (r"мм\b", "мм"),
    (r"миллиметр(?:ов|а)?", "мм"),
    (r"см\b", "см"),
    (r"сантиметр(?:ов|а)?", "см"),
    (r"км/ч\b", "км/ч"),
    (r"километр(?:ов)?\s*в\s*час", "км/ч"),
    (r"град(?:ус(?:ов|а)?)?", "°"),
    (r"‰|промилле|промилл", "‰"),
    (r"\bм\b", "м"),
]

SEGMENT_SPLIT_RE = re.compile(
    r"(?="
    r"\b(?:далее|следующ(?:ий|ая|ее)\s+(?:запись|перегон)?|следующая\s+запись|следующий\s+перегон)\b"
    r"|\b(?:затем|потом|также)\b"
    r"|\bперегон\b"
    r"|\bнеисправност(?:ь|и)\b"
    r"|\bдефект\b"
    r")",
    re.IGNORECASE,
)

MULTI_DEFECT_SPLIT_RE = re.compile(
    r"(?<=[.;])\s*(?=(?:износ|просадка|трещина|отслоение|выбоина|неисправность|дефект|"
    r"уровень|ширина колеи|перекос|рихтовка|выправка|ограничение\s+скорости|скорость\s+не\s+более))",
    re.IGNORECASE,
)

TRANSITION_WORDS = {
    "далее", "затем", "потом", "следующий", "следующая", "следующее", "также",
    "следующая запись", "следующий перегон",
}


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text.replace("ё", "е")


def _extract_date(text: str) -> str | None:
    patterns = [
        r"дата\s*[:\-]?\s*(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})",
        r"(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_uchastok(text: str) -> str | None:
    m = re.search(
        r"участ(?:ок|ка)\s+(?:№|номер|n)?\s*([а-яa-z0-9\-–—\s]+?)(?:\s*,|\s+перегон|\s+путь|\s+км|\s+километр|$)",
        text,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _extract_peregon(text: str) -> str | None:
    m = re.search(
        r"перегон\s+([\u0410-\u042F\u0430-\u044fA-Za-z]\s*[-–—]\s*[\u0410-\u042F\u0430-\u044fA-Za-z])",
        text,
        re.IGNORECASE,
    )
    if m:
        return re.sub(r"\s+", "", m.group(1).upper().replace("—", "-").replace("–", "-"))

    patterns = [
        r"перегон\s+([^\s,]+(?:\s+[^\s,]+)*?)(?:\s*,|\s+путь|\s+км|\s+километр|\s+пикет|$)",
        r"станци[яи]\s+([^\s,]+)\s*[-–—]\s*([^\s,]+)",
    ]
    for i, pat in enumerate(patterns):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            if i == 1 and m.lastindex == 2:
                return f"{m.group(1).strip()} — {m.group(2).strip()}"
            return m.group(1).strip()
    return None


def _extract_put(text: str) -> str | None:
    m = re.search(r"путь\s*(?:№|номер|n)?\s*(\d+)", text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(
        r"путь\s+(?:№|номер|n)?\s*([а-яa-z\u0430-\u044f]+)",
        text,
        re.IGNORECASE,
    )
    if m:
        from app.services.normalizer import normalize_put

        return normalize_put(m.group(1))
    return None


def _extract_km(text: str) -> str | None:
    for pat in (
        r"(?:километр|км\.?)\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*(?:километр|км\.?)\b",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", ".")
    return None


def _extract_piket(text: str) -> str | None:
    m = re.search(
        r"пикет\s*(?:№|номер|n)?\s*(\d+(?:[.,]\d+)?)\s*(?:плюс|\+)\s*(\d+(?:[.,]\d+)?)",
        text,
        re.IGNORECASE,
    )
    if m:
        return f"{m.group(1).replace(',', '.')}+{m.group(2).replace(',', '.')}"

    for pat in (
        r"пикет\s*(?:№|номер|n)?\s*(\d+(?:[.,]\d+)?)",
        r"(\d+(?:[.,]\d+)?)\s*пикет",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).replace(",", ".")
    return None


def _extract_obekt(text: str) -> str | None:
    m = re.search(
        r"объект\s*[:\-]?\s*([а-яa-z\s]+?)(?:\s*,|\s+параметр|\s+дефект|\s+износ|$)",
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    for keyword in OBJECT_KEYWORDS:
        if keyword in text:
            return keyword
    return None


def _extract_speed_limit(text: str) -> str | None:
    for pat in (
        r"ограничени[ея]\s+скорост(?:и|ь)\s*(?:до\s*)?(\d+)",
        r"скорост(?:ь|и)\s*(?:не\s*более|до|ограничена)\s*(\d+)",
        r"(\d+)\s*(?:км/ч|километр(?:ов)?\s*в\s*час)",
    ):
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _extract_value_unit(after: str) -> tuple[str | None, str | None]:
    num_match = re.search(r"(\d+(?:[.,]\d+)?)", after)
    if not num_match:
        return None, None
    value = num_match.group(1).replace(",", ".")
    rest = after[num_match.end() :].strip()
    unit = None
    for pat, unit_name in UNIT_PATTERNS:
        if re.search(pat, rest, re.IGNORECASE) or re.search(pat, after, re.IGNORECASE):
            unit = unit_name
            break
    return value, unit


def _find_all_mentions(text: str, keywords: list[str]) -> list[tuple[str, int]]:
    found: list[tuple[str, int]] = []
    for kw in sorted(keywords, key=len, reverse=True):
        for m in re.finditer(re.escape(kw), text):
            found.append((kw, m.start()))
    found.sort(key=lambda x: x[1])
    seen_pos: set[int] = set()
    unique: list[tuple[str, int]] = []
    for kw, pos in found:
        if pos not in seen_pos:
            seen_pos.add(pos)
            unique.append((kw, pos))
    return unique


def _extract_parameter(text: str) -> str | None:
    for kw in PARAMETER_KEYWORDS:
        if kw in text:
            return kw
    m = re.search(r"параметр\s*[:\-]?\s*([а-яa-z\s]+?)(?:\s+\d|\s*,|$)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_defect(text: str) -> str | None:
    for kw in DEFECT_KEYWORDS:
        if kw in text:
            return kw
    m = re.search(r"(?:неисправность|дефект)\s*[:\-]?\s*([а-яa-z\s]+?)(?:\s+\d|\s*,|$)", text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def _extract_comment(text: str, record: ParsedRecord) -> str | None:
    m = re.search(r"(?:комментар(?:ий|ии)|примечани[ея])\s*[:\-]?\s*(.+)$", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _flag_disputed(record: ParsedRecord) -> None:
    """Помечает поля с низкой уверенностью как спорные."""
    if record.raw_text and not record.km and not record.piket:
        if re.search(r"\d", record.raw_text):
            record.disputed_fields.append("km")
    if record.parameter and not record.value:
        record.disputed_fields.append("value")
    if record.defect and not record.value and not record.comment:
        record.disputed_fields.append("defect")
    if record.peregon and len(record.peregon) < 3:
        record.disputed_fields.append("peregon")


def parse_chunk(text: str, start: float | None = None, end: float | None = None) -> ParsedRecord:
    normalized = _normalize_text(text)
    record = ParsedRecord(raw_text=text.strip(), segment_start=start, segment_end=end)
    record.record_date = _extract_date(normalized)
    record.uchastok = _extract_uchastok(normalized)
    record.peregon = _extract_peregon(normalized)

    single_loc = extract_single_location(normalized)
    if record.peregon and is_peregon_haul(record.peregon):
        pass
    elif single_loc:
        record.uchastok = single_loc
        if record.peregon and not is_peregon_haul(record.peregon):
            record.peregon = None
    elif record.peregon and not is_peregon_haul(record.peregon):
        record.uchastok = extract_single_location(record.peregon) or record.uchastok
        record.peregon = None
    record.put = _extract_put(normalized)
    record.km = _extract_km(normalized)
    record.piket = _extract_piket(normalized)
    record.obekt = _extract_obekt(normalized)
    record.speed_limit = _extract_speed_limit(normalized)
    record.parameter = _extract_parameter(normalized)
    record.defect = _extract_defect(normalized)

    keyword = record.parameter or record.defect
    if keyword and keyword in normalized:
        after = normalized.split(keyword, 1)[-1].strip(" ,:-")
        record.value, record.unit = _extract_value_unit(after)
    elif record.parameter is None and record.defect is None:
        record.parameter, record.value, record.unit = _extract_legacy_param(normalized)

    record.comment = _extract_comment(normalized, record)
    _flag_disputed(record)
    return record


def _extract_legacy_param(text: str) -> tuple[str | None, str | None, str | None]:
    all_kw = PARAMETER_KEYWORDS + DEFECT_KEYWORDS
    for keyword in all_kw:
        if keyword in text:
            after = text.split(keyword, 1)[-1].strip(" ,:-")
            value, unit = _extract_value_unit(after)
            return keyword, value, unit
    return None, None, None


def _split_multi_defects(text: str) -> list[str]:
    """Разбивает фрагмент с несколькими неисправностями на отдельные подфрагменты."""
    parts = MULTI_DEFECT_SPLIT_RE.split(text)
    parts = [p.strip(" ,.;") for p in parts if p.strip(" ,.;")]
    if len(parts) <= 1:
        mentions = _find_all_mentions(_normalize_text(text), DEFECT_KEYWORDS + PARAMETER_KEYWORDS)
        if len(mentions) <= 1:
            return [text]
        sub: list[str] = []
        for i, (kw, pos) in enumerate(mentions):
            end = mentions[i + 1][1] if i + 1 < len(mentions) else len(text)
            prefix = text[:pos].strip(" ,;.")
            fragment = text[pos:end].strip(" ,;.")
            if prefix and i == 0:
                sub.append(f"{prefix} {fragment}".strip())
            else:
                sub.append(fragment)
        return [s for s in sub if s]
    return parts


def _merge_transition_chunks(parts: list[str]) -> list[str]:
    if not parts:
        return parts
    merged: list[str] = []
    i = 0
    while i < len(parts):
        part = parts[i]
        normalized = part.strip().lower().rstrip(".")
        if normalized in TRANSITION_WORDS and i + 1 < len(parts):
            merged.append(f"{part} {parts[i + 1]}".strip())
            i += 2
        elif normalized in TRANSITION_WORDS:
            i += 1
        else:
            merged.append(part)
            i += 1
    return merged


def _split_on_context_change(
    chunks: list[tuple[str, float | None, float | None]],
) -> list[tuple[str, float | None, float | None]]:
    """Доп. разбиение при смене км/пикета/пути внутри длинного фрагмента."""
    result: list[tuple[str, float | None, float | None]] = []
    context = ParsedRecord()

    for text, start, end in chunks:
        normalized = _normalize_text(text)
        sub_parts = [normalized]
        if _extract_km(normalized) and context.km and _extract_km(normalized) != context.km:
            sub_parts = SEGMENT_SPLIT_RE.split(normalized)
            sub_parts = [p.strip(" ,.;") for p in sub_parts if p.strip(" ,.;")]
        if len(sub_parts) <= 1:
            result.append((text, start, end))
            rec = parse_chunk(text, start, end)
            for f in ("peregon", "put", "km", "piket"):
                if getattr(rec, f):
                    setattr(context, f, getattr(rec, f))
        else:
            for sp in sub_parts:
                result.append((sp, start, end))
    return result if result else chunks


def _merge_incomplete_chunks(
    chunks: list[tuple[str, float | None, float | None]],
) -> list[tuple[str, float | None, float | None]]:
    """Склеивает заголовочные фрагменты (дата/участок) со следующей записью."""
    if len(chunks) <= 1:
        return chunks

    merged: list[tuple[str, float | None, float | None]] = []
    i = 0
    while i < len(chunks):
        text, start, end = chunks[i]
        normalized = _normalize_text(text)
        has_location = bool(_extract_km(normalized) or _extract_piket(normalized))
        has_issue = bool(_extract_defect(normalized) or _extract_parameter(normalized))
        is_header_only = bool(_extract_date(normalized) or _extract_uchastok(normalized)) and not (
            has_location or has_issue or _extract_peregon(normalized)
        )

        if is_header_only and i + 1 < len(chunks):
            ntext, nstart, nend = chunks[i + 1]
            merged.append((f"{text} {ntext}".strip(), start or nstart, nend or end))
            i += 2
        else:
            merged.append((text, start, end))
            i += 1
    return merged


def split_into_logical_chunks(
    full_text: str, segments: list[TranscriptSegment] | None = None
) -> list[tuple[str, float | None, float | None]]:
    if segments:
        result = _split_by_segments(segments)
        return _merge_incomplete_chunks(result)

    text = _normalize_text(full_text)
    if not text:
        return []

    parts = SEGMENT_SPLIT_RE.split(text)
    parts = [p.strip(" ,.;") for p in parts if p.strip(" ,.;")]
    parts = _merge_transition_chunks(parts)
    if not parts:
        return [(full_text.strip(), None, None)]

    expanded: list[tuple[str, float | None, float | None]] = []
    for p in parts:
        expanded.append((p, None, None))
    return _merge_incomplete_chunks(expanded)


def _split_by_segments(segments: list[TranscriptSegment]) -> list[tuple[str, float | None, float | None]]:
    if not segments:
        return []

    chunks: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = []

    for seg in segments:
        text = _normalize_text(seg.text)
        is_new = bool(
            re.search(
                r"\b(?:перегон|далее|следующ(?:ий|ая|ее)|"
                r"следующая\s+запись|следующий\s+перегон|"
                r"затем|неисправност|дефект)\b",
                text,
            )
        )
        if is_new and current:
            chunks.append(current)
            current = [seg]
        else:
            current.append(seg)

    if current:
        chunks.append(current)

    if len(chunks) == 1 and len(segments) > 3:
        chunks = _subdivide_long_chunk(segments)

    result: list[tuple[str, float | None, float | None]] = []
    for group in chunks:
        text = " ".join(s.text.strip() for s in group).strip()
        if text:
            start, end = group[0].start, group[-1].end
            result.append((text, start, end))
    return result


def _subdivide_long_chunk(segments: list[TranscriptSegment]) -> list[list[TranscriptSegment]]:
    groups: list[list[TranscriptSegment]] = []
    current: list[TranscriptSegment] = [segments[0]]

    for prev, seg in zip(segments, segments[1:], strict=False):
        gap = seg.start - prev.end
        text = _normalize_text(seg.text)
        force = bool(re.search(r"\b(?:перегон|далее|следующ|затем|дефект)\b", text))
        if gap > 1.5 or force:
            groups.append(current)
            current = [seg]
        else:
            current.append(seg)
    if current:
        groups.append(current)
    return groups if groups else [segments]


def detect_unknown_terms(full_text: str) -> list[dict]:
    """Находит слова, не входящие в доменный словарь."""
    words = re.findall(r"[а-яa-z]{4,}", _normalize_text(full_text))
    unknown: dict[str, int] = {}
    for w in words:
        if w in KNOWN_TERMS:
            continue
        if w.isdigit():
            continue
        unknown[w] = unknown.get(w, 0) + 1
    return [{"term": k, "count": v} for k, v in sorted(unknown.items(), key=lambda x: -x[1])[:50]]


def parse_transcript(
    full_text: str, segments: list[TranscriptSegment] | None = None
) -> ParseResult:
    from app.services.record_expander import expand_blocks_to_rows
    from app.services.segmentation import segment_logical_blocks

    blocks = segment_logical_blocks(full_text, segments)
    records = expand_blocks_to_rows(blocks)
    errors: list[dict] = []

    for idx, record in enumerate(records):
        if not any([record.km, record.piket, record.parameter, record.defect, record.peregon]):
            errors.append({
                "row": idx,
                "text": (record.raw_text or "")[:200],
                "error": "Не удалось извлечь ключевые поля",
            })

    return ParseResult(
        records=records,
        unknown_terms=detect_unknown_terms(full_text),
        errors=errors,
    )
