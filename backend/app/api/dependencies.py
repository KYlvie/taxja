"""API dependencies for rate limiting and authentication"""
from typing import Optional
from fastapi import Depends, Request, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.core.rate_limiter import rate_limiter, RATE_LIMITS, get_rate_limit_key
from app.core.security import get_current_user
from app.models.user import User


async def rate_limit_default(request: Request):
    """Apply default rate limit"""
    config = RATE_LIMITS["default"]
    key = get_rate_limit_key(request)
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def rate_limit_auth(request: Request):
    """Apply authentication endpoint rate limit"""
    config = RATE_LIMITS["auth"]
    # Use IP for auth endpoints (before user is authenticated)
    key = f"ip:{request.client.host if request.client else 'unknown'}"
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def rate_limit_ocr(request: Request):
    """Apply OCR endpoint rate limit"""
    config = RATE_LIMITS["ocr"]
    key = get_rate_limit_key(request)
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def rate_limit_ai_chat(request: Request):
    """Apply AI chat endpoint rate limit"""
    config = RATE_LIMITS["ai_chat"]
    key = get_rate_limit_key(request)
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def rate_limit_upload(request: Request):
    """Apply upload endpoint rate limit"""
    config = RATE_LIMITS["upload"]
    key = get_rate_limit_key(request)
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def rate_limit_export(request: Request):
    """Apply export endpoint rate limit"""
    config = RATE_LIMITS["export"]
    key = get_rate_limit_key(request)
    await rate_limiter.check_rate_limit(
        request,
        rate=config["rate"],
        window=config["window"],
        key_func=lambda r: key
    )


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current active user with database session.
    
    Raises:
        HTTPException: If user is inactive
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    return current_user
