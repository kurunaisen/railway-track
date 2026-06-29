# Деплой: Supabase + Vercel + Railway

Облачная схема для production с **Yandex SpeechKit** (ASR), **ChatGPT** (разбор) и **Claude** (ревью спорных полей).

```
┌─────────────────┐         ┌──────────────────┐
│  Vercel         │  HTTPS  │  Railway         │
│  React SPA      │ ──────► │  FastAPI + ffmpeg│
└────────┬────────┘         └────────┬─────────┘
         │                           │
         │                           ├──► Yandex SpeechKit (ASR)
         │                           ├──► OpenAI API (ChatGPT)
         │                           └──► Anthropic API (Claude)
         │
         └──────────────────────────► Supabase
                                      ├── Postgres (данные)
                                      └── Storage (аудиофайлы)
```

> **Почему API не на Vercel?** Обработка аудио требует ffmpeg, длительных HTTP-запросов (ASR + LLM) и иногда фоновой очереди. Vercel serverless имеет лимит 10–60 с и не поддерживает Whisper/ffmpeg. API размещается на **Railway** (или Render/Fly.io), фронтенд — на **Vercel**.

---

## 1. Supabase

### 1.1 Проект и база

1. Создайте проект на [supabase.com](https://supabase.com).
2. **SQL Editor** → выполните `supabase/migrations/001_schema.sql`.
3. **Connection string** — два способа найти (интерфейс Supabase обновлён):

   **Способ A (проще):** на главной странице проекта нажмите зелёную кнопку **Connect** (вверху). Откроется панель со строками подключения.

   **Способ B:** слева **Project Settings** (иконка шестерёнки) → **Database** → блок **Connection string** / **Connection info**.

4. Для Railway выберите **Transaction pooler** (порт **6543**) — Mode: `Transaction`, Type: `URI`. Скопируйте строку вида:
   ```
   postgresql://postgres.[PROJECT-REF]:[YOUR-PASSWORD]@aws-0-[REGION].pooler.supabase.com:6543/postgres
   ```
5. Замените `[YOUR-PASSWORD]` на пароль БД. Если не помните — **Project Settings → Database → Database password → Reset database password**.
6. Сохраните итоговую строку как `DATABASE_URL` в Railway.

### 1.2 Storage и API-ключи

1. **Storage → New bucket** → имя `audio`, **Private**.
2. **Project URL** и **service_role key**:

   **Способ A:** слева внизу **Project Settings** (шестерёнка) → **API** (или **Data API** в новом интерфейсе).

   **Способ B:** кнопка **Connect** на главной странице проекта → вкладка с API / App frameworks.

3. Скопируйте:

   | В Dashboard | В `.env` (Railway) |
   |-------------|-------------------|
   | **Project URL** (например `https://abcdefgh.supabase.co`) | `SUPABASE_URL` |
   | **service_role** key (Secret, не anon!) | `SUPABASE_SERVICE_ROLE_KEY` |

   > **service_role** даёт полный доступ — только на бэкенде (Railway), никогда не вставляйте во фронтенд/Vercel.

4. Если в интерфейсе два раздела ключей: **Legacy API Keys** или **API Keys** — service_role обычно в Legacy или помечен как `service_role` / Secret.

---

## 2. API-ключи нейросетей

| Сервис | Переменная | Где получить |
|--------|-----------|--------------|
| Yandex SpeechKit | `YANDEX_SPEECH_API_KEY`, `YANDEX_SPEECH_FOLDER_ID` | [Yandex Cloud](https://cloud.yandex.ru/docs/speechkit/) |
| ChatGPT | `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com/) |
| Claude | `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) |

Рекомендуемые настройки (уже в `.env.cloud.example`):

```env
ASR_PROVIDER=yandex
PARSER_MODE=hybrid
LLM_PRIMARY_PARSER=openai
LLM_REVIEW_DISPUTED=true
```

---

## 3. Railway (бэкенд) — пошагово для первого раза

> **Перед Railway** должны быть готовы: проект Supabase, выполнен SQL из `supabase/migrations/001_schema.sql`, bucket `audio`, скопированы `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`.

> **Код на GitHub:** Railway деплоит из репозитория. Если проект только на компьютере — сначала создайте репозиторий на GitHub и запушьте код (`git push`).

---

### Шаг 3.1. Регистрация и вход

1. Откройте [railway.app](https://railway.app).
2. Нажмите **Login** → **Continue with GitHub**.
3. Разрешите Railway доступ к GitHub (Authorize).

---

### Шаг 3.2. Создать проект из GitHub

1. На главной Railway нажмите **+ New Project** (или **Create a New Project**).
2. Выберите **Deploy from GitHub repo**.
3. Если GitHub ещё не подключён — нажмите **Configure GitHub App** и дайте доступ к репозиторию с проектом Railway.
4. В списке репозиториев найдите **Railway** (или как называется ваш репо) и нажмите на него.
5. Railway создаст сервис и начнёт первую сборку — пока **не ждите успеха**, сначала настроим папку и переменные.

---

### Шаг 3.3. Указать папку `backend`

1. Откроется страница сервиса (карточка с названием репозитория).
2. Перейдите на вкладку **Settings** (вверху).
3. Прокрутите до блока **Source** (или **Root Directory** / **Service Root**).
4. В поле **Root Directory** введите: `backend`
5. Нажмите **Save** или галочку — Railway пересоберёт проект из папки `backend` (там лежат `Dockerfile` и `railway.toml`).

---

### Шаг 3.4. Добавить переменные окружения

1. На той же странице сервиса откройте вкладку **Variables** (слева или сверху).
2. Нажмите **+ New Variable** или **Raw Editor** (удобнее вставить всё сразу).
3. Добавьте переменные **по одной** (имя = слева, значение = справа). Шаблон — файл `backend/.env.cloud.example` в репозитории.

#### Обязательные переменные (заполните своими значениями)

| Имя переменной | Откуда взять значение |
|----------------|----------------------|
| `DATABASE_URL` | Supabase → **Connect** → Transaction pooler, порт **6543** → URI. Вставьте пароль вместо `[YOUR-PASSWORD]`. |
| `STORAGE_BACKEND` | Буквально: `supabase` |
| `SUPABASE_URL` | Supabase → **Project Settings** → **API** → **Project URL** |
| `SUPABASE_SERVICE_ROLE_KEY` | Там же → ключ **service_role** (Secret) |
| `SUPABASE_STORAGE_BUCKET` | Буквально: `audio` |
| `ASR_PROVIDER` | Буквально: `yandex` |
| `YANDEX_SPEECH_API_KEY` | Yandex Cloud → API-ключ SpeechKit |
| `YANDEX_SPEECH_FOLDER_ID` | Yandex Cloud → ID каталога (folder) |
| `PARSER_MODE` | `hybrid` |
| `LLM_PRIMARY_PARSER` | `openai` |
| `OPENAI_API_KEY` | platform.openai.com → API Keys |
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys |
| `LLM_REVIEW_DISPUTED` | `true` |
| `AUTH_REQUIRED` | `true` |
| `SECRET_KEY` | Случайная строка 32+ символов (см. ниже) |
| `DATA_ENCRYPTION_KEY` | Ещё одна случайная строка 32+ символов |
| `ENCRYPT_TRANSCRIPTS` | `true` |
| `USE_TASK_QUEUE` | `false` |
| `TRUST_PROXY_HEADERS` | `true` |
| `MAX_UPLOAD_MB` | `100` |

#### Сгенерировать SECRET_KEY на Windows (PowerShell)

```powershell
-join ((48..57 + 97..122 | Get-Random -Count 64 | ForEach-Object {[char]$_}))
```

Запустите команду **два раза** — первый результат → `SECRET_KEY`, второй → `DATA_ENCRYPTION_KEY`.

#### Пароль админа (рекомендуется)

| Имя | Значение |
|-----|----------|
| `DEFAULT_ADMIN_USERNAME` | `admin` |
| `DEFAULT_ADMIN_PASSWORD` | Придумайте свой сложный пароль |

4. После добавления всех переменных Railway **автоматически перезапустит** деплой.

---

### Шаг 3.5. Дождаться успешной сборки

1. Откройте вкладку **Deployments**.
2. Кликните на последний деплой → смотрите **Build Logs** и **Deploy Logs**.
3. Успех: в логах что-то вроде `Application startup complete` / `Uvicorn running`.
4. Если **Failed** — прокрутите лог вниз, частые причины:
   - неверный `DATABASE_URL` (опечатка в пароле);
   - Supabase SQL ещё не выполнен;
   - не задан `SUPABASE_URL` или `SUPABASE_SERVICE_ROLE_KEY`.

---

### Шаг 3.6. Получить публичный URL

1. Вкладка **Settings** → блок **Networking** (или **Public Networking**).
2. Нажмите **Generate Domain** (или **Add Public Domain**).
3. Railway выдаст URL, например: `https://railway-track-production.up.railway.app`
4. **Скопируйте его** — понадобится для Vercel (`VITE_API_URL`) и для проверки.

---

### Шаг 3.7. Проверить, что API работает

1. Откройте в браузере: `https://ВАШ-URL.up.railway.app/health`
2. Должен открыться JSON, например:

```json
{
  "status": "ok",
  "integrations": {
    "yandex_speechkit": true,
    "openai": true,
    "anthropic": true
  }
}
```

3. Если `"status": "ok"` — бэкенд жив.
4. Если `integrations` показывает `false` — ключ API для этого сервиса не задан или пустой в Variables.
5. Если страница не открывается — проверьте Deployments (деплой упал) или домен не сгенерирован.

---

### Шаг 3.8. Пользователи для входа

При **первом** успешном запуске с пустой базой Supabase создаются пользователи:

| Логин | Пароль по умолчанию | Роль |
|-------|---------------------|------|
| `admin` | `admin` (или ваш `DEFAULT_ADMIN_PASSWORD`) | админ |
| `operator` | `operator` | оператор |
| `viewer` | `viewer` | просмотр |

> Обязательно задайте `DEFAULT_ADMIN_PASSWORD` в Variables **до первого деплоя**, иначе останется пароль `admin`.

---

### Шаг 3.9. После деплоя Vercel (CORS)

Когда получите URL сайта на Vercel, вернитесь в Railway → **Variables** и добавьте:

```
VERCEL_URL=https://ваш-сайт.vercel.app
CORS_ORIGINS=["https://ваш-сайт.vercel.app"]
```

Сохраните — Railway перезапустится.

---

## 4. Vercel (фронтенд)

1. [vercel.com](https://vercel.com) → **Import Git Repository**.
2. **Root Directory** = `frontend`.
3. **Environment Variables**:

| Переменная | Значение |
|-----------|----------|
| `VITE_API_URL` | `https://YOUR-BACKEND.up.railway.app` (без `/api`) |

4. Deploy.

5. В Railway добавьте URL Vercel:

```env
VERCEL_URL=https://your-app.vercel.app
CORS_ORIGINS=["https://your-app.vercel.app"]
```

---

## 5. Проверка end-to-end

1. Откройте сайт на Vercel.
2. Войдите (admin / пароль из env).
3. Загрузите WAV/MP3 → «Обработать».
4. Дождитесь таблицы и скачайте Excel.

Если загрузка не работает — DevTools → Network: `POST .../api/upload` должен идти на Railway URL, не на Vercel.

---

## 6. Опционально: фоновая очередь

Для длинных аудио включите Celery + Redis (например [Upstash](https://upstash.com)):

```env
USE_TASK_QUEUE=true
REDIS_URL=rediss://default:...@....upstash.io:6379
```

На Railway добавьте второй сервис **Worker** с той же переменной окружения:

```bash
celery -A app.tasks.celery_app worker --loglevel=info --concurrency=1
```

---

## Локальная разработка с облачными API

```powershell
# backend/.env
DATABASE_URL=postgresql://...pooler.supabase.com:6543/postgres
STORAGE_BACKEND=supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
ASR_PROVIDER=yandex
YANDEX_SPEECH_API_KEY=...
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
AUTH_REQUIRED=false

# frontend/.env.local
VITE_API_URL=http://127.0.0.1:8000
```

```powershell
cd backend && uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

---

## Файлы конфигурации

| Файл | Назначение |
|------|-----------|
| `backend/.env.cloud.example` | Шаблон env для Railway |
| `frontend/.env.example` | `VITE_API_URL` для Vercel |
| `frontend/vercel.json` | Настройки сборки Vite |
| `backend/railway.toml` | Healthcheck Railway |
| `supabase/migrations/001_schema.sql` | Схема БД FR-11 |
