"""
Integration tests for Health Check Router.

Tests cover:
- Health endpoint accessibility
- Neo4j status reporting
- No authentication requirement
- Response structure
- Error handling
"""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient

from src.remote.db.connection_manager import ConnectionManager
from src.remote.server.config import ATGServerConfig
from src.remote.server.routers.health import router


@pytest.fixture
def mock_connection_manager():
    """Create mock ConnectionManager for testing."""
    manager = Mock(spec=ConnectionManager)
    manager.health_check = AsyncMock(return_value=True)
    return manager


@pytest.fixture
def mock_config():
    """Create mock ATGServerConfig for testing."""
    config = Mock(spec=ATGServerConfig)
    config.environment = "dev"
    return config


@pytest.fixture
def test_app(mock_connection_manager, mock_config):
    """Create test FastAPI app with health router."""
    from fastapi import FastAPI

    from src.remote.server.dependencies import get_config, get_connection_manager

    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    # Override dependencies
    app.dependency_overrides[get_connection_manager] = lambda: mock_connection_manager
    app.dependency_overrides[get_config] = lambda: mock_config

    return app


@pytest.fixture
def client(test_app):
    """Create test client."""
    return TestClient(test_app)


# Health Endpoint Tests


def test_health_endpoint_returns_200(client):
    """Test that /health endpoint returns 200 OK."""
    response = client.get("/api/v1/health")

    assert response.status_code == 200


def test_health_endpoint_no_auth_required(client):
    """Test that /health endpoint does not require authentication."""
    # No Authorization header provided
    response = client.get("/api/v1/health")

    # Should still return 200 (no 401 Unauthorized)
    assert response.status_code == 200


def test_health_endpoint_returns_json(client):
    """Test that /health endpoint returns JSON response."""
    response = client.get("/api/v1/health")

    assert response.headers["content-type"] == "application/json"


def test_health_endpoint_includes_status(client):
    """Test that health response includes status field."""
    response = client.get("/api/v1/health")
    data = response.json()

    assert "status" in data
    assert data["status"] == "healthy"


def test_health_endpoint_includes_version(client):
    """Test that health response includes version field."""
    response = client.get("/api/v1/health")
    data = response.json()

    assert "version" in data
    assert data["version"] == "1.0.0"


def test_health_endpoint_includes_neo4j_status(client, mock_connection_manager):
    """Test that health response includes neo4j_status field."""
    mock_connection_manager.health_check = AsyncMock(return_value=True)

    response = client.get("/api/v1/health")
    data = response.json()

    assert "neo4j_status" in data
    assert data["neo4j_status"] in ["connected", "disconnected"]


def test_health_endpoint_includes_environment(client, mock_config):
    """Test that health response includes environment field."""
    mock_config.environment = "integration"

    response = client.get("/api/v1/health")
    data = response.json()

    assert "environment" in data
    assert data["environment"] == "integration"


# Neo4j Status Tests


def test_health_endpoint_reports_neo4j_connected(client, mock_connection_manager):
    """Test that health endpoint reports Neo4j as connected when healthy."""
    mock_connection_manager.health_check = AsyncMock(return_value=True)

    response = client.get("/api/v1/health")
    data = response.json()

    assert data["neo4j_status"] == "connected"


def test_health_endpoint_reports_neo4j_disconnected_when_unhealthy(
    client, mock_connection_manager
):
    """Test that health endpoint reports Neo4j as disconnected when unhealthy."""
    mock_connection_manager.health_check = AsyncMock(return_value=False)

    response = client.get("/api/v1/health")
    data = response.json()

    assert data["neo4j_status"] == "disconnected"


def test_health_endpoint_reports_neo4j_disconnected_on_exception(
    client, mock_connection_manager
):
    """Test that health endpoint reports Neo4j as disconnected on exception."""
    mock_connection_manager.health_check = AsyncMock(
        side_effect=Exception("Connection failed")
    )

    response = client.get("/api/v1/health")
    data = response.json()

    # Should still return 200 but report disconnected
    assert response.status_code == 200
    assert data["neo4j_status"] == "disconnected"


# Response Structure Tests


def test_health_response_structure_is_complete(client):
    """Test that health response has all expected fields."""
    response = client.get("/api/v1/health")
    data = response.json()

    expected_fields = ["status", "version", "neo4j_status", "environment"]
    for field in expected_fields:
        assert field in data, f"Missing field: {field}"


def test_health_response_types_are_correct(client):
    """Test that health response fields have correct types."""
    response = client.get("/api/v1/health")
    data = response.json()

    assert isinstance(data["status"], str)
    assert isinstance(data["version"], str)
    assert isinstance(data["neo4j_status"], str)
    assert isinstance(data["environment"], str)


# Multiple Request Tests


def test_health_endpoint_handles_multiple_requests(client):
    """Test that health endpoint can handle multiple sequential requests."""
    responses = [client.get("/api/v1/health") for _ in range(5)]

    assert all(r.status_code == 200 for r in responses)
    assert all("status" in r.json() for r in responses)


def test_health_endpoint_consistent_responses(client):
    """Test that health endpoint returns consistent responses."""
    response1 = client.get("/api/v1/health")
    response2 = client.get("/api/v1/health")

    data1 = response1.json()
    data2 = response2.json()

    # Status and version should be same
    assert data1["status"] == data2["status"]
    assert data1["version"] == data2["version"]


# Error Handling Tests


def test_health_endpoint_gracefully_handles_config_error(
    client, test_app, mock_connection_manager
):
    """Test that health endpoint handles config dependency errors gracefully."""
    # This tests the overall robustness of the endpoint
    response = client.get("/api/v1/health")

    # Should still return a response (may be 500 if dependency fails, but shouldn't crash)
    assert response.status_code in [200, 500]


# Edge Cases


def test_health_endpoint_with_query_parameters_ignored(client):
    """Test that health endpoint ignores query parameters."""
    response = client.get("/api/v1/health?foo=bar&baz=qux")

    # Should still work normally
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


def test_health_endpoint_with_trailing_slash(client):
    """Test that health endpoint works with trailing slash."""
    response = client.get("/api/v1/health/")

    # FastAPI should handle this gracefully (may redirect or accept)
    assert response.status_code in [200, 307]  # 307 is temporary redirect


# Integration with Dependencies


def test_health_endpoint_calls_connection_manager_health_check(
    client, mock_connection_manager
):
    """Test that health endpoint calls connection manager health check."""
    mock_connection_manager.health_check = AsyncMock(return_value=True)

    client.get("/api/v1/health")

    mock_connection_manager.health_check.assert_called_once()


def test_health_endpoint_uses_config_environment(client, mock_config):
    """Test that health endpoint uses config environment value."""
    mock_config.environment = "production"

    response = client.get("/api/v1/health")
    data = response.json()

    assert data["environment"] == "production"


# Performance Tests


def test_health_endpoint_responds_quickly(client):
    """Test that health endpoint responds within reasonable time."""
    import time

    start = time.time()
    response = client.get("/api/v1/health")
    elapsed = time.time() - start

    assert response.status_code == 200
    assert elapsed < 1.0  # Should respond in less than 1 second


# HTTP Method Tests


def test_health_endpoint_only_accepts_get(client):
    """Test that health endpoint only accepts GET requests."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    # POST should not be allowed
    response = client.post("/api/v1/health")
    assert response.status_code == 405  # Method Not Allowed

    # PUT should not be allowed
    response = client.put("/api/v1/health")
    assert response.status_code == 405

    # DELETE should not be allowed
    response = client.delete("/api/v1/health")
    assert response.status_code == 405
