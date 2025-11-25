#!/usr/bin/env python3
"""
Migration 012: Add Multi-Layer Graph Support

This migration adds support for multi-layer graph projections, enabling
non-destructive scale operations by maintaining multiple coexisting abstracted
projections while preserving the immutable Original graph.

Key Changes:
1. Add layer_id, layer_type, layer_created_at, layer_description properties to Resource nodes
2. Create composite unique constraint on (id, layer_id)
3. Create performance indexes for layer queries
4. Create :Layer metadata nodes
5. Migrate existing abstracted nodes to "default" layer
6. Set "default" layer as active and baseline

Usage:
    python migrations/012_add_layer_support.py [--dry-run]

Environment Variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_PASSWORD: Neo4j password (required)
"""

import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import Dict, Optional, Tuple

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class LayerSupportMigrator:
    """Migrates graph to support multi-layer projections."""

    def __init__(self, uri: str, password: str):
        """Initialize migrator with Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=("neo4j", password))
        logger.info(f"Connected to Neo4j at {uri}")

    def close(self):
        """Close Neo4j driver connection."""
        self.driver.close()

    def check_prerequisites(self) -> Tuple[bool, Optional[str]]:
        """
        Check if migration prerequisites are met.

        Returns:
            Tuple of (success, error_message)
        """
        try:
            with self.driver.session() as session:
                # Check if dual-graph architecture exists
                result = session.run(
                    """
                    MATCH (r:Resource:Original)
                    RETURN count(r) as original_count
                    """
                )
                record = result.single()
                original_count = record["original_count"] if record else 0

                # Check if abstracted nodes exist
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original
                    RETURN count(r) as abstracted_count
                    """
                )
                record = result.single()
                abstracted_count = record["abstracted_count"] if record else 0

                logger.info(
                    f"Found {original_count} Original nodes and {abstracted_count} Abstracted nodes"
                )

                if original_count == 0:
                    return (
                        False,
                        "No Original nodes found. Dual-graph architecture not initialized.",
                    )

                # Check if layer_id already exists (migration already run)
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original AND r.layer_id IS NOT NULL
                    RETURN count(r) as migrated_count
                    """
                )
                record = result.single()
                migrated_count = record["migrated_count"] if record else 0

                if migrated_count > 0:
                    return (
                        False,
                        f"Migration already partially applied. Found {migrated_count} nodes with layer_id.",
                    )

                return (True, None)

        except Exception as e:
            return (False, f"Failed to check prerequisites: {e}")

    def get_tenant_info(self) -> Dict[str, str]:
        """
        Get tenant information from existing nodes.

        Returns:
            Dict with tenant_id and subscription_ids
        """
        try:
            with self.driver.session() as session:
                # Get tenant_id from any Resource node
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original
                    RETURN r.tenant_id as tenant_id
                    LIMIT 1
                    """
                )
                record = result.single()
                tenant_id = record["tenant_id"] if record else "unknown"

                # Get all subscription IDs
                result = session.run(
                    """
                    MATCH (s:Subscription)
                    RETURN collect(s.id) as subscription_ids
                    """
                )
                record = result.single()
                subscription_ids = record["subscription_ids"] if record else []

                return {
                    "tenant_id": tenant_id,
                    "subscription_ids": subscription_ids,
                }

        except Exception as e:
            logger.warning(f"Failed to get tenant info: {e}")
            return {"tenant_id": "unknown", "subscription_ids": []}

    def add_layer_properties_to_abstracted_nodes(
        self, dry_run: bool = False
    ) -> Tuple[int, bool]:
        """
        Add layer properties to existing abstracted Resource nodes.

        Args:
            dry_run: If True, don't actually update the database

        Returns:
            Tuple of (count_updated, success)
        """
        logger.info("Step 1: Adding layer properties to abstracted nodes...")

        query = """
        MATCH (r:Resource)
        WHERE NOT r:Original AND r.layer_id IS NULL
        SET r.layer_id = 'default',
            r.layer_created_at = datetime(),
            r.layer_type = 'baseline',
            r.layer_description = '1:1 abstraction from initial scan'
        RETURN count(r) as updated_count
        """

        if dry_run:
            # Count nodes that would be updated
            count_query = """
            MATCH (r:Resource)
            WHERE NOT r:Original AND r.layer_id IS NULL
            RETURN count(r) as count
            """
            with self.driver.session() as session:
                result = session.run(count_query)
                record = result.single()
                count = record["count"] if record else 0
                logger.info(
                    f"[DRY RUN] Would add layer properties to {count} abstracted nodes"
                )
                return (count, True)

        try:
            with self.driver.session() as session:
                result = session.run(query)
                record = result.single()
                count = record["updated_count"] if record else 0
                logger.info(f"✓ Added layer properties to {count} abstracted nodes")
                return (count, True)

        except Exception as e:
            logger.error(f"✗ Failed to add layer properties: {e}")
            return (0, False)

    def create_layer_metadata_node(
        self, tenant_info: Dict[str, str], node_count: int, dry_run: bool = False
    ) -> bool:
        """
        Create the default Layer metadata node.

        Args:
            tenant_info: Tenant information
            node_count: Number of nodes in the layer
            dry_run: If True, don't actually update the database

        Returns:
            True if successful
        """
        logger.info("Step 2: Creating default Layer metadata node...")

        if dry_run:
            logger.info(
                f"[DRY RUN] Would create :Layer node for 'default' with {node_count} nodes"
            )
            return True

        query = """
        CREATE (l:Layer {
            layer_id: 'default',
            name: 'Default Baseline',
            description: '1:1 abstraction from initial scan',
            created_at: datetime(),
            created_by: 'migration-012',
            parent_layer_id: null,
            is_active: true,
            is_baseline: true,
            is_locked: false,
            tenant_id: $tenant_id,
            subscription_ids: $subscription_ids,
            node_count: $node_count,
            relationship_count: 0,
            layer_type: 'baseline',
            metadata: $metadata,
            tags: []
        })
        RETURN l.layer_id as layer_id
        """

        # Neo4j doesn't support nested maps, so serialize to JSON string
        metadata_dict = {
            "migration": "012_add_layer_support",
            "migrated_at": datetime.now(UTC).isoformat(),
        }
        metadata = json.dumps(metadata_dict)

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    tenant_id=tenant_info["tenant_id"],
                    subscription_ids=tenant_info["subscription_ids"],
                    node_count=node_count,
                    metadata=metadata,
                )
                record = result.single()
                if record:
                    logger.info(
                        f"✓ Created :Layer node with layer_id='{record['layer_id']}'"
                    )
                    return True
                else:
                    logger.error("✗ Failed to create :Layer node")
                    return False

        except Exception as e:
            logger.error(f"✗ Failed to create :Layer node: {e}")
            return False

    def update_layer_relationship_count(
        self, dry_run: bool = False
    ) -> Tuple[int, bool]:
        """
        Count relationships within the default layer and update metadata.

        Args:
            dry_run: If True, don't actually update the database

        Returns:
            Tuple of (relationship_count, success)
        """
        logger.info("Step 3: Counting relationships within default layer...")

        count_query = """
        MATCH (r1:Resource {layer_id: 'default'})
              -[rel]->
              (r2:Resource {layer_id: 'default'})
        WHERE NOT r1:Original AND NOT r2:Original
        RETURN count(rel) as rel_count
        """

        try:
            with self.driver.session() as session:
                result = session.run(count_query)
                record = result.single()
                rel_count = record["rel_count"] if record else 0
                logger.info(f"Found {rel_count} relationships within default layer")

                if dry_run:
                    logger.info(
                        f"[DRY RUN] Would set relationship_count={rel_count} on default layer"
                    )
                    return (rel_count, True)

                # Update Layer metadata
                update_query = """
                MATCH (l:Layer {layer_id: 'default'})
                SET l.relationship_count = $rel_count,
                    l.updated_at = datetime()
                RETURN l.relationship_count as updated_count
                """

                result = session.run(update_query, rel_count=rel_count)
                record = result.single()
                if record:
                    logger.info(
                        f"✓ Updated relationship_count={record['updated_count']} on default layer"
                    )
                    return (rel_count, True)
                else:
                    logger.warning("Could not update relationship_count")
                    return (rel_count, False)

        except Exception as e:
            logger.error(f"✗ Failed to count relationships: {e}")
            return (0, False)

    def create_indexes_and_constraints(self, dry_run: bool = False) -> bool:
        """
        Create indexes and constraints for layer support.

        Args:
            dry_run: If True, don't actually update the database

        Returns:
            True if successful
        """
        logger.info("Step 4: Creating indexes and constraints...")

        if dry_run:
            logger.info("[DRY RUN] Would create indexes and constraints")
            return True

        statements = [
            # Layer metadata constraint
            """
            CREATE CONSTRAINT layer_id_unique IF NOT EXISTS
            FOR (l:Layer) REQUIRE l.layer_id IS UNIQUE
            """,
            # Drop old resource_id_unique constraint if it exists
            """
            DROP CONSTRAINT resource_id_unique IF EXISTS
            """,
            # Create composite unique constraint (id, layer_id)
            """
            CREATE CONSTRAINT resource_layer_id_unique IF NOT EXISTS
            FOR (r:Resource) REQUIRE (r.id, r.layer_id) IS UNIQUE
            """,
            # Performance indexes
            """
            CREATE INDEX resource_layer_id IF NOT EXISTS
            FOR (r:Resource) ON (r.layer_id)
            """,
            """
            CREATE INDEX resource_type_layer IF NOT EXISTS
            FOR (r:Resource) ON (r.resource_type, r.layer_id)
            """,
            """
            CREATE INDEX layer_active IF NOT EXISTS
            FOR (l:Layer) ON (l.is_active)
            """,
            """
            CREATE INDEX layer_tenant IF NOT EXISTS
            FOR (l:Layer) ON (l.tenant_id)
            """,
            """
            CREATE INDEX layer_type_enum IF NOT EXISTS
            FOR (l:Layer) ON (l.layer_type)
            """,
        ]

        try:
            with self.driver.session() as session:
                for i, statement in enumerate(statements, 1):
                    try:
                        session.run(statement)
                        logger.info(
                            f"✓ Executed constraint/index statement {i}/{len(statements)}"
                        )
                    except Exception as e:
                        # Some statements may fail if constraint/index already exists
                        # Log as warning but continue
                        logger.warning(f"Statement {i} raised: {e}")

                logger.info("✓ Created indexes and constraints")
                return True

        except Exception as e:
            logger.error(f"✗ Failed to create indexes/constraints: {e}")
            return False

    def validate_migration(self) -> Tuple[bool, Dict[str, int]]:
        """
        Validate that migration was successful.

        Returns:
            Tuple of (success, stats_dict)
        """
        logger.info("Step 5: Validating migration...")

        try:
            with self.driver.session() as session:
                # Check all abstracted nodes have layer_id
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE NOT r:Original
                    RETURN count(r) as total,
                           sum(CASE WHEN r.layer_id IS NOT NULL THEN 1 ELSE 0 END) as with_layer_id
                    """
                )
                record = result.single()
                total = record["total"] if record else 0
                with_layer_id = record["with_layer_id"] if record else 0

                # Check Layer node exists
                result = session.run(
                    """
                    MATCH (l:Layer {layer_id: 'default'})
                    RETURN l.is_active as is_active,
                           l.is_baseline as is_baseline,
                           l.node_count as node_count,
                           l.relationship_count as relationship_count
                    """
                )
                record = result.single()
                if not record:
                    logger.error("✗ Default Layer node not found")
                    return (False, {})

                is_active = record["is_active"]
                is_baseline = record["is_baseline"]
                node_count = record["node_count"]
                rel_count = record["relationship_count"]

                stats = {
                    "total_abstracted_nodes": total,
                    "nodes_with_layer_id": with_layer_id,
                    "layer_node_count": node_count,
                    "layer_relationship_count": rel_count,
                }

                # Validate
                success = True
                if total != with_layer_id:
                    logger.error(
                        f"✗ Not all abstracted nodes have layer_id: {with_layer_id}/{total}"
                    )
                    success = False
                else:
                    logger.info(
                        f"✓ All {total} abstracted nodes have layer_id='default'"
                    )

                if not is_active:
                    logger.error("✗ Default layer is not active")
                    success = False
                else:
                    logger.info("✓ Default layer is active")

                if not is_baseline:
                    logger.error("✗ Default layer is not marked as baseline")
                    success = False
                else:
                    logger.info("✓ Default layer is marked as baseline")

                if total != node_count:
                    logger.warning(
                        f"⚠ Node count mismatch: {total} actual vs {node_count} in metadata"
                    )

                return (success, stats)

        except Exception as e:
            logger.error(f"✗ Validation failed: {e}")
            return (False, {})

    def migrate_all(self, dry_run: bool = False) -> bool:
        """
        Run complete migration.

        Args:
            dry_run: If True, show what would be done without updating database

        Returns:
            True if successful
        """
        if dry_run:
            logger.info("=" * 60)
            logger.info("RUNNING IN DRY RUN MODE - NO CHANGES WILL BE MADE")
            logger.info("=" * 60)

        # Check prerequisites
        logger.info("Checking prerequisites...")
        success, error = self.check_prerequisites()
        if not success:
            logger.error(f"Prerequisites not met: {error}")
            return False
        logger.info("✓ Prerequisites check passed")

        # Get tenant info
        tenant_info = self.get_tenant_info()
        logger.info(f"Tenant ID: {tenant_info['tenant_id']}")
        logger.info(f"Subscriptions: {len(tenant_info['subscription_ids'])} found")

        # Step 1: Add layer properties to abstracted nodes
        node_count, success = self.add_layer_properties_to_abstracted_nodes(dry_run)
        if not success:
            return False

        if dry_run:
            logger.info("\n" + "=" * 60)
            logger.info("DRY RUN COMPLETE - No changes were made")
            logger.info("=" * 60)
            logger.info(f"Would migrate {node_count} abstracted nodes to default layer")
            logger.info("Re-run without --dry-run to apply changes")
            return True

        # Step 2: Create Layer metadata node
        success = self.create_layer_metadata_node(tenant_info, node_count, dry_run)
        if not success:
            return False

        # Step 3: Update relationship count
        rel_count, success = self.update_layer_relationship_count(dry_run)
        if not success:
            logger.warning("Failed to update relationship count, continuing...")

        # Step 4: Create indexes and constraints
        success = self.create_indexes_and_constraints(dry_run)
        if not success:
            return False

        # Step 5: Validate migration
        success, stats = self.validate_migration()

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Status: {'✓ SUCCESS' if success else '✗ FAILED'}")
        logger.info(f"Abstracted nodes migrated: {stats.get('nodes_with_layer_id', 0)}")
        logger.info(f"Layer node count: {stats.get('layer_node_count', 0)}")
        logger.info(
            f"Layer relationship count: {stats.get('layer_relationship_count', 0)}"
        )
        logger.info("Active layer: default")
        logger.info("=" * 60)

        return success


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate graph to support multi-layer projections"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without actually updating the database",
    )
    args = parser.parse_args()

    # Get Neo4j connection details from environment
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_password = os.getenv("NEO4J_PASSWORD")

    if not neo4j_password:
        logger.error("NEO4J_PASSWORD environment variable is required")
        sys.exit(1)

    # Run migration
    migrator = LayerSupportMigrator(neo4j_uri, neo4j_password)

    try:
        success = migrator.migrate_all(dry_run=args.dry_run)
        sys.exit(0 if success else 1)

    finally:
        migrator.close()


if __name__ == "__main__":
    main()
