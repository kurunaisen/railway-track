"""FR 15.3 — Claude: ревью спорных полей (не основной парсер)."""

from __future__ import annotations

import json
import logging

from anthropic import Anthropic

from app.config import settings
from app.services.parser import ParsedRecord

logger = logging.getLogger(__name__)

REVIEW_SYSTEM = """Ты — ревьюер извлечённых данных обхода пути.
Не переписывай всю структуру. Исправь только спорные поля.
Верни ТОЛЬКО JSON: {"fields": {"имя_поля": "значение_or_null"}, "still_disputed": ["поля"]}."""


def review_disputed_record(record: ParsedRecord, full_context: str) -> ParsedRecord:
    if not settings.anthropic_api_key or not record.disputed_fields:
        return record

    client = Anthropic(api_key=settings.anthropic_api_key)
    prompt = json.dumps(
        {
            "role": "review_disputed_fields",
            "raw_text": record.raw_text,
            "context_excerpt": full_context[:2000],
            "current": {
                k: getattr(record, k)
                for k in (
                    "peregon", "put", "km", "piket", "parameter", "defect",
                    "value", "unit", "speed_limit", "position_type",
                )
            },
            "disputed_fields": record.disputed_fields,
        },
        ensure_ascii=False,
    )

    message = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=1024,
        system=REVIEW_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    text = message.content[0].text if message.content else "{}"
    if text.strip().startswith("```"):
        lines = text.strip().split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    data = json.loads(text)

    for field, value in (data.get("fields") or {}).items():
        if hasattr(record, field) and value is not None:
            setattr(record, field, str(value) if not isinstance(value, str) else value)

    record.disputed_fields = data.get("still_disputed", record.disputed_fields)
    logger.info("Claude review: disputed=%s", record.disputed_fields)
    return record


def review_all_disputed(records: list[ParsedRecord], full_text: str) -> list[ParsedRecord]:
    if not settings.llm_review_disputed or not settings.anthropic_api_key:
        return records
    return [
        review_disputed_record(r, full_text) if r.disputed_fields else r
        for r in records
    ]
