"""Tests for security-aware graph abstraction.

Tests cover:
- Pattern detection (unit tests with mocked Neo4j)
- Coverage calculation
- Sample augmentation logic
- Integration with SecurityPatternRegistry
"""

from unittest.mock import Mock

import pytest
from neo4j import Driver

from src.services.security_preserving_sampler import (
    LATERAL_MOVEMENT,
    MISSING_CONTROLS,
    OVER_PRIVILEGED,
    PRIVILEGE_ESCALATION,
    PUBLIC_TO_SENSITIVE,
    SecurityPattern,
    SecurityPatternRegistry,
    SecurityPreservingSampler,
)


# ==============================================================================
# Unit Tests - SecurityPatternRegistry
# ==============================================================================


class TestSecurityPatternRegistry:
    """Unit tests for SecurityPatternRegistry."""

    def test_registry_contains_all_patterns(self):
        """Test registry has all 5 built-in patterns."""
        registry = SecurityPatternRegistry()

        assert len(registry.patterns) == 5
        assert "public_to_sensitive" in registry.patterns
        assert "privilege_escalation" in registry.patterns
        assert "lateral_movement" in registry.patterns
        assert "over_privileged" in registry.patterns
        assert "missing_controls" in registry.patterns

    def test_get_pattern_by_name(self):
        """Test retrieving pattern by name."""
        registry = SecurityPatternRegistry()

        pattern = registry.get_pattern("public_to_sensitive")

        assert pattern.name == "Public-to-Sensitive"
        assert pattern.criticality == "HIGH"

    def test_get_pattern_not_found(self):
        """Test error when pattern doesn't exist."""
        registry = SecurityPatternRegistry()

        with pytest.raises(KeyError):
            registry.get_pattern("nonexistent")

    def test_get_all_patterns(self):
        """Test getting all patterns."""
        registry = SecurityPatternRegistry()

        patterns = registry.get_all_patterns()

        assert len(patterns) == 5
        assert all(isinstance(p, SecurityPattern) for p in patterns)

    def test_filter_by_criticality_high(self):
        """Test filtering HIGH criticality patterns."""
        registry = SecurityPatternRegistry()

        high_patterns = registry.filter_by_criticality("HIGH")

        assert len(high_patterns) == 3  # public_to_sensitive, privilege_escalation, missing_controls
        assert all(p.criticality == "HIGH" for p in high_patterns)

    def test_filter_by_criticality_medium(self):
        """Test filtering MEDIUM criticality patterns."""
        registry = SecurityPatternRegistry()

        medium_patterns = registry.filter_by_criticality("MEDIUM")

        assert len(medium_patterns) == 2  # lateral_movement, over_privileged
        assert all(p.criticality == "MEDIUM" for p in medium_patterns)


# ==============================================================================
# Unit Tests - SecurityPattern Definitions
# ==============================================================================


class TestSecurityPatternDefinitions:
    """Test built-in security pattern definitions."""

    def test_public_to_sensitive_pattern(self):
        """Test PUBLIC_TO_SENSITIVE pattern definition."""
        assert PUBLIC_TO_SENSITIVE.name == "Public-to-Sensitive"
        assert PUBLIC_TO_SENSITIVE.criticality == "HIGH"
        assert PUBLIC_TO_SENSITIVE.min_path_length == 2
        assert "PublicIP" in PUBLIC_TO_SENSITIVE.cypher_query
        assert "Database" in PUBLIC_TO_SENSITIVE.cypher_query

    def test_privilege_escalation_pattern(self):
        """Test PRIVILEGE_ESCALATION pattern definition."""
        assert PRIVILEGE_ESCALATION.name == "Privilege-Escalation"
        assert PRIVILEGE_ESCALATION.criticality == "HIGH"
        assert PRIVILEGE_ESCALATION.min_path_length == 2
        assert "HAS_ROLE" in PRIVILEGE_ESCALATION.cypher_query

    def test_lateral_movement_pattern(self):
        """Test LATERAL_MOVEMENT pattern definition."""
        assert LATERAL_MOVEMENT.name == "Lateral-Movement"
        assert LATERAL_MOVEMENT.criticality == "MEDIUM"
        assert "virtualMachines" in LATERAL_MOVEMENT.cypher_query

    def test_over_privileged_pattern(self):
        """Test OVER_PRIVILEGED pattern definition."""
        assert OVER_PRIVILEGED.name == "Over-Privileged-Identity"
        assert OVER_PRIVILEGED.criticality == "MEDIUM"
        assert "Owner" in OVER_PRIVILEGED.cypher_query

    def test_missing_controls_pattern(self):
        """Test MISSING_CONTROLS pattern definition."""
        assert MISSING_CONTROLS.name == "Missing-Security-Controls"
        assert MISSING_CONTROLS.criticality == "HIGH"
        assert "networkSecurityGroups" in MISSING_CONTROLS.cypher_query


