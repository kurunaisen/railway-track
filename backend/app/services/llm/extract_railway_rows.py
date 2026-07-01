"""Один LLM-вызов: transcript → RailwayRow[]."""

from __future__ import annotations

import json

from app.services.llm.provider import get_llm_provider
from app.services.railway.normalize_railway_rows import normalize_railway_rows
from app.services.railway.schema import parse_llm_rows_payload
from app.services.railway.types import RailwayRow

EXTRACTION_SYSTEM_PROMPT = """Ты извлекаешь строки таблицы обхода железнодорожного пути из русской ASR-диктовки.

Правила:
1. Одна неисправность = одна строка.
2. Используй ТОЛЬКО информацию из transcript.
3. Ничего не придумывай:
   - не добавляй 2288р
   - не добавляй ограничения скорости, если их нет в тексте
   - не добавляй нормативные решения
4. Если в одном фрагменте две неисправности — верни две строки.
5. Наследуй контекст между фрагментами:
   - станция / перегон
   - путь / стрелочный перевод
   - привязка (км, пк, м)
   - примечание вроде «звено 2»
6. sourceText — дословный фрагмент текста именно этой строки.
7. Если не уверен — оставь поле null и добавь пояснение в warnings.

Поля строки:
- location: станция или перегон
- assetKind: "track" | "switch" | null
- assetNumber: номер пути или перевода
- reference: привязка «1418 км, пк 2, 87 м»
- defect: выявленная неисправность
- speedLimit: число км/ч только если явно названо
- note: уточнения (острие остряка, звено N и т.п.)
- sourceText: фрагмент transcript
- warnings: массив строк (может быть пустым)
"""

ROWS_JSON_SCHEMA: dict = {
    "name": "railway_rows",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "rows": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "location": {"type": ["string", "null"]},
                        "assetKind": {
                            "anyOf": [
                                {"type": "string", "enum": ["track", "switch"]},
                                {"type": "null"},
                            ],
                        },
                        "assetNumber": {"type": ["string", "null"]},
                        "reference": {"type": ["string", "null"]},
                        "defect": {"type": ["string", "null"]},
                        "speedLimit": {"type": ["number", "null"]},
                        "note": {"type": ["string", "null"]},
                        "sourceText": {"type": "string"},
                        "warnings": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "location",
                        "assetKind",
                        "assetNumber",
                        "reference",
                        "defect",
                        "speedLimit",
                        "note",
                        "sourceText",
                        "warnings",
                    ],
                },
            },
        },
        "required": ["rows"],
    },
}


def extract_railway_rows(transcript: str) -> list[RailwayRow]:
    text = transcript.strip()
    if not text:
        return []

    provider = get_llm_provider()
    raw = provider.complete_json(
        system=EXTRACTION_SYSTEM_PROMPT,
        user=json.dumps({"transcript": text}, ensure_ascii=False),
        schema=ROWS_JSON_SCHEMA,
    )
    rows = parse_llm_rows_payload(raw)
    return normalize_railway_rows(rows)
