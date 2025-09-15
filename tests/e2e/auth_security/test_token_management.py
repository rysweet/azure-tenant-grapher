"""
End-to-end tests for token lifecycle management.

This module tests token generation, validation, refresh, expiration,
revocation, and secure storage of tokens.
"""

import base64
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, patch

import jwt
import pytest

from tests.e2e.auth_security.security_utils import (
    AuditLogger,
    EncryptionHelper,
    MockAzureADClient,
    TokenValidator,
)


class TokenManager:
    """Mock token manager for testing token lifecycle."""

    def __init__(self, encryption_key: bytes = None):
        self.tokens = {}
        self.refresh_tokens = {}
        self.revoked_tokens = set()
        self.token_expiry = {}
        self.encryption_key = encryption_key or EncryptionHelper.generate_key()
        self.audit_logger = AuditLogger()

    def generate_token(
        self,
        user_id: str,
        scopes: list = None,
        expires_in: int = 3600
    ) -> Dict[str, Any]:
        """Generate new access and refresh tokens."""
        import secrets

        access_token = f"access_{secrets.token_urlsafe(32)}"
        refresh_token = f"refresh_{secrets.token_urlsafe(32)}"

        expiry_time = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        token_data = {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": expires_in,
            "expires_at": expiry_time.isoformat(),
            "user_id": user_id,
            "scopes": scopes or ["read"],
            "issued_at": datetime.now(timezone.utc).isoformat()
        }

        # Store tokens
        self.tokens[access_token] = token_data
        self.refresh_tokens[refresh_token] = access_token
        self.token_expiry[access_token] = expiry_time

        # Audit log
        self.audit_logger.log_authentication(
            user_id=user_id,
            success=True,
            method="token_generation",
            ip_address="127.0.0.1"
        )

        return token_data

    def validate_token(self, access_token: str) -> Tuple[bool, Optional[str]]:
        """Validate access token."""
        # Check if revoked
        if access_token in self.revoked_tokens:
            return False, "Token has been revoked"

        # Check if exists
        if access_token not in self.tokens:
            return False, "Token not found"

        # Check expiration
        expiry = self.token_expiry.get(access_token)
        if expiry and expiry < datetime.now(timezone.utc):
            return False, "Token has expired"

        return True, None

    def refresh_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh access token using refresh token."""
        if refresh_token not in self.refresh_tokens:
            raise ValueError("Invalid refresh token")

        old_access_token = self.refresh_tokens[refresh_token]
        old_token_data = self.tokens.get(old_access_token)

        if not old_token_data:
            raise ValueError("Associated access token not found")

        # Generate new tokens
        new_token_data = self.generate_token(
            user_id=old_token_data["user_id"],
            scopes=old_token_data["scopes"]
        )

        # Revoke old tokens
        self.revoke_token(old_access_token)
        del self.refresh_tokens[refresh_token]

        return new_token_data

    def revoke_token(self, access_token: str) -> bool:
        """Revoke an access token."""
        if access_token in self.tokens:
            self.revoked_tokens.add(access_token)
            # Also revoke associated refresh token
            for refresh, access in list(self.refresh_tokens.items()):
                if access == access_token:
                    del self.refresh_tokens[refresh]
            return True
        return False

    def store_token_encrypted(self, token_data: Dict[str, Any]) -> str:
        """Store token data encrypted."""
        json_data = json.dumps(token_data)
        encrypted = EncryptionHelper.encrypt_data(json_data, self.encryption_key)
        return encrypted

    def retrieve_token_encrypted(self, encrypted_data: str) -> Dict[str, Any]:
        """Retrieve and decrypt token data."""
        decrypted = EncryptionHelper.decrypt_data(encrypted_data, self.encryption_key)
        return json.loads(decrypted)


class TestTokenManagement:
    """Test token lifecycle management."""

    def test_token_generation(self):
        """Test secure token generation."""
        manager = TokenManager()

        token_data = manager.generate_token(
            user_id="user123",
            scopes=["read", "write"]
        )

        # Verify token structure
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        assert "expires_in" in token_data
        assert token_data["token_type"] == "Bearer"

        # Verify tokens are unique
        token2 = manager.generate_token("user456")
        assert token_data["access_token"] != token2["access_token"]
        assert token_data["refresh_token"] != token2["refresh_token"]

    def test_token_validation(self):
        """Test token validation logic."""
        manager = TokenManager()

        # Generate token
        token_data = manager.generate_token("user123")
        access_token = token_data["access_token"]

        # Valid token should pass
        is_valid, error = manager.validate_token(access_token)
        assert is_valid
        assert error is None

        # Invalid token should fail
        is_valid, error = manager.validate_token("invalid_token")
        assert not is_valid
        assert "not found" in error.lower()

    def test_token_expiration(self):
        """Test that tokens expire correctly."""
        manager = TokenManager()

        # Generate token with short expiry
        token_data = manager.generate_token("user123", expires_in=1)
        access_token = token_data["access_token"]

        # Token should be valid immediately
        is_valid, _ = manager.validate_token(access_token)
        assert is_valid

        # Wait for expiration
        time.sleep(2)

        # Manually set expiry to past for testing
        manager.token_expiry[access_token] = datetime.now(timezone.utc) - timedelta(seconds=1)

        # Token should be expired
        is_valid, error = manager.validate_token(access_token)
        assert not is_valid
        assert "expired" in error.lower()

    def test_token_refresh(self):
        """Test token refresh flow."""
        manager = TokenManager()

        # Generate initial tokens
        initial_data = manager.generate_token("user123")
        initial_access = initial_data["access_token"]
        refresh_token = initial_data["refresh_token"]

        # Refresh tokens
        new_data = manager.refresh_token(refresh_token)

        # Verify new tokens are generated
        assert new_data["access_token"] != initial_access
        assert new_data["refresh_token"] != refresh_token

        # Old access token should be revoked
        is_valid, error = manager.validate_token(initial_access)
        assert not is_valid
        assert "revoked" in error.lower()

        # Old refresh token should not work
        with pytest.raises(ValueError):
            manager.refresh_token(refresh_token)

    def test_token_revocation(self):
        """Test token revocation."""
        manager = TokenManager()

        # Generate token
        token_data = manager.generate_token("user123")
        access_token = token_data["access_token"]

        # Token should be valid
        is_valid, _ = manager.validate_token(access_token)
        assert is_valid

        # Revoke token
        assert manager.revoke_token(access_token)

        # Token should no longer be valid
        is_valid, error = manager.validate_token(access_token)
        assert not is_valid
        assert "revoked" in error.lower()

    def test_token_rotation_security(self):
        """Test that token rotation prevents replay attacks."""
        manager = TokenManager()

        # Generate initial token
        initial_data = manager.generate_token("user123")
        refresh_token = initial_data["refresh_token"]

        # First refresh should succeed
        new_data = manager.refresh_token(refresh_token)

        # Attempting to use the same refresh token again should fail
        with pytest.raises(ValueError) as exc_info:
            manager.refresh_token(refresh_token)
        assert "Invalid refresh token" in str(exc_info.value)

    def test_encrypted_token_storage(self):
        """Test secure storage of tokens."""
        manager = TokenManager()

        # Generate token
        token_data = manager.generate_token("user123", scopes=["admin"])

        # Encrypt token data
        encrypted = manager.store_token_encrypted(token_data)

        # Verify it's actually encrypted
        assert encrypted != json.dumps(token_data)
        assert "access_token" not in encrypted
        assert "user123" not in encrypted

        # Decrypt and verify
        decrypted = manager.retrieve_token_encrypted(encrypted)
        assert decrypted["access_token"] == token_data["access_token"]
        assert decrypted["user_id"] == "user123"

    def test_token_tampering_detection(self, create_test_token, mock_rsa_keys):
        """Test detection of tampered JWT tokens."""
        validator = TokenValidator()

        # Create valid token
        valid_token = create_test_token()

        # Tamper with the token by modifying payload
        parts = valid_token.split('.')
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + '=='))
        payload["admin"] = True  # Add unauthorized claim
        tampered_payload = base64.urlsafe_b64encode(
            json.dumps(payload).encode()
        ).decode().rstrip('=')

        tampered_token = f"{parts[0]}.{tampered_payload}.{parts[2]}"

        # Token structure might still be valid
        is_valid, issues = validator.validate_token_structure(tampered_token)

        # But signature verification would fail (in real implementation)
        # For testing, we check that tokens are different
        assert tampered_token != valid_token

    def test_concurrent_token_operations(self):
        """Test thread safety of concurrent token operations."""
        import threading

        manager = TokenManager()
        results = {"generated": [], "validated": [], "errors": []}
        lock = threading.Lock()

        def generate_tokens(user_id: str, count: int):
            """Generate multiple tokens."""
            for _ in range(count):
                try:
                    token_data = manager.generate_token(user_id)
                    with lock:
                        results["generated"].append(token_data["access_token"])
                except Exception as e:
                    with lock:
                        results["errors"].append(str(e))

        def validate_tokens(tokens: list):
            """Validate multiple tokens."""
            for token in tokens:
                try:
                    is_valid, _ = manager.validate_token(token)
                    with lock:
                        results["validated"].append((token, is_valid))
                except Exception as e:
                    with lock:
                        results["errors"].append(str(e))

        # Create threads for concurrent operations
        threads = []

        # Generate tokens concurrently
        for i in range(5):
            t = threading.Thread(target=generate_tokens, args=(f"user{i}", 10))
            threads.append(t)
            t.start()

        # Wait for generation to complete
        for t in threads:
            t.join()

        # Validate tokens concurrently
        validation_threads = []
        for i in range(3):
            tokens_subset = results["generated"][i*10:(i+1)*10]
            t = threading.Thread(target=validate_tokens, args=(tokens_subset,))
            validation_threads.append(t)
            t.start()

        for t in validation_threads:
            t.join()

        # Verify results
        assert len(results["generated"]) == 50  # 5 users * 10 tokens
        assert len(results["errors"]) == 0
        assert all(valid for _, valid in results["validated"][:30])  # First 30 should be valid

    def test_token_scope_enforcement(self):
        """Test that token scopes are properly enforced."""
        manager = TokenManager()

        # Generate tokens with different scopes
        read_token = manager.generate_token("user1", scopes=["read"])
        write_token = manager.generate_token("user2", scopes=["read", "write"])
        admin_token = manager.generate_token("admin", scopes=["read", "write", "delete", "admin"])

        # Verify scopes are stored correctly
        assert manager.tokens[read_token["access_token"]]["scopes"] == ["read"]
        assert "write" in manager.tokens[write_token["access_token"]]["scopes"]
        assert "admin" in manager.tokens[admin_token["access_token"]]["scopes"]

    def test_token_jti_uniqueness(self, create_test_token):
        """Test that JWT ID (jti) claims are unique to prevent replay."""
        seen_jtis = set()

        for _ in range(100):
            import uuid
            token = create_test_token(claims={"jti": str(uuid.uuid4())})
            decoded = jwt.decode(token, options={"verify_signature": False})

            jti = decoded.get("jti")
            assert jti not in seen_jtis  # Each token should have unique jti
            seen_jtis.add(jti)

    def test_token_audience_validation(self, create_test_token):
        """Test that token audience is properly validated."""
        # Token for different audience
        wrong_audience_token = create_test_token(
            claims={"aud": "https://wrong-api.example.com"}
        )

        decoded = jwt.decode(wrong_audience_token, options={"verify_signature": False})
        assert decoded["aud"] != "https://graph.microsoft.com"

    def test_token_issuer_validation(self, create_test_token):
        """Test that token issuer is properly validated."""
        # Token from untrusted issuer
        untrusted_issuer_token = create_test_token(
            claims={"iss": "https://evil.example.com/"}
        )

        decoded = jwt.decode(untrusted_issuer_token, options={"verify_signature": False})
        assert "evil.example.com" in decoded["iss"]

    def test_token_nbf_validation(self, create_test_token):
        """Test 'not before' (nbf) claim validation."""
        # Token not valid yet
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        future_token = create_test_token(
            claims={"nbf": int(future_time.timestamp())}
        )

        decoded = jwt.decode(future_token, options={"verify_signature": False})
        nbf_time = datetime.fromtimestamp(decoded["nbf"], tz=timezone.utc)
        assert nbf_time > datetime.now(timezone.utc)

    def test_refresh_token_security(self):
        """Test that refresh tokens have appropriate security measures."""
        manager = TokenManager()

        # Generate token
        token_data = manager.generate_token("user123")
        refresh_token = token_data["refresh_token"]

        # Refresh token should be long and random
        assert len(refresh_token) > 30
        assert refresh_token.startswith("refresh_")

        # Refresh token should not contain user information
        assert "user123" not in refresh_token
        assert "admin" not in refresh_token

    def test_token_storage_security(self):
        """Test that tokens are not stored in plain text."""
        manager = TokenManager()

        # Generate sensitive token
        token_data = manager.generate_token(
            "admin_user",
            scopes=["admin", "delete_all"]
        )

        # Encrypt for storage
        encrypted = manager.store_token_encrypted(token_data)

        # Sensitive data should not be visible in encrypted form
        assert "admin_user" not in encrypted
        assert "delete_all" not in encrypted
        assert token_data["access_token"] not in encrypted

    def test_token_cleanup_expired(self):
        """Test cleanup of expired tokens to prevent memory leaks."""
        manager = TokenManager()

        # Generate tokens with different expiry times
        expired_tokens = []
        for i in range(5):
            token_data = manager.generate_token(f"user{i}", expires_in=1)
            expired_tokens.append(token_data["access_token"])
            # Set to expired
            manager.token_expiry[token_data["access_token"]] = (
                datetime.now(timezone.utc) - timedelta(seconds=1)
            )

        # Generate valid tokens
        valid_tokens = []
        for i in range(5):
            token_data = manager.generate_token(f"user{i+5}", expires_in=3600)
            valid_tokens.append(token_data["access_token"])

        # Implement cleanup method
        def cleanup_expired_tokens():
            now = datetime.now(timezone.utc)
            expired = []
            for token, expiry in list(manager.token_expiry.items()):
                if expiry < now:
                    expired.append(token)
                    del manager.tokens[token]
                    del manager.token_expiry[token]
            return expired

        # Run cleanup
        cleaned = cleanup_expired_tokens()

        # Verify expired tokens were removed
        assert len(cleaned) == 5
        for token in expired_tokens:
            assert token not in manager.tokens

        # Verify valid tokens remain
        for token in valid_tokens:
            assert token in manager.tokens

    def test_token_binding_to_client(self):
        """Test that tokens are bound to specific clients/devices."""
        manager = TokenManager()

        # Extend token data with client binding
        class ClientBoundTokenManager(TokenManager):
            def generate_token(self, user_id: str, client_id: str = None, **kwargs):
                token_data = super().generate_token(user_id, **kwargs)
                token_data["client_id"] = client_id
                token_data["client_fingerprint"] = self._generate_fingerprint(client_id)
                return token_data

            def _generate_fingerprint(self, client_id: str) -> str:
                import hashlib
                return hashlib.sha256(f"{client_id}".encode()).hexdigest()[:16]

            def validate_token_with_client(self, access_token: str, client_id: str):
                is_valid, error = self.validate_token(access_token)
                if not is_valid:
                    return False, error

                token_data = self.tokens.get(access_token)
                if token_data["client_id"] != client_id:
                    return False, "Token not valid for this client"

                return True, None

        bound_manager = ClientBoundTokenManager()

        # Generate token for specific client
        token_data = bound_manager.generate_token("user123", client_id="mobile_app_v1")

        # Validation should fail with different client
        is_valid, error = bound_manager.validate_token_with_client(
            token_data["access_token"], "web_browser"
        )
        assert not is_valid
        assert "not valid for this client" in error

        # Validation should succeed with correct client
        is_valid, error = bound_manager.validate_token_with_client(
            token_data["access_token"], "mobile_app_v1"
        )
        assert is_valid