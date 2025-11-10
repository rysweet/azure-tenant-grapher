"""
Scale-Up Service for Azure Tenant Grapher

This service implements scale-up operations that generate synthetic resources
in the abstracted graph layer (:Resource nodes, not :Original nodes).

The service provides three scale-up strategies:
1. Template-based: Replicate existing resources with variations
2. Scenario-based: Generate topology patterns (hub-spoke, multi-region, etc.)
3. Random: Generate resources within defined constraints

All synthetic resources are marked with:
- synthetic: true
- scale_operation_id: unique operation identifier
- generation_strategy: template/scenario/random
- generation_timestamp: ISO 8601 timestamp

Performance target: 1000 resources in <30 seconds
"""

import logging
import random
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.services.base_scale_service import BaseScaleService
from src.services.scale_validation import ScaleValidation
from src.utils.session_manager import Neo4jSessionManager
from src.utils.synthetic_id import generate_synthetic_id

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
    ) -> None:
        """
        Initialize the scale-up service.

        Args:
            session_manager: Neo4j session manager for database operations
            batch_size: Number of resources to process per batch (default: 500)
            validation_enabled: Enable post-operation validation (default: True)
        """
        super().__init__(session_manager)
        self.batch_size = batch_size
        self.validation_enabled = validation_enabled

    async def scale_up_template(
        self,
        tenant_id: str,
        scale_factor: float,
        resource_types: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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
            >>> print(f"Created {result.resources_created} synthetic resources")
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

            base_resources = await self._get_base_resources(tenant_id, resource_types)
            if not base_resources:
                raise ValueError(
                    f"No base resources found for tenant {tenant_id}"
                    + (f" with types {resource_types}" if resource_types else "")
                )

            self.logger.info(f"Found {len(base_resources)} base resources to replicate")

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

            resources_created = await self._replicate_resources(
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
                target_count=target_new_resources,
                progress_callback=progress_callback,
                progress_start=20,
                progress_end=60,
            )

            # Step 4: Clone relationships
            if progress_callback:
                progress_callback("Cloning relationships...", 60, 100)

            relationships_created = await self._clone_relationships(
                tenant_id=tenant_id,
                operation_id=operation_id,
                base_resources=base_resources,
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

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Scale-up failed: {e}")

            # Attempt rollback
            try:
                await self.rollback_operation(operation_id)
            except Exception as rollback_error:
                self.logger.error(f"Rollback failed: {rollback_error}")

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
            )

    async def scale_up_scenario(
        self,
        tenant_id: str,
        scenario: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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
                ) = await self._generate_hub_spoke(
                    tenant_id, operation_id, params, progress_callback
                )
            elif scenario == "multi-region":
                (
                    resources_created,
                    relationships_created,
                ) = await self._generate_multi_region(
                    tenant_id, operation_id, params, progress_callback
                )
            elif scenario == "dev-test-prod":
                (
                    resources_created,
                    relationships_created,
                ) = await self._generate_dev_test_prod(
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

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Scenario scale-up failed: {e}")

            try:
                await self.rollback_operation(operation_id)
            except Exception as rollback_error:
                self.logger.error(f"Rollback failed: {rollback_error}")

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
            )

    async def scale_up_random(
        self,
        tenant_id: str,
        target_count: int,
        config: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
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
            resources_created = await self._generate_random_resources(
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
            relationships_created = await self._generate_random_relationships(
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

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            self.logger.exception(f"Random scale-up failed: {e}")

            try:
                await self.rollback_operation(operation_id)
            except Exception as rollback_error:
                self.logger.error(f"Rollback failed: {rollback_error}")

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
            >>> print(f"Rolled back {deleted_count} resources")
        """
        self.logger.info(f"Rolling back operation: {operation_id}")

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
                result = session.run(query, {"operation_id": operation_id})
                record = result.single()
                deleted_count = record["deleted_count"] if record else 0

            self.logger.info(
                f"Rollback complete: deleted {deleted_count} synthetic resources"
            )
            return deleted_count

        except Exception as e:
            self.logger.exception(f"Rollback failed for operation {operation_id}: {e}")
            raise

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

    async def _get_base_resources(
        self, tenant_id: str, resource_types: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Get base resources from abstracted layer for template replication.

        Args:
            tenant_id: Azure tenant ID
            resource_types: Optional list of resource types to filter

        Returns:
            List of resource dictionaries with id, type, properties
        """
        type_filter = ""
        if resource_types:
            # Create type filter: r.type IN ['type1', 'type2']
            type_list = ", ".join(f"'{t}'" for t in resource_types)
            type_filter = f"AND r.type IN [{type_list}]"

        query = f"""
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.tenant_id = $tenant_id
          AND (r.synthetic IS NULL OR r.synthetic = false)
          {type_filter}
        RETURN r.id as id, r.type as type, properties(r) as props
        LIMIT 10000
        """

        with self.session_manager.session() as session:
            result = session.run(query, {"tenant_id": tenant_id})
            resources = [
                {"id": record["id"], "type": record["type"], "props": record["props"]}
                for record in result
            ]

        return resources

    async def _replicate_resources(
        self,
        tenant_id: str,
        operation_id: str,
        base_resources: List[Dict[str, Any]],
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Replicate base resources to create synthetic copies.

        Uses round-robin selection from base resources with property variations.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            base_resources: List of base resources to replicate
            target_count: Number of synthetic resources to create
            progress_callback: Optional progress callback
            progress_start: Progress percentage at start
            progress_end: Progress percentage at end

        Returns:
            Number of resources created
        """
        created_count = 0
        generation_timestamp = datetime.now().isoformat()

        # Batch resources
        batches = []
        current_batch = []

        for i in range(target_count):
            # Round-robin selection from base resources
            base = base_resources[i % len(base_resources)]

            # Generate synthetic ID
            synthetic_id = generate_synthetic_id(base["type"])

            # Copy properties and add synthetic markers
            props = dict(base["props"])
            props.update(
                {
                    "id": synthetic_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "template",
                    "generation_timestamp": generation_timestamp,
                    "template_source_id": base["id"],
                }
            )

            current_batch.append(
                {"id": synthetic_id, "type": base["type"], "props": props}
            )

            if len(current_batch) >= self.batch_size:
                batches.append(current_batch)
                current_batch = []

        # Add remaining
        if current_batch:
            batches.append(current_batch)

        # Insert batches
        for batch_idx, batch in enumerate(batches):
            await self._insert_resource_batch(batch)
            created_count += len(batch)

            # Update progress
            if progress_callback:
                progress = progress_start + int(
                    ((batch_idx + 1) / len(batches)) * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {created_count}/{target_count} resources...",
                    progress,
                    100,
                )

        self.logger.info(
            f"Created {created_count} synthetic resources in {len(batches)} batches"
        )
        return created_count

    async def _insert_resource_batch(self, resources: List[Dict[str, Any]]) -> None:
        """
        Insert a batch of resources into Neo4j.

        Args:
            resources: List of resource dicts with id, type, props
        """
        query = """
        UNWIND $resources as res
        CREATE (r:Resource)
        SET r = res.props
        """

        with self.session_manager.session() as session:
            session.run(query, {"resources": resources})

    async def _clone_relationships(
        self,
        tenant_id: str,
        operation_id: str,
        base_resources: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Clone relationships between synthetic resources.

        Finds relationship patterns between base resources and replicates
        them for synthetic resources.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            base_resources: List of base resources
            progress_callback: Optional progress callback
            progress_start: Progress percentage at start
            progress_end: Progress percentage at end

        Returns:
            Number of relationships created
        """
        # Build mapping: base_id -> list of synthetic_ids
        base_to_synthetic = await self._build_resource_mapping(
            operation_id, base_resources
        )

        if progress_callback:
            progress_callback("Analyzing relationship patterns...", progress_start, 100)

        # Get relationship patterns from base resources
        patterns = await self._get_relationship_patterns(base_resources)

        if not patterns:
            self.logger.info("No relationship patterns found to clone")
            return 0

        if progress_callback:
            progress_callback(
                f"Cloning {len(patterns)} relationship patterns...",
                progress_start + 10,
                100,
            )

        # Clone relationships in batches
        relationships_created = 0
        batches = []
        current_batch = []

        for pattern in patterns:
            source_base_id = pattern["source_id"]
            target_base_id = pattern["target_id"]
            rel_type = pattern["rel_type"]
            rel_props = pattern["rel_props"]

            # Get synthetic IDs for source and target
            source_synthetic_ids = base_to_synthetic.get(source_base_id, [])
            target_synthetic_ids = base_to_synthetic.get(target_base_id, [])

            # Create relationships for all synthetic pairs
            for src_id in source_synthetic_ids:
                for tgt_id in target_synthetic_ids:
                    current_batch.append(
                        {
                            "source_id": src_id,
                            "target_id": tgt_id,
                            "rel_type": rel_type,
                            "rel_props": rel_props,
                        }
                    )

                    if len(current_batch) >= self.batch_size:
                        batches.append(current_batch)
                        current_batch = []

        if current_batch:
            batches.append(current_batch)

        # Insert relationship batches
        for batch_idx, batch in enumerate(batches):
            await self._insert_relationship_batch(batch)
            relationships_created += len(batch)

            if progress_callback:
                progress = progress_start + int(
                    ((batch_idx + 1) / len(batches)) * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {relationships_created} relationships...", progress, 100
                )

        self.logger.info(
            f"Created {relationships_created} relationships in {len(batches)} batches"
        )
        return relationships_created

    async def _build_resource_mapping(
        self, operation_id: str, base_resources: List[Dict[str, Any]]
    ) -> Dict[str, List[str]]:
        """
        Build mapping from base resource IDs to synthetic resource IDs.

        Args:
            operation_id: Scale operation ID
            base_resources: List of base resources

        Returns:
            Dict mapping base_id -> [synthetic_id1, synthetic_id2, ...]
        """
        # Get all synthetic resources for this operation
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.scale_operation_id = $operation_id
          AND r.synthetic = true
        RETURN r.id as id, r.template_source_id as source_id
        """

        mapping: Dict[str, List[str]] = defaultdict(list)

        with self.session_manager.session() as session:
            result = session.run(query, {"operation_id": operation_id})
            for record in result:
                synthetic_id = record["id"]
                source_id = record.get("source_id")
                if source_id:
                    mapping[source_id].append(synthetic_id)

        return dict(mapping)

    async def _get_relationship_patterns(
        self, base_resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract relationship patterns from base resources.

        Args:
            base_resources: List of base resources

        Returns:
            List of relationship patterns with source_id, target_id, type, props
        """
        base_ids = [r["id"] for r in base_resources]
        if not base_ids:
            return []

        # Create parameter for IN clause
        id_list = ", ".join(f"'{id}'" for id in base_ids)

        query = f"""
        MATCH (source:Resource)-[rel]->(target:Resource)
        WHERE NOT source:Original AND NOT target:Original
          AND source.id IN [{id_list}]
          AND target.id IN [{id_list}]
        RETURN source.id as source_id,
               target.id as target_id,
               type(rel) as rel_type,
               properties(rel) as rel_props
        LIMIT 100000
        """

        patterns = []
        with self.session_manager.session() as session:
            result = session.run(query)
            for record in result:
                patterns.append(
                    {
                        "source_id": record["source_id"],
                        "target_id": record["target_id"],
                        "rel_type": record["rel_type"],
                        "rel_props": record["rel_props"],
                    }
                )

        return patterns

    async def _insert_relationship_batch(
        self, relationships: List[Dict[str, Any]]
    ) -> None:
        """
        Insert a batch of relationships into Neo4j.

        Args:
            relationships: List of relationship dicts
        """
        # Group by relationship type for efficiency
        by_type: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for rel in relationships:
            by_type[rel["rel_type"]].append(rel)

        with self.session_manager.session() as session:
            for rel_type, rels in by_type.items():
                # Use APOC if available, otherwise standard query
                query = f"""
                UNWIND $rels as rel
                MATCH (source:Resource {{id: rel.source_id}})
                MATCH (target:Resource {{id: rel.target_id}})
                CREATE (source)-[r:{rel_type}]->(target)
                SET r = rel.rel_props
                """
                session.run(query, {"rels": rels})

    async def _generate_hub_spoke(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate hub-spoke network topology.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            params: Parameters including spoke_count, resources_per_spoke
            progress_callback: Optional progress callback

        Returns:
            Tuple of (resources_created, relationships_created)
        """
        spoke_count = params.get("spoke_count", 3)
        resources_per_spoke = params.get("resources_per_spoke", 10)

        generation_timestamp = datetime.now().isoformat()
        resources_created = 0
        relationships_created = 0

        # Create hub VNet
        hub_id = generate_synthetic_id("Microsoft.Network/virtualNetworks")
        hub = {
            "id": hub_id,
            "type": "Microsoft.Network/virtualNetworks",
            "props": {
                "id": hub_id,
                "name": "hub-vnet",
                "type": "Microsoft.Network/virtualNetworks",
                "tenant_id": tenant_id,
                "synthetic": True,
                "scale_operation_id": operation_id,
                "generation_strategy": "scenario",
                "generation_timestamp": generation_timestamp,
                "scenario_name": "hub-spoke",
                "role": "hub",
            },
        }
        await self._insert_resource_batch([hub])
        resources_created += 1

        # Create spokes and connect to hub
        spoke_resources = []
        for i in range(spoke_count):
            spoke_id = generate_synthetic_id("Microsoft.Network/virtualNetworks")
            spoke = {
                "id": spoke_id,
                "type": "Microsoft.Network/virtualNetworks",
                "props": {
                    "id": spoke_id,
                    "name": f"spoke-{i + 1}-vnet",
                    "type": "Microsoft.Network/virtualNetworks",
                    "tenant_id": tenant_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "scenario",
                    "generation_timestamp": generation_timestamp,
                    "scenario_name": "hub-spoke",
                    "role": "spoke",
                    "spoke_index": i,
                },
            }
            spoke_resources.append(spoke)

            # Add resources to spoke
            for j in range(resources_per_spoke):
                resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
                resource = {
                    "id": resource_id,
                    "type": "Microsoft.Compute/virtualMachines",
                    "props": {
                        "id": resource_id,
                        "name": f"spoke-{i + 1}-vm-{j + 1}",
                        "type": "Microsoft.Compute/virtualMachines",
                        "tenant_id": tenant_id,
                        "synthetic": True,
                        "scale_operation_id": operation_id,
                        "generation_strategy": "scenario",
                        "generation_timestamp": generation_timestamp,
                        "scenario_name": "hub-spoke",
                        "spoke_index": i,
                    },
                }
                spoke_resources.append(resource)

        await self._insert_resource_batch(spoke_resources)
        resources_created += len(spoke_resources)

        # Create hub-spoke relationships
        hub_spoke_rels = []
        for spoke in spoke_resources:
            if spoke["type"] == "Microsoft.Network/virtualNetworks":
                hub_spoke_rels.append(
                    {
                        "source_id": hub_id,
                        "target_id": spoke["id"],
                        "rel_type": "CONNECTED_TO",
                        "rel_props": {"connection_type": "peering"},
                    }
                )

        await self._insert_relationship_batch(hub_spoke_rels)
        relationships_created += len(hub_spoke_rels)

        return resources_created, relationships_created

    async def _generate_multi_region(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate multi-region deployment topology.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            params: Parameters including region_count, resources_per_region
            progress_callback: Optional progress callback

        Returns:
            Tuple of (resources_created, relationships_created)
        """
        region_count = params.get("region_count", 3)
        resources_per_region = params.get("resources_per_region", 20)
        regions = ["eastus", "westus", "centralus", "northeurope", "westeurope"]

        generation_timestamp = datetime.now().isoformat()
        resources_created = 0
        relationships_created = 0

        all_resources = []
        for i in range(min(region_count, len(regions))):
            region = regions[i]

            for j in range(resources_per_region):
                resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
                resource = {
                    "id": resource_id,
                    "type": "Microsoft.Compute/virtualMachines",
                    "props": {
                        "id": resource_id,
                        "name": f"{region}-vm-{j + 1}",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": region,
                        "tenant_id": tenant_id,
                        "synthetic": True,
                        "scale_operation_id": operation_id,
                        "generation_strategy": "scenario",
                        "generation_timestamp": generation_timestamp,
                        "scenario_name": "multi-region",
                        "region": region,
                    },
                }
                all_resources.append(resource)

        await self._insert_resource_batch(all_resources)
        resources_created += len(all_resources)

        return resources_created, relationships_created

    async def _generate_dev_test_prod(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate dev/test/prod environment topology.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            params: Parameters including resources_per_env
            progress_callback: Optional progress callback

        Returns:
            Tuple of (resources_created, relationships_created)
        """
        resources_per_env = params.get("resources_per_env", 15)
        environments = ["dev", "test", "prod"]

        generation_timestamp = datetime.now().isoformat()
        resources_created = 0
        relationships_created = 0

        all_resources = []
        for env in environments:
            for j in range(resources_per_env):
                resource_id = generate_synthetic_id("Microsoft.Compute/virtualMachines")
                resource = {
                    "id": resource_id,
                    "type": "Microsoft.Compute/virtualMachines",
                    "props": {
                        "id": resource_id,
                        "name": f"{env}-vm-{j + 1}",
                        "type": "Microsoft.Compute/virtualMachines",
                        "tenant_id": tenant_id,
                        "synthetic": True,
                        "scale_operation_id": operation_id,
                        "generation_strategy": "scenario",
                        "generation_timestamp": generation_timestamp,
                        "scenario_name": "dev-test-prod",
                        "environment": env,
                    },
                }
                all_resources.append(resource)

        await self._insert_resource_batch(all_resources)
        resources_created += len(all_resources)

        return resources_created, relationships_created

    async def _generate_random_resources(
        self,
        tenant_id: str,
        operation_id: str,
        target_count: int,
        distribution: Dict[str, float],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Generate random resources based on type distribution.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            target_count: Number of resources to create
            distribution: Resource type to probability mapping
            progress_callback: Optional progress callback
            progress_start: Progress start percentage
            progress_end: Progress end percentage

        Returns:
            Number of resources created
        """
        # Normalize distribution
        total_prob = sum(distribution.values())
        normalized = {k: v / total_prob for k, v in distribution.items()}

        generation_timestamp = datetime.now().isoformat()
        resources = []

        for i in range(target_count):
            # Select resource type based on distribution
            rand_val = random.random()
            cumulative = 0.0
            selected_type = next(iter(normalized.keys()))  # Default

            for resource_type, prob in normalized.items():
                cumulative += prob
                if rand_val <= cumulative:
                    selected_type = resource_type
                    break

            resource_id = generate_synthetic_id(selected_type)
            resource = {
                "id": resource_id,
                "type": selected_type,
                "props": {
                    "id": resource_id,
                    "name": f"random-{i + 1}",
                    "type": selected_type,
                    "tenant_id": tenant_id,
                    "synthetic": True,
                    "scale_operation_id": operation_id,
                    "generation_strategy": "random",
                    "generation_timestamp": generation_timestamp,
                },
            }
            resources.append(resource)

        # Insert in batches
        created_count = 0
        for i in range(0, len(resources), self.batch_size):
            batch = resources[i : i + self.batch_size]
            await self._insert_resource_batch(batch)
            created_count += len(batch)

            if progress_callback:
                progress = progress_start + int(
                    ((i + len(batch)) / len(resources))
                    * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {created_count}/{target_count} resources...",
                    progress,
                    100,
                )

        return created_count

    async def _generate_random_relationships(
        self,
        tenant_id: str,
        operation_id: str,
        density: float,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Generate random relationships between synthetic resources.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            density: Relationship density (0.0-1.0)
            progress_callback: Optional progress callback
            progress_start: Progress start percentage
            progress_end: Progress end percentage

        Returns:
            Number of relationships created
        """
        # Get all synthetic resources for this operation
        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original
          AND r.scale_operation_id = $operation_id
          AND r.synthetic = true
        RETURN r.id as id, r.type as type
        """

        resource_ids = []
        with self.session_manager.session() as session:
            result = session.run(query, {"operation_id": operation_id})
            resource_ids = [record["id"] for record in result]

        if len(resource_ids) < 2:
            return 0

        # Calculate number of relationships to create
        max_relationships = len(resource_ids) * (len(resource_ids) - 1)
        target_relationships = int(max_relationships * density)

        relationships = []
        relationship_types = ["CONNECTED_TO", "DEPENDS_ON", "CONTAINS"]

        for _ in range(target_relationships):
            source_id = random.choice(resource_ids)
            target_id = random.choice(resource_ids)

            if source_id != target_id:
                rel_type = random.choice(relationship_types)
                relationships.append(
                    {
                        "source_id": source_id,
                        "target_id": target_id,
                        "rel_type": rel_type,
                        "rel_props": {},
                    }
                )

        # Insert in batches
        created_count = 0
        for i in range(0, len(relationships), self.batch_size):
            batch = relationships[i : i + self.batch_size]
            await self._insert_relationship_batch(batch)
            created_count += len(batch)

            if progress_callback:
                progress = progress_start + int(
                    ((i + len(batch)) / len(relationships))
                    * (progress_end - progress_start)
                )
                progress_callback(
                    f"Created {created_count} relationships...", progress, 100
                )

        return created_count

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
                self.logger.warning(f"Validation failed: {message}")
            return is_valid
