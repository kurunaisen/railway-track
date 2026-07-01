"""LLM provider — только OpenAI (ChatGPT)."""

from __future__ import annotations

from typing import Any, Protocol

from app.config import settings


class LlmProvider(Protocol):
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> str: ...


class OpenAiProvider:
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, Any],
        model: str | None = None,
    ) -> str:
        from openai import OpenAI

        if not settings.openai_api_key:
            raise RuntimeError("OPENAI_API_KEY не задан")

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=model or settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.0,
            response_format={
                "type": "json_schema",
                "json_schema": schema,
            },
        )
        return response.choices[0].message.content or "{}"


def get_llm_provider() -> LlmProvider:
    return OpenAiProvider()
