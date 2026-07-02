"""User-taught ASR phrase corrections.

The file is intentionally simple JSON so operators can inspect or remove a bad
rule without touching the database.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings


CORRECTIONS_FILE = settings.upload_dir / "asr_corrections.json"
LEARNABLE_FIELDS = {
    "uchastok",
    "peregon",
    "obekt",
    "parameter",
    "defect",
    "comment",
    "raw_text",
}


def _now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text or None


def _key(value: str) -> str:
    text = value.lower().replace("ё", "е")
    text = re.sub(r"\s*[-–—]\s*", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _is_safe_phrase_pair(source: str, target: str, *, field: str | None = None) -> bool:
    if _key(source) == _key(target):
        return False
    is_location_field = field in {"uchastok", "peregon"}
    if is_location_field:
        if len(source) < 2 or len(target) < 3:
            return False
    elif len(source) < 4 or len(target) < 2:
        return False
    if len(source) > 120 or len(target) > 120:
        return False
    if not is_location_field and len(source) < 8 and " " not in source:
        return False
    # Avoid learning whole unrelated sentences as a global replacement.
    ratio = len(target) / max(len(source), 1)
    return 0.25 <= ratio <= 4.0


def _source_variants(source: str) -> list[str]:
    variants: list[str] = []
    dashless = re.sub(r"\s*[-–—]\s*", " ", source).strip()
    if dashless:
        variants.append(dashless)
    if source not in variants:
        variants.append(source)
    spaced_dash = re.sub(r"\s*[-–—]\s*", " — ", source).strip()
    if spaced_dash and spaced_dash not in variants:
        variants.append(spaced_dash)
    return variants


def _load_payload() -> dict[str, Any]:
    if not CORRECTIONS_FILE.exists():
        return {"version": 1, "replacements": []}
    try:
        return json.loads(CORRECTIONS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"version": 1, "replacements": []}


def load_user_corrections() -> list[dict[str, Any]]:
    payload = _load_payload()
    rows = payload.get("replacements", [])
    return rows if isinstance(rows, list) else []


def list_user_corrections() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for row in load_user_corrections():
        target = _clean(row.get("target"))
        if not target:
            continue
        result.append({
            "target": target,
            "sources": _row_sources(row),
            "field": row.get("field"),
            "enabled": bool(row.get("enabled", True)),
            "count": int(row.get("count") or 0),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        })
    return result


def _row_sources(row: dict[str, Any]) -> list[str]:
    result: list[str] = []
    raw_sources = row.get("sources")
    if isinstance(raw_sources, list):
        result.extend(str(item) for item in raw_sources if _clean(item))
    source = _clean(row.get("source"))
    if source:
        result.append(source)
    deduped: list[str] = []
    seen: set[str] = set()
    for source in result:
        key = _key(source)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _write_payload(payload: dict[str, Any]) -> None:
    CORRECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CORRECTIONS_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(CORRECTIONS_FILE)


def add_user_correction(
    source: str,
    target: str,
    *,
    field: str | None = None,
    created_by: str | None = None,
) -> bool:
    source_clean = _clean(source)
    target_clean = _clean(target)
    if not source_clean or not target_clean or not _is_safe_phrase_pair(
        source_clean,
        target_clean,
        field=field,
    ):
        return False

    payload = _load_payload()
    rows = payload.setdefault("replacements", [])
    if not isinstance(rows, list):
        payload["replacements"] = rows = []

    source_key = _key(source_clean)
    target_key = _key(target_clean)
    for row in rows:
        row_target = _clean(row.get("target"))
        if not row_target:
            continue
        row_target_key = _key(row_target)
        if row_target_key == target_key:
            sources = _row_sources(row)
            if any(_key(source) == source_key for source in sources):
                row["count"] = int(row.get("count") or 1) + 1
                row["updated_at"] = _now_iso()
                _write_payload(payload)
                return False
            sources.append(source_clean)
            row["sources"] = sorted(sources, key=len, reverse=True)
            row.pop("source", None)
            row["count"] = int(row.get("count") or 0) + 1
            row["updated_at"] = _now_iso()
            if field and not row.get("field"):
                row["field"] = field
            _write_payload(payload)
            return True
        if any(_key(source) == source_key for source in _row_sources(row)):
            # Do not silently map the same ASR phrase to two different targets.
            return False

    rows.append({
        "sources": [source_clean],
        "target": target_clean,
        "field": field,
        "enabled": True,
        "created_by": created_by,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "count": 1,
    })
    rows.sort(key=lambda item: len(str(item.get("target", ""))), reverse=True)
    _write_payload(payload)
    return True


def learn_corrections_from_update(
    before: dict[str, Any],
    patch: dict[str, Any],
    *,
    created_by: str | None = None,
) -> int:
    learned = 0
    for field in LEARNABLE_FIELDS.intersection(patch.keys()):
        old_value = _clean(before.get(field))
        new_value = _clean(patch.get(field))
        if not old_value or not new_value:
            continue
        for source in _source_variants(old_value):
            if add_user_correction(source, new_value, field=field, created_by=created_by):
                learned += 1
    return learned


def set_user_correction_enabled(target: str, enabled: bool, source: str | None = None) -> bool:
    target_key = _key(target)
    source_key = _key(source) if source else None
    payload = _load_payload()
    changed = False
    for row in payload.get("replacements", []):
        row_target = _clean(row.get("target"))
        if not row_target or _key(row_target) != target_key:
            continue
        if source_key:
            sources = _row_sources(row)
            if not any(_key(item) == source_key for item in sources):
                continue
        row["enabled"] = enabled
        row["updated_at"] = _now_iso()
        changed = True
    if changed:
        _write_payload(payload)
    return changed


def delete_user_correction(target: str, source: str | None = None) -> bool:
    target_key = _key(target)
    source_key = _key(source) if source else None
    payload = _load_payload()
    rows = payload.get("replacements", [])
    if not isinstance(rows, list):
        return False
    changed = False
    next_rows: list[dict[str, Any]] = []
    for row in rows:
        row_target = _clean(row.get("target"))
        if not row_target or _key(row_target) != target_key:
            next_rows.append(row)
            continue
        if not source_key:
            changed = True
            continue
        sources = [item for item in _row_sources(row) if _key(item) != source_key]
        if len(sources) != len(_row_sources(row)):
            changed = True
            if sources:
                row["sources"] = sources
                row.pop("source", None)
                row["updated_at"] = _now_iso()
                next_rows.append(row)
            continue
        next_rows.append(row)
    if changed:
        payload["replacements"] = next_rows
        _write_payload(payload)
    return changed


def apply_user_corrections(text: str) -> str:
    if not text:
        return text
    fixed = text
    for row in load_user_corrections():
        if not row.get("enabled", True):
            continue
        target = _clean(row.get("target"))
        if not target:
            continue
        sources = sorted(_row_sources(row), key=len, reverse=True)
        for source in sources:
            pattern = re.escape(source)
            if re.match(r"^\w", source, re.UNICODE):
                pattern = rf"(?<!\w){pattern}"
            if re.search(r"\w$", source, re.UNICODE):
                pattern = rf"{pattern}(?!\w)"
            fixed = re.sub(pattern, target, fixed, flags=re.IGNORECASE)
    return fixed
