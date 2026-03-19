"""FastAPI Application Entry Point"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.core.config import settings
from app.core.error_handlers import setup_error_handlers
from app.core.security_headers import SecurityHeadersMiddleware
from app.core.cache import cache
from app.core.rate_limiter import rate_limiter
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

    # Pre-load SentenceTransformer embedding model to avoid cold-start delay
    try:
        from app.services.vector_db_service import get_vector_db_service
        _vdb = get_vector_db_service()
        print(f"[OK] Vector DB + embedding model pre-loaded ({_vdb.embedding_model.get_sentence_embedding_dimension()}d)")
    except Exception as e:
        print(f"[WARN] Vector DB pre-load skipped: {e}")

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
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan
)

# Setup global error handlers
setup_error_handlers(app)

# Security headers middleware (should be first)
app.add_middleware(SecurityHeadersMiddleware)

# Trusted host middleware (prevent host header attacks)
# app.add_middleware(
#     TrustedHostMiddleware,
#     allowed_hosts=["taxja.at", "*.taxja.at", "localhost", "127.0.0.1"]
# )

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]
)

# GZip compression middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Include API router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "cache": await cache.exists("health_check"),
        "rate_limiter": rate_limiter.redis_client is not None
    }


@app.get("/metrics")
async def metrics():
    """
    Prometheus metrics endpoint.
    
    Exposes metrics for monitoring property management operations:
    - property_created_total: Counter for property creation events
    - depreciation_generated_total: Counter for depreciation generation events
    - backfill_duration_seconds: Histogram for backfill operation duration
    
    This endpoint is typically scraped by Prometheus server.
    """
    return PlainTextResponse(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )
