from app.core.security import create_access_token
from app.models.user import UserType
from tests.fixtures.models import create_test_user


def _auth_headers(email: str) -> dict[str, str]:
    token = create_access_token(data={"sub": email})
    return {"Authorization": f"Bearer {token}"}


def test_usage_summary_exposes_read_only_compatibility_header(client, db):
    user = create_test_user(
        db,
        email="usage-compat@example.com",
        user_type=UserType.EMPLOYEE,
    )

    response = client.get(
        "/api/v1/usage/summary",
        headers=_auth_headers(user.email),
    )

    assert response.status_code == 200
    assert response.headers["X-Usage-Compatibility"] == "read-only"
