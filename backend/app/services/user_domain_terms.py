"""User-maintained domain terms that should not be reported as unknown."""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from app.config import settings


TERMS_FILE = settings.upload_dir / "domain_terms.json"


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def normalize_term(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip().lower().replace("ё", "е"))
    return text or None


def _load_payload() -> dict[str, Any]:
    if not TERMS_FILE.exists():
        return {"version": 1, "terms": []}
    try:
        return json.loads(TERMS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "terms": []}


def _write_payload(payload: dict[str, Any]) -> None:
    TERMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = TERMS_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(TERMS_FILE)


def list_user_domain_terms() -> list[dict[str, Any]]:
    payload = _load_payload()
    rows = payload.get("terms", [])
    return rows if isinstance(rows, list) else []


def user_domain_term_values() -> set[str]:
    return {
        normalized
        for row in list_user_domain_terms()
        if row.get("enabled", True)
        for normalized in [normalize_term(row.get("term"))]
        if normalized
    }


def add_user_domain_term(term: str, *, created_by: str | None = None) -> bool:
    normalized = normalize_term(term)
    if not normalized or len(normalized) < 2 or len(normalized) > 80:
        return False
    payload = _load_payload()
    rows = payload.setdefault("terms", [])
    if not isinstance(rows, list):
        payload["terms"] = rows = []
    for row in rows:
        if normalize_term(row.get("term")) == normalized:
            row["enabled"] = True
            row["updated_at"] = _now_iso()
            _write_payload(payload)
            return False
    rows.append({
        "term": normalized,
        "enabled": True,
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
    })
    rows.sort(key=lambda row: str(row.get("term", "")))
    _write_payload(payload)
    return True


def set_user_domain_term_enabled(term: str, enabled: bool) -> bool:
    normalized = normalize_term(term)
    if not normalized:
        return False
    payload = _load_payload()
    changed = False
    for row in payload.get("terms", []):
        if normalize_term(row.get("term")) == normalized:
            row["enabled"] = enabled
            row["updated_at"] = _now_iso()
            changed = True
    if changed:
        _write_payload(payload)
    return changed


def delete_user_domain_term(term: str) -> bool:
    normalized = normalize_term(term)
    if not normalized:
        return False
    payload = _load_payload()
    rows = payload.get("terms", [])
    if not isinstance(rows, list):
        return False
    next_rows = [row for row in rows if normalize_term(row.get("term")) != normalized]
    if len(next_rows) == len(rows):
        return False
    payload["terms"] = next_rows
    _write_payload(payload)
    return True
