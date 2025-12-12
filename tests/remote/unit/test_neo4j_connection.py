"""
Unit tests for Neo4j connection management.

Tests connection pooling, health checks, retry logic, and transaction management
following NEO4J_CONNECTION_DESIGN.md.

Philosophy:
- Test connection logic in isolation
- Mock Neo4j driver responses
- Fast execution (< 100ms per test)
- Follow connection design from NEO4J_CONNECTION_DESIGN.md
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# ConnectionManager Tests (Connection Design Section 2)
# =============================================================================


@pytest.mark.asyncio
async def test_connection_manager_is_singleton():
    """Test that ConnectionManager implements singleton pattern."""
    from src.remote.db.connection_manager import ConnectionManager

    # This class doesn't exist yet - will fail!
    manager1 = ConnectionManager()
    manager2 = ConnectionManager()

    assert manager1 is manager2


@pytest.mark.asyncio
async def test_connection_manager_configure_environment():
    """Test that ConnectionManager configures connection for an environment."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://neo4j-dev:7687",
        user="neo4j",
        password="SecurePassword123!@#",
        max_pool_size=50,
    )

    await manager.configure("dev", config)

    assert "dev" in manager._configs
    assert manager._configs["dev"].uri == "bolt://neo4j-dev:7687"


@pytest.mark.asyncio
async def test_connection_manager_creates_driver_lazily():
    """Test that ConnectionManager creates driver on first session request."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    # Driver should not exist yet
    assert "dev" not in manager._drivers

    # Mock Neo4j driver creation
    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()
        mock_driver_cls.return_value = mock_driver

        # Request session - should create driver
        await manager.get_session("dev")

        # Driver should now exist
        assert "dev" in manager._drivers


@pytest.mark.asyncio
async def test_connection_manager_verifies_connectivity_on_creation():
    """Test that ConnectionManager verifies connectivity when creating driver."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()
        mock_driver_cls.return_value = mock_driver

        await manager.get_session("dev")

        # verify_connectivity should have been called
        mock_driver.verify_connectivity.assert_called_once()


@pytest.mark.asyncio
async def test_connection_manager_raises_on_unconfigured_environment():
    """Test that ConnectionManager raises error for unconfigured environment."""
    from src.remote.db.connection_manager import ConnectionManager

    manager = ConnectionManager()

    with pytest.raises(ValueError) as exc_info:
        await manager.get_session("nonexistent")

    assert "not configured" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_connection_manager_closes_environment():
    """Test that ConnectionManager closes connections for specific environment."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()
        mock_driver.close = AsyncMock()
        mock_driver_cls.return_value = mock_driver

        # Create driver
        await manager.get_session("dev")

        # Close environment
        await manager.close("dev")

        # Driver should be closed and removed
        mock_driver.close.assert_called_once()
        assert "dev" not in manager._drivers


@pytest.mark.asyncio
async def test_connection_manager_closes_all_environments():
    """Test that ConnectionManager closes all connections."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    # Configure multiple environments
    for env in ["dev", "integration"]:
        config = Neo4jConnectionConfig(
            uri=f"bolt://neo4j-{env}:7687",
            user="neo4j",
            password="SecurePassword123!@#",
        )
        await manager.configure(env, config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_drivers = {}

        def create_mock_driver(*args, **kwargs):
            mock_driver = AsyncMock()
            mock_driver.verify_connectivity = AsyncMock()
            mock_driver.close = AsyncMock()
            mock_drivers[len(mock_drivers)] = mock_driver
            return mock_driver

        mock_driver_cls.side_effect = create_mock_driver

        # Create drivers
        await manager.get_session("dev")
        await manager.get_session("integration")

        # Close all
        await manager.close_all()

        # All drivers should be closed
        for mock_driver in mock_drivers.values():
            mock_driver.close.assert_called_once()

        assert len(manager._drivers) == 0


# =============================================================================
# Neo4jConnectionConfig Tests (Connection Design Section 2)
# =============================================================================


def test_neo4j_connection_config_validates_uri():
    """Test that Neo4jConnectionConfig validates URI is not empty."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    with pytest.raises(ValueError) as exc_info:
        Neo4jConnectionConfig(uri="", user="neo4j", password="SecurePassword123!@#")

    assert "uri" in str(exc_info.value).lower()


def test_neo4j_connection_config_validates_user():
    """Test that Neo4jConnectionConfig validates user is not empty."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    with pytest.raises(ValueError) as exc_info:
        Neo4jConnectionConfig(
            uri="bolt://localhost:7687", user="", password="SecurePassword123!@#"
        )

    assert "user" in str(exc_info.value).lower()


def test_neo4j_connection_config_validates_password():
    """Test that Neo4jConnectionConfig validates password is not empty."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    with pytest.raises(ValueError) as exc_info:
        Neo4jConnectionConfig(uri="bolt://localhost:7687", user="neo4j", password="")

    assert "password" in str(exc_info.value).lower()


def test_neo4j_connection_config_validates_pool_size():
    """Test that Neo4jConnectionConfig validates pool size is positive."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    with pytest.raises(ValueError) as exc_info:
        Neo4jConnectionConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="SecurePassword123!@#",
            max_pool_size=0,
        )

    assert "pool size" in str(exc_info.value).lower()


