# Neo4j Connection Management Design for ATG Remote Service

**Status**: Design Document
**Created**: 2025-12-09
**Author**: Database Agent
**Philosophy**: Ruthless simplicity with pragmatic reliability

---

## Executive Summary

This document defines the Neo4j connection management architecture for the ATG remote service. The design follows the "brick philosophy" - simple, self-contained, regeneratable modules that handle connection pooling, environment isolation, and long-running operations with zero-BS implementation.

**Core Principle**: Start simple, measure first, optimize when justified by actual metrics.

---

## 1. Architecture Overview

### Design Philosophy

Following ruthless simplicity:
- **Trust the driver**: Neo4j Python driver handles most pooling automatically
- **Measure before optimizing**: Start with defaults, optimize based on metrics
- **Fail fast and visible**: Clear error messages during development
- **Environment isolation**: Configuration-based, not code-based

### Connection Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Remote Service                        │
│  ┌───────────────────────────────────────────────────┐  │
│  │          ConnectionManager (Singleton)            │  │
│  │  - One driver per environment                     │  │
│  │  - Lazy initialization                            │  │
│  │  - Automatic health checks                        │  │
│  └───────────────┬───────────────────────────────────┘  │
│                  │                                        │
│  ┌───────────────▼────────┐   ┌────────────────────┐   │
│  │  Driver: dev-neo4j     │   │  Driver: test-neo4j│   │
│  │  (max_pool_size: 50)   │   │  (max_pool_size: 30)  │
│  └────────────────────────┘   └────────────────────┘   │
└─────────────┬──────────────────────┬────────────────────┘
              │                      │
              ▼                      ▼
    ┌─────────────────┐    ┌─────────────────┐
    │  Neo4j Dev DB   │    │  Neo4j Test DB  │
    │  eastus:7687    │    │  eastus:7687    │
    └─────────────────┘    └─────────────────┘
```

---

## 2. Connection Manager Implementation

### Core Module Structure

```
src/db/
├── __init__.py           # Exports ConnectionManager
├── connection_manager.py # Main connection logic
├── config.py            # Environment-specific configs
└── health.py            # Health check utilities
```

### ConnectionManager Interface

```python
"""
Neo4j Connection Manager for ATG Remote Service

Philosophy:
- Single responsibility: Manage Neo4j connections
- Standard library + neo4j driver only
- Self-contained and regeneratable
- Trust the Neo4j driver's built-in pooling

Public API (the "studs"):
    ConnectionManager: Singleton connection manager
    get_session: Get session for environment
    close_all: Cleanup all connections
"""

from typing import Optional, Dict
from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession
from dataclasses import dataclass
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class Neo4jConnectionConfig:
    """Configuration for a Neo4j connection."""
    uri: str
    user: str
    password: str
    max_pool_size: int = 50
    connection_timeout: float = 30.0
    max_transaction_retry_time: float = 30.0

    def __post_init__(self):
        """Validate configuration."""
        if not self.uri:
            raise ValueError("Neo4j URI is required")
        if not self.user:
            raise ValueError("Neo4j user is required")
        if not self.password:
            raise ValueError("Neo4j password is required")
        if self.max_pool_size < 1:
            raise ValueError("Max pool size must be at least 1")
        if self.connection_timeout < 1:
            raise ValueError("Connection timeout must be at least 1 second")

