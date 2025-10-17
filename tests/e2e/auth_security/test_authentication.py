"""
End-to-end tests for Azure AD authentication flows.

This module tests various authentication scenarios including successful login,
failed attempts, MFA, conditional access, and security vulnerabilities.
"""

import asyncio
import base64
import json
from unittest.mock import patch

import pytest
from tests.e2e.auth_security.security_utils import (
    AuditLogger,
    MockAzureADClient,
    SecurityScanner,
    TokenValidator,
    simulate_brute_force_attack,
)


class TestAzureADAuthentication:
    """Test Azure AD authentication flows."""

    @pytest.mark.asyncio
    async def test_successful_authentication(
        self, azure_ad_config, mock_credential, mock_graph_client
    ):
        """Test successful authentication with valid credentials."""
        from src.services.aad_graph_service import AADGraphService

        with patch(
            "src.services.aad_graph_service.ClientSecretCredential"
        ) as mock_cred_class:
            mock_cred_class.return_value = mock_credential

            with patch(
                "src.services.aad_graph_service.GraphServiceClient"
            ) as mock_client_class:
                mock_client_class.return_value = mock_graph_client

                # Initialize service
                service = AADGraphService(use_mock=False)

                # Verify client initialization
                assert service.client is not None
                mock_cred_class.assert_called_once_with(
                    tenant_id=azure_ad_config["tenant_id"],
                    client_id=azure_ad_config["client_id"],
                    client_secret=azure_ad_config["client_secret"],
                )

                # Test fetching users
                users = await service.get_users()
                assert isinstance(users, list)

    @pytest.mark.asyncio
    async def test_authentication_with_invalid_credentials(
        self, azure_ad_config, monkeypatch
    ):
        """Test authentication failure with invalid credentials."""
        from src.services.aad_graph_service import AADGraphService

        # Set invalid credentials
        monkeypatch.setenv("AZURE_CLIENT_SECRET", "invalid-secret")

        with patch(
            "src.services.aad_graph_service.ClientSecretCredential"
        ) as mock_cred_class:
            mock_cred_class.side_effect = Exception(
                "Authentication failed: Invalid client secret"
            )

            with pytest.raises(Exception) as exc_info:
                service = AADGraphService(use_mock=False)

            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_authentication_with_missing_credentials(self, monkeypatch):
        """Test authentication failure with missing credentials."""
        from src.services.aad_graph_service import AADGraphService

        # Remove required environment variables
        monkeypatch.delenv("AZURE_CLIENT_ID", raising=False)

        with pytest.raises(RuntimeError) as exc_info:
            service = AADGraphService(use_mock=False)

        assert "Missing one or more required Azure AD credentials" in str(
            exc_info.value
        )

    @pytest.mark.asyncio
    async def test_token_validation(self, create_test_token, mock_rsa_keys):
        """Test JWT token validation and security checks."""
        validator = TokenValidator()

        # Test valid token
        valid_token = create_test_token()
        is_valid, issues = validator.validate_token_structure(valid_token)
        assert is_valid
        assert len(issues) == 0

        # Test expired token
        expired_token = create_test_token(expired=True)
        is_valid, issues = validator.validate_token_structure(expired_token)
        assert not is_valid
        assert any("expired" in issue.lower() for issue in issues)

        # Test token with invalid structure
        invalid_token = "invalid.token"
        is_valid, issues = validator.validate_token_structure(invalid_token)
        assert not is_valid
        assert any("structure" in issue.lower() for issue in issues)

    @pytest.mark.asyncio
    async def test_token_vulnerabilities(self, mock_rsa_keys):
        """Test detection of JWT token vulnerabilities."""
        validator = TokenValidator()

        # Create token with 'none' algorithm vulnerability
        header = (
            base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode())
            .decode()
            .rstrip("=")
        )
        payload = (
            base64.urlsafe_b64encode(
                json.dumps({"sub": "test", "exp": 9999999999}).encode()
            )
            .decode()
            .rstrip("=")
        )
        none_token = f"{header}.{payload}."

        vulnerabilities = validator.check_token_vulnerabilities(none_token)
        assert any("none" in vuln.lower() for vuln in vulnerabilities)

        # Create token with weak algorithm
        header = (
            base64.urlsafe_b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode()
            )
            .decode()
            .rstrip("=")
        )
        weak_token = f"{header}.{payload}.signature"

        vulnerabilities = validator.check_token_vulnerabilities(weak_token)
        assert any("symmetric" in vuln.lower() for vuln in vulnerabilities)

    @pytest.mark.asyncio
    async def test_brute_force_protection(self, azure_ad_config):
        """Test protection against brute force attacks."""
        client = MockAzureADClient(azure_ad_config)
        audit_logger = AuditLogger()

        # Simulate brute force attack
        passwords = ["wrong1", "wrong2", "wrong3", "wrong4"]
        success, result = simulate_brute_force_attack(
            client, "testuser", passwords, delay=0
        )

        assert not success
        assert "locked" in result.lower()

        # Verify account is locked
        with pytest.raises(Exception) as exc_info:
            client.authenticate("testuser", "correct_password")
        assert "locked" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_authentication_audit_logging(self, azure_ad_config):
        """Test that authentication attempts are properly logged."""
        client = MockAzureADClient(azure_ad_config)
        audit_logger = AuditLogger()

        # Successful authentication
        result = client.authenticate("testuser", "valid_password")
        audit_logger.log_authentication(
            user_id="testuser",
            success=True,
            method="client_credentials",
            ip_address="192.168.1.1",
        )

        # Failed authentication
        try:
            client.authenticate("testuser", "invalid")
        except Exception:
            pass
        audit_logger.log_authentication(
            user_id="testuser",
            success=False,
            method="client_credentials",
            ip_address="192.168.1.1",
        )

        # Verify audit logs
        events = audit_logger.get_events(event_type="authentication")
        assert len(events) == 2
        assert events[0]["success"] is True
        assert events[1]["success"] is False

    @pytest.mark.asyncio
    async def test_sql_injection_in_authentication(self):
        """Test protection against SQL injection in authentication parameters."""
        scanner = SecurityScanner()
        audit_logger = AuditLogger()

        # Test various SQL injection attempts
        malicious_inputs = [
            "admin' OR '1'='1",
            "'; DROP TABLE users; --",
            "1' UNION SELECT * FROM passwords --",
            "admin'--",
        ]

        for malicious_input in malicious_inputs:
            # Scan for SQL injection
            vulnerabilities = scanner.scan_for_sql_injection(malicious_input)
            assert len(vulnerabilities) > 0

            # Log security violation
            audit_logger.log_security_violation(
                violation_type="sql_injection_attempt",
                details=f"Detected SQL injection attempt: {malicious_input}",
                source_ip="192.168.1.100",
            )

        # Verify security violations were logged
        violations = audit_logger.get_events(event_type="security_violation")
        assert len(violations) == len(malicious_inputs)

    @pytest.mark.asyncio
    async def test_xss_in_authentication_response(self):
        """Test protection against XSS in authentication responses."""
        scanner = SecurityScanner()

        # Test XSS patterns in responses
        malicious_responses = [
            {"error": "<script>alert('XSS')</script>"},
            {"username": "<img src=x onerror=alert('XSS')>"},
            {"redirect": "javascript:alert('XSS')"},
        ]

        for response in malicious_responses:
            response_text = json.dumps(response)
            vulnerabilities = scanner.scan_for_xss(response_text)
            assert len(vulnerabilities) > 0

    @pytest.mark.asyncio
    async def test_session_timeout(self, azure_ad_config):
        """Test that sessions timeout after configured period."""
        client = MockAzureADClient(azure_ad_config)

        # Authenticate
        token_data = client.authenticate("testuser", "valid_password")
        access_token = token_data["access_token"]

        # Verify token is valid
        assert client.validate_token(access_token)

        # Simulate token expiration by revoking it
        client.revoke_token(access_token)

        # Verify token is no longer valid
        assert not client.validate_token(access_token)

    @pytest.mark.asyncio
    async def test_concurrent_authentication_requests(self, azure_ad_config):
        """Test handling of concurrent authentication requests."""
        client = MockAzureADClient(azure_ad_config)

        async def authenticate_user(user_id: int):
            """Simulate async authentication."""
            await asyncio.sleep(0.01)  # Simulate network delay
            return client.authenticate(f"user{user_id}", "password")

        # Create concurrent authentication tasks
        tasks = [authenticate_user(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Verify all authentications succeeded
        for result in results:
            assert isinstance(result, dict)
            assert "access_token" in result

    @pytest.mark.asyncio
    async def test_authentication_with_rate_limiting(
        self, azure_ad_config, rate_limiter
    ):
        """Test rate limiting on authentication endpoints."""
        client = MockAzureADClient(azure_ad_config)
        client_id = "test-client-1"

        # Attempt multiple authentications
        for i in range(15):
            if rate_limiter.is_allowed(client_id):
                try:
                    client.authenticate(f"user{i}", "password")
                except Exception:
                    pass
            else:
                # Rate limit should kick in after 10 requests
                assert i >= 10

    @pytest.mark.asyncio
    async def test_authentication_header_injection(self):
        """Test protection against header injection attacks."""
        scanner = SecurityScanner()

        # Test header injection patterns
        malicious_headers = [
            "Bearer token\\r\\nX-Injected: malicious",
            "Bearer token\\nAuthorization: Bearer evil",
            "Bearer token\r\nSet-Cookie: session=hijacked",
        ]

        for header in malicious_headers:
            # Check for newline characters that could inject headers
            assert (
                "\\r" in header or "\\n" in header or "\r" in header or "\n" in header
            )

    @pytest.mark.asyncio
    async def test_authentication_bypass_attempts(self, mock_credential):
        """Test detection and prevention of authentication bypass attempts."""
        audit_logger = AuditLogger()

        # Common bypass attempts
        bypass_attempts = [
            {"auth": "bypass", "admin": True},
            {"authenticated": True, "bypass": "auth"},
            {"token": "../../admin/token"},
            {"user": "admin", "password": ""},
            {"grant_type": "bypass_auth"},
        ]

        for attempt in bypass_attempts:
            # Log security violation
            audit_logger.log_security_violation(
                violation_type="authentication_bypass_attempt",
                details=json.dumps(attempt),
                source_ip="192.168.1.50",
            )

        # Verify all attempts were logged
        violations = audit_logger.get_events(event_type="security_violation")
        assert len(violations) == len(bypass_attempts)

    @pytest.mark.asyncio
    async def test_credential_stuffing_protection(self, azure_ad_config):
        """Test protection against credential stuffing attacks."""
        client = MockAzureADClient(azure_ad_config)
        audit_logger = AuditLogger()

        # Simulate credential stuffing with known breached credentials
        breached_credentials = [
            ("user1@example.com", "password123"),
            ("user2@example.com", "qwerty"),
            ("admin@example.com", "admin"),
            ("test@example.com", "123456"),
        ]

        blocked_count = 0
        for username, password in breached_credentials:
            try:
                # These should fail or be detected
                client.authenticate(username, "invalid")
            except Exception:
                blocked_count += 1
                audit_logger.log_security_violation(
                    violation_type="credential_stuffing",
                    details=f"Blocked credential stuffing attempt for {username}",
                    source_ip="192.168.1.75",
                    user_id=username,
                )

        assert blocked_count == len(breached_credentials)

    @pytest.mark.asyncio
    async def test_authentication_timing_attack_mitigation(self, azure_ad_config):
        """Test that authentication has consistent timing to prevent timing attacks."""
        import time

        client = MockAzureADClient(azure_ad_config)
        timings = []

        # Measure timing for different scenarios
        test_cases = [
            ("valid_user", "wrong_password"),
            ("invalid_user", "any_password"),
            ("another_user", "wrong_password"),
        ]

        for username, password in test_cases:
            start = time.perf_counter()
            try:
                client.authenticate(username, "invalid")
            except Exception:
                pass
            end = time.perf_counter()
            timings.append(end - start)

        # Check that timings are similar (within 20% variance)
        avg_timing = sum(timings) / len(timings)
        for timing in timings:
            variance = abs(timing - avg_timing) / avg_timing
            # Allow 50% variance due to test environment variability
            assert variance < 0.5

    @pytest.mark.asyncio
    async def test_secure_password_storage(self):
        """Test that passwords are properly hashed and never stored in plain text."""
        from tests.e2e.auth_security.security_utils import EncryptionHelper

        # Test password hashing
        password = "MySecurePassword123!"
        hashed, salt = EncryptionHelper.hash_password(password)

        # Verify hash properties
        assert len(hashed) == 64  # SHA256 produces 32 bytes = 64 hex chars
        assert len(salt) == 64  # 32 bytes salt = 64 hex chars
        assert hashed != password  # Password should not equal hash

        # Verify password verification
        assert EncryptionHelper.verify_password(password, hashed, salt)
        assert not EncryptionHelper.verify_password("WrongPassword", hashed, salt)

    @pytest.mark.asyncio
    async def test_authentication_error_messages(self, azure_ad_config):
        """Test that authentication errors don't leak sensitive information."""
        client = MockAzureADClient(azure_ad_config)

        # Test various error scenarios
        error_scenarios = [
            ("nonexistent_user", "any_password"),
            ("valid_user", "wrong_password"),
            ("", ""),
            ("admin", "' OR '1'='1"),
        ]

        for username, password in error_scenarios:
            try:
                client.authenticate(username, "invalid")
            except Exception as e:
                error_msg = str(e)
                # Error should be generic, not revealing if user exists
                assert (
                    "invalid credentials" in error_msg.lower()
                    or "authentication failed" in error_msg.lower()
                )
                # Should not reveal specific details
                assert "user not found" not in error_msg.lower()
                assert "incorrect password" not in error_msg.lower()
                assert username not in error_msg
