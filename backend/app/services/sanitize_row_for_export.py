"""Backward-compatible re-exports — см. postprocess_railway_rows.py."""

from app.services.postprocess_railway_rows import (
    contains_explicit_speed,
    dash_if_empty,
    extract_deterministic_defect,
    normalize_spaces,
    parsed_row_from_record,
    sanitize_row_for_export,
    sanitizeRowForExport,
    sanitize_rows_for_export,
    sanitizeRowsForExport,
    to_display_rows,
    toDisplayRows,
)

__all__ = [
    "contains_explicit_speed",
    "dash_if_empty",
    "extract_deterministic_defect",
    "normalize_spaces",
    "parsed_row_from_record",
    "sanitize_row_for_export",
    "sanitizeRowForExport",
    "sanitize_rows_for_export",
    "sanitizeRowsForExport",
    "to_display_rows",
    "toDisplayRows",
]
