"""FastAPI Application Entry Point"""
from contextlib import asynccontextmanager
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.error_handlers import setup_error_handlers
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.cache import cache
from app.core.rate_limiter import rate_limit, rate_limiter
from app.api.v1.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    try:
        await cache.connect()
        await rate_limiter.connect()
        print("[OK] Cache and rate limiter connected")
    except Exception as e:
        print(f"[WARN] Cache/rate limiter connection failed (Redis not running?): {e}")
        print("[OK] Continuing without cache — app will work, just slower")

    # Keep startup fast and reliable in local/dev environments.
    # The vector DB and embedding model are lazily initialized on first use.
    print("[OK] Vector DB pre-load skipped — will initialize lazily on demand")

    yield
    
    # Shutdown
    try:
        await cache.disconnect()
        await rate_limiter.disconnect()
        print("[OK] Cache and rate limiter disconnected")
    except Exception:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
    docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
    redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Setup global error handlers
setup_error_handlers(app)

# Security headers middleware (should be first)
app.add_middleware(SecurityHeadersMiddleware)

# Trusted host middleware (prevent host header attacks)
if settings.allowed_hosts_list != ["*"]:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts_list,
    )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Accept-Language", "X-Requested-With", "X-CSRF-Token"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "X-Credits-Remaining", "X-CSRF-Token"]
)

# GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60))])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "cache": await cache.exists("health_check"),
        "rate_limiter": rate_limiter.redis_client is not None
    }


@app.get("/metrics")
async def metrics(authorization: str = Header(default="")):
    """
    Prometheus metrics endpoint.

    Exposes metrics for monitoring property management operations.
    Protected by METRICS_SECRET when configured.
    """
    if settings.METRICS_SECRET and authorization != f"Bearer {settings.METRICS_SECRET}":
        raise HTTPException(status_code=403, detail="Invalid metrics secret")
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
