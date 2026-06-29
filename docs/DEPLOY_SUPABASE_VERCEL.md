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

## 2. API-ключи Yandex SpeechKit (проверено по док. Yandex Cloud, июнь 2026)

Официальные инструкции:
- [Создание API-ключа](https://yandex.cloud/ru/docs/iam/operations/api-key/create)
- [ID каталога](https://yandex.cloud/ru/docs/resource-manager/operations/folder/get-id)
- [Назначение роли](https://yandex.cloud/ru/docs/iam/operations/roles/grant)
- [Роль SpeechKit STT](https://yandex.cloud/ru/docs/speechkit/security/)

Нужны две переменные для Railway: `YANDEX_SPEECH_API_KEY` и `YANDEX_SPEECH_FOLDER_ID`.

---

### 2.1. Войти в консоль

1. Откройте **https://console.yandex.cloud/**
2. Войдите через **Яндекс ID**
3. **Проверка:** видите дашборд с названием облака/каталога вверху

Если просит платёжный аккаунт — создайте его (Billing → статус `ACTIVE` или `TRIAL_ACTIVE`).

---

### 2.2. Получить `YANDEX_SPEECH_FOLDER_ID`

**Способ A — из адресной строки (самый надёжный):**

1. Вверху страницы нажмите на **название каталога** (например `default`) и выберите каталог, в котором будете работать
2. Посмотрите URL в браузере — он станет таким:
   ```
   https://console.yandex.cloud/folders/b1gxxxxxxxxxxxxxxxxxx
   ```
3. Часть после `/folders/` — это **ID каталога** → `YANDEX_SPEECH_FOLDER_ID`

**Способ B — на дашборде (по док. Yandex):**

1. Выберите каталог (см. выше)
2. На главной странице каталога **под названием каталога** показан идентификатор — наведите и нажмите иконку копирования

**Способ C — «Информация о каталоге»:**

1. Справа от названия каталога → **⋮** (три точки) → **Информация о каталоге**
2. Поле **Идентификатор каталога** → скопировать

**Проверка:** ID начинается с `b1` и ~20 символов, например `b1g2abc3def4ghi5jkl6m`

---

### 2.3. Создать сервисный аккаунт

1. Убедитесь, что вверху выбран **нужный каталог**
2. Слева откройте меню **≡** → **Identity and Access Management**  
   (в русской консоли может называться так же, на английском)
3. Слева в IAM: **Сервисные аккаунты**
4. Кнопка **Создать сервисный аккаунт**
5. Имя: `speechkit-railway` (латиница, 3–63 символа)
6. **Добавить роль** → выберите **`speechkit-stt.user`** или полное имя **`ai.speechkit-stt.user`**
7. **Создать**

**Проверка:** в списке «Сервисные аккаунты» появилась строка `speechkit-railway`

> Если роли нет при создании — назначьте отдельно (шаг 2.4).

---

### 2.4. Роль `ai.speechkit-stt.user` (если не назначили)

По [док. Yandex](https://yandex.cloud/ru/docs/iam/operations/roles/grant):

1. Вверху выберите **каталог**
2. Вкладка **Права доступа**
3. **Настроить доступ**
4. Найдите сервисный аккаунт `speechkit-railway`
5. **Добавить роль** → **`ai.speechkit-stt.user`**
6. **Сохранить**

---

### 2.5. Создать `YANDEX_SPEECH_API_KEY`

По [док. Yandex](https://yandex.cloud/ru/docs/iam/operations/api-key/create):

1. **Identity and Access Management** → **Сервисные аккаунты**
2. Откройте **`speechkit-railway`**
3. Вверху: **Создать новый ключ** → **Создать API-ключ**
4. Описание: `railway-backend`
5. **Область действия** — отметьте минимум:
   - **`yc.ai.speechkitStt.execute`** (распознавание речи)
6. **Создать**
7. **Сразу скопируйте секретный ключ** (начинается с `AQVN...`) — после закрытия окна его не покажут

→ это значение для `YANDEX_SPEECH_API_KEY`

**Не путайте:**
- ✅ **API-ключ** сервисного аккаунта (`AQVN...`)
- ❌ OAuth-токен пользователя
- ❌ IAM-токен (живёт ~12 часов)

---

### 2.6. Записать в Railway

| Variable | Пример |
|----------|--------|
| `ASR_PROVIDER` | `yandex` |
| `YANDEX_SPEECH_FOLDER_ID` | `b1gxxxxxxxxxxxxxxxxxx` |
| `YANDEX_SPEECH_API_KEY` | `AQVNxxxxxxxx...` |

**Redeploy** → проверка: `https://ВАШ-BACKEND/health` → `"yandex_speechkit": true`

---

## 2b. ChatGPT и Claude (кратко)

| Сервис | Variable | Где |
|--------|----------|-----|
| ChatGPT | `OPENAI_API_KEY` | https://platform.openai.com/api-keys |
| Claude | `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |

```env
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

### Шаг 3.3. Папка `backend` (два способа)

Railway часто **не показывает** Root Directory, если вы смотрите настройки **всего проекта**, а не **одного сервиса**. Есть два рабочих варианта.

---

#### Способ 1 — проще: ничего не менять (рекомендуется)

В корне репозитория лежит **`Dockerfile`** — он собирает бэкенд из папки `backend`.  
Root Directory **не нужен**.

1. Убедитесь, что на GitHub в репо есть файл **`Dockerfile`** в корне (не только в `backend/`).
2. Railway сам найдёт его и соберёт API.

Если деплой уже идёт из GitHub — просто дождитесь сборки или нажмите **Redeploy**.

---

#### Способ 2 — Root Directory (если хотите использовать `backend/Dockerfile`)

1. На главной странице проекта Railway вы видите **схему** (прямоугольник с названием репозитория, например `railway-track`).
2. **Кликните по этому прямоугольнику** (это сервис, не проект).
3. Откроется панель сервиса → вкладка **Settings**.
4. Прокрутите до раздела **Build** (не «Project Settings» слева в меню!).
5. Поле **Root Directory** → введите `backend` (можно с `/` или без).
6. Нажмите **Deploy** или галочку сохранения.

**Если Root Directory нет даже там:**

- **Settings** → **Variables** → добавьте:
  ```
  RAILWAY_DOCKERFILE_PATH=backend/Dockerfile
  ```
- И **Root Directory** оставьте пустым или `/`.

---

#### Как понять, что вы не там

| Где вы | Что видите | Это не то |
|--------|------------|-----------|
| Шестерёнка **Project Settings** (слева в проекте) | Members, Usage, Danger | Root Directory здесь **нет** |
| **Клик по сервису** → Settings | Build, Source, Networking | **Здесь** ищите Root Directory |

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

## 4. Vercel (фронтенд — сайт в браузере) — пошагово

> **Что это:** Vercel публикует **интерфейс** (кнопки, формы). **API** остаётся на Railway.  
> **Перед Vercel** нужен работающий бэкенд на Railway (шаг 3) и код на GitHub.

---

### Шаг 4.0. Что должно быть готово

- [ ] Код на GitHub (репозиторий `railway-track` или ваш)
- [ ] Railway: деплой **успешный** (Deployments → зелёная галочка)
- [ ] Railway: есть **публичный URL** бэкенда (см. ниже)

#### Как получить URL бэкенда на Railway

1. Откройте [railway.app](https://railway.app) → ваш проект
2. Кликните **сервис** (прямоугольник с названием репо)
3. Вкладка **Settings** → блок **Networking**
4. Если домена нет → **Generate Domain**
5. Скопируйте URL, например:
   ```
   https://railway-track-production.up.railway.app
   ```
6. Проверка в браузере: откройте `https://ВАШ-URL/health` → JSON `"status": "ok"`

**Запишите этот URL** — он понадобится как `VITE_API_URL`.

---

### Шаг 4.1. Регистрация на Vercel

1. Откройте **https://vercel.com**
2. **Sign Up** → **Continue with GitHub**
3. Разрешите Vercel доступ к GitHub (Authorize)

---

### Шаг 4.2. Импорт проекта

1. На главной Vercel нажмите **Add New…** → **Project**
2. В списке **Import Git Repository** найдите **`railway-track`**
   - если нет → **Adjust GitHub App Permissions** → дайте доступ к репозиторию
3. Нажмите **Import** напротив `railway-track`

---

### Шаг 4.3. Настройки сборки (важно)

На странице **Configure Project**:

| Поле | Значение |
|------|----------|
| **Framework Preset** | Vite (обычно определится сам) |
| **Root Directory** | нажмите **Edit** → введите `frontend` → **Continue** |
| **Build Command** | оставить `npm run build` |
| **Output Directory** | `dist` |

---

### Шаг 4.4. Переменная окружения (связь с Railway)

Раскройте **Environment Variables** и добавьте:

| Name | Value |
|------|-------|
| `VITE_API_URL` | `https://ВАШ-BACKEND.up.railway.app` |

**Важно:**
- вставьте **ваш** Railway URL из шага 4.0
- **без** `/api` в конце
- **без** слэша в конце

Пример:
```
VITE_API_URL=https://railway-track-production.up.railway.app
```

Environment: **Production** (и можно дублировать для Preview).

---

### Шаг 4.5. Деплой

1. Нажмите **Deploy**
2. Подождите 1–3 минуты (Building → Ready)
3. **Проверка:** появится **Congratulations** и ссылка вида:
   ```
   https://railway-track-xxxxx.vercel.app
   ```
4. Нажмите **Visit** — откроется сайт «Обход пути»

Если сборка **Failed** → **View Build Logs** → пришлите текст ошибки.

---

### Шаг 4.6. CORS на Railway (после Vercel)

Без этого шага браузер **блокирует** запросы с Vercel к Railway.

1. Скопируйте URL сайта с Vercel, например:
   ```
   https://railway-track-xxxxx.vercel.app
   ```
2. Откройте [railway.app](https://railway.app) → ваш проект → **сервис бэкенда**
3. Вкладка **Variables**
4. Добавьте **две** переменные:

| Name | Value |
|------|-------|
| `VERCEL_URL` | `https://railway-track-xxxxx.vercel.app` |
| `CORS_ORIGINS` | `["https://railway-track-xxxxx.vercel.app"]` |

5. Подставьте **ваш** Vercel URL (как в шаге 4.5)
6. Сохраните — Railway **сам перезапустит** бэкенд (1–2 мин)

**Проверка CORS:** откройте сайт Vercel → F12 → Network → загрузите файл.  
Запрос `upload` должен идти на `....railway.app`, статус **200**, не CORS error.

---

### Шаг 4.7. Вход на сайт

1. Откройте URL Vercel
2. Логин: `admin`
3. Пароль: тот, что задали в Railway как `DEFAULT_ADMIN_PASSWORD`  
   (если не задавали — по умолчанию `admin`)

---

### Если меняли `VITE_API_URL` после деплоя

Переменные `VITE_*` вшиваются **при сборке**. После изменения:

1. Vercel → проект → **Deployments**
2. **⋯** у последнего деплоя → **Redeploy**

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
