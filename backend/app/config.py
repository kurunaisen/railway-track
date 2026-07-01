from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Role = Literal["admin", "operator", "viewer"]
StorageBackend = Literal["local", "s3", "supabase"]
AsrProvider = Literal["faster-whisper", "yandex"]
ParserMode = Literal["regex", "openai", "hybrid", "narrative"]
LlmPrimaryParser = Literal["openai", "anthropic"]
TableExportMode = Literal["evidenceOnly", "normsEnriched"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Database (PostgreSQL recommended for production) ──
    database_url: str = "sqlite:///./railway.db"

    # ── File storage (local | MinIO/S3) ──
    storage_backend: StorageBackend = "local"
    upload_dir: Path = Path("uploads")
    s3_endpoint: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""
    s3_bucket: str = "railway-audio"
    s3_region: str = "us-east-1"
    s3_use_ssl: bool = True

    # ── Supabase (Postgres + Storage для Vercel/Railway) ──
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "audio"

    # ── ASR (FR 15.1): faster-whisper локально или Yandex SpeechKit для русского ──
    asr_provider: AsrProvider = "faster-whisper"
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    yandex_speech_api_key: str = ""
    yandex_speech_folder_id: str = ""
    # JSON авторизованного ключа SA (рекомендуется вместо API-key для SpeechKit)
    yandex_sa_authorized_key: str = ""

    # ── LLM (FR 15.2–15.3): текст → строгий JSON, не Excel ──
    parser_mode: ParserMode = "hybrid"
    llm_primary_parser: LlmPrimaryParser = "openai"  # openai=ChatGPT | anthropic=Claude (A/B)
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"
    llm_review_disputed: bool = True  # Claude ревью при openai primary (и наоборот в A/B)

    # ── Security ──
    secret_key: str = Field(default="CHANGE-ME-in-production-use-openssl-rand-hex-32")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480
    auth_required: bool = True
    encrypt_transcripts: bool = True
    data_encryption_key: str = Field(default="")

    default_admin_username: str = "admin"
    default_admin_password: str = "admin"
    admin_password_reset: str = ""  # если задан — перезаписать пароль admin при старте (см. docs)

    # ── Task queue (Redis + Celery) ──
    use_task_queue: bool = False
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = ""
    celery_result_backend: str = ""

    # ── Deployment ──
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    vercel_url: str = ""  # https://your-app.vercel.app — добавляется в CORS автоматически
    cors_allow_vercel_domains: bool = True  # разрешить https://*.vercel.app (деплой на Vercel)
    trust_proxy_headers: bool = False
    max_upload_mb: int = 100

    # ── Нормы 2288р: макс. скорость на обслуживаемых участках (км/ч).
    # Лимит из инструкции выше этого значения не записывается — по участку и так не быстрее.
    max_track_speed_kmh: int = 80
    # Подстановка неисправности/V огр. по 2288р/436/р после ASR (не для таблицы обхода).
    apply_track_norms_on_save: bool = False
    # Таблицы 2288р/436/р в системном промпте LLM (иначе модель подставляет «уширение колеи» и V огр.).
    include_norms_in_llm_prompt: bool = False
    # evidenceOnly — только явный ASR-сегмент; normsEnriched — нормы 2288р в таблице
    table_export_mode: TableExportMode = "evidenceOnly"

    @field_validator("vercel_url", mode="before")
    @classmethod
    def strip_vercel_url(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator(
        "yandex_speech_api_key",
        "yandex_speech_folder_id",
        "openai_api_key",
        "anthropic_api_key",
        mode="before",
    )
    @classmethod
    def strip_secret(cls, v):
        if isinstance(v, str):
            return v.strip()
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [o.strip() for o in v.split(",") if o.strip()]
        return v

    # ── Preprocessing ──
    split_on_silence: bool = True
    silence_split_min_duration: float = 120.0

    @property
    def broker_url(self) -> str:
        return self.celery_broker_url or self.redis_url

    @property
    def result_backend(self) -> str:
        return self.celery_result_backend or self.redis_url

    @property
    def is_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def is_supabase_db(self) -> bool:
        return "supabase" in self.database_url

    @property
    def effective_cors_origins(self) -> list[str]:
        origins = list(self.cors_origins)
        if self.vercel_url and self.vercel_url not in origins:
            origins.append(self.vercel_url.rstrip("/"))
        return origins


settings = Settings()
# Рабочая папка для ffmpeg (конвертация WAV) нужна при любом STORAGE_BACKEND.
settings.upload_dir.mkdir(parents=True, exist_ok=True)
