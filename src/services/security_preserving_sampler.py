"""Security-aware graph abstraction with pattern preservation.

This module augments stratified sampling to preserve security-critical patterns
like attack paths, privilege escalation chains, and lateral movement opportunities.

Philosophy:
- Optional enhancement (doesn't modify base sampler)
- Pure Cypher queries (no external security libraries)
- Ruthlessly simple (~300 LOC total)
- Self-contained brick with clear interface

Public API ("studs"):
    SecurityPattern: Pattern definition dataclass
    SecurityPatternRegistry: Central pattern registry
    SecurityPreservingSampler: Augments base samples with security nodes
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from neo4j import Driver

logger = logging.getLogger(__name__)


@dataclass
class SecurityPattern:
    """Definition of a security-critical pattern to preserve.

    Security patterns are defined as Cypher queries that detect specific
    attack scenarios or security risks in Azure tenant graphs.
    """

    name: str
    """Human-readable pattern name (e.g., 'Public-to-Sensitive')"""

    cypher_query: str
    """Neo4j Cypher query to detect pattern instances"""

    min_path_length: int
    """Minimum path length to consider valid (filters noise)"""

    criticality: str
    """Pattern importance: 'HIGH', 'MEDIUM', or 'LOW'"""

    description: str
    """What this pattern represents (for documentation)"""


# ==============================================================================
# Built-in Security Patterns (5 patterns from Azure security architecture)
# ==============================================================================

PUBLIC_TO_SENSITIVE = SecurityPattern(
    name="Public-to-Sensitive",
    cypher_query="""
        MATCH path = (public:Resource)-[*1..3]->(sensitive:Resource)
        WHERE public.type CONTAINS 'PublicIP'
          AND (sensitive.type CONTAINS 'Database'
               OR sensitive.type CONTAINS 'KeyVault'
               OR sensitive.type CONTAINS 'Storage')
          AND public.tenant_id = $tenant_id
        RETURN path
    """,
    min_path_length=2,
    criticality="HIGH",
    description="Public internet access to sensitive data stores",
)

PRIVILEGE_ESCALATION = SecurityPattern(
    name="Privilege-Escalation",
    cypher_query="""
        MATCH path = (identity:Resource)-[:HAS_ROLE|HAS_PERMISSION*1..4]->(target:Resource)
        WHERE identity.type CONTAINS 'Identity'
          AND target.type CONTAINS 'Subscription'
          AND identity.tenant_id = $tenant_id
        RETURN path
    """,
    min_path_length=2,
    criticality="HIGH",
    description="Identity to high-privilege resource chains",
)

LATERAL_MOVEMENT = SecurityPattern(
    name="Lateral-Movement",
    cypher_query="""
        MATCH path = (vm1:Resource)-[:NETWORK_ACCESS|VNET_PEERING*1..3]->(vm2:Resource)
        WHERE vm1.type CONTAINS 'virtualMachines'
          AND vm2.type CONTAINS 'virtualMachines'
          AND vm1.id <> vm2.id
          AND vm1.tenant_id = $tenant_id
        RETURN path
    """,
    min_path_length=2,
    criticality="MEDIUM",
    description="VM-to-VM access paths for lateral movement",
)

OVER_PRIVILEGED = SecurityPattern(
    name="Over-Privileged-Identity",
    cypher_query="""
        MATCH (identity:Resource)-[r:HAS_ROLE]->(resource:Resource)
        WHERE identity.type CONTAINS 'Identity'
          AND r.role IN ['Owner', 'Contributor', 'Administrator']
          AND identity.tenant_id = $tenant_id
        WITH identity, COUNT(r) as privilege_count
        WHERE privilege_count > 5
        RETURN identity
    """,
    min_path_length=1,
    criticality="MEDIUM",
    description="Identities with excessive privileges",
)

MISSING_CONTROLS = SecurityPattern(
    name="Missing-Security-Controls",
    cypher_query="""
        MATCH (vm:Resource)
        WHERE vm.type CONTAINS 'virtualMachines'
          AND vm.tenant_id = $tenant_id
          AND NOT EXISTS {
              MATCH (vm)-[:PROTECTED_BY]->(nsg:Resource)
              WHERE nsg.type CONTAINS 'networkSecurityGroups'
          }
        RETURN vm
    """,
    min_path_length=1,
    criticality="HIGH",
    description="Resources without required security controls",
)


class SecurityPatternRegistry:
    """Central registry of security patterns.

    Provides access to built-in patterns and supports filtering by criticality.
    Extensible for custom patterns (future enhancement).
    """

    def __init__(self) -> None:
        """Initialize registry with built-in patterns."""
        self.patterns: Dict[str, SecurityPattern] = {
            "public_to_sensitive": PUBLIC_TO_SENSITIVE,
            "privilege_escalation": PRIVILEGE_ESCALATION,
            "lateral_movement": LATERAL_MOVEMENT,
            "over_privileged": OVER_PRIVILEGED,
            "missing_controls": MISSING_CONTROLS,
        }

    def get_pattern(self, name: str) -> SecurityPattern:
        """Retrieve pattern by name.

        Args:
            name: Pattern identifier (e.g., 'public_to_sensitive')

        Returns:
            SecurityPattern instance

        Raises:
            KeyError: If pattern not found
        """
        return self.patterns[name]

    def get_all_patterns(self) -> List[SecurityPattern]:
        """Get all registered patterns.

        Returns:
            List of all SecurityPattern instances
        """
        return list(self.patterns.values())

    def filter_by_criticality(self, level: str) -> List[SecurityPattern]:
        """Get patterns of specific criticality level.

        Args:
            level: Criticality level ('HIGH', 'MEDIUM', or 'LOW')

        Returns:
            List of patterns matching the criticality level
        """
        return [p for p in self.patterns.values() if p.criticality == level]


class SecurityPreservingSampler:
    """Augments base sample to preserve security-critical patterns.

    Takes stratified sample from base sampler and adds nodes needed to
    maintain security patterns like attack paths and privilege chains.

    This is an OPTIONAL enhancement - base sampler is never modified.
    """

    def __init__(self, driver: Driver, pattern_registry: SecurityPatternRegistry):
        """Initialize sampler with Neo4j driver and pattern registry.

        Args:
            driver: Neo4j database driver
            pattern_registry: Registry of security patterns to preserve
        """
        self.driver = driver
        self.registry = pattern_registry

    def augment_sample(
        self,
        tenant_id: str,
        base_sample_ids: Set[str],
        patterns_to_preserve: Optional[List[str]] = None,
        max_additional_nodes: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Augment base sample to preserve security patterns.

        Args:
            tenant_id: Tenant being sampled
            base_sample_ids: Node IDs from base stratified sample
            patterns_to_preserve: Pattern names to preserve (default: all HIGH)
            max_additional_nodes: Maximum nodes to add (default: 50% of base)

        Returns:
            Dictionary with:
            - augmented_sample_ids: Set[str] - All node IDs (base + added)
            - added_node_count: int - Nodes added for security
            - preserved_patterns: Dict[str, int] - Pattern -> instance count
            - coverage_metrics: Dict[str, float] - Pattern -> coverage %
        """
        # Default to HIGH criticality patterns
        if patterns_to_preserve is None:
            patterns = self.registry.filter_by_criticality("HIGH")
        else:
            patterns = [
                self.registry.get_pattern(name) for name in patterns_to_preserve
            ]

        # Default max additions: 50% of base sample
        if max_additional_nodes is None:
            max_additional_nodes = len(base_sample_ids) // 2

        logger.info(
            f"Security augmentation: {len(patterns)} patterns, "
            f"max {max_additional_nodes} additional nodes"
        )

        # Start with base sample
        augmented_ids = base_sample_ids.copy()
        additions_remaining = max_additional_nodes

        preserved_patterns = {}
        coverage_metrics = {}

        # Process each pattern
        for pattern in patterns:
            # Detect pattern instances in full graph
            pattern_instances = self._detect_pattern_instances(tenant_id, pattern)

            total_instances = len(pattern_instances)
            logger.info(f"Pattern '{pattern.name}': {total_instances} instances found")

            if total_instances == 0:
                preserved_patterns[pattern.name] = 0
                coverage_metrics[pattern.name] = 100.0  # No instances to preserve
                continue

            # Calculate current coverage
            preserved_before, _ = self._calculate_coverage(
                pattern_instances, augmented_ids
            )

            # Augment sample to preserve more instances
            if additions_remaining > 0:
                new_nodes = self._augment_for_pattern(
                    pattern, pattern_instances, augmented_ids, additions_remaining
                )
                augmented_ids.update(new_nodes)
                additions_remaining -= len(new_nodes)

            # Calculate final coverage
            preserved_after, coverage_pct = self._calculate_coverage(
                pattern_instances, augmented_ids
            )

            preserved_patterns[pattern.name] = preserved_after
            coverage_metrics[pattern.name] = coverage_pct

            logger.info(
                f"Pattern '{pattern.name}': {preserved_after}/{total_instances} "
                f"instances preserved ({coverage_pct:.1f}% coverage)"
            )

        added_node_count = len(augmented_ids) - len(base_sample_ids)

        logger.info(
            f"Security augmentation complete: added {added_node_count} nodes "
            f"({added_node_count / len(base_sample_ids) * 100:.1f}% overhead)"
        )

        return {
            "augmented_sample_ids": augmented_ids,
            "added_node_count": added_node_count,
            "preserved_patterns": preserved_patterns,
            "coverage_metrics": coverage_metrics,
        }

    def _detect_pattern_instances(
        self, tenant_id: str, pattern: SecurityPattern
    ) -> List[List[str]]:
        """Detect all instances of pattern in full tenant graph.

        Args:
            tenant_id: Tenant to search
            pattern: Security pattern to detect

        Returns:
            List of paths, where each path is a list of node IDs
        """
        with self.driver.session() as session:
            try:
                result = session.run(pattern.cypher_query, tenant_id=tenant_id)  # type: ignore[arg-type]

                paths = []
                for record in result:
                    # Handle both path and single node returns
                    if "path" in record:
                        path_obj = record["path"]
                        node_ids = [node["id"] for node in path_obj.nodes]
                    else:
                        # Single node pattern (e.g., over-privileged identities)
                        node = record[0]  # First value in record
                        node_ids = [node["id"]]

                    # Filter by minimum path length
                    if len(node_ids) >= pattern.min_path_length:
                        paths.append(node_ids)

                return paths

            except Exception as e:
                logger.warning(f"Pattern detection failed for '{pattern.name}': {e}")
                return []

    def _calculate_coverage(
        self, pattern_instances: List[List[str]], sample_ids: Set[str]
    ) -> tuple[int, float]:
        """Calculate how many pattern instances are preserved in sample.

        An instance is preserved if ALL nodes in its path are in the sample.

        Args:
            pattern_instances: List of paths (each path is list of node IDs)
            sample_ids: Node IDs in current sample

        Returns:
            Tuple of (preserved_count, coverage_percentage)
        """
        if not pattern_instances:
            return 0, 100.0

        preserved = 0
        for instance in pattern_instances:
            if all(node_id in sample_ids for node_id in instance):
                preserved += 1

        total = len(pattern_instances)
        coverage = (preserved / total * 100) if total > 0 else 100.0

        return preserved, coverage

    def _augment_for_pattern(
        self,
        pattern: SecurityPattern,
        pattern_instances: List[List[str]],
        sample_ids: Set[str],
        max_additions: int,
    ) -> Set[str]:
        """Add nodes to sample to preserve pattern instances.

        Strategy:
        - Sort instances by path length (shorter paths first)
        - For each incomplete instance, add missing nodes
        - Stop when max_additions reached

        Args:
            pattern: Security pattern being preserved
            pattern_instances: All instances of pattern
            sample_ids: Current sample node IDs
            max_additions: Maximum nodes to add

        Returns:
            Set of node IDs to add to sample
        """
        additions = set()

        # Sort by path length (preserve shorter paths first - easier to complete)
        sorted_instances = sorted(pattern_instances, key=len)

        for instance in sorted_instances:
            if len(additions) >= max_additions:
                break

            # Check if instance already complete
            missing = [nid for nid in instance if nid not in sample_ids]

            if missing:
                # Add missing nodes (up to max_additions limit)
                for node_id in missing:
                    if len(additions) < max_additions:
                        additions.add(node_id)
                    else:
                        break

        return additions


__all__ = [
    "LATERAL_MOVEMENT",
    "MISSING_CONTROLS",
    "OVER_PRIVILEGED",
    "PRIVILEGE_ESCALATION",
    "PUBLIC_TO_SENSITIVE",
    "SecurityPattern",
    "SecurityPatternRegistry",
    "SecurityPreservingSampler",
]
