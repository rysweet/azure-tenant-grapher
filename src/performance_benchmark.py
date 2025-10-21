"""
Performance Benchmark Script for Azure Tenant Grapher

Measures scan performance and identifies bottlenecks.
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Tracks performance metrics for scan operations."""

    # Discovery metrics
    subscription_discovery_time: float = 0.0
    resource_list_time: float = 0.0
    resource_property_fetch_time: float = 0.0
    api_version_lookup_time: float = 0.0

    # Processing metrics
    neo4j_write_time: float = 0.0
    relationship_creation_time: float = 0.0
    llm_generation_time: float = 0.0

    # Counts
    resources_discovered: int = 0
    resources_processed: int = 0
    api_calls_made: int = 0
    neo4j_operations: int = 0
    api_version_cache_hits: int = 0
    api_version_cache_misses: int = 0

    # Detailed timings
    resource_timings: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def total_time(self) -> float:
        """Total time spent across all operations."""
        return (
            self.subscription_discovery_time
            + self.resource_list_time
            + self.resource_property_fetch_time
            + self.api_version_lookup_time
            + self.neo4j_write_time
            + self.relationship_creation_time
            + self.llm_generation_time
        )

    @property
    def avg_resource_time(self) -> float:
        """Average time per resource."""
        if self.resources_processed == 0:
            return 0.0
        return self.total_time / self.resources_processed

    @property
    def resources_per_minute(self) -> float:
        """Resources processed per minute."""
        if self.total_time == 0:
            return 0.0
        return (self.resources_processed / self.total_time) * 60

    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "discovery": {
                "subscription_discovery_time": round(
                    self.subscription_discovery_time, 2
                ),
                "resource_list_time": round(self.resource_list_time, 2),
                "resource_property_fetch_time": round(
                    self.resource_property_fetch_time, 2
                ),
                "api_version_lookup_time": round(self.api_version_lookup_time, 2),
            },
            "processing": {
                "neo4j_write_time": round(self.neo4j_write_time, 2),
                "relationship_creation_time": round(
                    self.relationship_creation_time, 2
                ),
                "llm_generation_time": round(self.llm_generation_time, 2),
            },
            "counts": {
                "resources_discovered": self.resources_discovered,
                "resources_processed": self.resources_processed,
                "api_calls_made": self.api_calls_made,
                "neo4j_operations": self.neo4j_operations,
                "api_version_cache_hits": self.api_version_cache_hits,
                "api_version_cache_misses": self.api_version_cache_misses,
            },
            "summary": {
                "total_time": round(self.total_time, 2),
                "avg_resource_time": round(self.avg_resource_time, 3),
                "resources_per_minute": round(self.resources_per_minute, 2),
            },
        }

    def print_summary(self) -> None:
        """Print a formatted summary of performance metrics."""
        logger.info("=" * 80)
        logger.info("🔬 PERFORMANCE METRICS SUMMARY")
        logger.info("=" * 80)

        # Discovery breakdown
        logger.info("📊 Discovery Phase:")
        logger.info(
            f"  - Subscription Discovery: {self.subscription_discovery_time:.2f}s"
        )
        logger.info(f"  - Resource Listing: {self.resource_list_time:.2f}s")
        logger.info(
            f"  - Property Fetching: {self.resource_property_fetch_time:.2f}s"
        )
        logger.info(f"  - API Version Lookups: {self.api_version_lookup_time:.2f}s")

        # Processing breakdown
        logger.info("⚙️  Processing Phase:")
        logger.info(f"  - Neo4j Writes: {self.neo4j_write_time:.2f}s")
        logger.info(
            f"  - Relationship Creation: {self.relationship_creation_time:.2f}s"
        )
        logger.info(f"  - LLM Generation: {self.llm_generation_time:.2f}s")

        # Cache efficiency
        total_lookups = self.api_version_cache_hits + self.api_version_cache_misses
        cache_hit_rate = (
            (self.api_version_cache_hits / total_lookups * 100) if total_lookups > 0 else 0
        )
        logger.info("💾 Cache Efficiency:")
        logger.info(f"  - API Version Cache Hit Rate: {cache_hit_rate:.1f}%")
        logger.info(f"  - Cache Hits: {self.api_version_cache_hits}")
        logger.info(f"  - Cache Misses: {self.api_version_cache_misses}")

        # Performance summary
        logger.info("⚡ Performance Summary:")
        logger.info(f"  - Total Time: {self.total_time:.2f}s")
        logger.info(f"  - Resources Processed: {self.resources_processed}")
        logger.info(f"  - Avg Time/Resource: {self.avg_resource_time:.3f}s")
        logger.info(f"  - Resources/Minute: {self.resources_per_minute:.2f}")
        logger.info(f"  - API Calls Made: {self.api_calls_made}")
        logger.info(f"  - Neo4j Operations: {self.neo4j_operations}")

        # Bottleneck identification
        logger.info("🚦 Bottleneck Analysis:")
        phases = [
            ("Resource Property Fetching", self.resource_property_fetch_time),
            ("Neo4j Writes", self.neo4j_write_time),
            ("Relationship Creation", self.relationship_creation_time),
            ("LLM Generation", self.llm_generation_time),
            ("API Version Lookups", self.api_version_lookup_time),
            ("Resource Listing", self.resource_list_time),
        ]
        phases_sorted = sorted(phases, key=lambda x: x[1], reverse=True)
        for i, (name, duration) in enumerate(phases_sorted[:3], 1):
            pct = (duration / self.total_time * 100) if self.total_time > 0 else 0
            logger.info(f"  {i}. {name}: {duration:.2f}s ({pct:.1f}%)")

        logger.info("=" * 80)


class PerformanceTimer:
    """Context manager for timing operations."""

    def __init__(self, metrics: PerformanceMetrics, metric_name: str):
        self.metrics = metrics
        self.metric_name = metric_name
        self.start_time = 0.0

    def __enter__(self):
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        duration = time.perf_counter() - self.start_time
        current_value = getattr(self.metrics, self.metric_name, 0.0)
        setattr(self.metrics, self.metric_name, current_value + duration)
