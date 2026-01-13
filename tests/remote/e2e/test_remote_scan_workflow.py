"""
End-to-end tests for remote scan workflow.

Tests complete scan operation from CLI to results, including authentication,
WebSocket progress streaming, Neo4j storage, and result retrieval.

Philosophy:
- Test complete user workflows
- Use real service integration (or comprehensive mocks)
- Slower execution (< 30s per test)
- 10% of total test suite (E2E layer)
"""

import asyncio
import os

import pytest

# =============================================================================
# E2E Test Fixtures
# =============================================================================


@pytest.fixture
async def running_atg_service():
    """Provide running ATG service for E2E testing.

    In real E2E tests, this would start actual FastAPI server.
    For now, this is a mock that will be replaced with real implementation.
    """

    # Start service
    # This would use uvicorn or similar to start real server
    service_url = "http://localhost:8000"

    yield service_url

    # Cleanup
    pass


@pytest.fixture
def e2e_test_api_key():
    """Provide E2E test API key."""
    import secrets

    return f"atg_dev_{secrets.token_hex(32)}"


@pytest.fixture
async def e2e_neo4j_container():
    """Provide Neo4j container for E2E testing.

    In real E2E tests, this would use testcontainers to start Neo4j.
    """
    # This would start real Neo4j container
    neo4j_uri = "bolt://localhost:7687"
    neo4j_password = "test_password"  # pragma: allowlist secret

    yield neo4j_uri, neo4j_password

    # Cleanup
    pass


# =============================================================================
# Complete Scan Workflow Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_complete_remote_scan_workflow(
    running_atg_service, e2e_test_api_key, e2e_neo4j_container
):
    """Test complete end-to-end scan workflow via remote service.

    Flow:
    1. User runs: atg scan --tenant-id <ID> --remote
    2. CLI dispatches to remote client
    3. Remote client authenticates and submits scan
    4. Service executes scan, stores in Neo4j
    5. Progress updates streamed via WebSocket
    6. Results returned to CLI
    7. User sees scan results
    """
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    # Step 1: Configure remote client
    config = ATGClientConfig(
        remote_mode=True,
        service_url=running_atg_service,
        api_key=e2e_test_api_key,
        request_timeout=60,
    )

    client = RemoteClient(config)

    # Step 2: Track progress updates
    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append((progress, message))
        print(f"Progress: {progress}% - {message}")

    # Step 3: Execute scan
    tenant_id = "12345678-1234-1234-1234-123456789012"

    result = await client.scan(tenant_id=tenant_id, progress_callback=progress_callback)

    # Step 4: Verify results
    assert result["status"] == "completed"
    assert "resources_discovered" in result
    assert result["resources_discovered"] > 0

    # Step 5: Verify progress updates received
    assert len(progress_updates) > 0
    assert progress_updates[-1][0] == 100.0  # Final progress


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scan_results_stored_in_neo4j(
    running_atg_service, e2e_test_api_key, e2e_neo4j_container
):
    """Test that scan results are correctly stored in Neo4j."""
    from neo4j import AsyncGraphDatabase

    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    # Execute scan
    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)
    tenant_id = "12345678-1234-1234-1234-123456789012"

    result = await client.scan(tenant_id=tenant_id)

    # Verify data in Neo4j
    neo4j_uri, neo4j_password = e2e_neo4j_container

    driver = AsyncGraphDatabase.driver(neo4j_uri, auth=("neo4j", neo4j_password))

    async with driver.session() as session:
        # Query resources for this tenant
        query = """
        MATCH (t:Tenant {id: $tenant_id})-[:CONTAINS]->(r:Resource)
        RETURN count(r) as resource_count
        """

        result_neo4j = await session.run(query, tenant_id=tenant_id)
        record = await result_neo4j.single()

        assert record["resource_count"] > 0
        assert record["resource_count"] == result["resources_discovered"]

    await driver.close()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cli_to_service_authentication_flow(
    running_atg_service, e2e_test_api_key
):
    """Test authentication flow from CLI to service."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    # Valid API key
    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # Should succeed
    result = await client.health_check()
    assert result["status"] == "healthy"

    # Invalid API key
    invalid_config = ATGClientConfig(
        remote_mode=True,
        service_url=running_atg_service,
        api_key="invalid_key",  # pragma: allowlist secret
    )

    invalid_client = RemoteClient(invalid_config)

    # Should fail with authentication error
    with pytest.raises(Exception) as exc_info:
        await invalid_client.health_check()

    assert "401" in str(exc_info.value) or "unauthorized" in str(exc_info.value).lower()


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_websocket_progress_streaming(running_atg_service, e2e_test_api_key):
    """Test WebSocket progress streaming during long operation."""
    import time

    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    progress_updates = []
    timestamps = []

    def progress_callback(progress: float, message: str):
        progress_updates.append((progress, message))
        timestamps.append(time.time())

    tenant_id = "12345678-1234-1234-1234-123456789012"

    await client.scan(tenant_id=tenant_id, progress_callback=progress_callback)

    # Verify progress updates
    assert len(progress_updates) >= 3  # At least start, middle, end

    # Verify progress increases monotonically
    for i in range(1, len(progress_updates)):
        assert progress_updates[i][0] >= progress_updates[i - 1][0]

    # Verify real-time updates (not batched at end)
    if len(timestamps) > 1:
        time_span = timestamps[-1] - timestamps[0]
        assert time_span > 0  # Updates spread over time


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_error_handling_end_to_end(running_atg_service, e2e_test_api_key):
    """Test error handling throughout the stack."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # Test invalid tenant ID
    with pytest.raises(Exception) as exc_info:
        await client.scan(tenant_id="invalid-tenant-id")

    assert "tenant" in str(exc_info.value).lower()

    # Verify error was logged on service side
    # (In real E2E test, would query service logs)


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_concurrent_scans(running_atg_service, e2e_test_api_key):
    """Test handling of concurrent scan requests."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # Launch 3 concurrent scans (max_concurrent_operations = 3 per config)
    tenant_ids = [
        "12345678-1234-1234-1234-123456789012",
        "87654321-4321-4321-4321-210987654321",
        "abcdefab-cdef-abcd-efab-cdefabcdefab",
    ]

    tasks = [client.scan(tenant_id=tid) for tid in tenant_ids]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All should complete successfully
    for result in results:
        assert not isinstance(result, Exception)
        assert result["status"] == "completed"


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_timeout_handling(running_atg_service, e2e_test_api_key):
    """Test that long operations respect timeout settings."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    # Configure with very short timeout
    config = ATGClientConfig(
        remote_mode=True,
        service_url=running_atg_service,
        api_key=e2e_test_api_key,
        request_timeout=1,  # 1 second
    )

    client = RemoteClient(config)

    # Trigger operation that takes longer than timeout
    with pytest.raises(asyncio.TimeoutError):
        await client.scan(
            tenant_id="12345678-1234-1234-1234-123456789012",
            resource_limit=10000,  # Large scan to ensure timeout
        )


