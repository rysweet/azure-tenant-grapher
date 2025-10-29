"""
Security utility functions for authentication and authorization testing.

This module provides helper functions for security testing including
token validation, encryption/decryption, security scanning, and audit logging.
"""

import base64
import hmac
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import jwt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2


class TokenValidator:
    """Validate and analyze JWT tokens for security testing."""

    @staticmethod
    def decode_token_unsafe(token: str) -> Dict[str, Any]:
        """
        Decode token without signature verification (for testing only).

        Args:
            token: JWT token string

        Returns:
            Decoded token payload
        """
        return jwt.decode(token, options={"verify_signature": False})

    @staticmethod
    def validate_token_structure(token: str) -> Tuple[bool, List[str]]:
        """
        Validate JWT token structure and format.

        Args:
            token: JWT token string

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check basic structure
        parts = token.split(".")
        if len(parts) != 3:
            issues.append(
                f"Invalid token structure: expected 3 parts, got {len(parts)}"
            )
            return False, issues

        # Try to decode header
        try:
            header = json.loads(base64.urlsafe_b64decode(parts[0] + "=="))
            if "alg" not in header:
                issues.append("Missing 'alg' in header")
            if "typ" not in header:
                issues.append("Missing 'typ' in header")
        except Exception as e:
            issues.append(f"Invalid header encoding: {e}")

        # Try to decode payload
        try:
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "=="))

            # Check required claims
            required_claims = ["iss", "sub", "aud", "exp", "iat"]
            for claim in required_claims:
                if claim not in payload:
                    issues.append(f"Missing required claim: {claim}")

            # Check expiration
            if "exp" in payload:
                exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
                if exp_time < datetime.now(timezone.utc):
                    issues.append("Token is expired")

            # Check issued at time
            if "iat" in payload:
                iat_time = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
                if iat_time > datetime.now(timezone.utc):
                    issues.append("Token issued in the future")

        except Exception as e:
            issues.append(f"Invalid payload encoding: {e}")

        return len(issues) == 0, issues

    @staticmethod
    def check_token_vulnerabilities(token: str) -> List[str]:
        """
        Check for common JWT vulnerabilities.

        Args:
            token: JWT token string

        Returns:
            List of detected vulnerabilities
        """
        vulnerabilities = []

        try:
            header = json.loads(base64.urlsafe_b64decode(token.split(".")[0] + "=="))

            # Check for 'none' algorithm vulnerability
            if header.get("alg", "").lower() == "none":
                vulnerabilities.append("CRITICAL: Token uses 'none' algorithm")

            # Check for weak algorithms
            weak_algs = ["HS256", "HS384", "HS512"]
            if header.get("alg") in weak_algs:
                vulnerabilities.append(
                    f"Token uses symmetric algorithm: {header['alg']}"
                )

            # Check for algorithm confusion
            if "jku" in header or "jwk" in header or "x5u" in header:
                vulnerabilities.append(
                    "Token contains key URL claims (potential key confusion)"
                )

        except Exception:
            vulnerabilities.append("Unable to parse token header")

        return vulnerabilities


class EncryptionHelper:
    """Helper class for encryption and decryption operations."""

    @staticmethod
    def generate_key() -> bytes:
        """Generate a new Fernet encryption key."""
        return Fernet.generate_key()

    @staticmethod
    def encrypt_data(data: str, key: bytes) -> str:
        """
        Encrypt data using Fernet symmetric encryption.

        Args:
            data: String data to encrypt
            key: Encryption key

        Returns:
            Base64 encoded encrypted data
        """
        f = Fernet(key)
        encrypted = f.encrypt(data.encode())
        return base64.b64encode(encrypted).decode()

    @staticmethod
    def decrypt_data(encrypted_data: str, key: bytes) -> str:
        """
        Decrypt data using Fernet symmetric encryption.

        Args:
            encrypted_data: Base64 encoded encrypted data
            key: Decryption key

        Returns:
            Decrypted string data
        """
        f = Fernet(key)
        decrypted = f.decrypt(base64.b64decode(encrypted_data))
        return decrypted.decode()

    @staticmethod
    def hash_password(password: str, salt: Optional[bytes] = None) -> Tuple[str, str]:
        """
        Hash password using PBKDF2.

        Args:
            password: Password to hash
            salt: Optional salt (will be generated if not provided)

        Returns:
            Tuple of (hashed_password, salt) both as hex strings
        """
        if salt is None:
            salt = secrets.token_bytes(32)

        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())

        return key.hex(), salt.hex()

    @staticmethod
    def verify_password(password: str, hashed: str, salt: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Password to verify
            hashed: Hex string of hashed password
            salt: Hex string of salt

        Returns:
            True if password matches
        """
        salt_bytes = bytes.fromhex(salt)
        new_hash, _ = EncryptionHelper.hash_password(password, salt_bytes)
        return hmac.compare_digest(new_hash, hashed)


