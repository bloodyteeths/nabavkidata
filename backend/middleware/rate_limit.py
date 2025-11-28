"""
Rate Limiting Middleware for nabavkidata.com
Prevents API abuse through request rate limiting
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable, Dict
from datetime import datetime, timedelta
import logging
from collections import defaultdict
import asyncio

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware for rate limiting API requests

    Implements token bucket algorithm for rate limiting per IP address
    Different endpoints can have different rate limits
    """

    # Rate limit configuration (requests per time window)
    RATE_LIMITS = {
        # Authentication endpoints - more lenient
        "/api/auth/login": {"requests": 5, "window_seconds": 60},
        "/api/auth/register": {"requests": 3, "window_seconds": 3600},
        "/api/auth/forgot-password": {"requests": 3, "window_seconds": 3600},

        # AI/RAG endpoints - strict limits
        "/api/ai/query": {"requests": 10, "window_seconds": 60},
        "/api/rag/query": {"requests": 10, "window_seconds": 60},

        # Billing endpoints - moderate limits
        "/api/billing": {"requests": 10, "window_seconds": 60},

        # Admin endpoints - strict limits
        "/api/admin": {"requests": 30, "window_seconds": 60},

        # Default rate limit for all other endpoints
        "default": {"requests": 60, "window_seconds": 60},
    }

    # Endpoints exempt from rate limiting
    EXEMPT_ENDPOINTS = [
        "/health",
        "/api/docs",
        "/api/openapi.json",
        "/api/redoc",
    ]

    def __init__(self, app):
        super().__init__(app)
        # Store request counts per IP per endpoint
        # WARNING: In-memory storage - resets on restart, not shared across workers
        # TODO: Implement Redis-backed rate limiting for production (Phase 4)
        self.request_counts: Dict[str, Dict[str, list]] = defaultdict(lambda: defaultdict(list))
        # Start cleanup task
        self._cleanup_task = None
        logger.warning(
            "RateLimitMiddleware: Using in-memory storage. Rate limits reset on restart "
            "and are not shared across workers. For production scale, implement Redis-backed rate limiting."
        )

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process the request through rate limiting
        """
        path = request.url.path

        # Skip exempt endpoints
        if any(path.startswith(endpoint) for endpoint in self.EXEMPT_ENDPOINTS):
            return await call_next(request)

        # Get client IP
        ip_address = self._get_client_ip(request)

        # Get rate limit configuration for this endpoint
        rate_limit = self._get_rate_limit(path)

        # Check rate limit
        if not self._is_allowed(ip_address, path, rate_limit):
            logger.warning(
                f"Rate limit exceeded for IP {ip_address} on endpoint {path}"
            )

            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "retry_after": rate_limit["window_seconds"]
                },
                headers={
                    "Retry-After": str(rate_limit["window_seconds"])
                }
            )

        # Continue with the request
        response = await call_next(request)

        # Add rate limit headers to response
        remaining = self._get_remaining_requests(ip_address, path, rate_limit)
        response.headers["X-RateLimit-Limit"] = str(rate_limit["requests"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(rate_limit["window_seconds"])

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        client_host = request.client.host if request.client else "unknown"
        return client_host

    def _get_rate_limit(self, path: str) -> Dict[str, int]:
        """Get rate limit configuration for endpoint"""
        # Check for exact match first
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]

        # Check for prefix match
        for endpoint, limit in self.RATE_LIMITS.items():
            if endpoint != "default" and path.startswith(endpoint):
                return limit

        # Return default rate limit
        return self.RATE_LIMITS["default"]

    def _is_allowed(self, ip: str, path: str, rate_limit: Dict[str, int]) -> bool:
        """
        Check if request is allowed based on rate limit
        Uses sliding window algorithm
        """
        now = datetime.utcnow()
        window_seconds = rate_limit["window_seconds"]
        max_requests = rate_limit["requests"]

        # Get request history for this IP and endpoint
        key = f"{ip}:{path}"
        request_times = self.request_counts[ip][path]

        # Remove old requests outside the time window
        cutoff_time = now - timedelta(seconds=window_seconds)
        request_times[:] = [t for t in request_times if t > cutoff_time]

        # Check if limit exceeded
        if len(request_times) >= max_requests:
            return False

        # Add current request
        request_times.append(now)
        return True

    def _get_remaining_requests(self, ip: str, path: str, rate_limit: Dict[str, int]) -> int:
        """Get number of remaining requests in current window"""
        now = datetime.utcnow()
        window_seconds = rate_limit["window_seconds"]
        max_requests = rate_limit["requests"]

        # Get request history
        request_times = self.request_counts[ip][path]

        # Remove old requests
        cutoff_time = now - timedelta(seconds=window_seconds)
        request_times[:] = [t for t in request_times if t > cutoff_time]

        # Calculate remaining
        return max(0, max_requests - len(request_times))

    async def _cleanup_old_entries(self):
        """
        Periodic cleanup of old request records
        Runs every 5 minutes
        """
        while True:
            await asyncio.sleep(300)  # 5 minutes

            try:
                now = datetime.utcnow()
                # Keep only last hour of data
                cutoff_time = now - timedelta(hours=1)

                for ip in list(self.request_counts.keys()):
                    for path in list(self.request_counts[ip].keys()):
                        request_times = self.request_counts[ip][path]
                        request_times[:] = [t for t in request_times if t > cutoff_time]

                        # Remove empty paths
                        if not request_times:
                            del self.request_counts[ip][path]

                    # Remove empty IPs
                    if not self.request_counts[ip]:
                        del self.request_counts[ip]

                logger.info("Rate limit cleanup completed")
            except Exception as e:
                logger.error(f"Error in rate limit cleanup: {e}")
