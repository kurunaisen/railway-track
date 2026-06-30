"""Нормализация ошибок и предупреждений конвейера для API."""

from __future__ import annotations


def normalize_pipeline_issues(items: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Разделяет ошибки и предупреждения, приводит message/error к одному тексту.
    Ошибки валидации приходят с ключом message, ошибки пайплайна — с error.
    """
    errors: list[dict] = []
    warnings: list[dict] = []

    for raw in items:
        text = (raw.get("error") or raw.get("message") or "").strip()
        field = raw.get("field") or "general"
        row = raw.get("row", -1)
        severity = raw.get("severity")
        if severity is None:
            severity = "warning" if raw.get("field") else "error"

        item = {
            "row": row,
            "field": field,
            "message": text,
            "error": text,
            "text": raw.get("text"),
            "severity": severity,
        }
        if not text:
            continue
        if severity == "warning":
            warnings.append(item)
        else:
            errors.append(item)

    return errors, warnings
