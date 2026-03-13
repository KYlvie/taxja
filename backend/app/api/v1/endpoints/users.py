"""User profile endpoints"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.base import get_db
from app.core.security import get_current_user, get_password_hash, verify_password
from app.models.user import User

router = APIRouter()


@router.get("/profile")
def get_profile(current_user: User = Depends(get_current_user)):
    """Get current user profile ? flattens JSON fields for frontend consumption"""
    commuting = current_user.commuting_info or {}
    family = current_user.family_info or {}
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
        "user_type": current_user.user_type.value if hasattr(current_user.user_type, 'value') else current_user.user_type,
        "user_roles": family.get("user_roles", []),
        "language": current_user.language or "de",
        "two_factor_enabled": current_user.two_factor_enabled or False,
        "home_office_eligible": current_user.home_office_eligible or False,
        "tax_number": current_user.tax_number,
        "vat_number": current_user.vat_number,
        "address": current_user.address,
        # Flatten commuting_info JSON for frontend
        "commuting_distance_km": commuting.get("distance_km", 0),
        "public_transport_available": commuting.get("public_transport_available", True),
        # Flatten family_info JSON for frontend
        "num_children": family.get("num_children", 0),
        "is_single_parent": family.get("is_single_parent", False),
        "disclaimer_accepted": current_user.disclaimer_accepted_at is not None,
    }


@router.put("/profile")
def update_profile(
    profile_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user profile ? accepts flat fields from frontend, packs into JSON"""
    # Direct scalar fields
    scalar_fields = ["name", "language", "home_office_eligible", "tax_number",
                     "vat_number", "address", "user_type"]
    for field in scalar_fields:
        if field in profile_data:
            setattr(current_user, field, profile_data[field])

    # Pack commuting flat fields ? commuting_info JSON
    commuting = dict(current_user.commuting_info or {})
    if "commuting_distance_km" in profile_data:
        commuting["distance_km"] = profile_data["commuting_distance_km"]
    if "public_transport_available" in profile_data:
        commuting["public_transport_available"] = profile_data["public_transport_available"]
    current_user.commuting_info = commuting

    # Pack family flat fields ? family_info JSON
    family = dict(current_user.family_info or {})
    if "num_children" in profile_data:
        family["num_children"] = profile_data["num_children"]
    if "is_single_parent" in profile_data:
        family["is_single_parent"] = profile_data["is_single_parent"]
    if "user_roles" in profile_data:
        family["user_roles"] = profile_data["user_roles"]
    current_user.family_info = family

    db.commit()
    db.refresh(current_user)
    return get_profile(current_user)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(
    data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    if not verify_password(data.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    current_user.password_hash = get_password_hash(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}


@router.delete("/account")
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete user account"""
    db.delete(current_user)
    db.commit()
    return {"message": "Account deleted successfully"}


@router.post("/disclaimer/accept")
def accept_disclaimer(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Accept disclaimer"""
    current_user.disclaimer_accepted_at = datetime.utcnow()
    db.commit()
    return {"accepted": True, "accepted_at": current_user.disclaimer_accepted_at.isoformat()}


@router.get("/disclaimer/status")
def disclaimer_status(current_user: User = Depends(get_current_user)):
    """Get disclaimer status"""
    accepted = current_user.disclaimer_accepted_at is not None
    return {
        "accepted": accepted,
        "accepted_at": current_user.disclaimer_accepted_at.isoformat() if accepted else None
    }

