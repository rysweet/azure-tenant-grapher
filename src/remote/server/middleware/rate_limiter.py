"""Rate limiting middleware for ATG Remote Service.

Philosophy:
- Ruthless simplicity: In-memory rate limiting (no Redis dependency)
- Production-ready: 10 scans per hour limit
- Clear error messages: Tell users when they're rate limited

Issue #580: Security hardening for production deployment
"""

import logging
import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class RateLimiter(BaseHTTPMiddleware):
    """Simple in-memory rate limiter for scan operations.

    Limits scan operations to 10 per hour per API key to prevent abuse.
    """

    def __init__(self, app, requests_per_hour: int = 10):
        """Initialize rate limiter.

        Args:
            app: FastAPI application
            requests_per_hour: Maximum requests allowed per hour (default: 10)
        """
        super().__init__(app)
        self.requests_per_hour = requests_per_hour
        self.window_seconds = 3600  # 1 hour
        # Track: api_key -> list of (timestamp, endpoint) tuples
        self._requests: Dict[str, list[Tuple[float, str]]] = defaultdict(list)
        logger.info(f"Rate limiter initialized: {requests_per_hour} requests per hour")

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting."""
        # Only rate limit scan endpoints
        if not request.url.path.startswith("/scan"):
            return await call_next(request)

        # Get API key from header
        api_key = request.headers.get("X-API-Key", "anonymous")

        # Clean old entries and check rate limit
        current_time = time.time()
        self._clean_old_entries(api_key, current_time)

        if self._is_rate_limited(api_key):
            logger.warning(f"Rate limit exceeded for API key: {api_key[:8]}...")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "limit": f"{self.requests_per_hour} scans per hour",
                    "retry_after": self._get_retry_after(api_key),
                },
            )

        # Record this request
        self._requests[api_key].append((current_time, request.url.path))

        # Process request
        return await call_next(request)

    def _clean_old_entries(self, api_key: str, current_time: float) -> None:
        """Remove entries older than the time window."""
        cutoff = current_time - self.window_seconds
        self._requests[api_key] = [
            (ts, path) for ts, path in self._requests[api_key] if ts > cutoff
        ]

    def _is_rate_limited(self, api_key: str) -> bool:
        """Check if API key has exceeded rate limit."""
        return len(self._requests[api_key]) >= self.requests_per_hour

    def _get_retry_after(self, api_key: str) -> int:
        """Get seconds until next request allowed."""
        if not self._requests[api_key]:
            return 0

        oldest_request = min(ts for ts, _ in self._requests[api_key])
        retry_after = int((oldest_request + self.window_seconds) - time.time())
        return max(0, retry_after)

    def get_stats(self, api_key: str) -> Dict[str, int]:
        """Get rate limit stats for an API key."""
        current_time = time.time()
        self._clean_old_entries(api_key, current_time)

        return {
            "requests_used": len(self._requests[api_key]),
            "requests_remaining": max(
                0, self.requests_per_hour - len(self._requests[api_key])
            ),
            "window_seconds": self.window_seconds,
            "retry_after": self._get_retry_after(api_key)
            if self._is_rate_limited(api_key)
            else 0,
        }


__all__ = ["RateLimiter"]
