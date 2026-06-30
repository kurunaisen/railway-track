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

LLM_SYSTEM_RULES = """Роль: текст → структура. НЕ формируй Excel, таблицы Markdown или пояснения.
Верни ТОЛЬКО один JSON-объект формата {"records": [...]}.

Каждый элемент records[] — одна логическая запись (перегон/км/пикет):
- sequence_number: int, с 1, порядок произнесения
- start_sec, end_sec: float|null — из ASR-сегментов
- haul_name, track_number, km_value, picket_value, section_name, date_value, comment, object_name
- items[] — позиции внутри записи (один параметр/дефект/V огр. на item)

Каждый item:
- order_in_record: int, с 1
- parameter_name: string
- value_numeric: number|null
- value_text: string|null
- unit: string|null
- position_type: "parameter" | "defect" | "speed_limit"
- defect_text: string|null (для defect)

Правила:
- Несколько перегонов («Далее…») → несколько records с разными sequence_number
- Один параметр на item (правило 10.3)
- Пустые поля → null
- Порядок строго как в расшифровке
- Известные перегоны (haul_name): """ + peregon_names_for_prompt() + """
- Известные станции и блок-посты (section_name, без слова «станция» в значении): """ + station_names_for_prompt() + """
- О.П. / остановочный пункт = Блокпост с километром (например «О.П. 1425 км» → «Блокпост 1425 км»)
- section_name: «станция Мурманск» → «Мурманск»; блок-пост только с км: «Блокпост 1381 км»
- km_value: километр привязки дефекта (например 1385). Км в названии блок-поста/перегона (1381 у «Блокпост 1381 км») — НЕ km_value
- km_value: если сказали «1000 385 км» с паузой — это «1385 км», не два числа
- object_name: сторона рельсовой нити — в comment (примечание), например «На левой стороне рельсовой нити». Это указатель места, НЕ defect и не отдельный item
- «на левой стороне рельсовой нити отсутствует болт» → comment «На левой стороне рельсовой нити», один item с defect «отсутствует стыковой болт»
- Ограничение скорости — НЕ defect. Это следствие неисправности: speed_limit=60, unit «км/ч», position_type «speed_limit»
- «ограничение скорости 60», «скорость 60 км/ч», «скорость не более 40» → item speed_limit с value_numeric=число, без defect_text
- Нормы Распоряжения ОАО «РЖД» от 14.11.2016 № 2288р: превышение нормы = неисправность; V огр. по таблицам инструкции, если инспектор не назвал скорость. Пример: стыковой зазор до 24 мм — норма; св. 24 до 26 мм — 100 км/ч; св. 26 до 30 мм — 60 км/ч; св. 30 до 35 мм — 25 км/ч; более 35 мм — движение закрывается. Ширина колеи на пути: номинал 1520 мм, допуск +4/−8 мм (1512–1524); св. 1524 до 1544 мм — 60 км/ч; св. 1544 до 1548 — 25 км/ч; менее 1512 или более 1548 — закрытие. На стрелочном переводе допуск ±3 мм (1517–1523), макс. 1546 мм
- Если в одной записи и дефект, и скорость — два items: defect + speed_limit (скорость не дублировать в defect_text)
"""


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