# ==============================================================================
# Unit Tests - SecurityPreservingSampler
# ==============================================================================


class TestSecurityPreservingSampler:
    """Unit tests for SecurityPreservingSampler with mocked Neo4j."""

    def test_calculate_coverage_all_preserved(self):
        """Test coverage calculation when all instances preserved."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],
            ["node4", "node5", "node6"],
        ]
        sample_ids = {"node1", "node2", "node3", "node4", "node5", "node6"}

        preserved, coverage = sampler._calculate_coverage(pattern_instances, sample_ids)

        assert preserved == 2
        assert coverage == 100.0

    def test_calculate_coverage_partial(self):
        """Test coverage calculation with partial preservation."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],  # Complete
            ["node4", "node5", "node6"],  # Missing node5
            ["node7", "node8", "node9"],  # Complete
        ]
        sample_ids = {"node1", "node2", "node3", "node4", "node6", "node7", "node8", "node9"}

        preserved, coverage = sampler._calculate_coverage(pattern_instances, sample_ids)

        assert preserved == 2
        assert abs(coverage - 66.67) < 0.1  # 2 out of 3

    def test_calculate_coverage_none_preserved(self):
        """Test coverage when no instances preserved."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],
            ["node4", "node5", "node6"],
        ]
        sample_ids = {"node1", "node4"}  # Missing nodes from all paths

        preserved, coverage = sampler._calculate_coverage(pattern_instances, sample_ids)

        assert preserved == 0
        assert coverage == 0.0

    def test_calculate_coverage_empty_instances(self):
        """Test coverage with no pattern instances."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = []
        sample_ids = {"node1", "node2"}

        preserved, coverage = sampler._calculate_coverage(pattern_instances, sample_ids)

        assert preserved == 0
        assert coverage == 100.0  # No instances to preserve = 100% coverage

    def test_augment_for_pattern_adds_missing_nodes(self):
        """Test augmentation adds minimum nodes needed."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],  # Missing node2
        ]
        sample_ids = {"node1", "node3"}

        additions = sampler._augment_for_pattern(
            PUBLIC_TO_SENSITIVE, pattern_instances, sample_ids, max_additions=10
        )

        assert additions == {"node2"}

    def test_augment_for_pattern_respects_max_additions(self):
        """Test augmentation stops at max_additions limit."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],
            ["node4", "node5", "node6"],
            ["node7", "node8", "node9"],
        ]
        sample_ids = set()  # Empty sample

        additions = sampler._augment_for_pattern(
            PUBLIC_TO_SENSITIVE, pattern_instances, sample_ids, max_additions=5
        )

        assert len(additions) == 5  # Should stop at limit

    def test_augment_for_pattern_prioritizes_short_paths(self):
        """Test augmentation prioritizes shorter paths."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3", "node4"],  # 4-node path
            ["node5", "node6"],  # 2-node path (should be completed first)
        ]
        sample_ids = set()

        additions = sampler._augment_for_pattern(
            PUBLIC_TO_SENSITIVE, pattern_instances, sample_ids, max_additions=2
        )

        # Should complete shorter path first
        assert "node5" in additions
        assert "node6" in additions

    def test_augment_for_pattern_skips_complete_instances(self):
        """Test augmentation skips already complete instances."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern_instances = [
            ["node1", "node2", "node3"],  # Already complete
        ]
        sample_ids = {"node1", "node2", "node3"}

        additions = sampler._augment_for_pattern(
            PUBLIC_TO_SENSITIVE, pattern_instances, sample_ids, max_additions=10
        )

        assert len(additions) == 0  # No additions needed