class ConnectionManager:
    """
    Singleton connection manager for Neo4j.

    Manages one driver per environment (dev, integration, etc).
    Uses Neo4j driver's built-in connection pooling.

    Example:
        manager = ConnectionManager()
        async with manager.get_session("dev") as session:
            result = await session.run("MATCH (n) RETURN count(n)")
    """

    _instance: Optional['ConnectionManager'] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._drivers: Dict[str, AsyncDriver] = {}
        self._configs: Dict[str, Neo4jConnectionConfig] = {}
        self._initialized = True
        logger.info("ConnectionManager initialized")

    async def configure(self, environment: str, config: Neo4jConnectionConfig):
        """
        Configure connection for an environment.

        Args:
            environment: Environment name (dev, integration, etc)
            config: Connection configuration
        """
        async with self._lock:
            if environment in self._drivers:
                logger.warning(f"Environment {environment} already configured, closing existing driver")
                await self._drivers[environment].close()

            self._configs[environment] = config
            logger.info(f"Configured environment: {environment} -> {config.uri}")

    async def _get_or_create_driver(self, environment: str) -> AsyncDriver:
        """Get or create driver for environment."""
        if environment not in self._drivers:
            if environment not in self._configs:
                raise ValueError(f"Environment '{environment}' not configured")

            config = self._configs[environment]
            driver = AsyncGraphDatabase.driver(
                config.uri,
                auth=(config.user, config.password),
                max_connection_pool_size=config.max_pool_size,
                connection_timeout=config.connection_timeout,
                max_transaction_retry_time=config.max_transaction_retry_time,
            )

            # Verify connectivity
            await driver.verify_connectivity()
            self._drivers[environment] = driver
            logger.info(f"Created driver for {environment}")

        return self._drivers[environment]

    async def get_session(self, environment: str) -> AsyncSession:
        """
        Get Neo4j session for environment.

        Args:
            environment: Environment name

        Returns:
            AsyncSession context manager
        """
        driver = await self._get_or_create_driver(environment)
        return driver.session()

    async def close(self, environment: str):
        """Close connections for specific environment."""
        async with self._lock:
            if environment in self._drivers:
                await self._drivers[environment].close()
                del self._drivers[environment]
                logger.info(f"Closed driver for {environment}")

    async def close_all(self):
        """Close all connections."""
        async with self._lock:
            for env, driver in self._drivers.items():
                await driver.close()
                logger.info(f"Closed driver for {env}")
            self._drivers.clear()

    async def health_check(self, environment: str) -> bool:
        """
        Check if connection to environment is healthy.

        Returns:
            True if healthy, False otherwise
        """
        try:
            driver = await self._get_or_create_driver(environment)
            await driver.verify_connectivity()
            return True
        except Exception as e:
            logger.error(f"Health check failed for {environment}: {e}")
            return False

__all__ = ["ConnectionManager", "Neo4jConnectionConfig"]
```

---

## 3. Environment Configuration

### Configuration Module

```python
"""
Environment-specific Neo4j configurations.

Philosophy:
- Environment isolation through configuration
- No hardcoded credentials
- All config from environment variables
"""

import os
from typing import Dict
from .connection_manager import Neo4jConnectionConfig

def load_environment_configs() -> Dict[str, Neo4jConnectionConfig]:
    """
    Load all environment configurations from environment variables.

    Expected variables:
    - NEO4J_DEV_URI
    - NEO4J_DEV_USER
    - NEO4J_DEV_PASSWORD
    - NEO4J_INTEGRATION_URI
    - NEO4J_INTEGRATION_USER
    - NEO4J_INTEGRATION_PASSWORD

    Returns:
        Dict mapping environment name to config
    """
    configs = {}

    # Dev environment
    dev_uri = os.getenv("NEO4J_DEV_URI")
    if dev_uri:
        configs["dev"] = Neo4jConnectionConfig(
            uri=dev_uri,
            user=os.getenv("NEO4J_DEV_USER", "neo4j"),
            password=os.getenv("NEO4J_DEV_PASSWORD", ""),
            max_pool_size=int(os.getenv("NEO4J_DEV_POOL_SIZE", "50")),
        )

    # Integration environment
    integration_uri = os.getenv("NEO4J_INTEGRATION_URI")
    if integration_uri:
        configs["integration"] = Neo4jConnectionConfig(
            uri=integration_uri,
            user=os.getenv("NEO4J_INTEGRATION_USER", "neo4j"),
            password=os.getenv("NEO4J_INTEGRATION_PASSWORD", ""),
            max_pool_size=int(os.getenv("NEO4J_INTEGRATION_POOL_SIZE", "30")),
        )

    return configs

def get_environment_from_tenant(tenant_id: str) -> str:
    """
    Map tenant ID to environment.

    This is a simple implementation - enhance based on your needs.
    Could use a config file, database lookup, etc.
    """
    # Example mapping - customize for your needs
    env_mapping = {
        os.getenv("DEV_TENANT_ID"): "dev",
        os.getenv("INTEGRATION_TENANT_ID"): "integration",
    }

    environment = env_mapping.get(tenant_id)
    if not environment:
        raise ValueError(f"Unknown tenant ID: {tenant_id}")

    return environment

__all__ = ["load_environment_configs", "get_environment_from_tenant"]
```

### Environment Variables

```bash
# Dev Environment
NEO4J_DEV_URI=bolt://neo4j-dev-kqib4q.eastus.azurecontainer.io:7687
NEO4J_DEV_USER=neo4j
NEO4J_DEV_PASSWORD=your-password
NEO4J_DEV_POOL_SIZE=50

# Integration Environment
NEO4J_INTEGRATION_URI=bolt://neo4j-test-kqib4q.eastus.azurecontainer.io:7687
NEO4J_INTEGRATION_USER=neo4j
NEO4J_INTEGRATION_PASSWORD=your-password
NEO4J_INTEGRATION_POOL_SIZE=30

# Tenant to Environment Mapping
DEV_TENANT_ID=your-dev-tenant-id
INTEGRATION_TENANT_ID=your-integration-tenant-id
```

---

## 4. Transaction Management for Long Operations

### Transaction Patterns

```python
"""
Transaction patterns for long-running operations.

Philosophy:
- Explicit transaction boundaries
- Progress tracking for user visibility
- Graceful handling of transaction timeouts
"""

from typing import AsyncIterator, TypeVar, Callable, Any
import asyncio

T = TypeVar('T')

async def chunked_transaction(
    session: AsyncSession,
    items: list[T],
    chunk_size: int,
    process_fn: Callable[[AsyncTransaction, list[T]], Any],
    progress_callback: Optional[Callable[[int, int], None]] = None,
) -> list[Any]:
    """
    Process items in chunked transactions.

    Use for large batch operations that would timeout in single transaction.

    Args:
        session: Neo4j session
        items: Items to process
        chunk_size: Items per transaction
        process_fn: Function to process chunk in transaction
        progress_callback: Optional callback(processed, total)

    Returns:
        List of results from each chunk
    """
    results = []
    total = len(items)

    for i in range(0, total, chunk_size):
        chunk = items[i:i + chunk_size]

        async with session.begin_transaction() as tx:
            result = await process_fn(tx, chunk)
            await tx.commit()
            results.append(result)

        if progress_callback:
            progress_callback(min(i + chunk_size, total), total)

    return results

async def with_retry(
    session: AsyncSession,
    operation: Callable[[AsyncTransaction], Any],
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> Any:
    """
    Execute operation with retry logic.

    Use for operations that may fail due to transient errors.

    Args:
        session: Neo4j session
        operation: Operation to execute
        max_retries: Max retry attempts
        retry_delay: Delay between retries (exponential backoff)

    Returns:
        Result from operation
    """
    last_error = None

    for attempt in range(max_retries):
        try:
            async with session.begin_transaction() as tx:
                result = await operation(tx)
                await tx.commit()
                return result
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (2 ** attempt))
                logger.warning(f"Retry {attempt + 1}/{max_retries} after error: {e}")
            else:
                logger.error(f"Operation failed after {max_retries} attempts")

    raise last_error

# Example usage for scan operations
async def process_scan_resources(
    manager: ConnectionManager,
    environment: str,
    resources: list[dict],
    chunk_size: int = 100,
):
    """Process resources from Azure scan in chunks."""
    async with await manager.get_session(environment) as session:
        async def process_chunk(tx, chunk):
            query = """
            UNWIND $resources AS resource
            MERGE (r:Resource {id: resource.id})
            SET r += resource.properties
            RETURN count(r) as created
            """
            result = await tx.run(query, resources=chunk)
            return await result.single()

        def progress(processed, total):
            logger.info(f"Processed {processed}/{total} resources")

        await chunked_transaction(
            session,
            resources,
            chunk_size,
            process_chunk,
            progress,
        )

