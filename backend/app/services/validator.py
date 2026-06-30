"""Шаг 7: валидация записей."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.parser import ParsedRecord

ALLOWED_UNITS = {"мм", "см", "м", "км/ч", "°", "‰", ""}

KM_RE = re.compile(r"^\d+(?:\.\d+)?$")
PIKET_RE = re.compile(r"^\d+(?:\+\d+)?(?:\.\d+)?$")

VALUE_RANGES: dict[str, tuple[float, float]] = {
    "износ": (0, 500),
    "просадка": (0, 500),
    "уровень": (-100, 100),
    "ширина колеи": (1000, 2000),
}


@dataclass
class ValidationIssue:
    row: int
    field: str
    message: str
    severity: str = "warning"  # warning | error


@dataclass
class ValidationResult:
    issues: list[ValidationIssue] = field(default_factory=list)
    record_errors: dict[int, list[str]] = field(default_factory=dict)

    def to_dicts(self) -> list[dict]:
        return [
            {"row": i.row, "field": i.field, "message": i.message, "severity": i.severity}
            for i in self.issues
        ]


def validate_record(record: ParsedRecord, row: int) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    has_location = any([record.km, record.piket, record.peregon])
    has_issue = any([record.parameter, record.defect, record.value])
    if not has_location and not has_issue:
        issues.append(ValidationIssue(row, "general", "Нет ключевых полей (км/пикет/перегон/дефект)", "error"))

    if record.km and not KM_RE.match(record.km):
        issues.append(ValidationIssue(row, "km", f"Неверный формат км: {record.km}", "error"))

    if record.piket and not PIKET_RE.match(record.piket):
        issues.append(ValidationIssue(row, "piket", f"Неверный формат пикета: {record.piket}", "error"))

    if record.unit and record.unit not in ALLOWED_UNITS:
        issues.append(ValidationIssue(row, "unit", f"Недопустимая единица: {record.unit}", "warning"))

    if record.value:
        try:
            num = float(record.value)
            label = record.parameter or record.defect or ""
            for key, (lo, hi) in VALUE_RANGES.items():
                if key in label and not (lo <= num <= hi):
                    issues.append(
                        ValidationIssue(
                            row, "value",
                            f"Значение {num} вне диапазона [{lo}, {hi}] для {key}",
                            "warning",
                        )
                    )
        except ValueError:
            issues.append(ValidationIssue(row, "value", f"Не числовое значение: {record.value}", "warning"))

    if (record.parameter or record.defect) and not record.value and not record.comment:
        issues.append(ValidationIssue(row, "value", "Параметр/дефект без значения", "warning"))

    has_param = bool(record.parameter)
    has_defect = bool(record.defect)
    if has_param and has_defect:
        issues.append(
            ValidationIssue(
                row, "position_type",
                "В одной строке допускается только один параметр или дефект (правило 10.3)",
                "error",
            )
        )

    if record.speed_limit:
        try:
            sp = int(record.speed_limit)
            if not (5 <= sp <= 200):
                issues.append(ValidationIssue(row, "speed_limit", f"Скорость {sp} вне 5–200", "warning"))
        except ValueError:
            issues.append(ValidationIssue(row, "speed_limit", "Неверный формат скорости", "error"))

    return issues


def validate_all(records: list[ParsedRecord]) -> ValidationResult:
    result = ValidationResult()
    for idx, rec in enumerate(records):
        row_issues = validate_record(rec, idx)
        result.issues.extend(row_issues)
        if row_issues:
            result.record_errors[idx] = [f"{i.field}: {i.message}" for i in row_issues]
            rec.disputed_fields = list(set(rec.disputed_fields + [i.field for i in row_issues if i.severity == "error"]))
    return result
