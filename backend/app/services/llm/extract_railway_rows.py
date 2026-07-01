"""Один LLM-вызов: transcript → RailwayRow[]."""

from __future__ import annotations

import json
import logging

from app.services.llm.provider import get_llm_provider
from app.services.railway.normalize_railway_rows import normalize_railway_rows
from app.services.railway.schema import parse_llm_rows_payload
from app.services.railway.types import RailwayRow

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """Ты извлекаешь строки дефектной ведомости железнодорожной инфраструктуры из расшифровки речи.

Требования:
1. Верни только JSON.
2. Верхний объект должен быть формата:
{
  "rows": RailwayRow[],
  "warnings": string[]
}

Где RailwayRow:
{
  "location": string | null,
  "assetKind": "track" | "switch" | null,
  "assetNumber": string | null,
  "reference": string | null,
  "defect": string | null,
  "speedLimit": number | null,
  "note": string | null,
  "sourceText": string,
  "warnings": string[]
}

Правила:
- Одна неисправность = одна строка.
- Используй только факты из текста.
- Ничего не придумывай.
- Если ограничение скорости явно не сказано, ставь null.
- Если нормативка явно не сказана, не добавляй ее.
- Если в одном предложении несколько неисправностей, разбей на несколько строк.
- Наследуй контекст от предыдущих фраз, если он очевиден:
  - станция / перегон
  - путь / стрелочный перевод
  - привязка
  - примечание
- sourceText должен быть именно тем фрагментом transcript, из которого получена эта строка.
- Если есть сомнение, оставь поле null и добавь warning.
- Не добавляй текст вне JSON."""

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
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["rows", "warnings"],
    },
}


def extract_railway_rows(transcript: str) -> list[RailwayRow]:
    text = transcript.strip()
    if not text:
        return []

    provider = get_llm_provider()
    raw = provider.complete_json(
        system=EXTRACTION_SYSTEM_PROMPT,
        user=f"Transcript:\n{text}",
        schema=ROWS_JSON_SCHEMA,
    )
    data = json.loads(raw or "{}")
    if isinstance(data, dict):
        top_warnings = data.get("warnings") or []
        if top_warnings:
            logger.info("LLM extraction warnings: %s", top_warnings)
    rows = parse_llm_rows_payload(raw)
    return normalize_railway_rows(rows)