__all__ = ["chunked_transaction", "with_retry", "process_scan_resources"]
```

---

## 5. Connection Pool Sizing

### Sizing Strategy

**Start Conservative, Measure, Optimize**

#### Initial Recommendations

**Environment-Specific Pools:**

| Environment  | Max Pool Size | Rationale                                    |
|--------------|---------------|----------------------------------------------|
| Dev          | 50            | Higher for concurrent development/testing    |
| Integration  | 30            | Lower for controlled test scenarios          |
| Production*  | 100           | Scale based on actual load metrics           |

*Note: Production environment not yet defined in requirements

**Why These Numbers:**
- Neo4j driver default is 100 (too high for shared database)
- Start at 50% of default for dev (50 connections)
- Lower for integration to prevent resource contention
- Leave room for other services sharing the database

### Connection Lifecycle

```
Request Arrives
     ↓
Get Session from Pool
     ↓
Execute Query/Transaction
     ↓
Close Session (returns to pool)
     ↓
Connection reused for next request
```

### Pool Metrics to Monitor

```python
"""
Connection pool metrics and monitoring.

Philosophy:
- Measure what matters
- Simple metrics first
- Optimize based on data
"""

from dataclasses import dataclass
from typing import Dict
import time

@dataclass
class PoolMetrics:
    """Metrics for connection pool monitoring."""
    environment: str
    pool_size: int
    active_connections: int
    idle_connections: int
    total_requests: int
    failed_requests: int
    avg_acquisition_time: float
    max_acquisition_time: float

    def utilization(self) -> float:
        """Calculate pool utilization percentage."""
        return (self.active_connections / self.pool_size) * 100 if self.pool_size > 0 else 0.0

    def failure_rate(self) -> float:
        """Calculate request failure rate."""
        return (self.failed_requests / self.total_requests) * 100 if self.total_requests > 0 else 0.0

class PoolMonitor:
    """Monitor connection pool health and performance."""

    def __init__(self, manager: ConnectionManager):
        self._manager = manager
        self._metrics: Dict[str, PoolMetrics] = {}

    async def collect_metrics(self, environment: str) -> PoolMetrics:
        """Collect current metrics for environment."""
        # Simplified - actual implementation would query driver internals
        driver = await self._manager._get_or_create_driver(environment)

        # Note: Neo4j driver doesn't expose all these metrics directly
        # This is a conceptual framework - adapt based on available APIs

        metrics = PoolMetrics(
            environment=environment,
            pool_size=self._manager._configs[environment].max_pool_size,
            active_connections=0,  # Would get from driver
            idle_connections=0,    # Would get from driver
            total_requests=0,      # Track in wrapper
            failed_requests=0,     # Track in wrapper
            avg_acquisition_time=0.0,  # Track in wrapper
            max_acquisition_time=0.0,  # Track in wrapper
        )

        self._metrics[environment] = metrics
        return metrics

    def should_scale_up(self, metrics: PoolMetrics) -> bool:
        """Determine if pool should be scaled up."""
        # Scale up if utilization > 80% consistently
        return metrics.utilization() > 80.0

    def should_scale_down(self, metrics: PoolMetrics) -> bool:
        """Determine if pool should be scaled down."""
        # Scale down if utilization < 20% consistently
        return metrics.utilization() < 20.0

__all__ = ["PoolMetrics", "PoolMonitor"]
```

### When to Adjust Pool Size

**Scale UP if:**
- Pool utilization consistently > 80%
- Connection acquisition time increasing
- Request queuing observed

**Scale DOWN if:**
- Pool utilization consistently < 20%
- Memory pressure on database
- Idle connections consuming resources

**Measure for 1 week before adjusting**

---

## 6. Health Checks and Recovery

### Health Check Implementation

```python
"""
Health check utilities for Neo4j connections.

Philosophy:
- Fail fast during startup
- Graceful degradation during runtime
- Clear visibility into connection health
"""

from dataclasses import dataclass
from typing import Optional
import asyncio
import logging

logger = logging.getLogger(__name__)

@dataclass
class HealthStatus:
    """Health check result."""
    healthy: bool
    message: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None

