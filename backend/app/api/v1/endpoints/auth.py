"""Authentication endpoints"""
import base64
import io
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import pyotp
import qrcode

from app.db.base import get_db
from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token_payload,
    generate_csrf_token,
    verify_password,
    get_password_hash,
    get_current_user,
)
from app.core.token_blacklist import (
    blacklist_all_user_tokens,
    blacklist_token,
    is_token_blacklisted,
)
from app.core.encryption import get_encryption
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse, ForgotPasswordRequest, ResetPasswordRequest, TwoFactorVerifyRequest
from app.services.email_service import generate_verification_token, send_verification_email, send_password_reset_email
from app.core.error_messages import get_error_message
from app.services.trial_service import TrialService
from app.core.rate_limiter import rate_limit

router = APIRouter()

EMPLOYER_MODES = {"none", "occasional", "regular"}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _derive_user_roles(user: User) -> list[str]:
    family = user.family_info or {}
    stored_roles = family.get("user_roles")
    if isinstance(stored_roles, list) and stored_roles:
        return stored_roles

    user_type = _enum_value(user.user_type) or "employee"
    if user_type == "mixed":
        return ["employee", "landlord", "self_employed"]
    return [user_type]


def _serialize_auth_user(user: User) -> dict:
    family = user.family_info or {}
    commuting = user.commuting_info or {}
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "user_type": _enum_value(user.user_type) or "employee",
        "user_roles": _derive_user_roles(user),
        "business_type": _enum_value(user.business_type),
        "business_name": user.business_name,
        "business_industry": user.business_industry,
        "vat_status": _enum_value(user.vat_status),
        "gewinnermittlungsart": (
            _enum_value(user.gewinnermittlungsart)
        ),
        "employer_mode": user.employer_mode or "none",
        "employer_region": user.employer_region,
        "commuting_distance_km": commuting.get("distance_km", 0),
        "public_transport_available": commuting.get("public_transport_available", True),
        "telearbeit_days": user.telearbeit_days or 0,
        "employer_telearbeit_pauschale": float(user.employer_telearbeit_pauschale or 0),
        "num_children": family.get("num_children", 0),
        "is_single_parent": family.get("is_single_parent", False),
        "language": user.language or "de",
        "two_factor_enabled": user.two_factor_enabled,
        "is_admin": user.is_admin or False,
        "onboarding_completed": (user.onboarding_dismiss_count or 0) >= 8,
    }


# ---------------------------------------------------------------------------
# Cookie helpers
# ---------------------------------------------------------------------------

def _set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
) -> str:
    """Set HttpOnly auth cookies and return the CSRF token.

    - access_token cookie: path=COOKIE_PATH, SameSite=lax
    - refresh_token cookie: path=<COOKIE_PATH>/auth/refresh, SameSite=strict
    """
    cookie_kwargs: dict = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
    }
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    # Access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=settings.COOKIE_PATH,
        **cookie_kwargs,
    )

    # Refresh token cookie — tighter path + strict SameSite
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path=f"{settings.COOKIE_PATH}/auth/refresh",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="strict",
        **({"domain": settings.COOKIE_DOMAIN} if settings.COOKIE_DOMAIN else {}),
    )

    # Derive CSRF token from the access token's JTI
    payload = decode_token_payload(access_token)
    jti = payload.get("jti", "") if payload else ""
    return generate_csrf_token(jti)


def _clear_auth_cookies(response: Response) -> None:
    """Delete both auth cookies."""
    cookie_kwargs: dict = {}
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.delete_cookie(
        key="access_token",
        path=settings.COOKIE_PATH,
        **cookie_kwargs,
    )
    response.delete_cookie(
        key="refresh_token",
        path=f"{settings.COOKIE_PATH}/auth/refresh",
        **cookie_kwargs,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/register", status_code=status.HTTP_201_CREATED, dependencies=[Depends(rate_limit(max_requests=3, window_seconds=60))])
def register(user_data: UserRegister, request: Request, db: Session = Depends(get_db)):
    """Register a new user and send verification email."""
    language = request.headers.get("Accept-Language", "de").split(",")[0].strip()[:2]
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_error_message("email_already_registered", language),
        )

    employer_mode = user_data.employer_mode or "none"
    if employer_mode not in EMPLOYER_MODES:
        employer_mode = "none"

    family_info = {}
    if user_data.user_roles:
        family_info["user_roles"] = user_data.user_roles
    if user_data.num_children is not None:
        family_info["num_children"] = user_data.num_children
    if user_data.is_single_parent is not None:
        family_info["is_single_parent"] = user_data.is_single_parent

    commuting_info = {}
    if user_data.commuting_distance_km is not None:
        commuting_info["distance_km"] = user_data.commuting_distance_km
    if user_data.public_transport_available is not None:
        commuting_info["public_transport_available"] = user_data.public_transport_available

    token = generate_verification_token()
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=get_password_hash(user_data.password),
        user_type=user_data.user_type,
        business_type=user_data.business_type,
        business_name=user_data.business_name,
        business_industry=user_data.business_industry,
        tax_number=user_data.tax_number,
        vat_number=user_data.vat_number,
        address=user_data.address,
        vat_status=user_data.vat_status,
        gewinnermittlungsart=user_data.gewinnermittlungsart,
        employer_mode=employer_mode,
        employer_region=user_data.employer_region,
        commuting_info=commuting_info,
        family_info=family_info,
        telearbeit_days=user_data.telearbeit_days,
        employer_telearbeit_pauschale=user_data.employer_telearbeit_pauschale,
        language=user_data.language or "de",
        email_verified=False,
        email_verification_token=token,
        email_verification_sent_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user.email, user.name, token, user_data.language or "de")

    return {"message": "verification_email_sent", "email": user.email}


