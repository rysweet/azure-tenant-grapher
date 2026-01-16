"""
Health check utilities for Neo4j connections.

Philosophy:
- Fail fast during startup
- Graceful degradation during runtime
- Clear visibility into connection health

Health Check Strategy:
    1. Verify connectivity (driver.verify_connectivity())
    2. Run simple query (RETURN 1)
    3. Measure latency
    4. Return structured health status
"""

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Dict, Optional

from .connection_manager import ConnectionManager

logger = logging.getLogger(__name__)


@dataclass
class HealthStatus:
    """
    Health check result.

    Attributes:
        healthy: Whether the connection is healthy
        message: Human-readable status message
        latency_ms: Connection latency in milliseconds (if healthy)
        error: Error message (if unhealthy)
    """

    healthy: bool
    message: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthChecker:
    """
    Health check utilities for Neo4j connections.

    Philosophy:
    - Simple health checks with clear reporting
    - Wait-for-ready capability for startup
    - Detailed error reporting

    Example:
        manager = ConnectionManager()
        checker = HealthChecker(manager)

        # Check specific environment
        status = await checker.check_environment("dev")
        if status.healthy:
            print(str(f"Healthy! Latency: {status.latency_ms}ms"))

        # Wait for environment to be ready
        ready = await checker.wait_for_ready("dev", timeout=30.0)
    """

    def __init__(self, manager: ConnectionManager):
        """
        Initialize health checker.

        Args:
            manager: ConnectionManager instance
        """
        self._manager = manager

    async def check_environment(self, environment: str) -> HealthStatus:
        """
        Check health of specific environment.

        Performs:
        1. Connectivity check
        2. Simple query (RETURN 1)
        3. Latency measurement

        Args:
            environment: Environment name

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
                    result = await session.run("RETURN 1 as test")  # type: ignore[arg-type]
                    await result.single()

                latency = (time.time() - start) * 1000  # Convert to ms
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
            logger.error(str(f"Health check error for {environment}: {e}"))
            return HealthStatus(
                healthy=False,
                message=f"Health check failed for {environment}",
                error=str(e),
            )

    async def check_all(self) -> Dict[str, HealthStatus]:
        """
        Check health of all configured environments.

        Returns:
            Dictionary mapping environment name to HealthStatus
        """
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
            check_interval: Time between checks in seconds

        Returns:
            True if ready within timeout, False otherwise
        """
        start = time.time()

        while (time.time() - start) < timeout:
            status = await self.check_environment(environment)
            if status.healthy:
                logger.info(str(f"Environment {environment} is ready"))
                return True

            logger.debug(str(f"Waiting for {environment} to be ready..."))
            await asyncio.sleep(check_interval)

        logger.error(str(f"Timeout waiting for {environment} to be ready"))
        return False


__all__ = ["HealthChecker", "HealthStatus"]
