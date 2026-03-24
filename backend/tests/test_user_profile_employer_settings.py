"""Functional tests for employer-related profile persistence."""
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token, get_password_hash
from app.models.user import Gewinnermittlungsart, UserType, VatStatus
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_profile_update_persists_employer_settings_across_login(client: TestClient, db: Session):
    """Saving employer settings in the profile should survive a fresh login."""
    password = "StrongPass123!"
    user = create_test_user(
        db,
        email="profile-employer@example.com",
        user_type=UserType.SELF_EMPLOYED,
        employer_mode="none",
        employer_region=None,
    )
    user.email_verified = True
    user.password_hash = get_password_hash(password)
    db.commit()
    db.refresh(user)

    update_response = client.put(
        "/api/v1/users/profile",
        json={
            "name": "Profile Employer",
            "user_type": "self_employed",
            "user_roles": ["self_employed"],
            "employer_mode": "regular",
            "employer_region": "Wien",
        },
        headers=_auth_headers(user.email),
    )

    assert update_response.status_code == 200
    profile = update_response.json()
    assert profile["employer_mode"] == "regular"
    assert profile["employer_region"] == "Wien"

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["user"]["employer_mode"] == "regular"
    assert login_data["user"]["employer_region"] == "Wien"

    profile_response = client.get(
        "/api/v1/users/profile",
        headers=_auth_headers(user.email),
    )
    assert profile_response.status_code == 200
    persisted_profile = profile_response.json()
    assert persisted_profile["employer_mode"] == "regular"
    assert persisted_profile["employer_region"] == "Wien"


def test_profile_update_persists_tax_profile_fields_and_completeness(client: TestClient, db: Session):
    user = create_test_user(
        db,
        email="profile-tax@example.com",
        user_type=UserType.SELF_EMPLOYED,
        vat_status=None,
        gewinnermittlungsart=None,
    )
    user.email_verified = True
    db.commit()

    update_response = client.put(
        "/api/v1/users/profile",
        json={
            "name": "Profile Tax",
            "user_type": "self_employed",
            "user_roles": ["self_employed"],
            "vat_status": VatStatus.REGELBESTEUERT.value,
            "gewinnermittlungsart": Gewinnermittlungsart.EA_RECHNUNG.value,
        },
        headers=_auth_headers(user.email),
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["vat_status"] == VatStatus.REGELBESTEUERT.value
    assert payload["gewinnermittlungsart"] == Gewinnermittlungsart.EA_RECHNUNG.value
    assert payload["tax_profile_completeness"]["is_complete_for_asset_automation"] is True
    assert payload["tax_profile_completeness"]["missing_fields"] == []
    assert payload["tax_profile_completeness"]["source"] == "persisted_user_profile"
    assert payload["tax_profile_completeness"]["contract_version"] == "v1"

    profile_response = client.get(
        "/api/v1/users/profile",
        headers=_auth_headers(user.email),
    )

    assert profile_response.status_code == 200
    persisted_profile = profile_response.json()
    assert persisted_profile["vat_status"] == VatStatus.REGELBESTEUERT.value
    assert (
        persisted_profile["gewinnermittlungsart"]
        == Gewinnermittlungsart.EA_RECHNUNG.value
    )
    assert (
        persisted_profile["tax_profile_completeness"]["source"]
        == "persisted_user_profile"
    )
    assert persisted_profile["tax_profile_completeness"]["contract_version"] == "v1"


def test_profile_update_persists_family_fields_across_login(client: TestClient, db: Session):
    password = "StrongPass123!"
    user = create_test_user(
        db,
        email="profile-family@example.com",
        user_type=UserType.EMPLOYEE,
    )
    user.email_verified = True
    user.password_hash = get_password_hash(password)
    db.commit()
    db.refresh(user)

    update_response = client.put(
        "/api/v1/users/profile",
        json={
            "name": "Family Profile",
            "user_type": "employee",
            "user_roles": ["employee"],
            "num_children": 3,
            "is_single_parent": True,
        },
        headers=_auth_headers(user.email),
    )

    assert update_response.status_code == 200
    payload = update_response.json()
    assert payload["num_children"] == 3
    assert payload["is_single_parent"] is True

    login_response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": password},
    )

    assert login_response.status_code == 200
    login_data = login_response.json()
    assert login_data["user"]["num_children"] == 3
    assert login_data["user"]["is_single_parent"] is True

    profile_response = client.get(
        "/api/v1/users/profile",
        headers=_auth_headers(user.email),
    )
    assert profile_response.status_code == 200
    persisted_profile = profile_response.json()
    assert persisted_profile["num_children"] == 3
    assert persisted_profile["is_single_parent"] is True