class HealthChecker:
    """Health check utilities for Neo4j."""

    def __init__(self, manager: ConnectionManager):
        self._manager = manager

    async def check_environment(self, environment: str) -> HealthStatus:
        """
        Check health of specific environment.

        Returns:
            HealthStatus with details
        """
        start = time.time()

        try:
            # Verify connectivity
            is_healthy = await self._manager.health_check(environment)

            if is_healthy:
                # Run simple query to verify functionality
                async with await self._manager.get_session(environment) as session:
                    result = await session.run("RETURN 1 as test")
                    await result.single()

                latency = (time.time() - start) * 1000
                return HealthStatus(
                    healthy=True,
                    message=f"Environment {environment} is healthy",
                    latency_ms=latency,
                )
            else:
                return HealthStatus(
                    healthy=False,
                    message=f"Environment {environment} connectivity check failed",
                )

        except Exception as e:
            logger.error(f"Health check error for {environment}: {e}")
            return HealthStatus(
                healthy=False,
                message=f"Health check failed for {environment}",
                error=str(e),
            )

    async def check_all(self) -> Dict[str, HealthStatus]:
        """Check health of all configured environments."""
        environments = list(self._manager._configs.keys())

        results = {}
        for env in environments:
            results[env] = await self.check_environment(env)

        return results

    async def wait_for_ready(
        self,
        environment: str,
        timeout: float = 30.0,
        check_interval: float = 1.0,
    ) -> bool:
        """
        Wait for environment to be ready.

        Use during service startup to ensure database is available.

        Args:
            environment: Environment to check
            timeout: Max wait time in seconds
            check_interval: Time between checks

        Returns:
            True if ready, False if timeout
        """
        start = time.time()

        while (time.time() - start) < timeout:
            status = await self.check_environment(environment)
            if status.healthy:
                logger.info(f"Environment {environment} is ready")
                return True

            logger.debug(f"Waiting for {environment} to be ready...")
            await asyncio.sleep(check_interval)

        logger.error(f"Timeout waiting for {environment} to be ready")
        return False

__all__ = ["HealthStatus", "HealthChecker"]
```

### Recovery Strategies

```python
"""
Connection recovery strategies.

Philosophy:
- Automatic recovery for transient errors
- Manual intervention for persistent errors
- Clear error reporting
"""

from enum import Enum
import asyncio

class RecoveryAction(Enum):
    """Recovery actions for connection issues."""
    RETRY = "retry"
    RECONNECT = "reconnect"
    FAIL = "fail"

async def recover_connection(
    manager: ConnectionManager,
    environment: str,
    max_retries: int = 3,
) -> bool:
    """
    Attempt to recover failed connection.

    Args:
        manager: Connection manager
        environment: Environment to recover
        max_retries: Max recovery attempts

    Returns:
        True if recovered, False otherwise
    """
    logger.warning(f"Attempting to recover connection for {environment}")

    for attempt in range(max_retries):
        try:
            # Close existing driver
            await manager.close(environment)

            # Wait before reconnecting (exponential backoff)
            await asyncio.sleep(2 ** attempt)

            # Verify new connection
            if await manager.health_check(environment):
                logger.info(f"Connection recovered for {environment}")
                return True

        except Exception as e:
            logger.error(f"Recovery attempt {attempt + 1} failed: {e}")

    logger.error(f"Failed to recover connection for {environment}")
    return False

__all__ = ["RecoveryAction", "recover_connection"]
```

---

## 7. Error Handling

### Error Categories and Responses

```python
"""
Error handling for Neo4j operations.

Philosophy:
- Specific error types for specific problems
- Clear error messages with context
- Actionable error responses
"""

from typing import Optional
from dataclasses import dataclass

class Neo4jConnectionError(Exception):
    """Base exception for connection errors."""
    pass

class EnvironmentNotConfiguredError(Neo4jConnectionError):
    """Raised when environment is not configured."""

    def __init__(self, environment: str):
        self.environment = environment
        super().__init__(
            f"Environment '{environment}' is not configured. "
            f"Please set NEO4J_{environment.upper()}_URI and related variables."
        )

class ConnectionPoolExhaustedError(Neo4jConnectionError):
    """Raised when connection pool is exhausted."""

    def __init__(self, environment: str):
        self.environment = environment
        super().__init__(
            f"Connection pool exhausted for environment '{environment}'. "
            f"Consider increasing pool size or reducing concurrent requests."
        )

