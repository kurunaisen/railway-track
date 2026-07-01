"""Optional AI review for suspicious ASR transcript fragments."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services.llm.provider import get_llm_provider

logger = logging.getLogger(__name__)

Severity = Literal["warning", "error"]


class TranscriptReviewIssue(BaseModel):
    quote: str = Field(min_length=1)
    start: int = Field(ge=0)
    end: int = Field(ge=0)
    severity: Severity
    title: str
    description: str


class TranscriptReviewPayload(BaseModel):
    issues: list[TranscriptReviewIssue] = Field(default_factory=list)


TRANSCRIPT_REVIEW_PROMPT = """Ты проверяешь transcript железнодорожного обхода на ошибки ASR.

Верни только JSON.

Ищи только фрагменты, которые пользователю стоит проверить перед формированием таблицы:
- лишние числа в измерениях, например "уширение колеи 1400 1543 мм";
- неполные слова, например "пике" вместо "пикет";
- вероятные искажения названий станций/перегонов;
- неполные привязки км/пк/м;
- фразы, где смысл для дефектной ведомости неясен.

Не исправляй текст сам. Не отмечай нормальные технические слова.

Для каждого issue верни:
- quote: точный фрагмент из transcript;
- start/end: индексы quote в transcript;
- severity: "warning" или "error";
- title: короткий заголовок;
- description: что проверить пользователю."""


REVIEW_JSON_SCHEMA: dict = {
    "name": "transcript_review",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "quote": {"type": "string"},
                        "start": {"type": "integer"},
                        "end": {"type": "integer"},
                        "severity": {"type": "string", "enum": ["warning", "error"]},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                    },
                    "required": ["quote", "start", "end", "severity", "title", "description"],
                },
            },
        },
        "required": ["issues"],
    },
}


def _locate_quote(transcript: str, issue: TranscriptReviewIssue) -> tuple[int, int] | None:
    quote = issue.quote.strip()
    if not quote:
        return None

    if (
        0 <= issue.start < issue.end <= len(transcript)
        and transcript[issue.start : issue.end] == quote
    ):
        return issue.start, issue.end

    start = transcript.find(quote)
    if start >= 0:
        return start, start + len(quote)

    start = transcript.lower().find(quote.lower())
    if start >= 0:
        return start, start + len(quote)

    return None


def review_transcript_with_ai(transcript: str) -> list[TranscriptReviewIssue]:
    text = transcript.strip()
    if not text:
        return []

    provider = get_llm_provider()
    raw = provider.complete_json(
        system=TRANSCRIPT_REVIEW_PROMPT,
        user=f"Transcript:\n{text}",
        schema=REVIEW_JSON_SCHEMA,
        model=settings.openai_model,
    )

    try:
        payload = TranscriptReviewPayload.model_validate(json.loads(raw or "{}"))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"Invalid transcript review JSON from LLM: {exc}") from exc

    issues: list[TranscriptReviewIssue] = []
    seen: set[tuple[int, int, str]] = set()
    for issue in payload.issues[:20]:
        located = _locate_quote(text, issue)
        if not located:
            logger.info("Skip transcript review issue with unmatched quote: %s", issue.quote)
            continue
        start, end = located
        key = (start, end, issue.title)
        if key in seen:
            continue
        seen.add(key)
        issues.append(
            TranscriptReviewIssue(
                quote=text[start:end],
                start=start,
                end=end,
                severity=issue.severity,
                title=issue.title,
                description=issue.description,
            )
        )
    return issues