# =============================================================================
# Cross-Tenant Deployment E2E Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_cross_tenant_iac_generation(running_atg_service, e2e_test_api_key):
    """Test end-to-end cross-tenant IaC generation."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # First, scan source tenant
    source_tenant = "12345678-1234-1234-1234-123456789012"
    await client.scan(tenant_id=source_tenant)

    # Then, generate IaC for target tenant
    target_tenant = "87654321-4321-4321-4321-210987654321"

    result = await client.generate_iac(
        tenant_id=source_tenant, target_tenant_id=target_tenant, format="terraform"
    )

    assert result["status"] == "completed"
    assert "files" in result
    assert len(result["files"]) > 0

    # Verify IaC files contain target tenant references
    for file_info in result["files"]:
        if file_info["filename"].endswith(".tf"):
            # In real test, would download and verify content
            assert file_info["size"] > 0


# =============================================================================
# Service Reliability Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_service_recovers_from_neo4j_restart(
    running_atg_service, e2e_test_api_key, e2e_neo4j_container
):
    """Test that service recovers gracefully from Neo4j restart."""
    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # First scan succeeds
    result1 = await client.scan(tenant_id="12345678-1234-1234-1234-123456789012")
    assert result1["status"] == "completed"

    # Simulate Neo4j restart
    # (In real E2E test, would restart container)

    # Second scan should still succeed (service reconnects)
    result2 = await client.scan(tenant_id="12345678-1234-1234-1234-123456789012")
    assert result2["status"] == "completed"


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
def test_service_handles_multiple_client_connections(
    running_atg_service, e2e_test_api_key
):
    """Test that service handles multiple simultaneous client connections."""
    import threading

    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    results = []

    def run_scan(client_id):
        client = RemoteClient(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            client.scan(tenant_id="12345678-1234-1234-1234-123456789012")
        )

        results.append((client_id, result))

    # Launch 5 concurrent clients
    threads = []
    for i in range(5):
        t = threading.Thread(target=run_scan, args=(i,))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    # All should complete successfully
    assert len(results) == 5
    for _client_id, result in results:
        assert result["status"] == "completed"


# =============================================================================
# Performance Benchmark Tests
# =============================================================================


@pytest.mark.skipif(
    os.getenv("ATG_SERVICE_URL") is None,
    reason="E2E tests require deployed ATG service in Azure ACI",
)
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_scan_performance_baseline(running_atg_service, e2e_test_api_key):
    """Establish performance baseline for remote scan operations."""
    import time

    from src.remote.client import RemoteClient
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True, service_url=running_atg_service, api_key=e2e_test_api_key
    )

    client = RemoteClient(config)

    # Time scan with resource limit
    start = time.time()

    result = await client.scan(
        tenant_id="12345678-1234-1234-1234-123456789012",
        resource_limit=100,  # Limited for consistent testing
    )

    elapsed = time.time() - start

    # Verify reasonable performance
    assert result["status"] == "completed"
    assert elapsed < 60  # Should complete in < 1 minute for 100 resources

    print(f"Scan of 100 resources completed in {elapsed:.2f} seconds")