class TransactionTimeoutError(Neo4jConnectionError):
    """Raised when transaction times out."""

    def __init__(self, environment: str, timeout: float):
        self.environment = environment
        self.timeout = timeout
        super().__init__(
            f"Transaction timed out after {timeout}s in environment '{environment}'. "
            f"Consider breaking operation into smaller chunks."
        )

@dataclass
class ErrorResponse:
    """Standardized error response."""
    error_type: str
    message: str
    environment: str
    recoverable: bool
    suggested_action: str

def handle_connection_error(e: Exception, environment: str) -> ErrorResponse:
    """
    Convert exception to standardized error response.

    Args:
        e: Exception that occurred
        environment: Environment where error occurred

    Returns:
        ErrorResponse with details and suggested action
    """
    if isinstance(e, EnvironmentNotConfiguredError):
        return ErrorResponse(
            error_type="configuration",
            message=str(e),
            environment=environment,
            recoverable=False,
            suggested_action="Configure environment variables and restart service",
        )

    elif isinstance(e, ConnectionPoolExhaustedError):
        return ErrorResponse(
            error_type="pool_exhausted",
            message=str(e),
            environment=environment,
            recoverable=True,
            suggested_action="Increase pool size or reduce concurrent load",
        )

    elif isinstance(e, TransactionTimeoutError):
        return ErrorResponse(
            error_type="timeout",
            message=str(e),
            environment=environment,
            recoverable=True,
            suggested_action="Break operation into smaller transactions",
        )

    else:
        return ErrorResponse(
            error_type="unknown",
            message=str(e),
            environment=environment,
            recoverable=True,
            suggested_action="Check logs and retry operation",
        )

__all__ = [
    "Neo4jConnectionError",
    "EnvironmentNotConfiguredError",
    "ConnectionPoolExhaustedError",
    "TransactionTimeoutError",
    "ErrorResponse",
    "handle_connection_error",
]
```

---

## 8. Integration with Existing Code

### Migration from Current Pattern

**Current Pattern:**
```python
# Existing pattern in codebase
async with AsyncNeo4jSession(driver) as session:
    await session.run("MATCH (n) RETURN n")
```

**New Pattern:**
```python
# New pattern with ConnectionManager
manager = ConnectionManager()
environment = get_environment_from_tenant(tenant_id)

async with await manager.get_session(environment) as session:
    await session.run("MATCH (n) RETURN n")
```

### Service Initialization

```python
"""
Service initialization with connection management.
"""

async def initialize_service():
    """Initialize ATG remote service."""
    # Load environment configs
    configs = load_environment_configs()

    # Initialize connection manager
    manager = ConnectionManager()

    # Configure all environments
    for env_name, config in configs.items():
        await manager.configure(env_name, config)

    # Wait for all environments to be ready
    health_checker = HealthChecker(manager)

    for env_name in configs.keys():
        ready = await health_checker.wait_for_ready(env_name, timeout=30.0)
        if not ready:
            raise RuntimeError(f"Environment {env_name} not ready")

    logger.info("Service initialized successfully")
    return manager

async def shutdown_service(manager: ConnectionManager):
    """Shutdown service and cleanup connections."""
    await manager.close_all()
    logger.info("Service shutdown complete")
