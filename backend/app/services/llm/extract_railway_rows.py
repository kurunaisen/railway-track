"""Один LLM-вызов: transcript → RailwayRow[]."""

from __future__ import annotations

import json
import logging

from app.services.llm.provider import get_llm_provider
from app.config import settings
from app.services.railway.normalize_railway_rows import normalize_railway_rows
from app.services.railway.schema import parse_llm_rows_payload
from app.services.railway.semantic_repair import repair_railway_rows
from app.services.railway.types import RailwayRow

logger = logging.getLogger(__name__)

EXTRACTION_SYSTEM_PROMPT = """Ты извлекаешь строки дефектной ведомости из transcript.

Верни только JSON.

Жесткие правила:
- location: только станция или перегон
- assetKind/assetNumber: только путь или стрелочный перевод
- reference: только км/пк/м
- note: только примечание
- никогда не помещай путь, стрелочный перевод, км, пикет, метр, звено в location
- одна неисправность = одна строка
- если в одном фрагменте две неисправности, верни две строки
- используй только данные из transcript
- если не уверен, оставь поле null и добавь warning"""

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
    logger.info("Railway extraction raw transcript: %s", text)
    raw = provider.complete_json(
        system=EXTRACTION_SYSTEM_PROMPT,
        user=f"Transcript:\n{text}",
        schema=ROWS_JSON_SCHEMA,
        model=settings.openai_extraction_model,
    )
    data = json.loads(raw or "{}")
    logger.info("Railway extraction raw LLM JSON: %s", data)
    if isinstance(data, dict):
        top_warnings = data.get("warnings") or []
        if top_warnings:
            logger.info("LLM extraction warnings: %s", top_warnings)
    raw_rows = parse_llm_rows_payload(raw)
    repaired_rows = repair_railway_rows(raw_rows)
    logger.info(
        "Railway extraction repaired rows: %s",
        [row.to_api_dict() for row in repaired_rows],
    )
    final_rows = normalize_railway_rows(repaired_rows)
    logger.info(
        "Railway extraction final rows: %s",
        [row.to_api_dict() for row in final_rows],
    )
    return final_rows
