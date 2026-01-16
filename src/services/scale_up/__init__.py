"""
Scale-Up Service Package for Azure Tenant Grapher

This package provides comprehensive synthetic resource generation capabilities
using three distinct strategies: template-based, scenario-based, and random.

Main Components:
- ScaleUpService: Main orchestrator coordinating strategies
- template_strategy: Template-based resource replication
- scenario_strategy: Topology pattern generation (hub-spoke, multi-region, etc.)
- random_strategy: Random resource generation with constraints
- common: Shared utilities for batch operations and performance optimization

Usage:
    >>> from src.services.scale_up import ScaleUpService
    >>> service = ScaleUpService(session_manager)
    >>> result = await service.scale_up_template(
    ...     tenant_id="abc123",
    ...     scale_factor=2.0
    ... )
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.base_scale_service import BaseScaleService
from src.services.scale_up import (
    common,
    random_strategy,
    scenario_strategy,
    template_strategy,
)
from src.services.scale_validation import ScaleValidation
from src.utils.session_manager import Neo4jSessionManager

logger = logging.getLogger(__name__)


@dataclass
class ScaleUpResult:
    """
    Result of a scale-up operation.

    Attributes:
        operation_id: Unique identifier for this operation
        tenant_id: Azure tenant ID
        strategy: Strategy used (template/scenario/random)
        resources_created: Number of resources created
        relationships_created: Number of relationships created
        duration_seconds: Operation duration
        success: Whether operation succeeded
        validation_passed: Whether post-operation validation passed
        error_message: Error message if operation failed
        metadata: Additional operation-specific data
        rollback_attempted: Whether rollback was attempted on failure
        rollback_succeeded: Whether rollback succeeded (if attempted)
        rollback_error: Error message from rollback (if failed)
    """

    operation_id: str
    tenant_id: str
    strategy: str
    resources_created: int
    relationships_created: int
    duration_seconds: float
    success: bool
    validation_passed: bool
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    rollback_attempted: bool = False
    rollback_succeeded: bool = False
    rollback_error: Optional[str] = None


class ScaleUpService(BaseScaleService):
    """
    Service for scaling up Azure tenant graphs with synthetic data.

    This service generates synthetic resources in the abstracted graph layer
    using various strategies. It maintains graph topology while creating
    realistic test data for performance testing and development.

    All operations:
    - Create resources in abstracted layer only (no :Original nodes)
    - Mark resources as synthetic
    - Support progress callbacks for UI/CLI integration
    - Include validation and rollback capabilities
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        batch_size: int = 500,
        validation_enabled: bool = True,
        enable_performance_monitoring: bool = True,
        enable_adaptive_batching: bool = True,
    ) -> None:
        """
        Initialize the scale-up service.

        Args:
            session_manager: Neo4j session manager for database operations
            batch_size: Number of resources to process per batch (default: 500)
            validation_enabled: Enable post-operation validation (default: True)
            enable_performance_monitoring: Enable performance metrics collection
            enable_adaptive_batching: Use adaptive batch sizing for large operations
        """
        super().__init__(session_manager)
        self.batch_size = batch_size
        self.validation_enabled = validation_enabled
        self.enable_performance_monitoring = enable_performance_monitoring
        self.enable_adaptive_batching = enable_adaptive_batching

        # Ensure critical indexes exist for optimal performance
        common.ensure_indexes(session_manager)

    async def scale_up_template(
        self,
        tenant_id: str,
        scale_factor: float,
        resource_types: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        target_layer_id: Optional[str] = None,
        new_layer: Optional[str] = None,
    ) -> ScaleUpResult:
        """
        Scale up resources using template-based replication.

        Analyzes existing abstracted resources and replicates them with variations.
        Maintains topology structure and resource type proportions.

        Args:
            tenant_id: Azure tenant ID
            scale_factor: Multiplier for resource counts (e.g., 2.0 = double resources)
            resource_types: Optional list of resource types to scale (None = all types)
            progress_callback: Optional callback(message, current, total)
            target_layer_id: Specific layer to write synthetic resources to (mutually exclusive with new_layer)
            new_layer: Auto-create new layer with this ID for synthetic resources (mutually exclusive with target_layer_id)

        Returns:
            ScaleUpResult: Operation results including counts and validation status

        Raises:
            ValueError: If tenant doesn't exist or scale_factor is invalid
            Exception: If operation fails

        Example:
            >>> result = await service.scale_up_template(
            ...     tenant_id="abc123",
            ...     scale_factor=2.0,
            ...     resource_types=["Microsoft.Compute/virtualMachines"]
            ... )
            >>> print(str(f"Created {result.resources_created} synthetic resources"))
        """
        start_time = datetime.now()
        operation_id = await self.generate_session_id()

        try:
            # Validate tenant exists
            if not await self.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found in database")

            if scale_factor <= 0:
                raise ValueError("Scale factor must be positive")

            self.logger.info(
                f"Starting template-based scale-up: tenant={tenant_id}, "
                f"factor={scale_factor}, operation_id={operation_id}"
            )

            # Step 1: Analyze existing resources
            if progress_callback:
                progress_callback("Analyzing existing resources...", 0, 100)

            base_resources = await template_strategy.get_base_resources(
                self.session_manager, tenant_id, resource_types
            )
            if not base_resources:
                raise ValueError(
                    f"No base resources found for tenant {tenant_id}"
                    + (f" with types {resource_types}" if resource_types else "")
                )

            self.logger.info(
                str(f"Found {len(base_resources)} base resources to replicate")
            )

            # Step 2: Calculate target counts
            target_new_resources = int(len(base_resources) * (scale_factor - 1))
            if target_new_resources <= 0:
                raise ValueError(
                    f"Scale factor {scale_factor} would create {target_new_resources} "
                    f"resources. Must be > 1.0 to create new resources."
                )

            # Step 3: Generate synthetic resources
            if progress_callback:
                progress_callback(
                    f"Generating {target_new_resources} synthetic resources...", 20, 100
                )

            resources_created = await template_strategy.replicate_resources(
                session_manager=self.session_manager,
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
                target_count=target_new_resources,
                batch_size=self.batch_size,
                enable_adaptive_batching=self.enable_adaptive_batching,
                enable_performance_monitoring=self.enable_performance_monitoring,
                progress_callback=progress_callback,
                progress_start=20,
                progress_end=60,
            )

            # Step 4: Clone relationships
            if progress_callback:
                progress_callback("Cloning relationships...", 60, 100)

            relationships_created = await template_strategy.clone_relationships(
                session_manager=self.session_manager,
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
                batch_size=self.batch_size,
                enable_adaptive_batching=self.enable_adaptive_batching,
                enable_performance_monitoring=self.enable_performance_monitoring,
                progress_callback=progress_callback,
                progress_start=60,
                progress_end=90,
            )

            # Step 5: Validate
            validation_passed = True
            if self.validation_enabled:
                if progress_callback:
                    progress_callback("Validating operation...", 90, 100)

                validation_passed = await self._validate_operation(operation_id)

            duration = (datetime.now() - start_time).total_seconds()

            if progress_callback:
                progress_callback("Scale-up complete!", 100, 100)

            self.logger.info(
                f"Scale-up completed: {resources_created} resources, "
                f"{relationships_created} relationships in {duration:.2f}s"
            )

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="template",
                resources_created=resources_created,
                relationships_created=relationships_created,
                duration_seconds=duration,
                success=True,
                validation_passed=validation_passed,
                metadata={
                    "scale_factor": scale_factor,
                    "base_resource_count": len(base_resources),
                    "resource_types": resource_types,
                },
            )

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Scale-up failed: {e}")

            # Attempt rollback and track outcome
            rollback_attempted = True
            rollback_succeeded = False
            rollback_error = None

            try:
                await self.rollback_operation(operation_id)
                rollback_succeeded = True
                self.logger.info(
                    str(f"Rollback succeeded for operation {operation_id}")
                )
            except (Neo4jError, ValueError, RuntimeError) as rollback_err:
                rollback_error = str(rollback_err)
                self.logger.error(str(f"Rollback failed: {rollback_err}"))
            except Exception as unexpected_error:
                rollback_error = str(unexpected_error)
                self.logger.exception(
                    f"Unexpected error during rollback: {unexpected_error}"
                )
                raise

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="template",
                resources_created=0,
                relationships_created=0,
                duration_seconds=duration,
                success=False,
                validation_passed=False,
                error_message=str(e),
                rollback_attempted=rollback_attempted,
                rollback_succeeded=rollback_succeeded,
                rollback_error=rollback_error,
            )

    async def scale_up_scenario(
        self,
        tenant_id: str,
        scenario: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        target_layer_id: Optional[str] = None,
        new_layer: Optional[str] = None,
    ) -> ScaleUpResult:
        """
        Scale up resources using scenario-based topology generation.

        Generates realistic topology patterns like hub-spoke networks,
        multi-region deployments, or dev/test/prod environments.

        Args:
            tenant_id: Azure tenant ID
            scenario: Scenario name (hub-spoke, multi-region, dev-test-prod)
            params: Scenario-specific parameters
            progress_callback: Optional callback(message, current, total)
            target_layer_id: Specific layer to write synthetic resources to
            new_layer: Auto-create new layer with this ID

        Returns:
            ScaleUpResult: Operation results

        Raises:
            ValueError: If scenario is unknown or params are invalid
            Exception: If operation fails

        Example:
            >>> result = await service.scale_up_scenario(
            ...     tenant_id="abc123",
            ...     scenario="hub-spoke",
            ...     params={"spoke_count": 5, "resources_per_spoke": 10}
            ... )
        """
        start_time = datetime.now()
        operation_id = await self.generate_session_id()

        try:
            # Validate tenant
            if not await self.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found")

            self.logger.info(
                f"Starting scenario-based scale-up: tenant={tenant_id}, "
                f"scenario={scenario}, operation_id={operation_id}"
            )

            if progress_callback:
                progress_callback(f"Generating {scenario} topology...", 0, 100)

            # Route to scenario generator
            if scenario == "hub-spoke":
                (
                    resources_created,
                    relationships_created,
                ) = await scenario_strategy.generate_hub_spoke(
                    self.session_manager,
                    tenant_id,
                    operation_id,
                    params,
                    progress_callback,
                )
            elif scenario == "multi-region":
                (
                    resources_created,
                    relationships_created,
                ) = await scenario_strategy.generate_multi_region(
                    self.session_manager,
                    tenant_id,
                    operation_id,
                    params,
                    progress_callback,
                )
            elif scenario == "dev-test-prod":
                (
                    resources_created,
                    relationships_created,
                ) = await scenario_strategy.generate_dev_test_prod(
                    self.session_manager,
                    tenant_id,
                    operation_id,
                    params,
                    progress_callback,
                )
            else:
                raise ValueError(
                    f"Unknown scenario: {scenario}. "
                    f"Available: hub-spoke, multi-region, dev-test-prod"
                )

            # Validate
            validation_passed = True
            if self.validation_enabled:
                if progress_callback:
                    progress_callback("Validating operation...", 90, 100)
                validation_passed = await self._validate_operation(operation_id)

            duration = (datetime.now() - start_time).total_seconds()

            if progress_callback:
                progress_callback("Scenario generation complete!", 100, 100)

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="scenario",
                resources_created=resources_created,
                relationships_created=relationships_created,
                duration_seconds=duration,
                success=True,
                validation_passed=validation_passed,
                metadata={"scenario": scenario, "params": params},
            )

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Scenario scale-up failed: {e}")

            # Attempt rollback and track outcome
            rollback_attempted = True
            rollback_succeeded = False
            rollback_error = None

            try:
                await self.rollback_operation(operation_id)
                rollback_succeeded = True
                self.logger.info(
                    str(f"Rollback succeeded for operation {operation_id}")
                )
            except (Neo4jError, ValueError, RuntimeError) as rollback_err:
                rollback_error = str(rollback_err)
                self.logger.error(str(f"Rollback failed: {rollback_err}"))
            except Exception as unexpected_error:
                rollback_error = str(unexpected_error)
                self.logger.exception(
                    f"Unexpected error during rollback: {unexpected_error}"
                )
                raise

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="scenario",
                resources_created=0,
                relationships_created=0,
                duration_seconds=duration,
                success=False,
                validation_passed=False,
                error_message=str(e),
                metadata={"scenario": scenario, "params": params},
                rollback_attempted=rollback_attempted,
                rollback_succeeded=rollback_succeeded,
                rollback_error=rollback_error,
            )

    async def scale_up_random(
        self,
        tenant_id: str,
        target_count: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        target_layer_id: Optional[str] = None,
        new_layer: Optional[str] = None,
    ) -> ScaleUpResult:
        """
        Scale up resources using random generation with constraints.

        Generates random resources within defined bounds (resource type
        distributions, relationship density, property ranges).

        Args:
            tenant_id: Azure tenant ID
            target_count: Target number of resources to create
            config: Configuration including:
                - resource_type_distribution: Dict[str, float] (type -> probability)
                - relationship_density: float (0.0-1.0)
                - seed: Optional[int] for reproducibility
            progress_callback: Optional callback(message, current, total)
            target_layer_id: Specific layer to write synthetic resources to
            new_layer: Auto-create new layer with this ID

        Returns:
            ScaleUpResult: Operation results

        Raises:
            ValueError: If config is invalid or target_count <= 0
            Exception: If operation fails

        Example:
            >>> result = await service.scale_up_random(
            ...     tenant_id="abc123",
            ...     target_count=1000,
            ...     config={
            ...         "resource_type_distribution": {
            ...             "Microsoft.Compute/virtualMachines": 0.3,
            ...             "Microsoft.Network/virtualNetworks": 0.2,
            ...             "Microsoft.Storage/storageAccounts": 0.5
            ...         },
            ...         "relationship_density": 0.3,
            ...         "seed": 42
            ...     }
            ... )
        """
        start_time = datetime.now()
        operation_id = await self.generate_session_id()

        try:
            # Validate inputs
            if not await self.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found")

            if target_count <= 0:
                raise ValueError("target_count must be positive")

            if "resource_type_distribution" not in config:
                raise ValueError("config must include 'resource_type_distribution'")

            # Set random seed if provided
            if "seed" in config:
                random.seed(config["seed"])

            self.logger.info(
                f"Starting random scale-up: tenant={tenant_id}, "
                f"target={target_count}, operation_id={operation_id}"
            )

            if progress_callback:
                progress_callback(
                    f"Generating {target_count} random resources...", 0, 100
                )

            # Generate resources
            resources_created = await random_strategy.generate_random_resources(
                session_manager=self.session_manager,
                tenant_id=tenant_id,
                operation_id=operation_id,
                target_count=target_count,
                distribution=config["resource_type_distribution"],
                batch_size=self.batch_size,
                progress_callback=progress_callback,
                progress_start=0,
                progress_end=70,
            )

            # Generate relationships
            relationship_density = config.get("relationship_density", 0.3)
            relationships_created = await random_strategy.generate_random_relationships(
                session_manager=self.session_manager,
                tenant_id=tenant_id,
                operation_id=operation_id,
                density=relationship_density,
                batch_size=self.batch_size,
                progress_callback=progress_callback,
                progress_start=70,
                progress_end=90,
            )

            # Validate
            validation_passed = True
            if self.validation_enabled:
                if progress_callback:
                    progress_callback("Validating operation...", 90, 100)
                validation_passed = await self._validate_operation(operation_id)

            duration = (datetime.now() - start_time).total_seconds()

            if progress_callback:
                progress_callback("Random generation complete!", 100, 100)

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="random",
                resources_created=resources_created,
                relationships_created=relationships_created,
                duration_seconds=duration,
                success=True,
                validation_passed=validation_passed,
                metadata={
                    "target_count": target_count,
                    "relationship_density": relationship_density,
                    "config": config,
                },
            )

        except (Neo4jError, ValueError, RuntimeError) as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Random scale-up failed: {e}")

            # Attempt rollback and track outcome
            rollback_attempted = True
            rollback_succeeded = False
            rollback_error = None

            try:
                await self.rollback_operation(operation_id)
                rollback_succeeded = True
                self.logger.info(
                    str(f"Rollback succeeded for operation {operation_id}")
                )
            except (Neo4jError, ValueError, RuntimeError) as rollback_err:
                rollback_error = str(rollback_err)
                self.logger.error(str(f"Rollback failed: {rollback_err}"))
            except Exception as unexpected_error:
                rollback_error = str(unexpected_error)
                self.logger.exception(
                    f"Unexpected error during rollback: {unexpected_error}"
                )
                raise

            return ScaleUpResult(
                operation_id=operation_id,
                tenant_id=tenant_id,
                strategy="random",
                resources_created=0,
                relationships_created=0,
                duration_seconds=duration,
                success=False,
                validation_passed=False,
                error_message=str(e),
                rollback_attempted=rollback_attempted,
                rollback_succeeded=rollback_succeeded,
                rollback_error=rollback_error,
            )

    async def rollback_operation(self, operation_id: str) -> int:
        """
        Rollback a scale operation by deleting all synthetic resources.

        This removes all resources and relationships created during the
        specified operation. Safe to call multiple times.

        Args:
            operation_id: Scale operation ID to rollback

        Returns:
            int: Number of resources deleted

        Raises:
            Exception: If rollback fails

        Example:
            >>> deleted_count = await service.rollback_operation(
            ...     "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(str(f"Rolled back {deleted_count} resources"))
        """
        self.logger.info(str(f"Rolling back operation: {operation_id}"))

        try:
            # Delete all synthetic resources for this operation
            # Relationships are automatically deleted due to CASCADE
            query = """
            MATCH (r:Resource)
            WHERE NOT r:Original
              AND r.scale_operation_id = $operation_id
              AND r.synthetic = true
            WITH r
            DETACH DELETE r
            RETURN count(r) as deleted_count
            """

            with self.session_manager.session() as session:
                result = session.run(query, {"operation_id": operation_id})  # type: ignore[arg-type]
                record = result.single()
                deleted_count = record["deleted_count"] if record else 0

            self.logger.info(
                f"Rollback complete: deleted {deleted_count} synthetic resources"
            )
            return deleted_count

        except (Neo4jError, ValueError) as e:
            self.logger.exception(f"Rollback failed for operation {operation_id}: {e}")
            raise
        except Exception as e:
            self.logger.exception(
                f"Unexpected error during rollback for operation {operation_id}: {e}"
            )
            raise

    async def _validate_operation(self, operation_id: str) -> bool:
        """
        Validate a scale operation.

        Args:
            operation_id: Scale operation ID to validate

        Returns:
            True if all validations pass, False otherwise
        """
        with self.session_manager.session() as session:
            is_valid, message = await ScaleValidation.validate_operation(
                session, operation_id
            )
            if not is_valid:
                self.logger.warning(str(f"Validation failed: {message}"))
            return is_valid


__all__ = [
    "ScaleUpResult",
    "ScaleUpService",
]