```

---

## 9. Testing Strategy

### Unit Tests

```python
"""
Unit tests for connection management.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

@pytest.mark.asyncio
async def test_connection_manager_singleton():
    """Test that ConnectionManager is a singleton."""
    manager1 = ConnectionManager()
    manager2 = ConnectionManager()
    assert manager1 is manager2

@pytest.mark.asyncio
async def test_configure_environment():
    """Test environment configuration."""
    manager = ConnectionManager()
    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
    )

    await manager.configure("test", config)
    assert "test" in manager._configs

@pytest.mark.asyncio
async def test_get_session_creates_driver():
    """Test that getting session creates driver."""
    manager = ConnectionManager()
    config = Neo4jConnectionConfig(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="test",
    )

    await manager.configure("test", config)

    with patch.object(AsyncGraphDatabase, 'driver') as mock_driver:
        mock_driver.return_value.verify_connectivity = AsyncMock()
        mock_driver.return_value.session = Mock()

        session = await manager.get_session("test")

        mock_driver.assert_called_once()
        assert "test" in manager._drivers

@pytest.mark.asyncio
async def test_health_check_success():
    """Test successful health check."""
    manager = ConnectionManager()
    # ... setup mocks ...

    healthy = await manager.health_check("test")
    assert healthy is True

@pytest.mark.asyncio
async def test_health_check_failure():
    """Test failed health check."""
    manager = ConnectionManager()
    # ... setup mocks to raise error ...

    healthy = await manager.health_check("test")
    assert healthy is False
```

### Integration Tests

```python
"""
Integration tests with real Neo4j (testcontainers).
"""

import pytest
from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="module")
def neo4j_container():
    """Start Neo4j container for testing."""
    with Neo4jContainer() as container:
        yield container

@pytest.mark.asyncio
async def test_full_workflow(neo4j_container):
    """Test complete connection workflow."""
    manager = ConnectionManager()

    config = Neo4jConnectionConfig(
        uri=neo4j_container.get_connection_url(),
        user="neo4j",
        password=neo4j_container.NEO4J_ADMIN_PASSWORD,
    )

    await manager.configure("test", config)

    # Test session creation
    async with await manager.get_session("test") as session:
        result = await session.run("RETURN 1 as num")
        record = await result.single()
        assert record["num"] == 1

    # Test cleanup
    await manager.close("test")
```

---

## 10. Deployment Considerations

### Resource Requirements

**Per Environment:**
- Memory: ~100MB per 50 connections (idle)
- CPU: Minimal when idle, scales with query load
- Network: Persistent TCP connections to Neo4j

**Total for Service:**
- Memory: ~300MB (3 environments × 100MB)
- Plus application memory overhead

### Configuration Management

**Development:**
```bash
# .env.development
NEO4J_DEV_URI=bolt://localhost:7687
NEO4J_DEV_PASSWORD=dev-password
NEO4J_DEV_POOL_SIZE=20
```

**Production:**
```bash
# Kubernetes ConfigMap or Azure Key Vault
NEO4J_DEV_URI=${KEYVAULT_SECRET_NEO4J_DEV_URI}
NEO4J_DEV_PASSWORD=${KEYVAULT_SECRET_NEO4J_DEV_PASSWORD}
NEO4J_DEV_POOL_SIZE=50
```

### Monitoring

**Key Metrics to Track:**
- Connection pool utilization per environment
- Connection acquisition time (p50, p95, p99)
- Transaction duration (p50, p95, p99)
- Failed connection attempts
- Health check failures

**Alerting Thresholds:**
- Pool utilization > 90% for 5 minutes
- Connection acquisition time > 1s (p95)
- Health check failures > 3 in 1 minute

---

## 11. Performance Optimization Guidelines

### When to Optimize

**DON'T optimize until you measure:**
- Start with default pool sizes (50/30)
- Run service for 1 week minimum
- Collect metrics (pool utilization, latency)
- Optimize based on actual data

**Signs you need to optimize:**
- Pool utilization consistently > 80%
- Connection acquisition time increasing
- Transaction timeouts
- Memory pressure

### Optimization Strategies

**If pool exhaustion:**
1. Increase pool size incrementally (10 connections at a time)
2. Monitor impact on database resources
3. Consider if concurrent request limit is appropriate

**If transaction timeouts:**
1. Break operations into smaller chunks (chunked_transaction)
2. Increase max_transaction_retry_time
3. Consider read replicas for read-heavy operations

**If memory pressure:**
1. Reduce pool size
2. Implement connection cleanup on idle
3. Review query complexity and result set sizes

### Best Practices

1. **Use connection pooling** - Don't create new drivers per request
2. **Close sessions properly** - Use async context managers
3. **Batch operations** - Use UNWIND for bulk inserts
4. **Monitor metrics** - Track pool health continuously
5. **Test with load** - Simulate concurrent requests before production

---

## 12. Neo4j Driver Best Practices

### Driver Configuration

```python
# GOOD - Configure driver with appropriate settings
driver = AsyncGraphDatabase.driver(
    uri,
    auth=(user, password),
    max_connection_pool_size=50,          # Limit concurrent connections
    connection_timeout=30.0,              # Timeout for new connections
    max_transaction_retry_time=30.0,      # Timeout for retries
    connection_acquisition_timeout=60.0,  # Max wait for connection from pool
)

# BAD - Using defaults without considering environment
driver = AsyncGraphDatabase.driver(uri, auth=(user, password))
```

### Session Usage

```python
# GOOD - Use async context manager for session
async with driver.session() as session:
    result = await session.run("MATCH (n) RETURN n")
    # Session automatically closed

# BAD - Manual session management
session = driver.session()
result = await session.run("MATCH (n) RETURN n")
# Easy to forget to close
```

### Transaction Management

```python
# GOOD - Explicit transactions for multiple operations
async with session.begin_transaction() as tx:
    await tx.run("CREATE (n:Node {id: $id})", id=1)
    await tx.run("CREATE (n:Node {id: $id})", id=2)
    await tx.commit()

# GOOD - Auto-commit for single operation
result = await session.run("MATCH (n:Node) RETURN n")

# BAD - Multiple auto-commit operations (slow)
await session.run("CREATE (n:Node {id: $id})", id=1)
await session.run("CREATE (n:Node {id: $id})", id=2)
```

### Query Optimization

```python
# GOOD - Use parameters to prevent injection and enable caching
result = await session.run(
    "MATCH (n:Node {id: $id}) RETURN n",
    id=node_id
)

# GOOD - Batch operations with UNWIND
result = await session.run(
    """
    UNWIND $nodes AS node
    CREATE (n:Node {id: node.id, name: node.name})
    """,
    nodes=[{"id": 1, "name": "A"}, {"id": 2, "name": "B"}]
)

# BAD - String concatenation (injection risk, no caching)
result = await session.run(f"MATCH (n:Node {{id: {node_id}}}) RETURN n")

# BAD - Multiple single creates
for node in nodes:
    await session.run("CREATE (n:Node {id: $id})", id=node.id)
```

---

## 13. Next Steps

### Implementation Phases

**Phase 1: Core Implementation (Week 1)**
1. Implement ConnectionManager with singleton pattern
2. Implement environment configuration loading
3. Add health check utilities
4. Write unit tests

**Phase 2: Integration (Week 2)**
1. Integrate with existing AsyncNeo4jSession code
2. Update service initialization
3. Add environment mapping logic
4. Write integration tests

**Phase 3: Monitoring (Week 3)**
1. Implement PoolMonitor
2. Add metrics collection
3. Set up alerting thresholds
4. Performance testing under load

**Phase 4: Optimization (Week 4+)**
1. Collect 1 week of production metrics
2. Adjust pool sizes based on data
3. Optimize slow queries
4. Document lessons learned

### Success Criteria

- [ ] All environments configured and healthy
- [ ] Connection pool utilization < 80%
- [ ] Connection acquisition time < 100ms (p95)
- [ ] Zero connection leaks (verified via metrics)
- [ ] Health checks passing consistently
- [ ] Unit test coverage > 80%
- [ ] Integration tests passing
- [ ] Documentation complete

---

## 14. Summary

This design provides a ruthlessly simple yet robust Neo4j connection management system for the ATG remote service:

**Key Features:**
- ✅ Singleton connection manager per environment
- ✅ Automatic connection pooling via Neo4j driver
- ✅ Environment isolation through configuration
- ✅ Health checks and recovery mechanisms
- ✅ Transaction patterns for long operations
- ✅ Comprehensive error handling
- ✅ Monitoring and metrics framework

**Philosophy Alignment:**
- ✅ Start simple, measure first, optimize when justified
- ✅ Trust the Neo4j driver's built-in capabilities
- ✅ Fail fast and visible during development
- ✅ Self-contained, regeneratable modules

**Next Action:** Begin Phase 1 implementation of ConnectionManager module.

---

**End of Design Document**
