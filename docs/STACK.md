# Рекомендуемый стек Railway Track Inspection

## Архитектура

```
┌─────────────┐     HTTPS      ┌──────────┐
│   Browser   │ ──────────────►│  Nginx   │
│ React+TW    │                └────┬─────┘
└─────────────┘                     │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               │
              ┌──────────┐   ┌──────────┐          │
              │ Frontend │   │ FastAPI  │          │
              │  (Vite)  │   │   API    │          │
              └──────────┘   └────┬─────┘          │
                                  │                 │
              ┌───────────────────┼─────────────────┤
              ▼                   ▼                 ▼
        ┌──────────┐       ┌──────────┐      ┌──────────┐
        │PostgreSQL│       │  Redis   │      │  MinIO   │
        └──────────┘       └────┬─────┘      │  (S3)    │
                                  │            └──────────┘
                                  ▼
                           ┌──────────┐
                           │  Celery  │
                           │  Worker  │
                           └────┬─────┘
                                │
                    ┌───────────┼───────────┐
                    ▼           ▼           ▼
              faster-whisper  Yandex    OpenAI + Claude
              (локально)    SpeechKit  (разбор + review)
```

## Компоненты

| Слой | Технология | Статус в проекте |
|------|------------|------------------|
| **Frontend** | React + Vite | ✅ |
| **UI** | Tailwind CSS | ✅ |
| **Запись** | MediaRecorder API | ✅ |
| **Backend** | Python + FastAPI | ✅ |
| **Схемы** | Pydantic v2 | ✅ |
| **ORM** | SQLAlchemy 2 | ✅ |
| **Очередь** | Redis + Celery | ✅ |
| **БД** | PostgreSQL (prod) / SQLite (dev) | ✅ |
| **Файлы** | Local / MinIO (S3) | ✅ |
| **ASR** | faster-whisper | ✅ по умолчанию |
| **ASR** | Yandex SpeechKit | ✅ опционально |
| **LLM** | OpenAI (ChatGPT) | ✅ `PARSER_MODE=openai\|hybrid` |
| **LLM** | Claude | ✅ review спорных полей |
| **Excel** | pandas + openpyxl | ✅ |
| **DevOps** | Docker Compose | ✅ |
| **Proxy** | Nginx + HTTPS | ✅ |

## Переменные окружения

```env
# Database
DATABASE_URL=postgresql://railway:pass@postgres:5432/railway

# Storage: local | s3
STORAGE_BACKEND=s3
S3_ENDPOINT=http://minio:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
S3_BUCKET=railway-audio

# ASR: faster-whisper | yandex
ASR_PROVIDER=faster-whisper
YANDEX_SPEECH_API_KEY=
YANDEX_SPEECH_FOLDER_ID=

# Parser: regex | openai | hybrid
PARSER_MODE=hybrid
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
ANTHROPIC_API_KEY=sk-ant-...
LLM_REVIEW_DISPUTED=true

# Queue
USE_TASK_QUEUE=true
REDIS_URL=redis://redis:6379/0
```

## Режимы разбора (PARSER_MODE)

| Режим | Описание |
|-------|----------|
| `regex` | Только rule-based парсер (без LLM) |
| `openai` | ChatGPT извлекает записи из текста |
| `hybrid` | OpenAI + regex fallback + Claude для спорных |

## ASR (ASR_PROVIDER)

| Провайдер | Когда использовать |
|-----------|-------------------|
| `faster-whisper` | Локально, offline, GPU/CPU |
| `yandex` | Облако, высокое качество русской речи |

Yandex требует mono 16 kHz WAV (конвертация ffmpeg выполняется автоматически).

## Запуск production stack

```powershell
# 1. HTTPS-сертификаты (dev)
.\deploy\nginx\generate-certs.ps1

# 2. Секреты в .env
# SECRET_KEY, DATA_ENCRYPTION_KEY, OPENAI_API_KEY, POSTGRES_PASSWORD

# 3. Запуск
docker compose up -d --build

# 4. Масштабирование воркеров
docker compose up -d --scale worker=3
```

- UI: https://localhost  
- MinIO console: http://localhost:9001  
- API health: https://localhost/health  

## Локальная разработка (Windows)

```powershell
.\scripts\setup-windows.ps1
# backend\.env:
# DATABASE_URL=sqlite:///./railway.db
# STORAGE_BACKEND=local
# ASR_PROVIDER=faster-whisper
# PARSER_MODE=regex
# AUTH_REQUIRED=false
```

## Альтернативы из ТЗ

| Рекомендация | Выбор в проекте |
|--------------|-----------------|
| Next.js **или** React | **React + Vite** (легче для SPA) |
| Ant Design / MUI / Tailwind | **Tailwind CSS** |
| Celery **или** RQ | **Celery** (масштабирование воркеров) |
| SQLModel | **SQLAlchemy** (уже интегрирован) |

Переход на Next.js или Ant Design возможен без смены backend API.
