"""Построение wide-таблицы для UI и Excel."""

from __future__ import annotations

from typing import Protocol

from app.services.evidence_only import (
    defect_from_segment,
    is_evidence_only,
    note_from_segment,
    speed_from_segment,
    track_parts_from_segment,
)
from app.services.inspection_form import format_object_kind, format_path, format_switch

LOCATION_COLUMNS = ("Дата", "Участок", "Перегон", "Путь", "Стрелочный перевод", "Км", "Пикет", "Объект")


class WideRowSource(Protocol):
    record_date: str | None
    uchastok: str | None
    peregon: str | None
    put: str | None
    km: str | None
    piket: str | None
    obekt: str | None
    parameter: str | None
    defect: str | None
    value: str | None
    unit: str | None
    comment: str | None
    speed_limit: str | None
    raw_text: str | None
    disputed_fields: list[str]


def build_wide_rows(
    records: list[WideRowSource],
    *,
    evidence_only: bool | None = None,
) -> tuple[list[str], list[dict]]:
    evidence = is_evidence_only(mode=evidence_only)
    param_names: list[str] = []
    for rec in records:
        label = defect_from_segment(rec) if evidence else (rec.parameter or rec.defect)
        if label and label not in param_names:
            param_names.append(label)

    groups: dict[str, dict] = {}
    for rec in records:
        if evidence:
            path, switch = track_parts_from_segment(rec)
            object_kind = None
            speed = speed_from_segment(rec)
            comment = note_from_segment(rec)
            defect_label = defect_from_segment(rec)
            uchastok = rec.uchastok
            peregon = rec.peregon
            km = rec.km if rec.km and rec.km in (rec.raw_text or "") else None
            piket = rec.piket if rec.piket and rec.piket in (rec.raw_text or "") else None
        else:
            path = format_path(rec)
            switch = format_switch(rec)
            uchastok = rec.uchastok
            peregon = rec.peregon
            km = rec.km
            piket = rec.piket
            object_kind = format_object_kind(rec)
            speed = rec.speed_limit
            comment = rec.comment
            defect_label = rec.parameter or rec.defect

        key = "|".join(str(x or "") for x in [
            rec.record_date, uchastok, peregon, path, switch, km, piket, object_kind
        ])
        if key not in groups:
            groups[key] = {
                "Дата": rec.record_date,
                "Участок": uchastok,
                "Перегон": peregon,
                "Путь": path,
                "Стрелочный перевод": switch,
                "Км": km,
                "Пикет": piket,
                "Объект": object_kind,
                "params": {},
                "Комментарий": comment,
                "V огр.": speed,
                "Спорные поля": set(rec.disputed_fields),
            }
        g = groups[key]
        if defect_label:
            val = rec.value or ""
            if rec.unit:
                val = f"{val} {rec.unit}".strip()
            g["params"][defect_label] = val
        if comment:
            g["Комментарий"] = (g.get("Комментарий") or "") + ("; " if g.get("Комментарий") else "") + comment
        g["Спорные поля"].update(rec.disputed_fields)

    columns = list(LOCATION_COLUMNS) + param_names + ["Комментарий", "V огр.", "Спорные поля"]

    rows: list[dict] = []
    for g in groups.values():
        row = {k: g[k] for k in LOCATION_COLUMNS}
        for pname in param_names:
            row[pname] = g["params"].get(pname, "")
        row["Комментарий"] = g.get("Комментарий")
        row["V огр."] = g.get("V огр.")
        row["Спорные поля"] = ", ".join(sorted(g["Спорные поля"]))
        rows.append(row)
    return columns, rows
