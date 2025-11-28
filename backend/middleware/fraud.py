"""
Fraud Prevention Middleware for nabavkidata.com
Integrates fraud detection into the request pipeline
"""
from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
import logging

from services.fraud_prevention import perform_fraud_check
from database import get_db

logger = logging.getLogger(__name__)


class FraudPreventionMiddleware(BaseHTTPMiddleware):
    """
    Middleware to perform fraud checks on protected endpoints

    This middleware intercepts requests to sensitive endpoints and performs
    fraud detection checks including:
    - Rate limiting
    - IP blocking
    - VPN/Proxy detection
    - Device fingerprinting
    """

    # Endpoints that require fraud checking
    PROTECTED_ENDPOINTS = [
        "/api/ai/query",
        "/api/rag/query",
        "/api/billing/create-checkout-session",
        "/api/billing/create-portal-session",
    ]

    # Endpoints exempt from fraud checking
    EXEMPT_ENDPOINTS = [
        "/api/auth/login",
        "/api/auth/register",
        "/api/auth/logout",
        "/health",
        "/api/docs",
        "/api/openapi.json",
    ]

    async def dispatch(self, request: Request, call_next: Callable):
        """
        Process the request through fraud prevention checks
        """
        # Skip OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path

        # Skip exempt endpoints
        if any(path.startswith(endpoint) for endpoint in self.EXEMPT_ENDPOINTS):
            return await call_next(request)

        # Check if endpoint requires fraud checking
        should_check = any(path.startswith(endpoint) for endpoint in self.PROTECTED_ENDPOINTS)

        if should_check:
            try:
                # Extract request information
                ip_address = self._get_client_ip(request)
                user_agent = request.headers.get("user-agent", "")
                device_fingerprint = request.headers.get("x-device-fingerprint", "")

                # Get user from request state (set by auth middleware)
                user = getattr(request.state, "user", None)

                if user:
                    # Perform fraud check
                    async for db in get_db():
                        is_allowed, reason, details = await perform_fraud_check(
                            db=db,
                            user=user,
                            ip_address=ip_address,
                            device_fingerprint=device_fingerprint,
                            user_agent=user_agent,
                            check_type="query"
                        )

                        if not is_allowed:
                            logger.warning(
                                f"Fraud check blocked user {user.user_id} "
                                f"from {ip_address}: {reason}"
                            )

                            # Return appropriate error response
                            if "limit" in reason.lower():
                                status_code = status.HTTP_429_TOO_MANY_REQUESTS
                            elif "trial" in reason.lower():
                                status_code = status.HTTP_402_PAYMENT_REQUIRED
                            else:
                                status_code = status.HTTP_403_FORBIDDEN

                            return JSONResponse(
                                status_code=status_code,
                                content={
                                    "detail": reason,
                                    "redirect_to": details.get("redirect_to", "/billing/plans"),
                                    "upgrade_required": "limit" in reason.lower() or "trial" in reason.lower()
                                }
                            )

                        break  # Exit the async generator

            except Exception as e:
                logger.error(f"Error in fraud prevention middleware: {e}")
                # Don't block the request on middleware errors
                # but log them for investigation

        # Continue with the request
        response = await call_next(request)
        return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request
        Handles proxy headers (X-Forwarded-For, X-Real-IP)
        """
        # Check for proxy headers first
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fall back to direct client IP
        client_host = request.client.host if request.client else "unknown"
        return client_host
