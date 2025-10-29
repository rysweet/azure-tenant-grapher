#!/usr/bin/env python3
"""
Migration script to populate addressSpace property for existing VNet nodes.

This script addresses the issue where VNets with large properties (>5000 chars)
had their addressSpace truncated by the Neo4j Python driver. It extracts the
addressSpace from the properties JSON and stores it as a separate top-level
property for reliable access during IaC generation.

Usage:
    python migrations/migrate_vnet_address_space.py [--dry-run]

Environment Variables:
    NEO4J_URI: Neo4j connection URI (default: bolt://localhost:7687)
    NEO4J_PASSWORD: Neo4j password (required)
"""

import json
import logging
import os
import sys
from typing import Dict, List, Tuple

from neo4j import GraphDatabase

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class VNetAddressSpaceMigrator:
    """Migrates VNet nodes to include addressSpace as top-level property."""

    def __init__(self, uri: str, password: str):
        """Initialize migrator with Neo4j connection."""
        self.driver = GraphDatabase.driver(uri, auth=("neo4j", password))
        logger.info(f"Connected to Neo4j at {uri}")

    def close(self):
        """Close Neo4j driver connection."""
        self.driver.close()

    def _extract_address_space(self, properties_value: str) -> List[str]:
        """
        Extract addressSpace.addressPrefixes from properties JSON.

        Args:
            properties_value: JSON string or dict containing VNet properties

        Returns:
            List of address prefixes, or empty list if extraction fails
        """
        try:
            # Handle both dict and JSON string
            if isinstance(properties_value, dict):
                props_dict = properties_value
            elif isinstance(properties_value, str):
                # Check if truncated
                if properties_value.endswith("...(truncated)"):
                    logger.warning("Properties JSON is truncated, extraction may fail")
                    # Try to parse what we have
                    truncated_json = properties_value[:-15]  # Remove "...(truncated)"
                    # Attempt to extract addressSpace from partial JSON
                    # Look for addressSpace pattern in the string
                    if '"addressSpace"' in truncated_json:
                        # Try to extract just the addressSpace section
                        import re

                        pattern = r'"addressSpace"\s*:\s*\{[^}]*"addressPrefixes"\s*:\s*(\[[^\]]*\])'
                        match = re.search(pattern, truncated_json)
                        if match:
                            address_prefixes_json = match.group(1)
                            return json.loads(address_prefixes_json)
                    return []

                # Normal JSON parsing
                props_dict = json.loads(properties_value)
            else:
                logger.warning(f"Unexpected properties type: {type(properties_value)}")
                return []

            # Extract addressSpace.addressPrefixes
            address_space = props_dict.get("addressSpace", {})
            address_prefixes = address_space.get("addressPrefixes", [])

            return address_prefixes if address_prefixes else []

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse properties JSON: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error extracting addressSpace: {e}")
            return []

    def find_vnets_needing_migration(self) -> List[Dict]:
        """
        Find all VNet nodes that don't have addressSpace as top-level property.

        Returns:
            List of VNet node records with id, name, and properties
        """
        query = """
        MATCH (r:Resource)
        WHERE r.type = 'Microsoft.Network/virtualNetworks'
          AND r.addressSpace IS NULL
        RETURN r.id AS id, r.name AS name, r.properties AS properties
        ORDER BY r.name
        """

        with self.driver.session() as session:
            result = session.run(query)
            vnets = [dict(record) for record in result]

        logger.info(f"Found {len(vnets)} VNets needing addressSpace migration")
        return vnets

    def migrate_vnet(
        self, vnet_id: str, address_space: List[str], dry_run: bool = False
    ) -> bool:
        """
        Update VNet node with addressSpace as top-level property.

        Args:
            vnet_id: VNet resource ID
            address_space: List of address prefixes
            dry_run: If True, don't actually update the database

        Returns:
            True if update succeeded (or would succeed in dry-run), False otherwise
        """
        if dry_run:
            logger.info(
                f"[DRY RUN] Would set addressSpace={json.dumps(address_space)} for {vnet_id}"
            )
            return True

        query = """
        MATCH (r:Resource {id: $vnet_id})
        SET r.addressSpace = $address_space_json
        RETURN r.id AS id, r.name AS name
        """

        try:
            with self.driver.session() as session:
                result = session.run(
                    query,
                    vnet_id=vnet_id,
                    address_space_json=json.dumps(address_space),
                )
                record = result.single()
                if record:
                    logger.info(
                        f"✓ Updated {record['name']} with addressSpace={address_space}"
                    )
                    return True
                else:
                    logger.error(f"✗ Failed to update {vnet_id} - node not found")
                    return False
        except Exception as e:
            logger.error(f"✗ Failed to update {vnet_id}: {e}")
            return False

    def migrate_all(self, dry_run: bool = False) -> Tuple[int, int, int]:
        """
        Migrate all VNets needing addressSpace property.

        Args:
            dry_run: If True, don't actually update the database

        Returns:
            Tuple of (total, successful, failed) counts
        """
        vnets = self.find_vnets_needing_migration()

        if not vnets:
            logger.info("No VNets need migration - all have addressSpace property")
            return (0, 0, 0)

        successful = 0
        failed = 0
        skipped = 0

        for vnet in vnets:
            vnet_id = vnet["id"]
            vnet_name = vnet["name"]
            properties = vnet["properties"]

            # Extract addressSpace from properties
            address_space = self._extract_address_space(properties)

            if not address_space:
                logger.warning(
                    f"⚠ Skipping {vnet_name} - could not extract addressSpace from properties"
                )
                skipped += 1
                continue

            # Migrate the VNet
            if self.migrate_vnet(vnet_id, address_space, dry_run):
                successful += 1
            else:
                failed += 1

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total VNets found:     {len(vnets)}")
        logger.info(f"Successfully migrated: {successful}")
        logger.info(f"Failed to migrate:     {failed}")
        logger.info(f"Skipped (no data):     {skipped}")
        logger.info("=" * 60)

        return (len(vnets), successful, failed)


def main():
    """Main entry point for migration script."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Migrate VNet nodes to include addressSpace property"
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
    migrator = VNetAddressSpaceMigrator(neo4j_uri, neo4j_password)

    try:
        if args.dry_run:
            logger.info("Running in DRY RUN mode - no changes will be made")

        total, successful, failed = migrator.migrate_all(dry_run=args.dry_run)

        # Exit with appropriate code
        if failed > 0:
            sys.exit(1)
        else:
            sys.exit(0)

    finally:
        migrator.close()


if __name__ == "__main__":
    main()
