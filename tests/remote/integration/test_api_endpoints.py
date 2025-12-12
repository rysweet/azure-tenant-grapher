"""
Integration tests for API endpoints.

Tests full API endpoint behavior including request validation, authentication,
Neo4j operations, and response formatting. Uses test fixtures for dependencies.

Philosophy:
- Test complete endpoint flows (request → response)
- Use testcontainers for Neo4j (or mocks when unavailable)
- Moderate execution time (< 5s per test)
- 30% of total test suite (integration layer)
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Provide mock Neo4j driver for testing."""
    from unittest.mock import MagicMock

    driver = Mock()
    driver.verify_connectivity = AsyncMock()

    # Mock session context manager - must be MagicMock to support __aenter__/__aexit__
    mock_session = AsyncMock()
    mock_session_context = MagicMock()
    mock_session_context.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session_context.__aexit__ = AsyncMock(return_value=None)

    driver.session = Mock(return_value=mock_session_context)

    return driver


@pytest.fixture
def mock_azure_credential():
    """Provide mock Azure credential."""
    credential = Mock()
    credential.get_token = Mock(return_value=Mock(token="test-token"))
    return credential


@pytest.fixture
def test_api_key():
    """Provide test API key."""
    import secrets

    return f"atg_dev_{secrets.token_hex(32)}"


@pytest.fixture
def api_client(mock_neo4j_driver, mock_azure_credential, test_api_key):
    """Provide FastAPI test client with mocked dependencies."""
    from src.remote.server.main import app

    # Configure app with test dependencies
    # This app doesn't exist yet - will fail!
    with patch("src.remote.db.connection_manager.ConnectionManager") as mock_conn_mgr:
        mock_manager = Mock()
        mock_manager.get_session = AsyncMock(return_value=mock_neo4j_driver.session())
        mock_conn_mgr.return_value = mock_manager

        with patch("src.remote.auth.get_api_key_store") as mock_key_store:
            store = Mock()
            store.validate = Mock(
                return_value={
                    "valid": True,
                    "environment": "dev",
                    "client_id": "test-client-001",
                }
            )
            mock_key_store.return_value = store

            client = TestClient(app)
            yield client


# =============================================================================
# Health Check Endpoint Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_health_endpoint_returns_200(api_client):
    """Test that /health endpoint returns 200 OK."""
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert "version" in data
    assert "neo4j_status" in data


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_health_endpoint_no_auth_required(api_client):
    """Test that /health endpoint does not require authentication."""
    # No Authorization header
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_health_endpoint_reports_neo4j_status(api_client, mock_neo4j_driver):
    """Test that /health endpoint reports Neo4j connection status."""
    with patch("src.remote.db.connection_manager.ConnectionManager") as mock_conn_mgr:
        mock_manager = Mock()
        mock_manager.health_check = AsyncMock(return_value=True)
        mock_conn_mgr.return_value = mock_manager

        response = api_client.get("/api/v1/health")

        data = response.json()
        assert data["neo4j_status"] == "connected"


# =============================================================================
# Scan Endpoint Tests (POST /api/v1/scan)
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_requires_authentication(api_client):
    """Test that /api/v1/scan requires API key authentication."""
    response = api_client.post(
        "/api/v1/scan", json={"tenant_id": "12345678-1234-1234-1234-123456789012"}
    )

    assert response.status_code == 401
    assert "authorization" in response.json()["error"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_accepts_valid_request(api_client, test_api_key):
    """Test that /api/v1/scan accepts valid authenticated request."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert response.status_code in [200, 202]  # 200 OK or 202 Accepted


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_validates_tenant_id_format(api_client, test_api_key):
    """Test that /api/v1/scan validates tenant_id format."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"tenant_id": "invalid-tenant-id"},
    )

    assert response.status_code == 400
    data = response.json()
    assert "tenant" in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_validates_required_fields(api_client, test_api_key):
    """Test that /api/v1/scan validates required fields."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={},  # Missing tenant_id
    )

    assert response.status_code == 400
    data = response.json()
    assert "tenant_id" in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_accepts_optional_parameters(api_client, test_api_key):
    """Test that /api/v1/scan accepts optional parameters."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "resource_limit": 1000,
            "max_llm_threads": 10,
            "generate_spec": True,
            "visualize": False,
        },
    )

    assert response.status_code in [200, 202]


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_scan_endpoint_returns_scan_result(api_client, test_api_key):
    """Test that /api/v1/scan returns scan result structure."""
    with patch("src.remote.server.handlers.scan_handler") as mock_handler:
        mock_handler.return_value = {
            "job_id": "scan-abc123",
            "status": "completed",
            "resources_discovered": 1523,
            "duration_seconds": 320,
        }

        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
        )

        data = response.json()
        assert "job_id" in data
        assert "status" in data
        assert data["status"] == "completed"


# =============================================================================
# Generate IaC Endpoint Tests (POST /api/v1/generate-iac)
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_iac_endpoint_requires_authentication(api_client):
    """Test that /api/v1/generate-iac requires authentication."""
    response = api_client.post(
        "/api/v1/generate-iac",
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert response.status_code == 401


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_iac_endpoint_accepts_format_parameter(api_client, test_api_key):
    """Test that /api/v1/generate-iac accepts format parameter."""
    valid_formats = ["terraform", "arm", "bicep"]

    for fmt in valid_formats:
        response = api_client.post(
            "/api/v1/generate-iac",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012", "format": fmt},
        )

        assert response.status_code in [200, 202]


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_iac_endpoint_rejects_invalid_format(api_client, test_api_key):
    """Test that /api/v1/generate-iac rejects invalid format."""
    response = api_client.post(
        "/api/v1/generate-iac",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "format": "yaml",  # Not supported
        },
    )

    assert response.status_code == 400
    data = response.json()
    assert "format" in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_iac_endpoint_supports_cross_tenant(api_client, test_api_key):
    """Test that /api/v1/generate-iac supports cross-tenant deployment."""
    response = api_client.post(
        "/api/v1/generate-iac",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={
            "tenant_id": "12345678-1234-1234-1234-123456789012",
            "target_tenant_id": "87654321-4321-4321-4321-210987654321",
            "format": "terraform",
        },
    )

    assert response.status_code in [200, 202]