@router.post("/verify-email", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
def verify_email(token: str, response: Response, db: Session = Depends(get_db)):
    """Verify email address using the token from the verification email."""
    user = db.query(User).filter(User.email_verification_token == token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        )

    user.email_verified = True
    user.email_verification_token = None
    db.commit()

    # Activate 14-day Pro trial for new verified users
    try:
        trial_service = TrialService(db)
        trial_service.activate_trial(user.id)
    except Exception:
        pass  # Don't block verification if trial activation fails

    # Auto-login after verification
    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    csrf_token = _set_auth_cookies(response, access_token, refresh_token)
    response.headers["X-CSRF-Token"] = csrf_token

    return {
        "message": "email_verified",
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_auth_user(user),
    }


@router.post("/resend-verification", dependencies=[Depends(rate_limit(max_requests=2, window_seconds=60))])
def resend_verification(email: str, db: Session = Depends(get_db)):
    """Resend verification email."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Don't reveal whether email exists
        return {"message": "verification_email_sent"}

    if user.email_verified:
        return {"message": "already_verified"}

    # Rate limit: at most once per 60 seconds
    if user.email_verification_sent_at:
        elapsed = datetime.utcnow() - user.email_verification_sent_at
        if elapsed < timedelta(seconds=60):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="please_wait_before_resending",
            )

    token = generate_verification_token()
    user.email_verification_token = token
    user.email_verification_sent_at = datetime.utcnow()
    db.commit()

    send_verification_email(user.email, user.name, token, language=user.language or "de")
    return {"message": "verification_email_sent"}


@router.post("/login", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
def login(credentials: UserLogin, request: Request, response: Response, db: Session = Depends(get_db)):
    """Login user with email and password."""
    language = request.headers.get("Accept-Language", "de").split(",")[0].strip()[:2]
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=get_error_message("incorrect_email_or_password", language),
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check account status
    if user.account_status == "deactivated":
        cooling_off_days_remaining = 0
        if user.scheduled_deletion_at:
            scheduled = user.scheduled_deletion_at
            now = datetime.now(timezone.utc)
            if scheduled.tzinfo is None:
                scheduled = scheduled.replace(tzinfo=timezone.utc)
            delta = scheduled - now
            cooling_off_days_remaining = max(0, delta.days)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Account is deactivated",
                "account_status": "deactivated",
                "cooling_off_days_remaining": cooling_off_days_remaining,
                "message": "Your account has been deactivated. You can reactivate it during the cooling-off period.",
            },
        )

    if user.account_status == "deletion_pending":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "Account is scheduled for deletion",
                "account_status": "deletion_pending",
                "message": "Your account has been scheduled for permanent deletion.",
            },
        )

    # Block unverified users
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "detail": "email_not_verified",
                "email": user.email,
                "message": "Please verify your email address before logging in.",
            },
        )

    # 2FA check
    if user.two_factor_enabled and user.two_factor_secret:
        if not credentials.two_factor_code:
            return JSONResponse(
                status_code=403,
                content={
                    "requires_2fa": True,
                    "detail": "two_factor_required",
                    "message": "Two-factor authentication code required.",
                },
            )
        encryption = get_encryption()
        decrypted_secret = encryption.decrypt_field(user.two_factor_secret)
        totp = pyotp.TOTP(decrypted_secret)
        if not totp.verify(credentials.two_factor_code, valid_window=2):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=get_error_message("invalid_2fa_code", language),
            )

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    csrf_token = _set_auth_cookies(response, access_token, refresh_token)
    response.headers["X-CSRF-Token"] = csrf_token

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_auth_user(user),
    }


@router.post("/forgot-password", dependencies=[Depends(rate_limit(max_requests=3, window_seconds=60))])
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Send password reset email. Always returns success to avoid email enumeration."""
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        # Don't reveal whether email exists
        return {"message": "password_reset_email_sent"}

    # Rate limit: at most once per 60 seconds
    if user.password_reset_sent_at:
        elapsed = datetime.utcnow() - user.password_reset_sent_at
        if elapsed < timedelta(seconds=60):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="please_wait_before_resending",
            )

    token = generate_verification_token()
    user.password_reset_token = token
    user.password_reset_sent_at = datetime.utcnow()
    db.commit()

    lang = data.language or getattr(user, "language", None) or "de"
    send_password_reset_email(user.email, user.name, token, lang)
    return {"message": "password_reset_email_sent"}


