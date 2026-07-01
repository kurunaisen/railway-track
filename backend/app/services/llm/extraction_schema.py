"""
Strict JSON Schema для structured output LLM (OpenAI json_schema / Claude).

Одна строка таблицы = один элемент rows[].
"""

from __future__ import annotations

from typing import Any

ROW_ITEM_SCHEMA: dict[str, Any] = {
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
    ],
}

RAILWAY_ROWS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "rows": {
            "type": "array",
            "items": ROW_ITEM_SCHEMA,
        },
    },
    "required": ["rows"],
}

RAILWAY_EXTRACTION_SCHEMA: dict[str, Any] = {
    "name": "railway_rows",
    "strict": True,
    "schema": RAILWAY_ROWS_SCHEMA,
}


def openai_response_format() -> dict[str, Any]:
    """response_format для OpenAI Chat Completions (structured outputs)."""
    return {
        "type": "json_schema",
        "json_schema": RAILWAY_EXTRACTION_SCHEMA,
    }
