"""Authentication endpoints"""
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.core.security import create_access_token, verify_password, get_password_hash
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, Token, UserResponse, ForgotPasswordRequest, ResetPasswordRequest
from app.services.email_service import generate_verification_token, send_verification_email, send_password_reset_email
from app.services.trial_service import TrialService

router = APIRouter()

EMPLOYER_MODES = {"none", "occasional", "regular"}


def _serialize_auth_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "user_type": user.user_type.value if hasattr(user.user_type, "value") else user.user_type,
        "vat_status": user.vat_status.value if getattr(user, "vat_status", None) is not None else None,
        "gewinnermittlungsart": (
            user.gewinnermittlungsart.value
            if getattr(user, "gewinnermittlungsart", None) is not None
            else None
        ),
        "employer_mode": user.employer_mode or "none",
        "employer_region": user.employer_region,
        "two_factor_enabled": user.two_factor_enabled,
        "is_admin": user.is_admin or False,
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)):
    """Register a new user and send verification email."""
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    employer_mode = user_data.employer_mode or "none"
    if employer_mode not in EMPLOYER_MODES:
        employer_mode = "none"

    token = generate_verification_token()
    user = User(
        email=user_data.email,
        name=user_data.name,
        password_hash=get_password_hash(user_data.password),
        user_type=user_data.user_type,
        business_type=user_data.business_type,
        business_industry=user_data.business_industry,
        employer_mode=employer_mode,
        employer_region=user_data.employer_region,
        email_verified=False,
        email_verification_token=token,
        email_verification_sent_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_verification_email(user.email, user.name, token, user_data.language or "de")

    return {"message": "verification_email_sent", "email": user.email}


@router.post("/verify-email")
def verify_email(token: str, db: Session = Depends(get_db)):
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
    return {
        "message": "email_verified",
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_auth_user(user),
    }


@router.post("/resend-verification")
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

    send_verification_email(user.email, user.name, token)
    return {"message": "verification_email_sent"}


@router.post("/login")
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user with email and password."""
    user = db.query(User).filter(User.email == credentials.email).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
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

    access_token = create_access_token(data={"sub": user.email})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": _serialize_auth_user(user),
    }


@router.post("/forgot-password")
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


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
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

    return {"message": "password_reset_success"}


@router.post("/logout")
def logout():
    """Logout user (client-side token removal)."""
    return {"message": "Successfully logged out"}


@router.post("/refresh")
def refresh_token():
    """Refresh token placeholder."""
    return {"message": "Token refresh not implemented yet"}


@router.post("/2fa/setup")
def setup_2fa():
    """2FA setup placeholder."""
    return {"qr_code": "", "secret": ""}


@router.post("/2fa/verify")
def verify_2fa():
    """2FA verify placeholder."""
    return {"success": True}
