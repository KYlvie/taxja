"""Rate limiting middleware for API protection"""
import time
from typing import Optional
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
import redis.asyncio as redis

from app.core.config import settings


class RateLimiter:
    """
    Token bucket rate limiter using Redis.
    
    Implements sliding window rate limiting to prevent abuse.
    """
    
    def __init__(
        self,
        redis_url: str = None,
        default_rate: int = 100,
        default_window: int = 60
    ):
        """
        Initialize rate limiter.
        
        Args:
            redis_url: Redis connection URL
            default_rate: Default requests per window
            default_window: Default time window in seconds
        """
        self.redis_url = redis_url or settings.REDIS_URL
        self.redis_client: Optional[redis.Redis] = None
        self.default_rate = default_rate
        self.default_window = default_window
    
    async def connect(self):
        """Connect to Redis. Fails gracefully if Redis is not available."""
        import asyncio
        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=3,
                socket_timeout=3,
            )
            await asyncio.wait_for(self.redis_client.ping(), timeout=3)
        except Exception:
            self.redis_client = None
    
    async def disconnect(self):
        """Disconnect from Redis"""
        if self.redis_client:
            await self.redis_client.close()
    
    async def is_allowed(
        self,
        key: str,
        rate: Optional[int] = None,
        window: Optional[int] = None
    ) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit.
        
        Args:
            key: Unique identifier for rate limiting (e.g., user_id, IP)
            rate: Requests allowed per window
            window: Time window in seconds
        
        Returns:
            Tuple of (is_allowed, info_dict)
        """
        if not self.redis_client:
            return True, {}
        
        rate = rate or self.default_rate
        window = window or self.default_window
        
        current_time = int(time.time())
        window_start = current_time - window
        
        # Redis key for this rate limit
        redis_key = f"rate_limit:{key}"
        
        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(redis_key, 0, window_start)
            
            # Count requests in current window
            pipe.zcard(redis_key)
            
            # Add current request
            pipe.zadd(redis_key, {str(current_time): current_time})
            
            # Set expiry on the key
            pipe.expire(redis_key, window)
            
            # Execute pipeline
            results = await pipe.execute()
            
            # Get count (result of zcard)
            request_count = results[1]
            
            # Check if allowed
            is_allowed = request_count < rate
            
            # Calculate reset time
            reset_time = current_time + window
            
            info = {
                "limit": rate,
                "remaining": max(0, rate - request_count - 1),
                "reset": reset_time,
                "window": window
            }
            
            return is_allowed, info
            
        except Exception as e:
            print(f"Rate limiter error: {e}")
            # Fail open - allow request if Redis is down
            return True, {}
    
    async def check_rate_limit(
        self,
        request: Request,
        rate: Optional[int] = None,
        window: Optional[int] = None,
        key_func: Optional[callable] = None
    ):
        """
        Check rate limit and raise exception if exceeded.
        
        Args:
            request: FastAPI request object
            rate: Requests allowed per window
            window: Time window in seconds
            key_func: Optional function to generate rate limit key
        
        Raises:
            HTTPException: If rate limit exceeded
        """
        # Generate rate limit key
        if key_func:
            key = key_func(request)
        else:
            # Default: use client IP
            key = request.client.host if request.client else "unknown"
        
        # Check rate limit
        is_allowed, info = await self.is_allowed(key, rate, window)
        
        if not is_allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": info.get("limit"),
                    "reset": info.get("reset"),
                    "window": info.get("window")
                },
                headers={
                    "X-RateLimit-Limit": str(info.get("limit", "")),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info.get("reset", "")),
                    "Retry-After": str(info.get("window", ""))
                }
            )
        
        # Add rate limit headers to response
        request.state.rate_limit_info = info


# Global rate limiter instance
rate_limiter = RateLimiter()


# Rate limit configurations for different endpoints
RATE_LIMITS = {
    "default": {"rate": 100, "window": 60},  # 100 requests per minute
    "auth": {"rate": 5, "window": 60},  # 5 login attempts per minute
    "ocr": {"rate": 10, "window": 60},  # 10 OCR requests per minute
    "ai_chat": {"rate": 20, "window": 60},  # 20 AI chat requests per minute
    "upload": {"rate": 30, "window": 60},  # 30 uploads per minute
    "export": {"rate": 10, "window": 60},  # 10 exports per minute
}


def get_rate_limit_key(request: Request) -> str:
    """
    Generate rate limit key from request.
    
    Uses user_id if authenticated, otherwise IP address.
    """
    # Check if user is authenticated
    if hasattr(request.state, "user") and request.state.user:
        return f"user:{request.state.user.id}"
    
    # Fall back to IP address
    return f"ip:{request.client.host if request.client else 'unknown'}"
