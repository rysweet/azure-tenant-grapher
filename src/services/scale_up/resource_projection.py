"""
Resource Projection Module for Scale-Up Service

This module handles the core projection logic for creating synthetic
resources and relationships in the Neo4j graph.

Responsibilities:
- Resource replication with property variations
- Relationship cloning and pattern matching
- Random resource generation
- Scenario-based topology generation (hub-spoke, multi-region, dev-test-prod)
- Batch insertion with parallel processing
"""

import asyncio
import logging
import random
from collections import defaultdict
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from src.services.scale_performance import PerformanceMonitor
from src.utils.session_manager import Neo4jSessionManager
from src.utils.synthetic_id import generate_synthetic_id

logger = logging.getLogger(__name__)


class ResourceProjection:
    """
    Handles resource and relationship projection for scale-up operations.

    This class provides methods for creating synthetic resources through
    various strategies: template replication, scenario generation, and
    random generation.
    """

    def __init__(
        self,
        session_manager: Neo4jSessionManager,
        batch_size: int = 500,
        enable_performance_monitoring: bool = True,
    ) -> None:
        """
        Initialize resource projection.

        Args:
            session_manager: Neo4j session manager
            batch_size: Default batch size for operations
            enable_performance_monitoring: Enable performance metrics collection
        """
        self.session_manager = session_manager
        self.batch_size = batch_size
        self.enable_performance_monitoring = enable_performance_monitoring
        self.logger = logger

    async def replicate_resources(
        self,
        tenant_id: str,
        operation_id: str,
        base_resources: List[Dict[str, Any]],
        target_count: int,
        adaptive_batch_size: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Replicate base resources to create synthetic copies.

        Uses round-robin selection from base resources with property variations.
        Optimized with adaptive batching and parallel batch inserts for large operations.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            base_resources: List of base resources to replicate
            target_count: Number of synthetic resources to create
            adaptive_batch_size: Batch size to use (from ProjectionSetup)
            progress_callback: Optional progress callback
            progress_start: Progress percentage at start
            progress_end: Progress percentage at end

        Returns:
            Number of resources created
        """
        monitor = (
            PerformanceMonitor(f"replicate_resources_{target_count}")
            if self.enable_performance_monitoring
            else None
        )

        if monitor:
            monitor.__enter__()

        try:
            created_count = 0
            generation_timestamp = datetime.now().isoformat()

            self.logger.info(
                f"Replicating {target_count} resources with batch size {adaptive_batch_size}"
            )

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

                if len(current_batch) >= adaptive_batch_size:
                    batches.append(current_batch)
                    current_batch = []

            # Add remaining
            if current_batch:
                batches.append(current_batch)

            # For very large operations (>10k resources), process batches in parallel
            # with controlled concurrency to avoid overwhelming Neo4j
            if target_count > 10000 and len(batches) > 10:
                created_count = await self._insert_batches_parallel(
                    batches,
                    target_count,
                    progress_callback,
                    progress_start,
                    progress_end,
                    monitor,
                )
            else:
                # Standard sequential processing for smaller operations
                for batch_idx, batch in enumerate(batches):
                    await self._insert_resource_batch(batch)
                    created_count += len(batch)

                    if monitor:
                        monitor.record_items(len(batch))
                        monitor.record_batch(len(batch))

                    # Update progress
                    if progress_callback:
                        progress = progress_start + int(
                            ((batch_idx + 1) / len(batches))
                            * (progress_end - progress_start)
                        )
                        progress_callback(
                            f"Created {created_count}/{target_count} resources...",
                            progress,
                            100,
                        )

            self.logger.info(
                f"Created {created_count} synthetic resources in {len(batches)} batches "
                f"(batch_size={adaptive_batch_size})"
            )

            if monitor:
                monitor.add_metadata("adaptive_batch_size", adaptive_batch_size)
                monitor.add_metadata("num_batches", len(batches))

            return created_count

        finally:
            if monitor:
                monitor.__exit__(None, None, None)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(str(monitor.get_metrics()))

    async def clone_relationships(
        self,
        tenant_id: str,
        operation_id: str,
        base_resources: List[Dict[str, Any]],
        adaptive_batch_size: int,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
        progress_start: int = 0,
        progress_end: int = 100,
    ) -> int:
        """
        Clone relationships between synthetic resources.

        Finds relationship patterns between base resources and replicates
        them for synthetic resources. Optimized with adaptive batching
        and parallel processing for large graphs.

        Args:
            tenant_id: Azure tenant ID
            operation_id: Scale operation ID
            base_resources: List of base resources
            adaptive_batch_size: Batch size to use
            progress_callback: Optional progress callback
            progress_start: Progress percentage at start
            progress_end: Progress percentage at end

        Returns:
            Number of relationships created
        """
        monitor = (
            PerformanceMonitor(f"clone_relationships_{len(base_resources)}")
            if self.enable_performance_monitoring
            else None
        )

        if monitor:
            monitor.__enter__()

        try:
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

            # Estimate total relationships
            total_synthetic_resources = sum(
                len(ids) for ids in base_to_synthetic.values()
            )
            estimated_relationships = len(patterns) * (
                total_synthetic_resources // len(base_resources)
            )

            self.logger.info(
                f"Cloning {len(patterns)} patterns for ~{estimated_relationships} relationships "
                f"(batch_size={adaptive_batch_size})"
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

                        if len(current_batch) >= adaptive_batch_size:
                            batches.append(current_batch)
                            current_batch = []

            if current_batch:
                batches.append(current_batch)

            # For large operations, use parallel batch inserts
            if estimated_relationships > 10000 and len(batches) > 10:
                relationships_created = await self._insert_relationship_batches_parallel(
                    batches, progress_callback, progress_start, progress_end, monitor
                )
            else:
                # Standard sequential processing
                for batch_idx, batch in enumerate(batches):
                    await self._insert_relationship_batch(batch)
                    relationships_created += len(batch)

                    if monitor:
                        monitor.record_items(len(batch))
                        monitor.record_batch(len(batch))

                    if progress_callback:
                        progress = progress_start + int(
                            ((batch_idx + 1) / len(batches))
                            * (progress_end - progress_start)
                        )
                        progress_callback(
                            f"Created {relationships_created} relationships...",
                            progress,
                            100,
                        )

            self.logger.info(
                f"Created {relationships_created} relationships in {len(batches)} batches "
                f"(batch_size={adaptive_batch_size})"
            )

            if monitor:
                monitor.add_metadata("adaptive_batch_size", adaptive_batch_size)
                monitor.add_metadata("num_batches", len(batches))
                monitor.add_metadata("num_patterns", len(patterns))

            return relationships_created

        finally:
            if monitor:
                monitor.__exit__(None, None, None)
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(str(monitor.get_metrics()))

    async def generate_random_resources(
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

    async def generate_random_relationships(
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

    async def generate_hub_spoke(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate hub-spoke network topology.

        Creates a central hub VNet with multiple spoke VNets connected to it,
        with resources distributed across the spokes.

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

    async def generate_multi_region(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate multi-region deployment topology.

        Creates resources distributed across multiple Azure regions.

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

    async def generate_dev_test_prod(
        self,
        tenant_id: str,
        operation_id: str,
        params: Dict[str, Any],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Tuple[int, int]:
        """
        Generate dev/test/prod environment topology.

        Creates separate resource sets for development, testing, and production
        environments.

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

    # =========================================================================
    # Private Helper Methods
    # =========================================================================

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
                query = f"""
                UNWIND $rels as rel
                MATCH (source:Resource {{id: rel.source_id}})
                MATCH (target:Resource {{id: rel.target_id}})
                CREATE (source)-[r:{rel_type}]->(target)
                SET r = rel.rel_props
                """
                session.run(query, {"rels": rels})

    async def _insert_batches_parallel(
        self,
        batches: List[List[Dict[str, Any]]],
        target_count: int,
        progress_callback: Optional[Callable[[str, int, int], None]],
        progress_start: int,
        progress_end: int,
        monitor: Optional[PerformanceMonitor] = None,
    ) -> int:
        """
        Insert resource batches in parallel with controlled concurrency.

        Uses asyncio.gather with semaphore to limit concurrent database operations.

        Args:
            batches: List of resource batches
            target_count: Total target count (for progress reporting)
            progress_callback: Optional progress callback
            progress_start: Progress start percentage
            progress_end: Progress end percentage
            monitor: Optional performance monitor

        Returns:
            Total number of resources created
        """
        # Limit concurrent batch inserts to avoid overwhelming Neo4j
        max_concurrent_batches = min(5, len(batches) // 10)
        semaphore = asyncio.Semaphore(max_concurrent_batches)
        created_count = 0
        completed_batches = 0

        async def insert_with_semaphore(batch: List[Dict[str, Any]]) -> int:
            """Insert batch with semaphore control."""
            nonlocal created_count, completed_batches

            async with semaphore:
                await self._insert_resource_batch(batch)
                count = len(batch)

                # Thread-safe counter update
                created_count += count
                completed_batches += 1

                if monitor:
                    monitor.record_items(count)
                    monitor.record_batch(count)

                # Update progress
                if progress_callback:
                    progress = progress_start + int(
                        (completed_batches / len(batches))
                        * (progress_end - progress_start)
                    )
                    progress_callback(
                        f"Created {created_count}/{target_count} resources...",
                        progress,
                        100,
                    )

                return count

        # Execute all batch inserts with limited concurrency
        self.logger.info(
            f"Inserting {len(batches)} batches in parallel "
            f"(max_concurrent={max_concurrent_batches})"
        )

        await asyncio.gather(*[insert_with_semaphore(batch) for batch in batches])

        return created_count

    async def _insert_relationship_batches_parallel(
        self,
        batches: List[List[Dict[str, Any]]],
        progress_callback: Optional[Callable[[str, int, int], None]],
        progress_start: int,
        progress_end: int,
        monitor: Optional[PerformanceMonitor] = None,
    ) -> int:
        """
        Insert relationship batches in parallel with controlled concurrency.

        Args:
            batches: List of relationship batches
            progress_callback: Optional progress callback
            progress_start: Progress start percentage
            progress_end: Progress end percentage
            monitor: Optional performance monitor

        Returns:
            Total number of relationships created
        """
        # Limit concurrent batch inserts
        max_concurrent_batches = min(5, len(batches) // 10)
        semaphore = asyncio.Semaphore(max_concurrent_batches)
        created_count = 0
        completed_batches = 0

        async def insert_with_semaphore(batch: List[Dict[str, Any]]) -> int:
            """Insert batch with semaphore control."""
            nonlocal created_count, completed_batches

            async with semaphore:
                await self._insert_relationship_batch(batch)
                count = len(batch)

                created_count += count
                completed_batches += 1

                if monitor:
                    monitor.record_items(count)
                    monitor.record_batch(count)

                if progress_callback:
                    progress = progress_start + int(
                        (completed_batches / len(batches))
                        * (progress_end - progress_start)
                    )
                    progress_callback(
                        f"Created {created_count} relationships...", progress, 100
                    )

                return count

        self.logger.info(
            f"Inserting {len(batches)} relationship batches in parallel "
            f"(max_concurrent={max_concurrent_batches})"
        )

        await asyncio.gather(*[insert_with_semaphore(batch) for batch in batches])

        return created_count

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

        For large resource lists (>5000), chunks the query to avoid
        Neo4j performance issues with large IN clauses.

        Args:
            base_resources: List of base resources

        Returns:
            List of relationship patterns with source_id, target_id, type, props
        """
        base_ids = [r["id"] for r in base_resources]
        if not base_ids:
            return []

        # Chunk large lists to avoid Neo4j performance issues with large IN clauses
        chunk_size = 5000
        patterns = []

        if len(base_ids) <= chunk_size:
            # Small list - single query
            patterns = await self._get_relationship_patterns_chunk(base_ids)
        else:
            # Large list - chunk and combine
            self.logger.info(
                f"Chunking {len(base_ids)} base IDs into {chunk_size}-ID chunks"
            )
            for i in range(0, len(base_ids), chunk_size):
                chunk = base_ids[i : i + chunk_size]
                chunk_patterns = await self._get_relationship_patterns_chunk(chunk)
                patterns.extend(chunk_patterns)
                self.logger.debug(
                    f"Processed chunk {i // chunk_size + 1}/{(len(base_ids) + chunk_size - 1) // chunk_size}: "
                    f"{len(chunk_patterns)} patterns"
                )

        return patterns

    async def _get_relationship_patterns_chunk(
        self, base_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Extract relationship patterns for a chunk of base resources.

        Args:
            base_ids: List of base resource IDs (should be <= 5000)

        Returns:
            List of relationship patterns
        """
        query = """
        MATCH (source:Resource)-[rel]->(target:Resource)
        WHERE NOT source:Original AND NOT target:Original
          AND source.id IN $base_ids
          AND target.id IN $base_ids
        RETURN source.id as source_id,
               target.id as target_id,
               type(rel) as rel_type,
               properties(rel) as rel_props
        LIMIT 100000
        """

        patterns = []
        with self.session_manager.session() as session:
            result = session.run(query, {"base_ids": base_ids})
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
