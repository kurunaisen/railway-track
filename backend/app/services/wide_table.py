"""Построение wide-таблицы для UI и Excel."""

from __future__ import annotations

from typing import Protocol

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


def build_wide_rows(records: list[WideRowSource]) -> tuple[list[str], list[dict]]:
    param_names: list[str] = []
    for rec in records:
        for name in (rec.parameter, rec.defect):
            if name and name not in param_names:
                param_names.append(name)

    groups: dict[str, dict] = {}
    for rec in records:
        path = format_path(rec)
        switch = format_switch(rec)
        object_kind = format_object_kind(rec)
        key = "|".join(str(x or "") for x in [
            rec.record_date, rec.uchastok, rec.peregon, path, switch, rec.km, rec.piket, object_kind
        ])
        if key not in groups:
            groups[key] = {
                "Дата": rec.record_date,
                "Участок": rec.uchastok,
                "Перегон": rec.peregon,
                "Путь": path,
                "Стрелочный перевод": switch,
                "Км": rec.km,
                "Пикет": rec.piket,
                "Объект": object_kind,
                "params": {},
                "Комментарий": rec.comment,
                "V огр.": rec.speed_limit,
                "Спорные поля": set(rec.disputed_fields),
            }
        g = groups[key]
        label = rec.parameter or rec.defect
        if label:
            val = rec.value or ""
            if rec.unit:
                val = f"{val} {rec.unit}".strip()
            g["params"][label] = val
        if rec.comment:
            g["Комментарий"] = (g.get("Комментарий") or "") + ("; " if g.get("Комментарий") else "") + rec.comment
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
