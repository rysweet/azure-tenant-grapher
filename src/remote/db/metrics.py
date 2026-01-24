"""
Connection pool metrics and monitoring.

Philosophy:
- Measure what matters
- Simple metrics first
- Optimize based on data

Metrics Tracked:
    - Pool utilization (active/total connections)
    - Request success/failure rates
    - Connection acquisition time

Use metrics to determine when to scale pool up or down.
"""

from dataclasses import dataclass
from typing import Dict

from .connection_manager import ConnectionManager


@dataclass
class PoolMetrics:
    """
    Metrics for connection pool monitoring.

    Attributes:
        environment: Environment name
        pool_size: Maximum pool size
        active_connections: Currently active connections
        idle_connections: Currently idle connections
        total_requests: Total requests processed
        failed_requests: Failed requests
        avg_acquisition_time: Average connection acquisition time (ms)
        max_acquisition_time: Maximum connection acquisition time (ms)
    """

    environment: str
    pool_size: int
    active_connections: int
    idle_connections: int
    total_requests: int
    failed_requests: int
    avg_acquisition_time: float
    max_acquisition_time: float

    def utilization(self) -> float:
        """
        Calculate pool utilization percentage.

        Returns:
            Utilization percentage (0-100)
        """
        if self.pool_size == 0:
            return 0.0
        return (self.active_connections / self.pool_size) * 100

    def failure_rate(self) -> float:
        """
        Calculate request failure rate percentage.

        Returns:
            Failure rate percentage (0-100)
        """
        if self.total_requests == 0:
            return 0.0
        return (self.failed_requests / self.total_requests) * 100


class PoolMonitor:
    """
    Monitor connection pool health and performance.

    Philosophy:
    - Track key metrics
    - Provide scaling recommendations
    - Simple thresholds (can be customized later)

    Scaling Thresholds:
        Scale UP: utilization > 80%
        Scale DOWN: utilization < 20%

    Example:
        import logging
        logger = logging.getLogger(__name__)

        manager = ConnectionManager()
        monitor = PoolMonitor(manager)

        metrics = await monitor.collect_metrics("dev")
        if monitor.should_scale_up(metrics):
            logger.warning("Consider increasing pool size")
    """

    def __init__(self, manager: ConnectionManager):
        """
        Initialize pool monitor.

        Args:
            manager: ConnectionManager instance
        """
        self._manager = manager
        self._metrics: Dict[str, PoolMetrics] = {}

    async def collect_metrics(self, environment: str) -> PoolMetrics:
        """
        Collect current metrics for environment.

        Note: Neo4j driver doesn't expose all metrics directly.
        This is a conceptual framework - actual implementation would
        need to track metrics in wrapper or use driver internals.

        Args:
            environment: Environment name

        Returns:
            PoolMetrics with current values
        """
        # Get pool size from config
        pool_size = self._manager._configs[environment].max_pool_size

        # Placeholder metrics (would be tracked in production)
        metrics = PoolMetrics(
            environment=environment,
            pool_size=pool_size,
            active_connections=0,  # Would track in wrapper
            idle_connections=pool_size,  # Would track in wrapper
            total_requests=0,  # Would track in wrapper
            failed_requests=0,  # Would track in wrapper
            avg_acquisition_time=0.0,  # Would track in wrapper
            max_acquisition_time=0.0,  # Would track in wrapper
        )

        self._metrics[environment] = metrics
        return metrics

    def should_scale_up(self, metrics: PoolMetrics) -> bool:
        """
        Determine if pool should be scaled up.

        Scale up if utilization > 80% consistently.

        Args:
            metrics: Current pool metrics

        Returns:
            True if should scale up
        """
        return metrics.utilization() > 80.0

    def should_scale_down(self, metrics: PoolMetrics) -> bool:
        """
        Determine if pool should be scaled down.

        Scale down if utilization < 20% consistently.

        Args:
            metrics: Current pool metrics

        Returns:
            True if should scale down
        """
        return metrics.utilization() < 20.0


__all__ = ["PoolMetrics", "PoolMonitor"]
