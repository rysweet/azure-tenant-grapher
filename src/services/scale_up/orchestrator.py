"""
Orchestrator Module for Scale-Up Service

This module coordinates the entire scale-up operation workflow,
orchestrating between setup, projection, and validation components.

Responsibilities:
- High-level operation coordination
- Error handling and rollback coordination
- Progress tracking
- Result aggregation
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from neo4j.exceptions import Neo4jError

from src.services.base_scale_service import BaseScaleService
from src.services.scale_up.projection_setup import ProjectionSetup
from src.services.scale_up.resource_projection import ResourceProjection
from src.services.scale_up.validation import ValidationService
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


class ScaleUpOrchestrator(BaseScaleService):
    """
    Orchestrates scale-up operations by coordinating setup, projection, and validation.

    This is the main entry point for scale-up operations. It delegates to
    specialized components for setup, resource projection, and validation.
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
        Initialize the scale-up orchestrator.

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

        # Initialize specialized components
        self.setup = ProjectionSetup(
            session_manager, batch_size, enable_adaptive_batching
        )
        self.projection = ResourceProjection(
            session_manager, batch_size, enable_performance_monitoring
        )
        self.validation = ValidationService(session_manager, validation_enabled)

        # Ensure indexes on initialization
        self.setup.ensure_indexes()

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
            >>> orchestrator = ScaleUpOrchestrator(session_manager)
            >>> result = await orchestrator.scale_up_template(
            ...     tenant_id="abc123",
            ...     scale_factor=2.0,
            ...     resource_types=["Microsoft.Compute/virtualMachines"]
            ... )
            >>> print(f"Created {result.resources_created} synthetic resources")
        """
        start_time = datetime.now()
        operation_id = await self.generate_session_id()

        try:
            # Step 1: Validate tenant and inputs
            if not await self.setup.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found in database")

            await self.setup.validate_scale_factor(scale_factor)

            self.logger.info(
                f"Starting template-based scale-up: tenant={tenant_id}, "
                f"factor={scale_factor}, operation_id={operation_id}"
            )

            # Step 2: Get base resources
            if progress_callback:
                progress_callback("Analyzing existing resources...", 0, 100)

            base_resources = await self.setup.get_base_resources(tenant_id, resource_types)
            if not base_resources:
                raise ValueError(
                    f"No base resources found for tenant {tenant_id}"
                    + (f" with types {resource_types}" if resource_types else "")
                )

            self.logger.info(f"Found {len(base_resources)} base resources to replicate")

            # Step 3: Calculate target counts
            target_new_resources = self.setup.calculate_target_resources(
                len(base_resources), scale_factor
            )

            # Step 4: Generate synthetic resources
            if progress_callback:
                progress_callback(
                    f"Generating {target_new_resources} synthetic resources...", 20, 100
                )

            adaptive_batch_size = self.setup.get_adaptive_batch_size(
                target_new_resources, "write"
            )

            resources_created = await self.projection.replicate_resources(
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
                target_count=target_new_resources,
                adaptive_batch_size=adaptive_batch_size,
                progress_callback=progress_callback,
                progress_start=20,
                progress_end=60,
            )

            # Step 5: Clone relationships
            if progress_callback:
                progress_callback("Cloning relationships...", 60, 100)

            relationships_created = await self.projection.clone_relationships(
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
                adaptive_batch_size=adaptive_batch_size,
                progress_callback=progress_callback,
                progress_start=60,
                progress_end=90,
            )

            # Step 6: Validate
            validation_passed = True
            if self.validation_enabled:
                if progress_callback:
                    progress_callback("Validating operation...", 90, 100)

                validation_passed = await self.validation.validate_operation(operation_id)

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
            return await self._handle_operation_failure(
                operation_id, tenant_id, "template", start_time, e
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
            target_layer_id: Specific layer to write to
            new_layer: Auto-create new layer with this ID

        Returns:
            ScaleUpResult: Operation results

        Raises:
            ValueError: If scenario is unknown or params are invalid
            Exception: If operation fails

        Example:
            >>> result = await orchestrator.scale_up_scenario(
            ...     tenant_id="abc123",
            ...     scenario="hub-spoke",
            ...     params={"spoke_count": 5, "resources_per_spoke": 10}
            ... )
        """
        start_time = datetime.now()
        operation_id = await self.generate_session_id()

        try:
            # Validate inputs
            if not await self.setup.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found")

            await self.setup.validate_scenario_params(scenario, params)

            self.logger.info(
                f"Starting scenario-based scale-up: tenant={tenant_id}, "
                f"scenario={scenario}, operation_id={operation_id}"
            )

            if progress_callback:
                progress_callback(f"Generating {scenario} topology...", 0, 100)

            # Route to scenario generator
            if scenario == "hub-spoke":
                resources_created, relationships_created = await self.projection.generate_hub_spoke(
                    tenant_id, operation_id, params, progress_callback
                )
            elif scenario == "multi-region":
                resources_created, relationships_created = await self.projection.generate_multi_region(
                    tenant_id, operation_id, params, progress_callback
                )
            elif scenario == "dev-test-prod":
                resources_created, relationships_created = await self.projection.generate_dev_test_prod(
                    tenant_id, operation_id, params, progress_callback
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
                validation_passed = await self.validation.validate_operation(operation_id)

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
            return await self._handle_operation_failure(
                operation_id, tenant_id, "scenario", start_time, e,
                metadata={"scenario": scenario, "params": params}
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
            target_layer_id: Specific layer to write to
            new_layer: Auto-create new layer with this ID

        Returns:
            ScaleUpResult: Operation results

        Raises:
            ValueError: If config is invalid or target_count <= 0
            Exception: If operation fails

        Example:
            >>> result = await orchestrator.scale_up_random(
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
            if not await self.setup.validate_tenant_exists(tenant_id):
                raise ValueError(f"Tenant {tenant_id} not found")

            await self.setup.validate_random_config(target_count, config)

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
            resources_created = await self.projection.generate_random_resources(
                tenant_id=tenant_id,
                operation_id=operation_id,
                target_count=target_count,
                distribution=config["resource_type_distribution"],
                progress_callback=progress_callback,
                progress_start=0,
                progress_end=70,
            )

            # Generate relationships
            relationship_density = config.get("relationship_density", 0.3)
            relationships_created = await self.projection.generate_random_relationships(
                tenant_id=tenant_id,
                operation_id=operation_id,
                density=relationship_density,
                progress_callback=progress_callback,
                progress_start=70,
                progress_end=90,
            )

            # Validate
            validation_passed = True
            if self.validation_enabled:
                if progress_callback:
                    progress_callback("Validating operation...", 90, 100)
                validation_passed = await self.validation.validate_operation(operation_id)

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
            return await self._handle_operation_failure(
                operation_id, tenant_id, "random", start_time, e
            )

    async def rollback_operation(self, operation_id: str) -> int:
        """
        Rollback a scale operation by deleting all synthetic resources.

        Delegates to validation service for rollback operation.

        Args:
            operation_id: Scale operation ID to rollback

        Returns:
            int: Number of resources deleted

        Raises:
            Exception: If rollback fails

        Example:
            >>> deleted_count = await orchestrator.rollback_operation(
            ...     "scale-20250110T123045-a1b2c3d4"
            ... )
            >>> print(f"Rolled back {deleted_count} resources")
        """
        return await self.validation.rollback_operation(operation_id)

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _handle_operation_failure(
        self,
        operation_id: str,
        tenant_id: str,
        strategy: str,
        start_time: datetime,
        error: Exception,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ScaleUpResult:
        """
        Handle operation failure with rollback attempt.

        Args:
            operation_id: Operation ID
            tenant_id: Tenant ID
            strategy: Strategy used
            start_time: Operation start time
            error: Exception that caused failure
            metadata: Optional metadata to include in result

        Returns:
            ScaleUpResult with failure details
        """
        duration = (datetime.now() - start_time).total_seconds()
        self.logger.exception(f"Scale-up failed: {error}")

        # Attempt rollback and track outcome
        rollback_attempted = True
        rollback_succeeded = False
        rollback_error = None

        try:
            await self.validation.rollback_operation(operation_id)
            rollback_succeeded = True
            self.logger.info(f"Rollback succeeded for operation {operation_id}")
        except (Neo4jError, ValueError, RuntimeError) as rollback_err:
            rollback_error = str(rollback_err)
            self.logger.error(f"Rollback failed: {rollback_err}")
        except Exception as unexpected_error:
            rollback_error = str(unexpected_error)
            self.logger.exception(f"Unexpected error during rollback: {unexpected_error}")
            raise

        return ScaleUpResult(
            operation_id=operation_id,
            tenant_id=tenant_id,
            strategy=strategy,
            resources_created=0,
            relationships_created=0,
            duration_seconds=duration,
            success=False,
            validation_passed=False,
            error_message=str(error),
            metadata=metadata,
            rollback_attempted=rollback_attempted,
            rollback_succeeded=rollback_succeeded,
            rollback_error=rollback_error,
        )