class SecurityScanner:
    """Scan for security vulnerabilities in requests and responses."""

    # Patterns for various attacks
    SQL_INJECTION_PATTERNS = [
        r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|CREATE)\b)",
        r"(--|#|\/\*|\*\/)",
        r"(\bOR\b\s*\d*\s*=\s*\d*)",
        r"(\bAND\b\s*\d*\s*=\s*\d*)",
        r"('|\"|;|\\x00|\\n|\\r|\\x1a)",
    ]

    XSS_PATTERNS = [
        r"(<script[^>]*>.*?</script>)",
        r"(javascript:)",
        r"(on\w+\s*=)",
        r"(<iframe[^>]*>)",
        r"(document\.(cookie|write|domain))",
        r"(window\.(location|open))",
    ]

    PATH_TRAVERSAL_PATTERNS = [
        r"(\.\./|\.\.\\)",
        r"(%2e%2e%2f|%2e%2e/)",
        r"(\.\.;)",
        r"(\w+://)",
        r"(/etc/passwd|/windows/system32)",
    ]

    @classmethod
    def scan_for_sql_injection(cls, text: str) -> List[str]:
        """
        Scan text for SQL injection patterns.

        Args:
            text: Text to scan

        Returns:
            List of detected patterns
        """
        detected = []
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(f"SQL Injection pattern detected: {pattern}")
        return detected

    @classmethod
    def scan_for_xss(cls, text: str) -> List[str]:
        """
        Scan text for XSS patterns.

        Args:
            text: Text to scan

        Returns:
            List of detected patterns
        """
        detected = []
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(f"XSS pattern detected: {pattern}")
        return detected

    @classmethod
    def scan_for_path_traversal(cls, text: str) -> List[str]:
        """
        Scan text for path traversal patterns.

        Args:
            text: Text to scan

        Returns:
            List of detected patterns
        """
        detected = []
        for pattern in cls.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append(f"Path traversal pattern detected: {pattern}")
        return detected

    @classmethod
    def scan_for_sensitive_data(cls, text: str) -> List[str]:
        """
        Scan text for sensitive data patterns.

        Args:
            text: Text to scan

        Returns:
            List of detected sensitive data
        """
        detected = []

        # Credit card pattern (simplified)
        if re.search(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b", text):
            detected.append("Potential credit card number detected")

        # SSN pattern
        if re.search(r"\b\d{3}-\d{2}-\d{4}\b", text):
            detected.append("Potential SSN detected")

        # API key patterns
        api_key_patterns = [
            r"api[_-]?key[\"']?\s*[:=]\s*[\"']?[\w-]{20,}",
            r"sk_[a-z]+_[\w]{20,}",
            r"pk_[a-z]+_[\w]{20,}",
        ]
        for pattern in api_key_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                detected.append("Potential API key detected")
                break

        # Private key pattern
        if "BEGIN RSA PRIVATE KEY" in text or "BEGIN PRIVATE KEY" in text:
            detected.append("Private key detected")

        return detected


class AuditLogger:
    """Mock audit logger for security event testing."""

    def __init__(self):
        self.events = []

    def log_authentication(
        self,
        user_id: str,
        success: bool,
        method: str,
        ip_address: str,
        user_agent: str = None,
    ):
        """Log authentication attempt."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "authentication",
            "user_id": user_id,
            "success": success,
            "method": method,
            "ip_address": ip_address,
            "user_agent": user_agent,
        }
        self.events.append(event)
        return event

    def log_authorization(
        self,
        user_id: str,
        resource: str,
        action: str,
        allowed: bool,
        reason: str = None,
    ):
        """Log authorization decision."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "authorization",
            "user_id": user_id,
            "resource": resource,
            "action": action,
            "allowed": allowed,
            "reason": reason,
        }
        self.events.append(event)
        return event

    def log_security_violation(
        self, violation_type: str, details: str, source_ip: str, user_id: str = None
    ):
        """Log security violation."""
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "security_violation",
            "violation_type": violation_type,
            "details": details,
            "source_ip": source_ip,
            "user_id": user_id,
        }
        self.events.append(event)
        return event

    def get_events(
        self,
        event_type: str = None,
        user_id: str = None,
        start_time: datetime = None,
        end_time: datetime = None,
    ) -> List[Dict[str, Any]]:
        """Query audit events."""
        filtered = self.events

        if event_type:
            filtered = [e for e in filtered if e["event_type"] == event_type]

        if user_id:
            filtered = [e for e in filtered if e.get("user_id") == user_id]

        if start_time:
            filtered = [
                e
                for e in filtered
                if datetime.fromisoformat(e["timestamp"]) >= start_time
            ]

        if end_time:
            filtered = [
                e
                for e in filtered
                if datetime.fromisoformat(e["timestamp"]) <= end_time
            ]

        return filtered

    def clear(self):
        """Clear all events."""
        self.events.clear()