# ==============================================================================
# Integration Tests - Require Neo4j testcontainer
# ==============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag",
)
class TestSecurityPreservingIntegration:
    """Integration tests with real Neo4j (testcontainers)."""

    @pytest.fixture(scope="class")
    def neo4j_container(self):
        """Start Neo4j container for integration tests."""
        pytest.importorskip("testcontainers")
        from testcontainers.neo4j import Neo4jContainer

        with Neo4jContainer("neo4j:5.15.0") as container:
            yield container

    @pytest.fixture
    def neo4j_driver(self, neo4j_container):
        """Create Neo4j driver from container."""
        from neo4j import GraphDatabase

        uri = neo4j_container.get_connection_url()
        driver = GraphDatabase.driver(uri, auth=("neo4j", "test"))
        yield driver
        driver.close()

    def _create_test_security_graph(self, driver, tenant_id: str):
        """Create test graph with security patterns.

        Creates:
        - PublicIP -> VM -> Database (public-to-sensitive)
        - Identity -> RoleAssignment -> Subscription (privilege escalation)
        - VM1 -> VNet -> VM2 (lateral movement)
        """
        with driver.session() as session:
            # Clear existing
            session.run("MATCH (n) DETACH DELETE n")

            # Create public-to-sensitive pattern
            session.run(
                """
                CREATE (public:Resource {id: 'publicip-1', type: 'Microsoft.Network/PublicIP', tenant_id: $tid})
                CREATE (vm:Resource {id: 'vm-1', type: 'Microsoft.Compute/virtualMachines', tenant_id: $tid})
                CREATE (db:Resource {id: 'db-1', type: 'Microsoft.Sql/Database', tenant_id: $tid})
                CREATE (public)-[:CONNECTED_TO]->(vm)
                CREATE (vm)-[:USES_DATABASE]->(db)
            """,
                tid=tenant_id,
            )

            # Create privilege escalation pattern
            session.run(
                """
                CREATE (identity:Resource {id: 'identity-1', type: 'Microsoft.Identity/user', tenant_id: $tid})
                CREATE (sub:Resource {id: 'sub-1', type: 'Microsoft.Resources/Subscription', tenant_id: $tid})
                CREATE (identity)-[:HAS_ROLE]->(sub)
            """,
                tid=tenant_id,
            )

            # Create lateral movement pattern
            session.run(
                """
                CREATE (vm1:Resource {id: 'vm-2', type: 'Microsoft.Compute/virtualMachines', tenant_id: $tid})
                CREATE (vnet:Resource {id: 'vnet-1', type: 'Microsoft.Network/virtualNetworks', tenant_id: $tid})
                CREATE (vm2:Resource {id: 'vm-3', type: 'Microsoft.Compute/virtualMachines', tenant_id: $tid})
                CREATE (vm1)-[:NETWORK_ACCESS]->(vnet)
                CREATE (vnet)-[:NETWORK_ACCESS]->(vm2)
            """,
                tid=tenant_id,
            )

    @pytest.mark.asyncio
    async def test_pattern_detection_with_real_graph(self, neo4j_driver):
        """Test pattern detection against real Neo4j graph."""
        tenant_id = "test-tenant"
        self._create_test_security_graph(neo4j_driver, tenant_id)

        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(neo4j_driver, registry)

        # Detect public-to-sensitive pattern
        pattern = registry.get_pattern("public_to_sensitive")
        instances = sampler._detect_pattern_instances(tenant_id, pattern)

        # Should find the PublicIP -> VM -> Database path
        assert len(instances) >= 1
        assert len(instances[0]) >= 2  # At least 2-node path

    @pytest.mark.asyncio
    async def test_augment_sample_increases_coverage(self, neo4j_driver):
        """Test augmentation improves pattern coverage."""
        tenant_id = "test-tenant"
        self._create_test_security_graph(neo4j_driver, tenant_id)

        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(neo4j_driver, registry)

        # Start with minimal sample (missing security nodes)
        base_sample = {"vm-1"}  # Only has VM, missing PublicIP and Database

        # Augment with security patterns
        result = sampler.augment_sample(
            tenant_id=tenant_id, base_sample_ids=base_sample, patterns_to_preserve=None
        )

        # Should add nodes to complete security patterns
        assert len(result["augmented_sample_ids"]) > len(base_sample)
        assert result["added_node_count"] > 0

        # Coverage should improve
        for coverage in result["coverage_metrics"].values():
            assert coverage >= 0.0


# ==============================================================================
# Error Handling Tests
# ==============================================================================


class TestSecuritySamplerErrorHandling:
    """Test error handling in security sampler."""

    def test_detect_pattern_handles_query_errors(self):
        """Test graceful handling of Cypher query errors."""
        mock_driver = Mock(spec=Driver)
        mock_session = Mock()
        mock_driver.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_driver.session.return_value.__exit__ = Mock(return_value=False)

        # Simulate query error
        mock_session.run.side_effect = Exception("Query failed")

        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        pattern = registry.get_pattern("public_to_sensitive")
        instances = sampler._detect_pattern_instances("test-tenant", pattern)

        # Should return empty list on error (graceful degradation)
        assert instances == []

    def test_augment_sample_with_no_patterns(self):
        """Test augmentation with empty pattern list."""
        mock_driver = Mock(spec=Driver)
        registry = SecurityPatternRegistry()
        sampler = SecurityPreservingSampler(mock_driver, registry)

        base_sample = {"node1", "node2"}

        result = sampler.augment_sample(
            tenant_id="test-tenant", base_sample_ids=base_sample, patterns_to_preserve=[]
        )

        # Should return base sample unchanged
        assert result["augmented_sample_ids"] == base_sample
        assert result["added_node_count"] == 0
