from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.asr_fixes import normalize_asr_text
from app.services.parser import detect_unknown_terms
from app.services.user_asr_corrections import load_user_corrections


WORD_LEFT = r"(?<![A-Za-zА-Яа-яЁё0-9])"
WORD_RIGHT = r"(?![A-Za-zА-Яа-яЁё0-9])"


@dataclass
class TranscriptSafeFix:
    replacement: str
    label: str


@dataclass
class TranscriptIssue:
    start: int
    end: int
    severity: str
    title: str
    description: str
    safe_fix: TranscriptSafeFix | None = None
    source: str = "backend"

    def to_api_dict(self) -> dict:
        data = {
            "id": f"{self.severity}-{self.start}-{self.end}-{self.title}",
            "start": self.start,
            "end": self.end,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "source": self.source,
        }
        if self.safe_fix:
            data["safeFix"] = {
                "replacement": self.safe_fix.replacement,
                "label": self.safe_fix.label,
            }
        return data


def _add_issue(issues: list[TranscriptIssue], issue: TranscriptIssue) -> None:
    if issue.start >= 0 and issue.end > issue.start:
        issues.append(issue)


def _word_pattern(source: str) -> str:
    pattern = re.escape(source)
    if re.match(r"^\w", source, re.UNICODE):
        pattern = rf"(?<!\w){pattern}"
    if re.search(r"\w$", source, re.UNICODE):
        pattern = rf"{pattern}(?!\w)"
    return pattern


def _static_issues(text: str, issues: list[TranscriptIssue]) -> None:
    for match in re.finditer(
        rf"{WORD_LEFT}(перед\s+гонк(?:ой|а|у)?\s+мурманск(?:ом|а)?){WORD_RIGHT}",
        text,
        flags=re.IGNORECASE,
    ):
        _add_issue(issues, TranscriptIssue(
            start=match.start(1),
            end=match.end(1),
            severity="error",
            title="Похоже на перегон Кола - Мурманск",
            description="ASR распознал «перегон Кола-Мурманск» как «перед гонкой Мурманск».",
            safe_fix=TranscriptSafeFix(
                replacement="перегон Кола — Мурманск",
                label="Заменить на перегон Кола — Мурманск",
            ),
        ))

    for match in re.finditer(rf"{WORD_LEFT}(лизат){WORD_RIGHT}", text, flags=re.IGNORECASE):
        original = match.group(1)
        replacement = "Лежат" if original[:1].isupper() else "лежат"
        _add_issue(issues, TranscriptIssue(
            start=match.start(1),
            end=match.end(1),
            severity="error",
            title="Похоже на слово «лежат»",
            description="ASR распознал слово как «лизат». В этом контексте, скорее всего, имелось в виду «лежат».",
            safe_fix=TranscriptSafeFix(replacement=replacement, label="Заменить на «лежат»"),
        ))


def _user_correction_issues(text: str, issues: list[TranscriptIssue]) -> None:
    for row in load_user_corrections():
        if not row.get("enabled", True):
            continue
        target = str(row.get("target") or "").strip()
        if not target:
            continue
        sources = row.get("sources") if isinstance(row.get("sources"), list) else [row.get("source")]
        for source_raw in sources:
            source = str(source_raw or "").strip()
            if not source:
                continue
            for match in re.finditer(_word_pattern(source), text, flags=re.IGNORECASE):
                _add_issue(issues, TranscriptIssue(
                    start=match.start(),
                    end=match.end(),
                    severity="warning",
                    title=f"Пользовательское правило: {target}",
                    description=f"Накопленное исправление заменит «{match.group(0)}» на «{target}».",
                    safe_fix=TranscriptSafeFix(replacement=target, label=f"Заменить на {target}"),
                    source="user_dictionary",
                ))


def _finalize_issues(issues: list[TranscriptIssue]) -> list[TranscriptIssue]:
    sorted_issues = sorted(issues, key=lambda item: (item.start, -(item.end - item.start)))
    result: list[TranscriptIssue] = []
    cursor = -1
    for issue in sorted_issues:
        if issue.start < cursor:
            continue
        result.append(issue)
        cursor = issue.end
    return result


def check_transcript_text(text: str) -> dict:
    issues: list[TranscriptIssue] = []
    _static_issues(text, issues)
    _user_correction_issues(text, issues)
    finalized = _finalize_issues(issues)
    normalized = normalize_asr_text(text)
    return {
        "issues": [issue.to_api_dict() for issue in finalized],
        "unknown_terms": detect_unknown_terms(normalized),
        "normalized_text": normalized,
    }