@router.post("/reset-password", dependencies=[Depends(rate_limit(max_requests=5, window_seconds=60))])
async def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using the token from the reset email."""
    user = db.query(User).filter(User.password_reset_token == data.token).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid_or_expired_token",
        )

    # Check token expiry (1 hour)
    if user.password_reset_sent_at:
        elapsed = datetime.utcnow() - user.password_reset_sent_at
        if elapsed > timedelta(hours=1):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="token_expired",
            )

    user.password_hash = get_password_hash(data.password)
    user.password_reset_token = None
    user.password_reset_sent_at = None
    db.commit()

    # Invalidate all existing sessions after password reset
    await blacklist_all_user_tokens(user.id)

    return {"message": "password_reset_success"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    """Logout user — blacklist tokens and clear cookies."""
    # Try to blacklist the access token
    access_token = (
        request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
        or request.cookies.get("access_token")
    )
    if access_token:
        payload = decode_token_payload(access_token)
        if payload and payload.get("jti"):
            # TTL = remaining lifetime of the token
            exp = payload.get("exp", 0)
            remaining = max(int(exp - datetime.utcnow().timestamp()), 0)
            if remaining > 0:
                await blacklist_token(payload["jti"], ttl=remaining)

    # Try to blacklist the refresh token
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        payload = decode_token_payload(refresh_token)
        if payload and payload.get("jti"):
            await blacklist_token(
                payload["jti"],
                ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
            )

    _clear_auth_cookies(response)
    return {"message": "Successfully logged out"}


@router.post("/refresh", dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60))])
async def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Refresh access token using a refresh token (cookie or body).

    Implements token rotation: the old refresh token is blacklisted and a
    fresh access + refresh pair is issued.
    """
    # 1. Get refresh token from cookie (web) or request body (mobile fallback)
    token = request.cookies.get("refresh_token")
    if not token:
        try:
            body = await request.json()
            token = body.get("refresh_token")
        except Exception:
            pass

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    # 2. Decode & validate
    payload = decode_token_payload(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    jti = payload.get("jti")
    if jti and await is_token_blacklisted(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    email = payload.get("sub")
    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Check user-level revocation
    iat = payload.get("iat")
    if iat is not None:
        from app.core.token_blacklist import get_user_revocation_time
        revoked_at = await get_user_revocation_time(user.id)
        if revoked_at is not None and iat <= revoked_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="All sessions have been revoked",
            )

    # 3. Token rotation — blacklist old refresh token
    if jti:
        await blacklist_token(jti, ttl=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400)

    # 4. Issue new pair
    new_access = create_access_token(data={"sub": user.email})
    new_refresh = create_refresh_token(data={"sub": user.email})

    csrf_token = _set_auth_cookies(response, new_access, new_refresh)
    response.headers["X-CSRF-Token"] = csrf_token

    return {
        "access_token": new_access,
        "token_type": "bearer",
    }


@router.post("/2fa/setup")
def setup_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate a TOTP secret and QR code for 2FA setup."""
    encryption = get_encryption()

    # Reuse existing secret if 2FA not yet enabled (avoid overwriting on page refresh)
    if current_user.two_factor_secret and not current_user.two_factor_enabled:
        secret = encryption.decrypt_field(current_user.two_factor_secret)
    else:
        secret = pyotp.random_base32()
        current_user.two_factor_secret = encryption.encrypt_field(secret)
        current_user.two_factor_enabled = False
        db.commit()

    totp = pyotp.TOTP(secret)
    provisioning_uri = totp.provisioning_uri(
        name=current_user.email,
        issuer_name="Taxja",
    )

    # Generate QR code as base64 PNG
    img = qrcode.make(provisioning_uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    qr_base64 = base64.b64encode(buf.getvalue()).decode("utf-8")

    return {
        "qr_code": f"data:image/png;base64,{qr_base64}",
        "secret": secret,
    }


@router.post("/2fa/verify")
def verify_2fa(
    body: TwoFactorVerifyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify TOTP code and enable 2FA for the user."""
    language = request.headers.get("Accept-Language", "de").split(",")[0].strip()[:2]
    if language not in ("de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"):
        language = "de"

    if not current_user.two_factor_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_error_message("2fa_not_setup", language),
        )

    encryption = get_encryption()
    decrypted_secret = encryption.decrypt_field(current_user.two_factor_secret)
    totp = pyotp.TOTP(decrypted_secret)

    if not totp.verify(body.code, valid_window=2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=get_error_message("invalid_2fa_code", language),
        )

    current_user.two_factor_enabled = True
    db.commit()

    return {"success": True}


@router.post("/2fa/disable")
def disable_2fa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disable 2FA for the user."""
    current_user.two_factor_enabled = False
    current_user.two_factor_secret = None
    db.commit()

    return {"success": True}


@router.post("/onboarding-complete")
def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Dismiss onboarding for this session. After 8 dismissals it stops showing."""
    count = (current_user.onboarding_dismiss_count or 0) + 1
    current_user.onboarding_dismiss_count = count
    if count >= 8:
        current_user.onboarding_completed = True
    db.commit()
    return {"success": True, "dismiss_count": count}
