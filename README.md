# Railway Track Inspection Service

> **Стек:** [docs/STACK.md](docs/STACK.md) · **NFR:** [docs/NFR.md](docs/NFR.md)

React + FastAPI + PostgreSQL + Redis/Celery + MinIO + Whisper/Yandex + OpenAI/Claude

## Быстрый старт (Windows)

```powershell
.\scripts\setup-windows.ps1
cd backend
uvicorn app.main:app --reload --port 8000
# другой терминал:
cd frontend
npm run dev
```

http://localhost:5173 — в режиме разработки (`AUTH_REQUIRED=false`) вход не требуется.

## Docker (локально / облако)

```powershell
docker compose up -d
```

http://localhost — frontend, http://localhost:8000/health — API.

## Пользователи по умолчанию (production)

| Логин | Пароль | Роль |
|-------|--------|------|
| admin | admin* | admin |
| operator | operator | operator |
| viewer | viewer | viewer |

\* сменить через `DEFAULT_ADMIN_PASSWORD`

## Функциональные требования (FR 3.1–3.6)

См. предыдущие разделы README и [docs/NFR.md](docs/NFR.md).

### 3.1 Работа с аудио
- `.wav`, `.mp3`, `.m4a`, `.flac` + запись с микрофона
- Конвертация **mono 16 kHz WAV** (ffmpeg, сервер)

### 3.2–3.6
Распознавание, разбор, много записей, редактирование, Excel (5 листов).

## Конфигурация

```env
USE_TASK_QUEUE=false          # true + Redis для очереди
AUTH_REQUIRED=false           # true в production
ENCRYPT_TRANSCRIPTS=false     # true + DATA_ENCRYPTION_KEY
SECRET_KEY=...
REDIS_URL=redis://localhost:6379/0
```

## API

| Метод | Путь | Роль |
|-------|------|------|
| POST | `/api/auth/login` | — |
| POST | `/api/upload` | operator+ |
| POST | `/api/sessions/{id}/process` | operator+ |
| GET | `/api/jobs/{id}` | viewer+ |
| GET | `/api/admin/audit` | admin |
| GET | `/api/sessions/{id}/export` | viewer+ |

## Тесты

```powershell
cd backend
python -m pytest tests/ -v
```

## Структура

```
Railway/
├── backend/app/
│   ├── auth/           # JWT, RBAC
│   ├── tasks/          # Celery worker
│   ├── services/       # processing, audit, encryption
│   └── routers/
├── frontend/
├── docker-compose.yml
├── scripts/setup-windows.ps1
└── docs/NFR.md
```