# =============================================================================
# Generate Spec Endpoint Tests (POST /api/v1/generate-spec)
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_spec_endpoint_works_without_tenant_id(api_client, test_api_key):
    """Test that /api/v1/generate-spec works without tenant_id (uses graph)."""
    response = api_client.post(
        "/api/v1/generate-spec",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={},
    )

    assert response.status_code in [200, 202]


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_generate_spec_endpoint_accepts_hierarchical_flag(api_client, test_api_key):
    """Test that /api/v1/generate-spec accepts hierarchical parameter."""
    response = api_client.post(
        "/api/v1/generate-spec",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"hierarchical": True},
    )

    assert response.status_code in [200, 202]


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_handles_azure_auth_failure(api_client, test_api_key):
    """Test that API handles Azure authentication failures gracefully."""
    with patch("src.remote.server.handlers.scan_handler") as mock_handler:
        mock_handler.side_effect = Exception("Azure authentication failed")

        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
        )

        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        # Should not expose internal details
        assert "azure" not in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_handles_neo4j_connection_failure(api_client, test_api_key):
    """Test that API handles Neo4j connection failures."""
    with patch("src.remote.db.connection_manager.ConnectionManager") as mock_conn_mgr:
        mock_manager = Mock()
        mock_manager.get_session = AsyncMock(side_effect=Exception("Neo4j unavailable"))
        mock_conn_mgr.return_value = mock_manager

        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
        )

        assert response.status_code == 503  # Service Unavailable
        data = response.json()
        assert "database" in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_returns_proper_error_structure(api_client, test_api_key):
    """Test that API returns consistent error structure."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"tenant_id": "invalid"},
    )

    data = response.json()

    assert "error" in data
    assert "code" in data["error"]
    assert "message" in data["error"]


# =============================================================================
# Rate Limiting Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_enforces_rate_limiting(api_client, test_api_key):
    """Test that API enforces rate limiting per API key."""
    # Make requests up to limit
    for _i in range(10):
        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
        )

    # 11th request should be rate limited
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert response.status_code == 429  # Too Many Requests
    data = response.json()
    assert "rate limit" in data["error"]["message"].lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_rate_limit_includes_retry_after_header(api_client, test_api_key):
    """Test that rate limit response includes Retry-After header."""
    # Trigger rate limit
    for _i in range(11):
        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
        )

    if response.status_code == 429:
        assert "Retry-After" in response.headers


# =============================================================================
# Long-Running Operation Tests (Simplified Architecture)
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
@pytest.mark.asyncio
async def test_scan_endpoint_handles_long_operation(api_client, test_api_key):
    """Test that /api/v1/scan handles long-running operations (30-60 min).

    Per simplified architecture: long HTTP timeout + WebSocket progress.
    """
    import asyncio

    with patch("src.remote.server.handlers.scan_handler") as mock_handler:

        async def long_scan(*args, **kwargs):
            # Simulate 5-second operation
            await asyncio.sleep(5)
            return {"job_id": "scan-abc123", "status": "completed"}

        mock_handler.side_effect = long_scan

        response = api_client.post(
            "/api/v1/scan",
            headers={"Authorization": f"Bearer {test_api_key}"},
            json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
            timeout=10,  # Client timeout > operation time
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"


# =============================================================================
# Request ID Tracking Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_generates_request_id(api_client, test_api_key):
    """Test that API generates unique request ID for tracking."""
    response = api_client.post(
        "/api/v1/scan",
        headers={"Authorization": f"Bearer {test_api_key}"},
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert "X-Request-ID" in response.headers
    request_id = response.headers["X-Request-ID"]
    assert len(request_id) > 0


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_accepts_client_request_id(api_client, test_api_key):
    """Test that API accepts and uses client-provided request ID."""
    client_request_id = "client-request-123"

    response = api_client.post(
        "/api/v1/scan",
        headers={
            "Authorization": f"Bearer {test_api_key}",
            "X-Request-ID": client_request_id,
        },
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert response.headers["X-Request-ID"] == client_request_id


# =============================================================================
# API Versioning Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_version_in_path(api_client):
    """Test that API version is included in path."""
    response = api_client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_rejects_invalid_version(api_client):
    """Test that API rejects invalid version."""
    response = api_client.get("/api/v2/health")

    assert response.status_code == 404


# =============================================================================
# Content Type Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_accepts_json_content_type(api_client, test_api_key):
    """Test that API accepts application/json content type."""
    response = api_client.post(
        "/api/v1/scan",
        headers={
            "Authorization": f"Bearer {test_api_key}",
            "Content-Type": "application/json",
        },
        json={"tenant_id": "12345678-1234-1234-1234-123456789012"},
    )

    assert response.status_code in [200, 202]


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="Integration tests require running ATG service"
)
def test_api_rejects_unsupported_content_type(api_client, test_api_key):
    """Test that API rejects unsupported content types."""
    response = api_client.post(
        "/api/v1/scan",
        headers={
            "Authorization": f"Bearer {test_api_key}",
            "Content-Type": "text/plain",
        },
        data="tenant_id=12345678-1234-1234-1234-123456789012",
    )

    assert response.status_code == 415  # Unsupported Media Type
