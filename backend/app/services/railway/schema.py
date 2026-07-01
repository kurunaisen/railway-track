"""Runtime-валидация JSON от LLM."""

from __future__ import annotations

import json
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.services.railway.types import RailwayRow

_ROWS_ADAPTER = TypeAdapter(list[RailwayRow])


def parse_llm_rows_payload(raw: str | dict[str, Any]) -> list[RailwayRow]:
    data = raw if isinstance(raw, dict) else json.loads(raw or "{}")
    if isinstance(data, list):
        rows_payload = data
    elif isinstance(data, dict) and isinstance(data.get("rows"), list):
        rows_payload = data["rows"]
    else:
        raise ValueError("LLM JSON must be { rows: RailwayRow[] }")

    try:
        return _ROWS_ADAPTER.validate_python(rows_payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid RailwayRow[] from LLM: {exc}") from exc
