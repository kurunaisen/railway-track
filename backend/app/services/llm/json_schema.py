"""
FR 15.2 — строгий JSON-схема для LLM (текст → структура).

Не Excel, не произвольный текст — только вложенный records[] / items[].
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.services.parser import ParsedRecord
from app.services.speed_limit import apply_speed_limit_fields
from app.services.peregons import peregon_names_for_prompt
from app.services.stations import station_names_for_prompt
from app.services.norms_for_llm import build_norms_summary_for_llm
from app.services.switch_terminology import build_switch_glossary_for_llm

logger = logging.getLogger(__name__)

# Пример для промпта (FR 14.2)
STRUCTURED_JSON_EXAMPLE = {
    "records": [
        {
            "sequence_number": 1,
            "start_sec": None,
            "end_sec": None,
            "haul_name": "А-Б",
            "track_number": "2",
            "switch_number": "15",
            "km_value": "35",
            "picket_value": "5+20",
            "items": [
                {
                    "order_in_record": 1,
                    "parameter_name": "Перекос",
                    "value_numeric": 4,
                    "unit": "мм",
                    "position_type": "parameter",
                }
            ],
        }
    ]
}

_LLM_CORE_RULES = """Ты — модуль структурирования дефектов железнодорожного пути из ASR-текста.

Правила:
1. Одна строка таблицы = одна выявленная неисправность. Каждая неисправность — отдельный records[] с ровно одним item (order_in_record=1).
2. Новый объект начинается только при явном указании:
   - «путь <номер>»
   - «стрелочный перевод <номер>» / «стр. перевод <номер>» / «номер <номер>» после слов «стрелочный перевод»
3. Если встретился новый объект «путь N», предыдущий объект закрывается. Номер стрелочного перевода не переносится в строку пути (switch_number=null).
4. Если встретился новый объект «стрелочный перевод N», предыдущий объект закрывается. Номер пути не переносится в строку стрелочного перевода (track_number=null), если путь не назван в той же фразе.
5. Фразы вроде:
   - «в острие остряка» / «на острие остряка»
   - «по прямому направлению» / «по боковому направлению»
   - «на крестовине» / «на усовике»
   — уточнение места измерения. Пиши в comment записи, не в defect_text и не отдельным item.
6. Не придумывай ограничения скорости. Поле speed_limit / item speed_limit — только если скорость явно названа в исходном тексте. V огр. по нормам рассчитывает бэкенд.
7. Не придумывай привязку (km_value, picket_value), comment, track_number, switch_number — только из текста.
8. Если значение отсутствует в тексте — null.
9. Верни только JSON по схеме ниже. Без Excel, Markdown и пояснений."""

_LLM_JSON_SCHEMA = """Формат ответа: {"records": [...]}

Каждый records[] — контекст одной строки таблицы (одна неисправность):
- sequence_number: int, с 1, порядок произнесения
- start_sec, end_sec: float|null — из ASR-сегментов, если есть
- haul_name, track_number, switch_number, km_value, picket_value, section_name, date_value, comment, object_name
- items[] — ровно один элемент на неисправность

Единственный item:
- order_in_record: 1
- parameter_name: string|null
- value_numeric: number|null
- value_text: string|null
- unit: string|null
- position_type: "parameter" | "defect" | "speed_limit"
- defect_text: string|null (для defect)