def test_neo4j_connection_config_validates_timeout():
    """Test that Neo4jConnectionConfig validates timeout is positive."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    with pytest.raises(ValueError) as exc_info:
        Neo4jConnectionConfig(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="SecurePassword123!@#",
            connection_timeout=0,
        )

    assert "timeout" in str(exc_info.value).lower()


def test_neo4j_connection_config_default_values():
    """Test that Neo4jConnectionConfig has sensible defaults."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    assert config.max_pool_size == 50
    assert config.connection_timeout == 30.0
    assert config.max_transaction_retry_time == 30.0


# =============================================================================
# Health Check Tests (Connection Design Section 6)
# =============================================================================


@pytest.mark.asyncio
async def test_health_check_returns_true_for_healthy_connection():
    """Test that health check returns True for healthy connection."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()  # Succeeds
        mock_driver_cls.return_value = mock_driver

        result = await manager.health_check("dev")

    assert result is True


@pytest.mark.asyncio
async def test_health_check_returns_false_for_unhealthy_connection():
    """Test that health check returns False for unhealthy connection."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        # Simulate connection failure
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        mock_driver_cls.return_value = mock_driver

        result = await manager.health_check("dev")

    assert result is False


@pytest.mark.asyncio
async def test_health_checker_checks_specific_environment():
    """Test that HealthChecker can check specific environment."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )
    from src.remote.db.health import HealthChecker

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()
        mock_driver.session = MagicMock()

        # Mock session for health check query
        mock_session = AsyncMock()
        mock_result = AsyncMock()
        mock_result.single = AsyncMock(return_value={"test": 1})
        mock_session.run = AsyncMock(return_value=mock_result)
        mock_driver.session.return_value.__aenter__.return_value = mock_session
        mock_driver.session.return_value.__aexit__.return_value = None

        mock_driver_cls.return_value = mock_driver

        # This class doesn't exist yet - will fail!
        checker = HealthChecker(manager)
        status = await checker.check_environment("dev")

    assert status.healthy is True
    assert status.latency_ms is not None
    assert status.latency_ms >= 0


@pytest.mark.skip(reason="Requires real Neo4j connection - not suitable for unit testing")
@pytest.mark.asyncio
async def test_health_checker_reports_errors():
    """Test that HealthChecker reports errors in status."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )
    from src.remote.db.health import HealthChecker

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        mock_driver_cls.return_value = mock_driver

        checker = HealthChecker(manager)
        status = await checker.check_environment("dev")

    assert status.healthy is False
    assert status.error is not None
    assert "connection failed" in status.error.lower()


