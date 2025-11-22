"""
Content Security Policy (CSP) Middleware
Implements strict CSP headers with nonce generation for inline scripts/styles
"""
import secrets
import hashlib
from typing import Callable, Optional, Dict, List
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

logger = logging.getLogger(__name__)


class CSPConfig:
    """CSP Configuration with sensible defaults"""

    def __init__(
        self,
        report_only: bool = False,
        report_uri: Optional[str] = None,
        script_src: List[str] = None,
        style_src: List[str] = None,
        img_src: List[str] = None,
        connect_src: List[str] = None,
        font_src: List[str] = None,
        object_src: List[str] = None,
        media_src: List[str] = None,
        frame_src: List[str] = None,
        frame_ancestors: List[str] = None,
        base_uri: List[str] = None,
        form_action: List[str] = None,
    ):
        self.report_only = report_only
        self.report_uri = report_uri

        # Default strict CSP directives
        self.script_src = script_src or ["'self'"]
        self.style_src = style_src or ["'self'"]
        self.img_src = img_src or ["'self'", "data:", "https:"]
        self.connect_src = connect_src or ["'self'"]
        self.font_src = font_src or ["'self'"]
        self.object_src = object_src or ["'none'"]
        self.media_src = media_src or ["'self'"]
        self.frame_src = frame_src or ["'none'"]
        self.frame_ancestors = frame_ancestors or ["'none'"]
        self.base_uri = base_uri or ["'self'"]
        self.form_action = form_action or ["'self'"]


class CSPMiddleware(BaseHTTPMiddleware):
    """
    Content Security Policy Middleware

    Features:
    - Automatic nonce generation for inline scripts/styles
    - Report-only mode for testing
    - Violation reporting
    - Per-request CSP customization
    """

    def __init__(self, app: ASGIApp, config: Optional[CSPConfig] = None):
        super().__init__(app)
        self.config = config or CSPConfig()

    def generate_nonce(self) -> str:
        """Generate cryptographically secure nonce"""
        return secrets.token_urlsafe(16)

    def build_csp_header(self, nonce: str) -> str:
        """Build CSP header value with nonce"""
        directives = []

        # Add nonce to script-src and style-src
        script_src = self.config.script_src.copy()
        script_src.append(f"'nonce-{nonce}'")
        script_src.append("'strict-dynamic'")  # Modern CSP

        style_src = self.config.style_src.copy()
        style_src.append(f"'nonce-{nonce}'")

        # Build all directives
        directives.append(f"default-src 'self'")
        directives.append(f"script-src {' '.join(script_src)}")
        directives.append(f"style-src {' '.join(style_src)}")
        directives.append(f"img-src {' '.join(self.config.img_src)}")
        directives.append(f"connect-src {' '.join(self.config.connect_src)}")
        directives.append(f"font-src {' '.join(self.config.font_src)}")
        directives.append(f"object-src {' '.join(self.config.object_src)}")
        directives.append(f"media-src {' '.join(self.config.media_src)}")
        directives.append(f"frame-src {' '.join(self.config.frame_src)}")
        directives.append(f"frame-ancestors {' '.join(self.config.frame_ancestors)}")
        directives.append(f"base-uri {' '.join(self.config.base_uri)}")
        directives.append(f"form-action {' '.join(self.config.form_action)}")

        # Add upgrade-insecure-requests in production
        directives.append("upgrade-insecure-requests")

        # Add report-uri if configured
        if self.config.report_uri:
            directives.append(f"report-uri {self.config.report_uri}")

        return "; ".join(directives)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add CSP headers"""
        # Generate nonce for this request
        nonce = self.generate_nonce()

        # Store nonce in request state for template rendering
        request.state.csp_nonce = nonce

        # Process request
        response = await call_next(request)

        # Build and add CSP header
        csp_header = self.build_csp_header(nonce)
        header_name = (
            "Content-Security-Policy-Report-Only"
            if self.config.report_only
            else "Content-Security-Policy"
        )

        response.headers[header_name] = csp_header

        logger.debug(f"Added CSP header: {header_name}")

        return response