class MockAzureADClient:
    """Mock Azure AD client for testing authentication flows."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.tokens = {}
        self.refresh_tokens = {}
        self.failed_attempts = {}

    def authenticate(
        self, username: str, password: str, tenant_id: str = None
    ) -> Dict[str, Any]:
        """Mock authentication flow."""
        tenant_id = tenant_id or self.config.get("tenant_id")

        # Track failed attempts
        key = f"{tenant_id}:{username}"
        if key not in self.failed_attempts:
            self.failed_attempts[key] = 0

        # Simulate account lockout after 3 attempts
        if self.failed_attempts[key] >= 3:
            raise Exception("Account locked due to multiple failed attempts")

        # Check credentials
        if password == "invalid":
            self.failed_attempts[key] += 1
            raise Exception("Invalid credentials")

        # Reset failed attempts on success
        self.failed_attempts[key] = 0

        # Generate tokens
        token_id = secrets.token_urlsafe(32)
        self.tokens[token_id] = {
            "access_token": f"access_{token_id}",
            "refresh_token": f"refresh_{token_id}",
            "expires_in": 3600,
            "token_type": "Bearer",
            "user_id": username,
            "tenant_id": tenant_id,
        }

        self.refresh_tokens[f"refresh_{token_id}"] = token_id

        return self.tokens[token_id]

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Mock token refresh flow."""
        if refresh_token not in self.refresh_tokens:
            raise Exception("Invalid refresh token")

        old_token_id = self.refresh_tokens[refresh_token]
        old_token = self.tokens.get(old_token_id)

        if not old_token:
            raise Exception("Token not found")

        # Generate new tokens
        new_token_id = secrets.token_urlsafe(32)
        self.tokens[new_token_id] = {
            "access_token": f"access_{new_token_id}",
            "refresh_token": f"refresh_{new_token_id}",
            "expires_in": 3600,
            "token_type": "Bearer",
            "user_id": old_token["user_id"],
            "tenant_id": old_token["tenant_id"],
        }

        # Invalidate old tokens
        del self.tokens[old_token_id]
        del self.refresh_tokens[refresh_token]

        self.refresh_tokens[f"refresh_{new_token_id}"] = new_token_id

        return self.tokens[new_token_id]

    def validate_token(self, access_token: str) -> bool:
        """Validate access token."""
        for token_data in self.tokens.values():
            if token_data["access_token"] == access_token:
                return True
        return False

    def revoke_token(self, access_token: str):
        """Revoke access token."""
        for token_id, token_data in list(self.tokens.items()):
            if token_data["access_token"] == access_token:
                # Remove access token
                del self.tokens[token_id]
                # Remove associated refresh token
                refresh_key = f"refresh_{token_id}"
                if refresh_key in self.refresh_tokens:
                    del self.refresh_tokens[refresh_key]
                return True
        return False


def generate_csrf_token() -> str:
    """Generate a CSRF token for testing."""
    return secrets.token_urlsafe(32)


def validate_csrf_token(token: str, expected: str) -> bool:
    """Validate CSRF token with timing-safe comparison."""
    return hmac.compare_digest(token, expected)


def simulate_brute_force_attack(
    client: MockAzureADClient, username: str, password_list: List[str], delay: float = 0
) -> Tuple[bool, str]:
    """
    Simulate brute force attack for testing.

    Args:
        client: Mock Azure AD client
        username: Target username
        password_list: List of passwords to try
        delay: Delay between attempts (seconds)

    Returns:
        Tuple of (success, successful_password or error_message)
    """
    for password in password_list:
        try:
            if delay > 0:
                time.sleep(delay)

            result = client.authenticate(username, password)
            return True, password
        except Exception as e:
            if "locked" in str(e).lower():
                return False, str(e)
            continue

    return False, "All passwords failed"


def check_security_headers(headers: Dict[str, str]) -> List[str]:
    """
    Check if security headers are properly set.

    Args:
        headers: HTTP headers dictionary

    Returns:
        List of missing or misconfigured headers
    """
    issues = []
    required_headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": ["DENY", "SAMEORIGIN"],
        "Strict-Transport-Security": None,  # Just check presence
        "Content-Security-Policy": None,  # Just check presence
    }

    for header, expected_value in required_headers.items():
        if header not in headers:
            issues.append(f"Missing security header: {header}")
        elif expected_value:
            actual = headers[header]
            if isinstance(expected_value, list):
                if actual not in expected_value:
                    issues.append(
                        f"Invalid {header}: {actual} (expected one of {expected_value})"
                    )
            elif actual != expected_value:
                issues.append(f"Invalid {header}: {actual} (expected {expected_value})")

    return issues
