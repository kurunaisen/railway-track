# Нефункциональные требования (NFR)

## Матрица соответствия

| Требование | Реализация |
|------------|------------|
| **Работа через браузер** | React SPA, запись с микрофона (MediaRecorder), загрузка файлов |
| **Windows у пользователей** | `scripts/setup-windows.ps1`, PowerShell-инструкции, пути через `pathlib`, Celery `--pool=solo` |
| **Серверная обработка аудио** | Конвертация ffmpeg + Whisper + парсер только на backend (`processing.py`) |
| **Локальное / облачное развёртывание** | Локально: uvicorn + npm; облако: `docker-compose.yml` (api, worker, redis, frontend/nginx) |
| **Масштабируемость (очередь)** | Celery + Redis, `USE_TASK_QUEUE=true`, воркеры `--concurrency=N`, API `GET /api/jobs/{id}` |
| **Аудит действий** | Таблица `audit_logs`, `GET /api/admin/audit` (admin), логирование upload/process/edit/export/login |
| **Разграничение ролей** | JWT + роли `admin` / `operator` / `viewer`, проверка в `auth/deps.py` |
| **Защита данных** | bcrypt, JWT, Fernet-шифрование расшифровок, security headers, rate limit, лимит размера файла |

## Роли

| Роль | Права |
|------|-------|
| **admin** | Всё + аудит + список пользователей |
| **operator** | Загрузка, обработка, редактирование, сохранение, подтверждение |
| **viewer** | Просмотр сессий и экспорт Excel |

## Развёртывание

### Windows (разработка)
```powershell
.\scripts\setup-windows.ps1
# backend\.env: AUTH_REQUIRED=false, USE_TASK_QUEUE=false
```

### Docker (production / cloud)
```powershell
# Задать секреты:
# SECRET_KEY, DATA_ENCRYPTION_KEY, DEFAULT_ADMIN_PASSWORD
docker compose up -d
```

### Масштабирование воркеров
```powershell
docker compose up -d --scale worker=3
```

На Windows для локального воркера:
```powershell
celery -A app.tasks.celery_app worker --pool=solo --loglevel=info
```

## Безопасность (checklist production)

1. Сменить `SECRET_KEY` и `DEFAULT_ADMIN_PASSWORD`
2. Сгенерировать `DATA_ENCRYPTION_KEY` (Fernet)
3. Включить `AUTH_REQUIRED=true`, `ENCRYPT_TRANSCRIPTS=true`
4. HTTPS через reverse proxy (nginx/Traefik)
5. Ограничить `CORS_ORIGINS` доменом организации
6. `TRUST_PROXY_HEADERS=true` за балансировщиком

## Генерация ключа шифрования

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
