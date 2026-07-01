import logging
import os

from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler

from slowapi.errors import RateLimitExceeded

from slowapi.util import get_remote_address



from app.config import settings

from app.database import Base, engine

from app.routers import admin, api, auth

from app.startup import run_schema_migrations, seed_default_admin



logger = logging.getLogger(__name__)



# Схема FR 11 — create_all для новых установок

Base.metadata.create_all(bind=engine)

run_schema_migrations()

limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])



seed_default_admin()



app = FastAPI(

    title="Railway Track Inspection",

    description="Сервис распознавания речевых описаний состояния железнодорожного пути",

    version="4.0.0",

)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)[:500]})



app.add_middleware(

    CORSMiddleware,

    allow_origins=settings.effective_cors_origins,

    allow_origin_regex=(
        r"https://[\w-]+\.vercel\.app" if settings.cors_allow_vercel_domains else None
    ),

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"],

)





@app.middleware("http")

async def security_headers(request: Request, call_next):

    response = await call_next(request)

    response.headers["X-Content-Type-Options"] = "nosniff"

    response.headers["X-Frame-Options"] = "DENY"

    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    return response





app.include_router(auth.router)

app.include_router(api.router)

from app.routers import railway as railway_router

app.include_router(railway_router.router, prefix="/api")

app.include_router(admin.router)





def _env_present(name: str) -> bool:
    return bool(str(os.environ.get(name, "")).strip())


@app.get("/health")

def health():

    return {

        "status": "ok",

        "db_schema": "FR-11",

        "deployment": {

            "database": "Supabase" if settings.is_supabase_db else ("PostgreSQL" if settings.is_postgres else "SQLite"),

            "storage": settings.storage_backend,

            "frontend": "Vercel" if settings.vercel_url else "local",

            "cors_vercel_regex": settings.cors_allow_vercel_domains,

            "cors_origins_count": len(settings.effective_cors_origins),

        },

        "integrations": {

            "yandex_speechkit": bool(
                settings.yandex_speech_api_key or settings.yandex_sa_authorized_key
            ),

            "openai": bool(settings.openai_api_key),

        },

        "env_present": {

            "ASR_PROVIDER": _env_present("ASR_PROVIDER"),

            "YANDEX_SPEECH_API_KEY": _env_present("YANDEX_SPEECH_API_KEY"),

            "YANDEX_SA_AUTHORIZED_KEY": _env_present("YANDEX_SA_AUTHORIZED_KEY"),

            "YANDEX_SPEECH_FOLDER_ID": _env_present("YANDEX_SPEECH_FOLDER_ID"),

            "OPENAI_API_KEY": _env_present("OPENAI_API_KEY"),

            "OPENAI_API_KEY": _env_present("OPENAI_API_KEY"),

            "DATABASE_URL": _env_present("DATABASE_URL"),

            "STORAGE_BACKEND": _env_present("STORAGE_BACKEND"),

            "SUPABASE_URL": _env_present("SUPABASE_URL"),

        },

        "stack": {

            "frontend": "React + Vite + Tailwind",

            "backend": "Python FastAPI + Pydantic + SQLAlchemy",

            "database": "PostgreSQL" if settings.is_postgres else "SQLite",

            "queue": "Redis + Celery" if settings.use_task_queue else "sync",

            "storage": settings.storage_backend,

            "asr": "yandex",

        "railway_pipeline": {
            "version": "v2",
            "asr": "yandex",
            "llm_provider": settings.llm_provider,
            "steps": ["upload", "transcribe", "edit_transcript", "extract", "preview", "export"],
        },

        "neural": {
            "asr": {
                "role": "audio_to_text",
                "provider": "yandex",
                "timestamps": True,
            },
            "llm": {
                "role": "transcript_to_railway_rows",
                "output": "strict JSON RailwayRow[]",
                "provider": settings.llm_provider,
            },
        },

            "excel": "pandas + openpyxl",

        },

        "task_queue": settings.use_task_queue,

        "auth_required": settings.auth_required,

    }