Поля track_number / switch_number:
- track_number — номер пути («5 путь» → «5»)
- switch_number — номер стрелочного перевода («стрелочный перевод 15» → «15»)
- В одной фразе «N путь стрелочный перевод M» — оба поля; иначе только то, что явно названо в фрагменте этой строки"""

_LLM_DOMAIN_RULES = """ASR и домен:
- Несколько перегонов («Далее…») → несколько records с разными sequence_number
- Порядок records строго как в расшифровке
- Известные перегоны (haul_name): """ + peregon_names_for_prompt() + """
- Известные станции и блок-посты (section_name, без слова «станция» в значении): """ + station_names_for_prompt() + """
- О.П. / остановочный пункт = Блокпост с километром («О.П. 1425 км» → «Блокпост 1425 км»)
- section_name: «станция Мурманск» → «Мурманск»; блок-пост только с км: «Блокпост 1381 км»
- km_value: километр привязки дефекта (например 1385). Км в названии блок-поста/перегона — НЕ km_value
- km_value: «1000 385 км» с паузой → «1385 км», не два числа
- object_name / comment про сторону нити — ТОЛЬКО если явно «левая/правая сторона рельсовой нити»
- «на левой стороне рельсовой нити отсутствует болт» → comment про нить, defect «отсутствует стыковой болт»
- Смена км, пикета или «на станции …» → новый records[] с обновлённым контекстом
- ASR путает «путь» и «пусть»: «острие остряка пусть 15 ширина колеи» → track_number=«15», не отдельный дефект «острие остряка 15»
- ASR «ширина коли» → ширина колеи; «уширение колеи 1544 мм» на пути 15 — одна неисправность, value_numeric=1544
- Явная скорость в тексте: «ограничение скорости 60», «скорость 60 км/ч» → отдельный records[] с item speed_limit (не смешивать с defect в одном item)"""

_LLM_SYSTEM_RULES_BASE = (
    _LLM_CORE_RULES + "\n\n" + _LLM_JSON_SCHEMA + "\n\n" + _LLM_DOMAIN_RULES
)


def build_llm_system_rules() -> str:
    """System prompt с актуальными нормами из gauge_norms / track_norms."""
    return (
        _LLM_SYSTEM_RULES_BASE
        + "\n"
        + build_norms_summary_for_llm()
        + "\n\n"
        + build_switch_glossary_for_llm()
    )


LLM_SYSTEM_RULES = build_llm_system_rules()


def validate_structured_payload(data: Any) -> dict:
    """Проверяет минимальную структуру JSON от LLM."""
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError('LLM JSON must contain "records" array')
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"records[{i}] must be object")
        if "sequence_number" not in rec:
            raise ValueError(f"records[{i}] missing sequence_number")
        items = rec.get("items")
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError(f"records[{i}] must have non-empty items[]")
        for j, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError(f"records[{i}].items[{j}] must be object")
            if "order_in_record" not in item:
                raise ValueError(f"records[{i}].items[{j}] missing order_in_record")
    return data


def parse_llm_json(content: str) -> dict:
    """Парсит и валидирует ответ LLM."""
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(content)
    return validate_structured_payload(data)


def structured_to_parsed_rows(data: dict) -> list[ParsedRecord]:
    """Конвертирует строгий JSON LLM → flat ParsedRecord для конвейера."""
    rows: list[ParsedRecord] = []
    for rec in data.get("records", []):
        seq = int(rec.get("sequence_number", 1)) - 1
        start = rec.get("start_sec")
        end = rec.get("end_sec")
        ctx_fields = {
            "peregon": rec.get("haul_name"),
            "put": str(rec["track_number"]) if rec.get("track_number") is not None else None,
            "switch": str(rec["switch_number"]) if rec.get("switch_number") is not None else None,
            "km": str(rec["km_value"]) if rec.get("km_value") is not None else None,
            "piket": str(rec["picket_value"]) if rec.get("picket_value") is not None else None,
            "record_date": rec.get("date_value"),
            "uchastok": rec.get("section_name"),
            "obekt": rec.get("object_name"),
            "comment": rec.get("comment"),
            "segment_start": float(start) if start is not None else None,
            "segment_end": float(end) if end is not None else None,
        }
        for item in rec.get("items", []):
            order = int(item.get("order_in_record", 1)) - 1
            ptype = item.get("position_type") or _infer_position_type(item)
            pname = item.get("parameter_name") or item.get("canonical_parameter") or ""
            val_num = item.get("value_numeric")
            val_txt = item.get("value_text")
            value = str(val_num) if val_num is not None else (str(val_txt) if val_txt is not None else None)
            unit = item.get("unit")
            speed = item.get("speed_limit")

            parameter = None
            defect = None
            if ptype == "speed_limit":
                speed = speed or value
                value = speed
                unit = unit or "км/ч"
                pname = pname or "Ограничение скорости"
            elif ptype == "defect":
                defect = item.get("defect_text") or pname.lower() or None
            else:
                parameter = (item.get("canonical_parameter") or pname or "").lower() or None

            rows.append(
                ParsedRecord(
                    **ctx_fields,
                    logical_record_index=seq,
                    logical_block_index=seq,
                    position_index=order,
                    position_type=ptype,
                    parameter=parameter,
                    defect=defect,
                    value=value,
                    unit=unit,
                    speed_limit=str(speed) if ptype == "speed_limit" and speed else None,
                    raw_text=item.get("raw_text")
                    or rec.get("source_text")
                    or item.get("defect_text")
                    or "",
                )
            )
    for row in rows:
        apply_speed_limit_fields(row)
    return rows


def _infer_position_type(item: dict) -> str:
    pname = (item.get("parameter_name") or item.get("canonical_parameter") or "").lower()
    if item.get("speed_limit") or "скорост" in pname:
        return "speed_limit"
    if pname.startswith("огранич") and re.search(r"\d", pname):
        return "speed_limit"
    if item.get("defect_text"):
        return "defect"
    return "parameter"


def count_structured_records(data: dict) -> tuple[int, int]:
    """(logical_records, positions)"""
    records = data.get("records", [])
    positions = sum(len(r.get("items", [])) for r in records)
    return len(records), positions
