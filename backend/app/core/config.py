"""Application Configuration"""
import logging
import secrets
from typing import List
from urllib.parse import urlparse
from pydantic import AnyHttpUrl, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


def _frontend_host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").strip().lower()
    except Exception:
        return ""


def _is_local_frontend(url: str) -> bool:
    return _frontend_host(url) in {"localhost", "127.0.0.1", "0.0.0.0"}


def _is_production_frontend(url: str) -> bool:
    return _frontend_host(url) in {"taxja.at", "www.taxja.at"}


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
    
    # Frontend URL (used in verification emails, password reset links)
    FRONTEND_URL: str = "http://localhost:5173"

    # Google Sign-In (web client ID used by Google Identity Services)
    GOOGLE_CLIENT_ID: str = ""

    # Security
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ENCRYPTION_KEY: str  # AES-256 key

    # Cookie settings
    COOKIE_DOMAIN: str = ".taxja.at"  # Covers taxja.at + subdomains (e.g. api.taxja.at)
    COOKIE_SECURE: bool = True        # HTTPS only — required for production
    COOKIE_SAMESITE: str = "lax"      # "lax" for access, "strict" for refresh
    COOKIE_PATH: str = "/api/v1"

    # CSRF
    CSRF_SECRET_KEY: str = ""

    # Token blacklist TTL (>= refresh token expiry)
    TOKEN_BLACKLIST_TTL_SECONDS: int = 604800  # 7 days

    # Debug mode (controls Swagger docs visibility)
    DEBUG: bool = True

    # Metrics endpoint authentication
    METRICS_SECRET: str = ""

    # Trusted host validation (comma-separated string, parsed via property)
    ALLOWED_HOSTS: str = "*"

    @field_validator("SECRET_KEY", mode="before")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            generated = secrets.token_urlsafe(64)
            logger.warning(
                "SECRET_KEY is missing or too short — generated a random key. "
                "Set SECRET_KEY in .env for production."
            )
            return generated
        return v

    @field_validator("CSRF_SECRET_KEY", mode="before")
    @classmethod
    def validate_csrf_secret_key(cls, v: str) -> str:
        if not v or len(v) < 32:
            generated = secrets.token_urlsafe(64)
            logger.warning(
                "CSRF_SECRET_KEY is missing or too short — generated a random key. "
                "Set CSRF_SECRET_KEY in .env for production."
            )
            return generated
        return v

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug_value(cls, v):
        if isinstance(v, str):
            normalized = v.strip().lower()
            if normalized in {"release", "prod", "production"}:
                return False
            if normalized in {"debug", "dev", "development"}:
                return True
        return v

    @property
    def allowed_hosts_list(self) -> List[str]:
        """Parse ALLOWED_HOSTS comma-separated string into a list."""
        if not self.ALLOWED_HOSTS or self.ALLOWED_HOSTS.strip() == "*":
            return ["*"]
        return [h.strip() for h in self.ALLOWED_HOSTS.split(",")]
    
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
    OPENAI_VISION_MODEL: str = ""
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-opus-4-1-20250805"
    ANTHROPIC_VISION_MODEL: str = "claude-opus-4-1-20250805"

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
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_VISION_MODEL: str = "meta-llama/llama-4-scout-17b-16e-instruct"
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
    SENSITIVE_DOCUMENT_MODE: str = ""
    CONTRACT_ROLE_MODE: str = "legacy"

    @field_validator("SENSITIVE_DOCUMENT_MODE", mode="before")
    @classmethod
    def normalize_sensitive_document_mode(cls, v: str) -> str:
        if v is None:
            return ""
        mode = str(v).strip().lower()
        if not mode:
            return ""
        if mode not in {"legacy", "shadow", "strict"}:
            logger.warning(
                "Unsupported SENSITIVE_DOCUMENT_MODE '%s' - ignoring value.",
                v,
            )
            return ""
        return mode

    @field_validator("CONTRACT_ROLE_MODE", mode="before")
    @classmethod
    def normalize_contract_role_mode(cls, v: str) -> str:
        mode = (v or "legacy").strip().lower()
        if mode not in {"legacy", "shadow", "strict"}:
            logger.warning(
                "Unsupported CONTRACT_ROLE_MODE '%s' - falling back to 'legacy'.",
                v,
            )
            return "legacy"
        return mode

    @model_validator(mode="after")
    def apply_environment_safety_defaults(self):
        is_local_frontend = _is_local_frontend(self.FRONTEND_URL)

        # Local development should not inherit production cookie defaults unless
        # they were intentionally overridden in the environment.
        if is_local_frontend:
            if "COOKIE_DOMAIN" not in self.model_fields_set and self.COOKIE_DOMAIN == ".taxja.at":
                self.COOKIE_DOMAIN = ""
            if "COOKIE_SECURE" not in self.model_fields_set and self.COOKIE_SECURE is True:
                self.COOKIE_SECURE = False

        if self.DEBUG and _is_production_frontend(self.FRONTEND_URL):
            logger.warning(
                "DEBUG/local backend is configured with production FRONTEND_URL '%s'. "
                "Verification and reset links will point to production.",
                self.FRONTEND_URL,
            )

        if self.DEBUG and self.ENABLE_EMAIL_NOTIFICATIONS and _is_production_frontend(self.FRONTEND_URL):
            logger.warning(
                "Email notifications are enabled while DEBUG is on and FRONTEND_URL points to production. "
                "Local registrations may send production links.",
            )

        return self

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

    # Contact form
    CONTACT_EMAIL: str = "office@oohk.com"


settings = Settings()
