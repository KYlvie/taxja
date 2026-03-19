"""Application Configuration"""
from typing import List
from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )
    
    # Project
    PROJECT_NAME: str = "Taxja - Austrian Tax Management System"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ENCRYPTION_KEY: str  # AES-256 key
    
    # Database
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    POSTGRES_PORT: int = 5432
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # MinIO/S3
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "taxja-documents"
    MINIO_SECURE: bool = False
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = []
    
    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: str | List[str]) -> List[str]:
        if isinstance(v, str):
            if not v:
                return []
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, list):
            return v
        return []
    
    # LLM / OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # GPT-OSS-120B (self-hosted via vLLM)
    GPT_OSS_ENABLED: bool = False
    GPT_OSS_BASE_URL: str = "http://localhost:8000/v1"
    GPT_OSS_MODEL: str = "openai/gpt-oss-120b"
    GPT_OSS_API_KEY: str = "not-needed"  # vLLM default, set if you configure auth

    # Ollama (local LLM with vision)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"
    OLLAMA_VISION_MODEL: str = "qwen3-vl:8b"
    OLLAMA_ENABLED: bool = False

    # Groq (fast cloud LLM)
    GROQ_ENABLED: bool = False
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    GROQ_FALLBACK_MODEL: str = "openai/gpt-oss-120b"

    # Celery
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""
    
    @property
    def CELERY_BROKER(self) -> str:
        return self.CELERY_BROKER_URL or self.REDIS_URL
    
    @property
    def CELERY_BACKEND(self) -> str:
        return self.CELERY_RESULT_BACKEND or self.REDIS_URL
    
    # Historical Data Import
    HISTORICAL_IMPORT_MAX_FILE_SIZE_MB: int = 50
    HISTORICAL_IMPORT_RETENTION_DAYS: int = 90
    HISTORICAL_IMPORT_MIN_CONFIDENCE: float = 0.7
    HISTORICAL_IMPORT_ENABLE_AUTO_LINK: bool = True

    # Stripe
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PLUS_MONTHLY_PRICE_ID: str = ""
    STRIPE_PLUS_YEARLY_PRICE_ID: str = ""
    STRIPE_PRO_MONTHLY_PRICE_ID: str = ""
    STRIPE_PRO_YEARLY_PRICE_ID: str = ""
    STRIPE_OVERAGE_PRODUCT_ID: str = ""

    # Email / SMTP
    ENABLE_EMAIL_NOTIFICATIONS: bool = False
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = "noreply@taxja.at"
    SMTP_FROM_NAME: str = "Taxja"
    SMTP_USE_TLS: bool = True


settings = Settings()
