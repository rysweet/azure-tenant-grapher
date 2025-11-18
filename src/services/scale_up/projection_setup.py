"""
Projection Setup Module for Scale-Up Service

This module handles setup, configuration, and preliminary validation
for scale-up projection operations.

Responsibilities:
- Index management and optimization
- Base resource discovery and filtering
- Tenant validation
- Configuration validation
- Adaptive batch size calculation
"""

import logging
import re
from typing import Any, Dict, List, Optional

from src.services.scale_performance import AdaptiveBatchSizer, QueryOptimizer
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


class ProjectionSetup:
    """
    Handles setup and configuration for scale-up projection operations.

    This class provides utilities for preparing the database and validating
    inputs before starting resource projection operations.
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        batch_size: int = 500,
        enable_adaptive_batching: bool = True,
    ) -> None:
        """
        Initialize projection setup.

        Args:
            session_manager: Neo4j session manager
            batch_size: Default batch size for operations
            enable_adaptive_batching: Whether to use adaptive batch sizing
        """
        self.session_manager = session_manager
        self.batch_size = batch_size
        self.enable_adaptive_batching = enable_adaptive_batching
        self.logger = logger

    def ensure_indexes(self) -> None:
        """
        Ensure critical Neo4j indexes exist for optimal performance.

        Creates indexes on Resource nodes for:
        - id (unique constraint)
        - scale_operation_id (for rollback)
        - synthetic flag (for filtering)
        - type (for resource type queries)
        """
        try:
            with self.session_manager.session() as session:
                QueryOptimizer.ensure_indexes(session, self.logger)
                self.logger.info("Neo4j indexes verified/created successfully")
        except Exception as e:
            self.logger.warning(f"Failed to ensure indexes: {e}")
            # Don't fail initialization if index creation fails

    def get_adaptive_batch_size(
        self, total_items: int, operation_type: str = "write"
    ) -> int:
        """
        Get batch size, using adaptive sizing if enabled.

        Adaptive sizing adjusts batch size based on total item count
        to optimize performance for both small and large operations.

        Args:
            total_items: Total number of items to process
            operation_type: "read" or "write"

        Returns:
            Optimal batch size for the operation

        Example:
            >>> setup = ProjectionSetup(session_manager)
            >>> batch_size = setup.get_adaptive_batch_size(10000, "write")
            >>> print(f"Using batch size: {batch_size}")
        """
        if self.enable_adaptive_batching and total_items > 1000:
            return AdaptiveBatchSizer.calculate_batch_size(
                total_items, operation_type, min_size=100, max_size=self.batch_size * 2
            )
        return self.batch_size

    async def validate_tenant_exists(self, tenant_id: str) -> bool:
        """
        Validate that a tenant exists in the database.

        Args:
            tenant_id: Azure tenant ID to validate

        Returns:
            True if tenant exists, False otherwise

        Example:
            >>> setup = ProjectionSetup(session_manager)
            >>> exists = await setup.validate_tenant_exists("abc-123")
            >>> if not exists:
            ...     raise ValueError("Tenant not found")
        """
        query = """
        MATCH (t:Tenant {tenant_id: $tenant_id})
        RETURN count(t) > 0 as exists
        """

        with self.session_manager.session() as session:
            result = session.run(query, {"tenant_id": tenant_id})
            record = result.single()
            return record["exists"] if record else False

    async def get_base_resources(
        self, tenant_id: str, resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get base resources from abstracted layer for template replication.

        Retrieves non-synthetic resources that can be used as templates
        for generating synthetic copies. Supports filtering by resource type.

        Args:
            tenant_id: Azure tenant ID
            resource_types: Optional list of resource types to filter

        Returns:
            List of resource dictionaries with id, type, properties

        Raises:
            ValueError: If resource_types contain invalid values

        Example:
            >>> setup = ProjectionSetup(session_manager)
            >>> resources = await setup.get_base_resources(
            ...     "abc-123",
            ...     ["Microsoft.Compute/virtualMachines"]
            ... )
            >>> print(f"Found {len(resources)} base resources")
        """
        # Validate resource types if provided
        if resource_types:
            self._validate_resource_types(resource_types)

        # Build query with parameterized resource types (no string interpolation)
        if resource_types:
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND (r.synthetic IS NULL OR r.synthetic = false)
              AND r.type IN $resource_types
            RETURN r.id as id, r.type as type, properties(r) as props
            LIMIT 10000
            """
            params = {"resource_types": resource_types}
        else:
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND (r.synthetic IS NULL OR r.synthetic = false)
            RETURN r.id as id, r.type as type, properties(r) as props
            LIMIT 10000
            """
            params = {}

        with self.session_manager.session() as session:
            result = session.run(query, params)
            resources = [
                {"id": record["id"], "type": record["type"], "props": record["props"]}
                for record in result
            ]

        self.logger.info(f"Retrieved {len(resources)} base resources for replication")
        return resources

    def _validate_resource_types(self, resource_types: List[str]) -> None:
        """
        Validate resource type format.

        Azure resource types follow the pattern:
        Provider.Service/resourceType (e.g., Microsoft.Compute/virtualMachines)

        Args:
            resource_types: List of resource type strings to validate

        Raises:
            ValueError: If any resource type has invalid format or is too long
        """
        for rt in resource_types:
            if not re.match(r'^[A-Za-z0-9]+\.[A-Za-z0-9]+/[A-Za-z0-9]+$', rt):
                raise ValueError(f"Invalid resource type format: {rt}")
            if len(rt) > 200:
                raise ValueError(f"Resource type too long: {rt}")

    async def validate_scale_factor(self, scale_factor: float) -> None:
        """
        Validate scale factor value.

        Args:
            scale_factor: Multiplier for resource counts

        Raises:
            ValueError: If scale factor is invalid
        """
        if scale_factor <= 0:
            raise ValueError("Scale factor must be positive")
        if scale_factor <= 1.0:
            raise ValueError(
                f"Scale factor {scale_factor} must be > 1.0 to create new resources"
            )

    async def validate_random_config(
        self, target_count: int, config: Dict[str, Any]
    ) -> None:
        """
        Validate random generation configuration.

        Args:
            target_count: Target number of resources to create
            config: Configuration dictionary

        Raises:
            ValueError: If config is invalid
        """
        if target_count <= 0:
            raise ValueError("target_count must be positive")

        if "resource_type_distribution" not in config:
            raise ValueError("config must include 'resource_type_distribution'")

        distribution = config["resource_type_distribution"]
        if not distribution:
            raise ValueError("resource_type_distribution cannot be empty")

        # Validate distribution values
        for resource_type, probability in distribution.items():
            if probability < 0:
                raise ValueError(
                    f"Probability for {resource_type} must be non-negative"
                )

        # Validate relationship density if provided
        if "relationship_density" in config:
            density = config["relationship_density"]
            if not 0.0 <= density <= 1.0:
                raise ValueError(
                    f"relationship_density must be between 0.0 and 1.0, got {density}"
                )

    async def validate_scenario_params(
        self, scenario: str, params: Dict[str, Any]
    ) -> None:
        """
        Validate scenario-specific parameters.

        Args:
            scenario: Scenario name (hub-spoke, multi-region, dev-test-prod)
            params: Scenario parameters

        Raises:
            ValueError: If scenario or params are invalid
        """
        valid_scenarios = ["hub-spoke", "multi-region", "dev-test-prod"]
        if scenario not in valid_scenarios:
            raise ValueError(
                f"Unknown scenario: {scenario}. Available: {', '.join(valid_scenarios)}"
            )

        if scenario == "hub-spoke":
            spoke_count = params.get("spoke_count", 3)
            resources_per_spoke = params.get("resources_per_spoke", 10)
            if spoke_count < 1:
                raise ValueError("spoke_count must be at least 1")
            if resources_per_spoke < 1:
                raise ValueError("resources_per_spoke must be at least 1")

        elif scenario == "multi-region":
            region_count = params.get("region_count", 3)
            resources_per_region = params.get("resources_per_region", 20)
            if region_count < 1:
                raise ValueError("region_count must be at least 1")
            if resources_per_region < 1:
                raise ValueError("resources_per_region must be at least 1")

        elif scenario == "dev-test-prod":
            resources_per_env = params.get("resources_per_env", 15)
            if resources_per_env < 1:
                raise ValueError("resources_per_env must be at least 1")

    def calculate_target_resources(
        self, base_count: int, scale_factor: float
    ) -> int:
        """
        Calculate target number of new resources to create.

        Args:
            base_count: Number of base resources
            scale_factor: Multiplier (e.g., 2.0 = double)

        Returns:
            Number of new resources to create

        Raises:
            ValueError: If calculation results in zero or negative resources
        """
        target_new_resources = int(base_count * (scale_factor - 1))
        if target_new_resources <= 0:
            raise ValueError(
                f"Scale factor {scale_factor} with {base_count} base resources "
                f"would create {target_new_resources} resources. Must create at least 1 resource."
            )
        return target_new_resources
