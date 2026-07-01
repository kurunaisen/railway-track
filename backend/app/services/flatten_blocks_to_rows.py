"""Наследование assetKind/assetNumber с блока на строки ParsedRow."""

from __future__ import annotations

from typing import Any, TypedDict

from app.services.llm.row_segment_validation import ParsedRow

AssetKind = str  # "track" | "switch"


class LogicalBlockLike(TypedDict, total=False):
    location: str | None
    assetKind: str | None
    assetNumber: str | None
    sourceText: str | None
    rows: list[dict[str, Any]]


def build_row_source_text(
    *,
    location: str | None,
    asset_kind: str | None,
    asset_number: str | None,
    defect: str | None,
    note: str | None,
) -> str:
    parts: list[str] = []
    if location:
        parts.append(f"станция {location}")
    if asset_kind == "switch" and asset_number:
        parts.append(f"стрелочный перевод номер {asset_number}")
    if asset_kind == "track" and asset_number:
        parts.append(f"путь {asset_number}")
    if defect:
        parts.append(defect)
    if note:
        parts.append(note)
    return " ".join(parts).strip()


def flatten_blocks_to_rows(blocks: list[LogicalBlockLike]) -> list[ParsedRow]:
    result: list[ParsedRow] = []
    for block in blocks:
        block_location = block.get("location")
        block_kind = block.get("assetKind")
        block_number = block.get("assetNumber")
        for row in block.get("rows") or []:
            asset_kind = row.get("assetKind") if row.get("assetKind") is not None else block_kind
            asset_number = row.get("assetNumber") if row.get("assetNumber") is not None else block_number
            location = row.get("location") if row.get("location") is not None else block_location

            source = (row.get("sourceText") or "").strip()
            if not source:
                source = build_row_source_text(
                    location=location,
                    asset_kind=asset_kind,
                    asset_number=asset_number,
                    defect=row.get("defect"),
                    note=row.get("note"),
                )

            result.append(
                {
                    "location": location,
                    "assetKind": asset_kind,
                    "assetNumber": asset_number,
                    "reference": row.get("reference"),
                    "defect": row.get("defect"),
                    "speedLimit": row.get("speedLimit"),
                    "note": row.get("note"),
                    "sourceText": source,
                    "rawDefect": row.get("rawDefect") or row.get("defect"),
                    "canonicalDefect": row.get("canonicalDefect") or row.get("defect"),
                    "normativeDecision": None,
                    "warnings": list(row.get("warnings") or []),
                }
            )
    return result
