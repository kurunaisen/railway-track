import logging



from fastapi import FastAPI, Request

from fastapi.middleware.cors import CORSMiddleware

from fastapi.responses import JSONResponse

from slowapi import Limiter, _rate_limit_exceeded_handler

from slowapi.errors import RateLimitExceeded

from slowapi.util import get_remote_address



from app.config import settings

from app.database import Base, engine

from app.routers import admin, api, auth

from app.startup import seed_default_admin



logger = logging.getLogger(__name__)



# Схема FR 11 — create_all для новых установок

Base.metadata.create_all(bind=engine)



limiter = Limiter(key_func=get_remote_address, default_limits=["200/minute"])



seed_default_admin()



app = FastAPI(

    title="Railway Track Inspection",

    description="Сервис распознавания речевых описаний состояния железнодорожного пути",

    version="4.0.0",

)

app.state.limiter = limiter

app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)



app.add_middleware(

    CORSMiddleware,

    allow_origins=settings.effective_cors_origins,

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

app.include_router(admin.router)





@app.get("/health")

def health():

    return {

        "status": "ok",

        "db_schema": "FR-11",

        "deployment": {

            "database": "Supabase" if settings.is_supabase_db else ("PostgreSQL" if settings.is_postgres else "SQLite"),

            "storage": settings.storage_backend,

            "frontend": "Vercel" if settings.vercel_url else "local",

        },

        "integrations": {

            "yandex_speechkit": bool(settings.yandex_speech_api_key),

            "openai": bool(settings.openai_api_key),

            "anthropic": bool(settings.anthropic_api_key),

        },

        "stack": {

            "frontend": "React + Vite + Tailwind",

            "backend": "Python FastAPI + Pydantic + SQLAlchemy",

            "database": "PostgreSQL" if settings.is_postgres else "SQLite",

            "queue": "Redis + Celery" if settings.use_task_queue else "sync",

            "storage": settings.storage_backend,

            "asr": settings.asr_provider,

        "neural": {
            "asr": {
                "role": "audio_to_text",
                "provider": settings.asr_provider,
                "timestamps": True,
                "recommended": "faster-whisper (local) or yandex (Russian cloud)",
            },
            "llm": {
                "role": "text_to_structure",
                "output": "strict JSON (records/items), not Excel",
                "primary_parser": settings.llm_primary_parser,
                "parser_mode": settings.parser_mode,
                "review_disputed": settings.llm_review_disputed,
                "review_provider": "anthropic" if settings.llm_primary_parser == "openai" else "openai",
            },
        },

            "excel": "pandas + openpyxl",

        },

        "task_queue": settings.use_task_queue,

        "auth_required": settings.auth_required,

    }


