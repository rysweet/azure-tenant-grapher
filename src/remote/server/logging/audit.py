"""Audit logging for ATG Remote Service operations.

Philosophy:
- Ruthless simplicity: Structured JSON logs to stdout
- Security-first: Automatic secret redaction
- Production-ready: All scan operations logged

Issue #580: Security hardening for production deployment
"""

import json
import logging
import re
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AuditLogger:
    """Structured audit logging for security-critical operations."""

    # Patterns for secrets to redact
    SECRET_PATTERNS = [
        (re.compile(r"(?i)(password|secret|key|token)[\s]*[:=][\s]*['\"]?([^'\"}\s,]+)", re.IGNORECASE), r"\1=<REDACTED>"),
        (re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE), "Bearer <REDACTED>"),
        (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE), "<GUID-REDACTED>"),
    ]

    def __init__(self, service_name: str = "atg-remote"):
        """Initialize audit logger.

        Args:
            service_name: Service identifier for log entries
        """
        self.service_name = service_name
        self.audit_log = logging.getLogger(f"{service_name}.audit")
        self.audit_log.setLevel(logging.INFO)

    def log_scan_request(
        self,
        api_key: str,
        tenant_id: str,
        subscription_ids: Optional[list[str]] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Log scan operation request.

        Args:
            api_key: API key used (will be truncated)
            tenant_id: Target tenant ID
            subscription_ids: Optional list of subscription IDs
            user_agent: Optional user agent string
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "event": "scan_request",
            "api_key": self._truncate_api_key(api_key),
            "tenant_id": self._redact_guid(tenant_id),
            "subscription_count": len(subscription_ids) if subscription_ids else 0,
            "user_agent": user_agent,
        }
        self.audit_log.info(json.dumps(entry))

    def log_scan_complete(
        self,
        api_key: str,
        tenant_id: str,
        resource_count: int,
        duration_seconds: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """Log scan operation completion.

        Args:
            api_key: API key used (will be truncated)
            tenant_id: Target tenant ID
            resource_count: Number of resources discovered
            duration_seconds: Scan duration
            success: Whether scan succeeded
            error: Optional error message
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "event": "scan_complete",
            "api_key": self._truncate_api_key(api_key),
            "tenant_id": self._redact_guid(tenant_id),
            "resource_count": resource_count,
            "duration_seconds": round(duration_seconds, 2),
            "success": success,
        }
        if error:
            entry["error"] = self._redact_secrets(error)

        self.audit_log.info(json.dumps(entry))

    def log_auth_failure(
        self, api_key: str, reason: str, ip_address: Optional[str] = None
    ) -> None:
        """Log authentication failure.

        Args:
            api_key: API key attempted (will be truncated)
            reason: Failure reason
            ip_address: Optional client IP
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "service": self.service_name,
            "event": "auth_failure",
            "api_key": self._truncate_api_key(api_key),
            "reason": reason,
            "ip_address": ip_address,
        }
        self.audit_log.warning(json.dumps(entry))

    def _truncate_api_key(self, api_key: str) -> str:
        """Truncate API key for logging (show first 8 chars only)."""
        if not api_key or len(api_key) < 8:
            return "***"
        return f"{api_key[:8]}..."

    def _redact_guid(self, guid: str) -> str:
        """Redact GUID for privacy."""
        if not guid or len(guid) < 8:
            return "***"
        return f"{guid[:8]}..."

    def _redact_secrets(self, text: str) -> str:
        """Redact secrets from text using pattern matching."""
        result = text
        for pattern, replacement in self.SECRET_PATTERNS:
            result = pattern.sub(replacement, result)
        return result


__all__ = ["AuditLogger"]
