"""
Advanced Rate Limiting with Redis Backend
Implements sliding window algorithm with per-endpoint and per-user limits
"""
import time
import hashlib
from typing import Optional, Dict, Callable, Tuple
from datetime import datetime, timedelta
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import redis.asyncio as redis
import logging
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimitConfig:
    """Rate limit configuration for different endpoint types"""

    # Global defaults
    DEFAULT_LIMIT = 100
    DEFAULT_WINDOW = 60  # seconds

    # Per-endpoint configurations
    ENDPOINT_LIMITS = {
        "/api/auth/login": (5, 60),  # 5 requests per minute
        "/api/auth/register": (3, 60),  # 3 requests per minute
        "/api/auth/password-reset": (3, 300),  # 3 requests per 5 minutes
        "/api/tenders/search": (30, 60),  # 30 requests per minute
        "/api/tenders/export": (5, 300),  # 5 exports per 5 minutes
        "/api/analytics": (20, 60),  # 20 requests per minute
        "/api/scraper/trigger": (1, 300),  # 1 trigger per 5 minutes
    }

    # User tier limits (authenticated users)
    USER_TIER_LIMITS = {
        "free": (100, 60),  # 100 requests per minute
        "premium": (500, 60),  # 500 requests per minute
        "enterprise": (2000, 60),  # 2000 requests per minute
    }


class SlidingWindowRateLimiter:
    """
    Redis-based sliding window rate limiter

    Features:
    - Sliding window algorithm for smooth rate limiting
    - Per-IP and per-user tracking
    - Distributed rate limiting via Redis
    - Automatic cleanup of old entries
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        prefix: str = "ratelimit",
    ):
        self.redis = redis_client
        self.prefix = prefix

    def _get_key(self, identifier: str, endpoint: str) -> str:
        """Generate Redis key for rate limit tracking"""
        key_hash = hashlib.sha256(f"{identifier}:{endpoint}".encode()).hexdigest()[:16]
        return f"{self.prefix}:{key_hash}"

    async def is_allowed(
        self,
        identifier: str,
        endpoint: str,
        limit: int,
        window: int,
    ) -> Tuple[bool, Dict[str, int]]:
        """
        Check if request is allowed under rate limit

        Returns:
            Tuple of (is_allowed, rate_limit_info)
        """
        key = self._get_key(identifier, endpoint)
        now = time.time()
        window_start = now - window

        try:
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count requests in current window
            pipe.zcard(key)

            # Add current request with score = timestamp
            pipe.zadd(key, {str(now): now})

            # Set expiration to window size
            pipe.expire(key, window)

            # Execute pipeline
            results = await pipe.execute()

            # Get count before adding current request
            current_count = results[1]

            # Check if limit exceeded
            is_allowed = current_count < limit
            remaining = max(0, limit - current_count - 1)

            # Calculate reset time
            reset_time = int(now + window)

            rate_limit_info = {
                "limit": limit,
                "remaining": remaining if is_allowed else 0,
                "reset": reset_time,
                "retry_after": window if not is_allowed else 0,
            }

            return is_allowed, rate_limit_info

        except redis.RedisError as e:
            logger.error(f"Redis error in rate limiter: {e}")
            # Fail open - allow request if Redis is down
            return True, {
                "limit": limit,
                "remaining": limit,
                "reset": int(now + window),
                "retry_after": 0,
            }

    async def reset_limit(self, identifier: str, endpoint: str) -> bool:
        """Reset rate limit for identifier/endpoint"""
        key = self._get_key(identifier, endpoint)
        try:
            await self.redis.delete(key)
            return True
        except redis.RedisError as e:
            logger.error(f"Failed to reset rate limit: {e}")
            return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware for FastAPI

    Features:
    - IP-based rate limiting for anonymous users
    - User-based rate limiting for authenticated users
    - Per-endpoint custom limits
    - X-RateLimit headers in responses
    """

    def __init__(
        self,
        app: ASGIApp,
        redis_client: redis.Redis,
        config: Optional[RateLimitConfig] = None,
    ):
        super().__init__(app)
        self.limiter = SlidingWindowRateLimiter(redis_client)
        self.config = config or RateLimitConfig()

    def _get_identifier(self, request: Request) -> str:
        """Get unique identifier for rate limiting (IP or user ID)"""
        # Check for authenticated user
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "id"):
            return f"user:{user.id}"

        # Fall back to IP address
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
        else:
            ip = request.client.host if request.client else "unknown"

        return f"ip:{ip}"

    def _get_limits(self, request: Request, endpoint: str) -> Tuple[int, int]:
        """Get rate limit and window for request"""
        # Check for per-endpoint limits
        if endpoint in self.config.ENDPOINT_LIMITS:
            return self.config.ENDPOINT_LIMITS[endpoint]

        # Check for user tier limits
        user = getattr(request.state, "user", None)
        if user and hasattr(user, "tier"):
            tier = user.tier.lower()
            if tier in self.config.USER_TIER_LIMITS:
                return self.config.USER_TIER_LIMITS[tier]

        # Default limits
        return self.config.DEFAULT_LIMIT, self.config.DEFAULT_WINDOW

    async def dispatch(self, request: Request, call_next: Callable):
        """Process request with rate limiting"""
        endpoint = request.url.path
        identifier = self._get_identifier(request)
        limit, window = self._get_limits(request, endpoint)

        # Check rate limit
        is_allowed, rate_info = await self.limiter.is_allowed(
            identifier, endpoint, limit, window
        )

        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for {identifier} on {endpoint}"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please retry after {rate_info['retry_after']} seconds.",
                    "retry_after": rate_info["retry_after"],
                },
                headers={
                    "X-RateLimit-Limit": str(rate_info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(rate_info["reset"]),
                    "Retry-After": str(rate_info["retry_after"]),
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(rate_info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(rate_info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(rate_info["reset"])

        return response
