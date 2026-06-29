# FR 15 — Роль нейросетей

## 15.1 ASR (аудио → текст)

| Провайдер | Когда использовать | Таймкоды |
|-----------|-------------------|----------|
| `faster-whisper` | Локально, offline, dev/prod без облака | ✅ сегменты + confidence |
| `yandex` | Облако, оптимизировано для русского | ✅ (блок; streaming — roadmap) |

Конфиг: `ASR_PROVIDER=faster-whisper|yandex`

Модули: `backend/app/services/asr/`

Результат ASR → `transcripts` + `transcript_segments` (start_sec, end_sec, confidence).

## 15.2 LLM (текст → структура)

ChatGPT и Claude **не формируют Excel**. Они возвращают **строгий JSON**:

```json
{
  "records": [
    {
      "sequence_number": 1,
      "haul_name": "А-Б",
      "km_value": "35",
      "items": [
        { "order_in_record": 1, "parameter_name": "Перекос", "value_numeric": 4, "unit": "мм" }
      ]
    }
  ]
}
```

Схема и валидация: `backend/app/services/llm/json_schema.py`

## 15.3 Рекомендуемая стратегия

| Роль | Модель | Env |
|------|--------|-----|
| **Основной парсер** | ChatGPT (OpenAI) | `LLM_PRIMARY_PARSER=openai`, `PARSER_MODE=hybrid` |
| **Ревью спорных** | Claude (Anthropic) | `LLM_REVIEW_DISPUTED=true` |
| **Fallback** | Regex / canonical | если LLM JSON невалиден или мало records |

Для A/B-тестов можно поменять: `LLM_PRIMARY_PARSER=anthropic`.

### Режимы `PARSER_MODE`

- `regex` — только rule-based (без LLM)
- `openai` / `hybrid` — LLM + fallback на regex при ошибке

### Пример `.env`

```env
ASR_PROVIDER=faster-whisper
PARSER_MODE=hybrid
LLM_PRIMARY_PARSER=openai
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LLM_REVIEW_DISPUTED=true
```

Проверка ролей: `GET /health` → секция `neural`.
