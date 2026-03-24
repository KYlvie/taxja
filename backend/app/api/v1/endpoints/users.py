"""User profile endpoints."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.error_messages import get_error_message
from app.core.security import get_current_user, get_password_hash, verify_password
from app.db.base import get_db
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserProfileUpdate
from app.services.tax_profile_service import TaxProfileService

router = APIRouter()

EMPLOYER_MODES = {"none", "occasional", "regular"}


def _enum_value(value):
    return value.value if hasattr(value, "value") else value


def _derive_user_roles(user: User, family: dict) -> list[str]:
    stored_roles = family.get("user_roles")
    if isinstance(stored_roles, list) and stored_roles:
        return stored_roles

    user_type = _enum_value(user.user_type) or "employee"
    if user_type == "mixed":
        return ["employee", "landlord", "self_employed"]
    return [user_type]


def _serialize_profile(current_user: User) -> UserProfileResponse:
    commuting = current_user.commuting_info or {}
    family = current_user.family_info or {}
    tax_profile = TaxProfileService().get_asset_tax_profile_context(current_user)

    return UserProfileResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        address=current_user.address,
        tax_number=current_user.tax_number,
        vat_number=current_user.vat_number,
        user_type=_enum_value(current_user.user_type) or "employee",
        user_roles=_derive_user_roles(current_user, family),
        business_type=_enum_value(current_user.business_type),
        business_name=current_user.business_name,
        business_industry=current_user.business_industry,
        vat_status=_enum_value(current_user.vat_status),
        gewinnermittlungsart=_enum_value(current_user.gewinnermittlungsart),
        tax_profile_completeness=tax_profile.completeness,
        employer_mode=current_user.employer_mode or "none",
        employer_region=current_user.employer_region,
        commuting_distance_km=commuting.get("distance_km", 0),
        public_transport_available=commuting.get("public_transport_available", True),
        telearbeit_days=current_user.telearbeit_days or 0,
        employer_telearbeit_pauschale=float(current_user.employer_telearbeit_pauschale or 0),
        num_children=family.get("num_children", 0),
        is_single_parent=family.get("is_single_parent", False),
        language=current_user.language or "de",
        two_factor_enabled=bool(current_user.two_factor_enabled),
        home_office_eligible=bool(current_user.home_office_eligible),
        disclaimer_accepted=current_user.disclaimer_accepted_at is not None,
    )


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile with flattened frontend fields."""
    return _serialize_profile(current_user)


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update current user profile and pack frontend fields into persisted shape."""
    payload = profile_data.model_dump(exclude_unset=True)

    scalar_fields = {
        "name",
        "language",
        "home_office_eligible",
        "tax_number",
        "vat_number",
        "address",
        "user_type",
        "business_type",
        "business_name",
        "business_industry",
        "vat_status",
        "gewinnermittlungsart",
        "telearbeit_days",
        "employer_region",
        "employer_telearbeit_pauschale",
    }
    for field in scalar_fields:
        if field in payload:
            setattr(current_user, field, payload[field])

    if "employer_mode" in payload:
        employer_mode = payload.get("employer_mode") or "none"
        current_user.employer_mode = employer_mode if employer_mode in EMPLOYER_MODES else "none"

    commuting = dict(current_user.commuting_info or {})
    if "commuting_distance_km" in payload:
        commuting["distance_km"] = payload["commuting_distance_km"]
    if "public_transport_available" in payload:
        commuting["public_transport_available"] = payload["public_transport_available"]
    if "commuting_info" in payload and isinstance(payload["commuting_info"], dict):
        commuting.update(payload["commuting_info"])
    current_user.commuting_info = commuting

    family = dict(current_user.family_info or {})
    if "num_children" in payload:
        family["num_children"] = payload["num_children"]
    if "is_single_parent" in payload:
        family["is_single_parent"] = payload["is_single_parent"]
    if "user_roles" in payload:
        family["user_roles"] = payload["user_roles"]
    if "family_info" in payload and isinstance(payload["family_info"], dict):
        family.update(payload["family_info"])
    current_user.family_info = family

    db.commit()
    db.refresh(current_user)
    return _serialize_profile(current_user)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
async def change_password(
    data: PasswordChange,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Change user password. Invalidates all existing sessions and issues fresh tokens."""
    from fastapi import HTTPException
    from app.core.token_blacklist import blacklist_all_user_tokens
    from app.core.security import create_access_token, create_refresh_token, generate_csrf_token, decode_token_payload

    if not verify_password(data.current_password, current_user.password_hash):
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(status_code=400, detail=get_error_message("current_password_incorrect", language))
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()

    # Revoke all existing sessions
    await blacklist_all_user_tokens(current_user.id)

    # Issue a fresh token pair for the current session
    access_token = create_access_token(data={"sub": current_user.email})
    refresh_token = create_refresh_token(data={"sub": current_user.email})

    # Set cookies
    cookie_kwargs: dict = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
    }
    if settings.COOKIE_DOMAIN:
        cookie_kwargs["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(
        key="access_token",
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path=settings.COOKIE_PATH,
        **cookie_kwargs,
    )
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

    payload = decode_token_payload(access_token)
    jti = payload.get("jti", "") if payload else ""
    csrf_token = generate_csrf_token(jti)
    response.headers["X-CSRF-Token"] = csrf_token

    return {
        "message": "Password changed successfully",
        "access_token": access_token,
        "token_type": "bearer",
    }


class AccountDeleteConfirmation(BaseModel):
    password: str


@router.post("/account/delete")
def delete_account(
    confirmation: AccountDeleteConfirmation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete user account. Requires password confirmation."""
    from fastapi import HTTPException

    if not verify_password(confirmation.password, current_user.password_hash):
        language = getattr(current_user, 'language', 'de') or 'de'
        raise HTTPException(status_code=400, detail=get_error_message("incorrect_password", language))
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}


@router.post("/disclaimer/accept")
def accept_disclaimer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Accept disclaimer."""
    current_user.disclaimer_accepted_at = datetime.utcnow()
    db.commit()
    return {"accepted": True, "accepted_at": current_user.disclaimer_accepted_at.isoformat()}


@router.get("/industries/{business_type}")
def get_industries(business_type: str):
    """Get available industries for a given business type."""
    from app.models.user import SelfEmployedType
    from app.services.business_deductibility_rules import INDUSTRIES_BY_TYPE, INDUSTRY_CONTEXTS

    try:
        bt = SelfEmployedType(business_type)
    except ValueError:
        return {"industries": []}

    industry_slugs = INDUSTRIES_BY_TYPE.get(bt, [])
    industries = []
    for slug in industry_slugs:
        ctx = INDUSTRY_CONTEXTS.get(slug, {})
        industries.append(
            {
                "value": slug,
                "label_de": ctx.get("description_de", slug),
                "label_en": ctx.get("description_en", slug),
                "label_zh": ctx.get("description_zh", slug),
            }
        )
    return {"industries": industries}


@router.get("/disclaimer/status")
def disclaimer_status(current_user: User = Depends(get_current_user)):
    """Get disclaimer status."""
    accepted = current_user.disclaimer_accepted_at is not None
    return {
        "accepted": accepted,
        "accepted_at": current_user.disclaimer_accepted_at.isoformat() if accepted else None,
    }
