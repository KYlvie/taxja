"""Security utilities for authentication and authorization"""
import hashlib
import hmac
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.token_blacklist import (
    get_user_revocation_time,
    is_token_blacklisted,
)
from app.db.base import get_db
from app.models.user import User

# Password hashing - use pbkdf2_sha256 to avoid bcrypt 72-byte limit issues
pwd_context = CryptContext(
    schemes=["pbkdf2_sha256"],
    deprecated="auto",
    pbkdf2_sha256__default_rounds=200000
)

# OAuth2 scheme — auto_error=False so we can fall back to cookies
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,
)

# HTTP methods that mutate state and therefore require CSRF validation
_MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token with jti, iat, and type claims."""
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({
        "exp": expire,
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "access",
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT refresh token with jti, iat, and type claims."""
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS))
    to_encode.update({
        "exp": expire,
        "iat": int(now.timestamp()),
        "jti": str(uuid.uuid4()),
        "type": "refresh",
    })
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def decode_access_token(token: str) -> Optional[str]:
    """Decode a JWT access token and return the subject (user email).

    Kept for backward compatibility — callers that only need the email.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


def decode_token_payload(token: str) -> Optional[dict]:
    """Decode a JWT and return the full payload dict, or None on failure."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# CSRF utilities
# ---------------------------------------------------------------------------

def generate_csrf_token(session_id: str) -> str:
    """Generate a CSRF token tied to a session (the access token's JTI)."""
    return hmac.new(
        settings.CSRF_SECRET_KEY.encode(),
        session_id.encode(),
        hashlib.sha256,
    ).hexdigest()


def validate_csrf_token(csrf_token: str, session_id: str) -> bool:
    """Validate a CSRF token against the expected value."""
    expected = generate_csrf_token(session_id)
    return hmac.compare_digest(csrf_token, expected)


# ---------------------------------------------------------------------------
# Dual-mode get_current_user (cookie + bearer)
# ---------------------------------------------------------------------------

async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    bearer_token: Optional[str] = Depends(oauth2_scheme),
) -> User:
    """Get the current authenticated user.

    Supports two auth modes:
    1. Bearer token (Authorization header) — used by mobile / API clients
    2. HttpOnly cookie (access_token) — used by web browsers

    When auth comes from a cookie and the request method mutates state,
    the X-CSRF-Token header is validated.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # --- 1. Extract token ---------------------------------------------------
    auth_mode = "bearer"
    token = bearer_token
    if not token:
        token = request.cookies.get("access_token")
        if token:
            auth_mode = "cookie"

    if not token:
        raise credentials_exception

    # --- 2. Decode -----------------------------------------------------------
    payload = decode_token_payload(token)
    if payload is None:
        raise credentials_exception

    # For new tokens, verify it's an access token (old tokens without type are OK)
    token_type = payload.get("type")
    if token_type is not None and token_type != "access":
        raise credentials_exception

    email: Optional[str] = payload.get("sub")
    if not email:
        raise credentials_exception

    # --- 3. Blacklist check (only for tokens with jti) -----------------------
    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise credentials_exception

    # --- 4. User lookup ------------------------------------------------------
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        raise credentials_exception

    # --- 5. User-level revocation (only for tokens with iat) -----------------
    iat = payload.get("iat")
    if iat is not None:
        revoked_at = await get_user_revocation_time(user.id)
        if revoked_at is not None and iat <= revoked_at:
            raise credentials_exception

    # --- 6. CSRF check (cookie auth + mutating method) -----------------------
    if auth_mode == "cookie" and request.method in _MUTATING_METHODS:
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not jti or not validate_csrf_token(csrf_header, jti):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed",
            )

    # --- 7. Store auth mode on request state for downstream use --------------
    request.state.auth_mode = auth_mode
    return user
