from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/unified_backend"
    SYNC_DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/unified_backend"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "changeme"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # Cloudflare R2
    R2_ENDPOINT_URL: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "doshi-unified-backend-r2-bucket"
    R2_PUBLIC_BASE_URL: str = ""

    # OpenRouter
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    # Email (SMTP)
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Shoot Right"

    # App
    # Comma-separated list of allowed origins, e.g. "https://app.vercel.app,http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"
    GOOGLE_CLIENT_ID: str = ""
    ENVIRONMENT: str = "development"

    # Rate limits
    UPLOAD_RATE_LIMIT: int = 10
    IMPROVEMENT_RATE_LIMIT: int = 3

    # Research Digest
    ARXIV_MAX_RESULTS: int = 50

    # Transcription
    # Model loaded locally via transformers library (no external API needed)
    # Popular options:
    # - "Oriserve/Whisper-Hindi2Hinglish-Swift" (Hindi/Hinglish, recommended)
    # - "openai/whisper-base" (English, smaller, fast)
    # - "openai/whisper-small" (English, larger, more accurate)
    # - "openai/whisper-tiny" (English, very small, very fast)
    TRANSCRIPTION_PROVIDER: str = "local"  # Provider type (currently only "local")
    TRANSCRIPTION_MODEL: str = "Oriserve/Whisper-Hindi2Hinglish-Swift"  # Model to load
    TRANSCRIPTION_MAX_FILE_SIZE_MB: int = 25

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_min_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("SECRET_KEY must be at least 8 characters")
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
