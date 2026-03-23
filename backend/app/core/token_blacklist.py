"""Token blacklist using Redis for JWT revocation.

Uses the global async RedisCache singleton. All functions are async and
fail-open (return False/None) when Redis is unavailable — preserving
the same stateless behaviour as before this module existed.
"""
import time
from typing import Optional

from app.core.cache import cache
from app.core.config import settings

# Key prefixes
_TOKEN_PREFIX = "token_blacklist:"
_USER_REVOKE_PREFIX = "user_token_revoked_at:"


async def blacklist_token(jti: str, ttl: Optional[int] = None) -> bool:
    """Add a single token JTI to the blacklist.

    Args:
        jti: The JWT ID to revoke.
        ttl: Time-to-live in seconds. Defaults to TOKEN_BLACKLIST_TTL_SECONDS.
    """
    ttl = ttl or settings.TOKEN_BLACKLIST_TTL_SECONDS
    return await cache.set(f"{_TOKEN_PREFIX}{jti}", 1, ttl=ttl)


async def is_token_blacklisted(jti: str) -> bool:
    """Check whether a JTI has been revoked."""
    return await cache.exists(f"{_TOKEN_PREFIX}{jti}")


async def blacklist_all_user_tokens(user_id: int) -> bool:
    """Revoke every token issued to *user_id* before this moment.

    Stores a Unix timestamp; any token whose ``iat`` is older will be
    rejected by the auth layer.
    """
    return await cache.set(
        f"{_USER_REVOKE_PREFIX}{user_id}",
        int(time.time()),
        ttl=settings.TOKEN_BLACKLIST_TTL_SECONDS,
    )


async def get_user_revocation_time(user_id: int) -> Optional[int]:
    """Return the Unix timestamp after which tokens for *user_id* are valid.

    Returns ``None`` when no user-level revocation is active (or Redis
    is unavailable).
    """
    val = await cache.get(f"{_USER_REVOKE_PREFIX}{user_id}")
    if val is not None:
        try:
            return int(val)
        except (TypeError, ValueError):
            return None
    return None
