"""
FR 15.2 — strict JSON schema для LLM (текст → rows[] → ParsedRecord).
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.locations import is_peregon_haul
from app.services.parser import ParsedRecord, _extract_km, _extract_piket, _extract_value_unit, _normalize_text
from app.services.peregons import normalize_peregon
from app.services.peregons import peregon_names_for_prompt
from app.services.speed_limit import apply_speed_limit_fields, strip_speed_limit_phrases
from app.services.stations import normalize_station_name
from app.services.stations import station_names_for_prompt
from app.services.norms_for_llm import build_norms_summary_for_llm
from app.services.switch_terminology import build_switch_glossary_for_llm

logger = logging.getLogger(__name__)

STRUCTURED_JSON_EXAMPLE = {
    "rows": [
        {
            "location": "Мурманск",
            "assetKind": "switch",
            "assetNumber": "10",
            "reference": None,
            "defect": "износ рамного рельса 7 мм",
            "speedLimit": None,
            "note": "в острии остряка",
            "sourceText": (
                "стрелочный перевод номер 10 износ рамного рельса 7 мм острие остряка"
            ),
        },
        {
            "location": "Мурманск",
            "assetKind": "track",
            "assetNumber": "15",
            "reference": None,
            "defect": "ширина колеи 1544 мм",
            "speedLimit": None,
            "note": None,
            "sourceText": "путь 15 ширина колеи 1544 мм",
        },
    ]
}

_LLM_CORE_RULES = """Ты — модуль структурирования дефектов железнодорожного пути из ASR-текста.

Правила:
1. Одна строка таблицы = одна выявленная неисправность = один элемент rows[].
2. Новый объект начинается только при явном указании:
   - «путь <номер>»
   - «стрелочный перевод <номер>» / «стр. перевод <номер>» / «номер <номер>» после слов «стрелочный перевод»
