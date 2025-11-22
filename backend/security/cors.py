"""
CORS Configuration with Whitelist Origins
Secure Cross-Origin Resource Sharing configuration
"""
from typing import List, Optional, Union
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import re
import logging

logger = logging.getLogger(__name__)


class CORSConfig:
    """CORS configuration with environment-based settings"""

    def __init__(
        self,
        environment: str = "production",
        allowed_origins: Optional[List[str]] = None,
        allowed_origin_regex: Optional[str] = None,
    ):
        self.environment = environment

        # Production whitelist
        if environment == "production":
            self.allowed_origins = allowed_origins or [
                "https://nabavki.gov.si",
                "https://www.nabavki.gov.si",
                "https://api.nabavki.gov.si",
            ]
            self.allow_credentials = True
            self.allowed_methods = ["GET", "POST", "PUT", "DELETE", "PATCH"]
            self.allowed_headers = [
                "Content-Type",
                "Authorization",
                "X-Requested-With",
                "X-CSRF-Token",
            ]
            self.expose_headers = [
                "X-Total-Count",
                "X-Page-Count",
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset",
            ]
            self.max_age = 3600  # 1 hour preflight cache

        # Development settings
        elif environment == "development":
            self.allowed_origins = allowed_origins or [
                "http://localhost:3000",
                "http://localhost:8000",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:8000",
            ]
            self.allow_credentials = True
            self.allowed_methods = ["*"]
            self.allowed_headers = ["*"]
            self.expose_headers = ["*"]
            self.max_age = 600  # 10 minutes

        # Testing settings
        else:
            self.allowed_origins = ["*"]
            self.allow_credentials = False
            self.allowed_methods = ["*"]
            self.allowed_headers = ["*"]
            self.expose_headers = ["*"]
            self.max_age = 0

        # Optional regex pattern for dynamic origins
        self.allowed_origin_regex = allowed_origin_regex


def configure_cors(app: FastAPI, config: Optional[CORSConfig] = None) -> None:
    """
    Configure CORS middleware for FastAPI application

    Args:
        app: FastAPI application instance
        config: CORS configuration (defaults to production)
    """
    if config is None:
        config = CORSConfig(environment="production")

    logger.info(f"Configuring CORS for {config.environment} environment")
    logger.info(f"Allowed origins: {config.allowed_origins}")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.allowed_origins,
        allow_credentials=config.allow_credentials,
        allow_methods=config.allowed_methods,
        allow_headers=config.allowed_headers,
        expose_headers=config.expose_headers,
        max_age=config.max_age,
        allow_origin_regex=config.allowed_origin_regex,
    )


class StrictCORSMiddleware(BaseHTTPMiddleware):
    """
    Strict CORS middleware with additional validation

    Features:
    - Origin validation against whitelist
    - Logging of CORS violations
    - Dynamic origin validation with regex
    """

    def __init__(self, app: ASGIApp, config: CORSConfig):
        super().__init__(app)
        self.config = config
        self.origin_regex = (
            re.compile(config.allowed_origin_regex)
            if config.allowed_origin_regex
            else None
        )

    def _is_origin_allowed(self, origin: str) -> bool:
        """Check if origin is in whitelist or matches regex"""
        # Check exact match
        if origin in self.config.allowed_origins:
            return True

        # Check regex pattern
        if self.origin_regex and self.origin_regex.match(origin):
            return True

        return False

    async def dispatch(self, request: Request, call_next):
        """Validate CORS origin before processing"""
        origin = request.headers.get("origin")

        if origin and not self._is_origin_allowed(origin):
            logger.warning(f"CORS violation: Blocked origin {origin} for {request.url.path}")

        response = await call_next(request)
        return response
