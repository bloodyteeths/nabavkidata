"""
Security Headers Middleware
Implements OWASP-recommended security headers
"""
from typing import Callable, Dict, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger(__name__)


class SecurityHeadersConfig:
    """Configuration for security headers"""

    def __init__(self, environment: str = "production"):
        self.environment = environment

        # HSTS (HTTP Strict Transport Security)
        self.hsts_max_age = 31536000  # 1 year
        self.hsts_include_subdomains = True
        self.hsts_preload = True

        # X-Frame-Options
        self.x_frame_options = "DENY"

        # X-Content-Type-Options
        self.x_content_type_options = "nosniff"

        # Referrer-Policy
        self.referrer_policy = "strict-origin-when-cross-origin"

        # Permissions-Policy (formerly Feature-Policy)
        self.permissions_policy = {
            "geolocation": [],
            "microphone": [],
            "camera": [],
            "payment": ["self"],
            "usb": [],
            "magnetometer": [],
            "gyroscope": [],
            "accelerometer": [],
        }

        # X-XSS-Protection (legacy, but still useful)
        self.x_xss_protection = "1; mode=block"

        # X-Permitted-Cross-Domain-Policies
        self.x_permitted_cross_domain_policies = "none"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Security headers middleware

    Adds OWASP-recommended security headers to all responses:
    - HSTS (HTTP Strict Transport Security)
    - X-Frame-Options
    - X-Content-Type-Options
    - Referrer-Policy
    - Permissions-Policy
    - X-XSS-Protection
    """

    def __init__(self, app: ASGIApp, config: Optional[SecurityHeadersConfig] = None):
        super().__init__(app)
        self.config = config or SecurityHeadersConfig()

    def _build_hsts_header(self) -> str:
        """Build HSTS header value"""
        hsts = f"max-age={self.config.hsts_max_age}"
        if self.config.hsts_include_subdomains:
            hsts += "; includeSubDomains"
        if self.config.hsts_preload:
            hsts += "; preload"
        return hsts

    def _build_permissions_policy(self) -> str:
        """Build Permissions-Policy header value"""
        policies = []
        for feature, allowed_origins in self.config.permissions_policy.items():
            if not allowed_origins:
                policies.append(f"{feature}=()")
            else:
                origins = " ".join(f'"{origin}"' if origin != "self" else origin for origin in allowed_origins)
                policies.append(f"{feature}=({origins})")
        return ", ".join(policies)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Add security headers to response"""
        response = await call_next(request)

        # HSTS - only on HTTPS
        if request.url.scheme == "https" or self.config.environment == "production":
            response.headers["Strict-Transport-Security"] = self._build_hsts_header()

        # X-Frame-Options - prevent clickjacking
        response.headers["X-Frame-Options"] = self.config.x_frame_options

        # X-Content-Type-Options - prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = self.config.x_content_type_options

        # Referrer-Policy - control referrer information
        response.headers["Referrer-Policy"] = self.config.referrer_policy

        # Permissions-Policy - control browser features
        response.headers["Permissions-Policy"] = self._build_permissions_policy()

        # X-XSS-Protection - legacy XSS protection
        response.headers["X-XSS-Protection"] = self.config.x_xss_protection

        # X-Permitted-Cross-Domain-Policies - prevent Adobe Flash/PDF access
        response.headers["X-Permitted-Cross-Domain-Policies"] = (
            self.config.x_permitted_cross_domain_policies
        )

        logger.debug("Security headers added to response")

        return response
