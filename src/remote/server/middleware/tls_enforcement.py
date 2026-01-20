"""TLS enforcement middleware for production security.

Philosophy:
- Ruthless simplicity: Simple HTTPS check
- Environment-aware: Only enforced in production
- Clear errors: Tell users to use HTTPS

Issue #580: Security hardening for production deployment
"""

import logging
import os

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class TLSEnforcement(BaseHTTPMiddleware):
    """Enforce HTTPS in production environments.

    Rejects non-HTTPS requests with clear error message.
    Disabled in development for easier testing.
    """

    def __init__(self, app, enforce: bool = True):
        """Initialize TLS enforcement.

        Args:
            app: FastAPI application
            enforce: Whether to enforce TLS (default: True in production)
        """
        super().__init__(app)
        # Auto-detect environment
        environment = os.getenv("ENVIRONMENT", "production").lower()
        self.enforce = enforce and environment == "production"
        logger.info(
            f"TLS enforcement: {'ENABLED' if self.enforce else 'DISABLED'} "
            f"(environment={environment})"
        )

    async def dispatch(self, request: Request, call_next):
        """Process request with TLS enforcement."""
        if not self.enforce:
            return await call_next(request)

        # Check if request is HTTPS
        if request.url.scheme != "https":
            logger.warning(
                f"Rejected non-HTTPS request: {request.method} {request.url.path}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "HTTPS required",
                    "message": "This service requires HTTPS in production. "
                    "Please use https:// instead of http://",
                    "documentation": "See docs/security/ for TLS setup",
                },
            )

        return await call_next(request)


__all__ = ["TLSEnforcement"]