3. Если встретился новый объект «путь N», предыдущий объект закрывается. assetKind=track, assetNumber=N; не переноси стрелочный перевод с предыдущей строки (assetKind=null на строке пути, если только путь).
4. Если встретился новый объект «стрелочный перевод N», предыдущий объект закрывается. assetKind=switch, assetNumber=N; номер пути не переносится, если не назван в той же фразе.
5. Фразы вроде «в острие остряка», «на острие остряка», «по прямому/боковому направлению», «на крестовине», «на усовике» — в note, не в defect.
6. Не придумывай speedLimit. Заполняй только если скорость явно названа в тексте. V огр. по нормам рассчитывает бэкенд.
7. Не придумывай reference, note, assetNumber, location — только из текста.
8. Если значение отсутствует — null (кроме sourceText — всегда фрагмент ASR для строки).
9. Ответ строго по JSON Schema railway_rows (structured output)."""

_LLM_JSON_SCHEMA = """Поля каждого rows[]:
- location: перегон или станция (без слова «станция»), null если не названо
- assetKind: "track" | "switch" | null — тип объекта этой строки
- assetNumber: номер пути или стр.п. строкой, null если не назван
- reference: привязка км/пк/м как в тексте, null если не названа
- defect: выявленная неисправность одной фразой, null только для чистого speedLimit
- speedLimit: число км/ч только если явно в тексте, иначе null
- note: примечание (место промера, сторона нити), null если нет
- sourceText: дословный фрагмент ASR для этой строки (обязательно)"""

_LLM_DOMAIN_RULES = """ASR и домен:
- Порядок rows[] строго как в расшифровке
- Известные перегоны (location): """ + peregon_names_for_prompt() + """
- Известные станции (location): """ + station_names_for_prompt() + """
- «станция Мурманск» → location «Мурманск»; «Блокпост 1381 км» — как в тексте
- reference: км привязки дефекта; км в названии перегона/блок-поста — не reference
- ASR «пусть 15» → путь 15, assetKind=track, assetNumber=«15»
- ASR «ширина коли» → «ширина колеи» в defect
- Явная скорость: отдельная строка rows[] с defect=null, speedLimit=N, sourceText=фраза про скорость"""

_LLM_SYSTEM_RULES_BASE = (
    _LLM_CORE_RULES + "\n\n" + _LLM_JSON_SCHEMA + "\n\n" + _LLM_DOMAIN_RULES
)


def build_llm_system_rules() -> str:
    return (
        _LLM_SYSTEM_RULES_BASE
        + "\n"
        + build_norms_summary_for_llm()
        + "\n\n"
        + build_switch_glossary_for_llm()
    )


LLM_SYSTEM_RULES = build_llm_system_rules()

_ROW_REQUIRED = {
    "location",
    "assetKind",
    "assetNumber",
    "reference",
    "defect",
    "speedLimit",
    "note",
    "sourceText",
}


def _location_fields(location: str | None) -> tuple[str | None, str | None]:
    if not location or not str(location).strip():
        return None, None
    text = str(location).strip()
    if is_peregon_haul(text):
        return normalize_peregon(text), None
    return None, normalize_station_name(text) or text


def _reference_fields(reference: str | None) -> tuple[str | None, str | None]:
    if not reference or not str(reference).strip():
        return None, None
    norm = _normalize_text(str(reference))
    return _extract_km(norm), _extract_piket(norm)


def validate_structured_payload(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise ValueError('LLM JSON must contain "rows" array')
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"rows[{i}] must be object")
        missing = _ROW_REQUIRED - row.keys()
        if missing:
            raise ValueError(f"rows[{i}] missing fields: {sorted(missing)}")
        if not isinstance(row.get("sourceText"), str):
            raise ValueError(f"rows[{i}].sourceText must be string")
        kind = row.get("assetKind")
        if kind is not None and kind not in ("track", "switch"):
            raise ValueError(f"rows[{i}].assetKind must be track, switch or null")
    return data


def parse_llm_json(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(content)
    return validate_structured_payload(data)


def _row_position_type(row: dict) -> str:
    if row.get("speedLimit") is not None and not (row.get("defect") or "").strip():
        return "speed_limit"
    if row.get("defect"):
        return "defect"
    return "parameter"


def structured_to_parsed_rows(data: dict) -> list[ParsedRecord]:
    rows: list[ParsedRecord] = []
    for index, row in enumerate(data.get("rows", [])):
        peregon, uchastok = _location_fields(row.get("location"))
        km, piket = _reference_fields(row.get("reference"))

        put: str | None = None
        switch: str | None = None
        kind = row.get("assetKind")
        number = row.get("assetNumber")
        if number is not None:
            num = str(number).strip()
            if kind == "track":
                put = num
            elif kind == "switch":
                switch = num

        defect_raw = (row.get("defect") or "").strip() or None
        speed = row.get("speedLimit")
        ptype = _row_position_type(row)

        defect = None
        parameter = None
        value: str | None = None
        unit: str | None = None
        speed_limit: str | None = None

        if ptype == "speed_limit":
            speed_limit = str(int(speed)) if speed is not None else None
            value = speed_limit
            unit = "км/ч"
        elif defect_raw:
            cleaned = strip_speed_limit_phrases(defect_raw).strip() or defect_raw
            defect = cleaned
            val, u = _extract_value_unit(_normalize_text(cleaned))
            if val:
                value = val
                unit = u or "мм"
            if speed is not None:
                speed_limit = str(int(speed))

        rows.append(
            ParsedRecord(
                peregon=peregon,
                uchastok=uchastok,
                put=put,
                switch=switch,
                km=km,
                piket=piket,
                comment=(row.get("note") or "").strip() or None,
                logical_record_index=index,
                logical_block_index=index,
                position_index=0,
                position_type=ptype,
                parameter=parameter,
                defect=defect,
                value=value,
                unit=unit,
                speed_limit=speed_limit,
                raw_text=row.get("sourceText") or defect_raw or "",
            )
        )
    for row in rows:
        apply_speed_limit_fields(row)
    return rows


def count_structured_records(data: dict) -> tuple[int, int]:
    rows = data.get("rows", [])
    n = len(rows)
    return n, n
