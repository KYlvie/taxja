"""Google Identity Services helpers."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2 import id_token

from app.core.config import settings


@dataclass(frozen=True)
class GoogleIdentity:
    """Normalized Google identity claims used by the auth layer."""

    subject: str
    email: str
    email_verified: bool
    name: str | None = None


class GoogleIdentityConfigurationError(RuntimeError):
    """Raised when Google Sign-In is not configured on the backend."""


class GoogleIdentityValidationError(ValueError):
    """Raised when the provided Google credential cannot be trusted."""


@lru_cache(maxsize=1)
def _google_request() -> GoogleRequest:
    return GoogleRequest()


def verify_google_identity_token(credential: str) -> GoogleIdentity:
    """Verify a Google ID token and return the normalized identity payload."""
    client_id = settings.GOOGLE_CLIENT_ID.strip()
    if not client_id:
        raise GoogleIdentityConfigurationError("GOOGLE_CLIENT_ID is not configured")

    try:
        payload = id_token.verify_oauth2_token(
            credential,
            _google_request(),
            client_id,
        )
    except ValueError as exc:
        raise GoogleIdentityValidationError("Invalid Google credential") from exc

    issuer = str(payload.get("iss") or "")
    if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
        raise GoogleIdentityValidationError("Invalid Google token issuer")

    subject = str(payload.get("sub") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    email_verified = bool(payload.get("email_verified"))
    name = str(payload.get("name") or "").strip() or None

    if not subject or not email:
        raise GoogleIdentityValidationError("Google account payload is incomplete")

    if not email_verified:
        raise GoogleIdentityValidationError("Google email address is not verified")

    return GoogleIdentity(
        subject=subject,
        email=email,
        email_verified=email_verified,
        name=name,
    )