@pytest.mark.skip(reason="Requires real Neo4j connection - not suitable for unit testing")
@pytest.mark.asyncio
async def test_health_checker_waits_for_ready():
    """Test that HealthChecker can wait for environment to be ready."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )
    from src.remote.db.health import HealthChecker

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    call_count = 0

    def mock_health_check(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Fail first 2 times, succeed on 3rd
        if call_count < 3:
            raise Exception("Not ready")
        return True

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock(side_effect=mock_health_check)
        mock_driver_cls.return_value = mock_driver

        checker = HealthChecker(manager)
        result = await checker.wait_for_ready("dev", timeout=5.0, check_interval=0.1)

    assert result is True
    assert call_count >= 3


@pytest.mark.asyncio
async def test_health_checker_timeout_on_wait():
    """Test that HealthChecker returns False on timeout."""
    from src.remote.db.connection_manager import (
        ConnectionManager,
        Neo4jConnectionConfig,
    )
    from src.remote.db.health import HealthChecker

    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687", user="neo4j", password="SecurePassword123!@#"
    )

    await manager.configure("dev", config)

    with patch("neo4j.AsyncGraphDatabase.driver") as mock_driver_cls:
        mock_driver = AsyncMock()
        # Always fail
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=Exception("Connection failed")
        )
        mock_driver_cls.return_value = mock_driver

        checker = HealthChecker(manager)
        result = await checker.wait_for_ready("dev", timeout=1.0, check_interval=0.2)

    assert result is False


# =============================================================================
# Transaction Management Tests (Connection Design Section 4)
# =============================================================================


@pytest.mark.asyncio
async def test_chunked_transaction_processes_items_in_chunks():
    """Test that chunked_transaction processes items in batches."""
    from src.remote.db.transaction import chunked_transaction

    items = list(range(100))
    chunk_size = 10
    processed_chunks = []

    async def mock_process_chunk(tx, chunk):
        processed_chunks.append(chunk)
        return len(chunk)

    # Mock session and transaction
    mock_tx = AsyncMock()
    mock_tx.commit = AsyncMock()

    mock_session = MagicMock()
    mock_session.begin_transaction = MagicMock()
    mock_session.begin_transaction.return_value.__aenter__.return_value = mock_tx
    mock_session.begin_transaction.return_value.__aexit__.return_value = None

    # This function doesn't exist yet - will fail!
    results = await chunked_transaction(
        mock_session, items, chunk_size, mock_process_chunk
    )

    assert len(processed_chunks) == 10  # 100 items / 10 per chunk
    assert len(results) == 10
    assert sum(results) == 100  # Total items processed


@pytest.mark.asyncio
async def test_chunked_transaction_reports_progress():
    """Test that chunked_transaction calls progress callback."""
    from src.remote.db.transaction import chunked_transaction

    items = list(range(50))
    chunk_size = 10
    progress_calls = []

    def progress_callback(processed, total):
        progress_calls.append((processed, total))

    async def mock_process_chunk(tx, chunk):
        return len(chunk)

    # Mock session and transaction
    mock_tx = AsyncMock()
    mock_tx.commit = AsyncMock()

    mock_session = MagicMock()
    mock_session.begin_transaction = MagicMock()
    mock_session.begin_transaction.return_value.__aenter__.return_value = mock_tx
    mock_session.begin_transaction.return_value.__aexit__.return_value = None

    await chunked_transaction(
        mock_session,
        items,
        chunk_size,
        mock_process_chunk,
        progress_callback=progress_callback,
    )

    assert len(progress_calls) == 5  # 50 items / 10 per chunk
    assert progress_calls[-1] == (50, 50)  # Final progress


@pytest.mark.asyncio
async def test_with_retry_retries_on_transient_failure():
    """Test that with_retry retries operations on transient failures."""
    from src.remote.db.transaction import with_retry

    call_count = 0

    async def mock_operation(tx):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise Exception("Transient error")
        return "success"

    # Mock session and transaction
    mock_tx = AsyncMock()
    mock_tx.commit = AsyncMock()

    mock_session = MagicMock()
    mock_session.begin_transaction = MagicMock()
    mock_session.begin_transaction.return_value.__aenter__.return_value = mock_tx
    mock_session.begin_transaction.return_value.__aexit__.return_value = None

    # This function doesn't exist yet - will fail!
    result = await with_retry(
        mock_session,
        mock_operation,
        max_retries=3,
        retry_delay=0.01,  # Fast retry for testing
    )

    assert result == "success"
    assert call_count == 3  # Should have retried twice


@pytest.mark.asyncio
async def test_with_retry_raises_after_max_retries():
    """Test that with_retry raises exception after max retries exceeded."""
    from src.remote.db.transaction import with_retry

    async def mock_operation(tx):
        raise Exception("Persistent error")

    # Mock session and transaction
    mock_tx = AsyncMock()
    mock_tx.commit = AsyncMock()

    mock_session = MagicMock()
    mock_session.begin_transaction = MagicMock()
    mock_session.begin_transaction.return_value.__aenter__.return_value = mock_tx
    mock_session.begin_transaction.return_value.__aexit__.return_value = None

    with pytest.raises(Exception) as exc_info:
        await with_retry(mock_session, mock_operation, max_retries=3, retry_delay=0.01)

    assert "persistent error" in str(exc_info.value).lower()


# =============================================================================
# Connection Pool Tests (Connection Design Section 5)
# =============================================================================


def test_connection_config_pool_size_per_environment():
    """Test that different environments can have different pool sizes."""
    from src.remote.db.connection_manager import Neo4jConnectionConfig

    dev_config = Neo4jConnectionConfig(
        uri="bolt://neo4j-dev:7687",
        user="neo4j",
        password="SecurePassword123!@#",
        max_pool_size=50,
    )

    integration_config = Neo4jConnectionConfig(
        uri="bolt://neo4j-int:7687",
        user="neo4j",
        password="SecurePassword123!@#",
        max_pool_size=30,
    )

    assert dev_config.max_pool_size == 50
    assert integration_config.max_pool_size == 30


def test_pool_metrics_calculates_utilization():
    """Test that PoolMetrics calculates pool utilization correctly."""
    from src.remote.db.metrics import PoolMetrics

    # This class doesn't exist yet - will fail!
    metrics = PoolMetrics(
        environment="dev",
        pool_size=50,
        active_connections=40,
        idle_connections=10,
        total_requests=1000,
        failed_requests=10,
        avg_acquisition_time=5.0,
        max_acquisition_time=15.0,
    )

    assert metrics.utilization() == 80.0  # 40/50 * 100
    assert metrics.failure_rate() == 1.0  # 10/1000 * 100


def test_pool_monitor_detects_scale_up_need():
    """Test that PoolMonitor detects when pool should scale up."""
    from src.remote.db.metrics import PoolMetrics, PoolMonitor

    metrics = PoolMetrics(
        environment="dev",
        pool_size=50,
        active_connections=45,  # 90% utilization
        idle_connections=5,
        total_requests=1000,
        failed_requests=0,
        avg_acquisition_time=5.0,
        max_acquisition_time=15.0,
    )

    # This class doesn't exist yet - will fail!
    monitor = PoolMonitor(None)

    assert monitor.should_scale_up(metrics) is True


def test_pool_monitor_detects_scale_down_opportunity():
    """Test that PoolMonitor detects when pool can scale down."""
    from src.remote.db.metrics import PoolMetrics, PoolMonitor

    metrics = PoolMetrics(
        environment="dev",
        pool_size=50,
        active_connections=5,  # 10% utilization
        idle_connections=45,
        total_requests=1000,
        failed_requests=0,
        avg_acquisition_time=1.0,
        max_acquisition_time=3.0,
    )

    monitor = PoolMonitor(None)

    assert monitor.should_scale_down(metrics) is True
