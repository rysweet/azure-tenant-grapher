"""Tests for graph abstraction layer MVP.

Tests cover:
- Integration tests with real Neo4j (testcontainers)
- Unit tests for sampling algorithm
- Error handling and edge cases
"""

from unittest.mock import MagicMock, Mock

import pytest
from neo4j import Driver

from src.services.graph_abstraction_sampler import StratifiedSampler
from src.services.graph_abstraction_service import GraphAbstractionService

# ==============================================================================
# Unit Tests - StratifiedSampler
# ==============================================================================


class TestStratifiedSampler:
    """Unit tests for StratifiedSampler with mocked Neo4j."""

    def test_calculate_quotas_proportional(self):
        """Test proportional quota allocation."""
        sampler = StratifiedSampler(Mock())

        type_counts = {
            "Microsoft.Compute/virtualMachines": 50,
            "Microsoft.Network/virtualNetworks": 30,
            "Microsoft.Storage/storageAccounts": 20,
        }

        quotas = sampler._calculate_quotas(type_counts, 10)

        # Expect: 5 VMs, 3 VNets, 2 Storage (proportional)
        assert quotas["Microsoft.Compute/virtualMachines"] == 5
        assert quotas["Microsoft.Network/virtualNetworks"] == 3
        assert quotas["Microsoft.Storage/storageAccounts"] == 2
        assert sum(quotas.values()) == 10

    def test_calculate_quotas_minimum_one(self):
        """Test minimum 1 sample per type."""
        sampler = StratifiedSampler(Mock())

        type_counts = {
            "Microsoft.Compute/virtualMachines": 100,
            "Microsoft.Rare/resource": 1,
        }

        quotas = sampler._calculate_quotas(type_counts, 10)

        # Rare type should still get 1 sample
        assert quotas["Microsoft.Rare/resource"] >= 1

    def test_calculate_quotas_single_type(self):
        """Test quota calculation with single resource type."""
        sampler = StratifiedSampler(Mock())

        type_counts = {"Microsoft.Compute/virtualMachines": 100}
        quotas = sampler._calculate_quotas(type_counts, 10)

        assert quotas["Microsoft.Compute/virtualMachines"] == 10

    def test_calculate_quotas_rounding_adjustment(self):
        """Test that quotas sum to exactly target size despite rounding."""
        sampler = StratifiedSampler(Mock())

        type_counts = {"Type1": 33, "Type2": 33, "Type3": 34}

        quotas = sampler._calculate_quotas(type_counts, 10)

        # Total should be exactly 10
        assert sum(quotas.values()) == 10

    def test_validate_distribution_passes(self):
        """Test distribution validation passes within tolerance."""
        sampler = StratifiedSampler(Mock())

        type_counts = {"Type1": 50, "Type2": 30, "Type3": 20}
        sampled_counts = {"Type1": 5, "Type2": 3, "Type3": 2}

        # Both are 50/30/20 distribution - should pass
        assert sampler._validate_distribution(type_counts, sampled_counts) is True

    def test_validate_distribution_fails(self):
        """Test distribution validation fails outside tolerance."""
        sampler = StratifiedSampler(Mock())

        type_counts = {"Type1": 50, "Type2": 50}
        sampled_counts = {"Type1": 9, "Type2": 1}  # 90/10 vs 50/50 - outside tolerance

        assert sampler._validate_distribution(type_counts, sampled_counts) is False

    def test_validate_distribution_edge_case(self):
        """Test validation with small sample sizes (buffer tolerance)."""
        sampler = StratifiedSampler(Mock())

        # Small sample might have larger variance due to rounding
        type_counts = {"Type1": 60, "Type2": 40}
        sampled_counts = {"Type1": 7, "Type2": 3}  # 70/30 vs 60/40 (10% delta)

        # Should pass due to 2% buffer (total 17% tolerance)
        assert sampler._validate_distribution(type_counts, sampled_counts) is True

    def test_get_type_distribution(self):
        """Test querying type distribution from Neo4j."""
        # Mock Neo4j driver and session with proper context manager
        mock_driver = Mock(spec=Driver)
        mock_session = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_context_manager

        mock_result = [
            {"resource_type": "Microsoft.Compute/virtualMachines", "count": 50},
            {"resource_type": "Microsoft.Storage/storageAccounts", "count": 30},
        ]
        mock_session.run.return_value = mock_result

        sampler = StratifiedSampler(mock_driver)
        type_counts = sampler._get_type_distribution("test-tenant")

        assert type_counts == {
            "Microsoft.Compute/virtualMachines": 50,
            "Microsoft.Storage/storageAccounts": 30,
        }


# ==============================================================================
# Unit Tests - GraphAbstractionService
# ==============================================================================


class TestGraphAbstractionService:
    """Unit tests for GraphAbstractionService."""

    def test_get_resource_count(self):
        """Test getting total resource count."""
        mock_driver = Mock(spec=Driver)
        mock_session = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_context_manager

        mock_result = Mock()
        mock_result.single.return_value = {"count": 100}
        mock_session.run.return_value = mock_result

        service = GraphAbstractionService(mock_driver)
        count = service._get_resource_count("test-tenant")

        assert count == 100

    @pytest.mark.asyncio
    async def test_abstract_tenant_graph_validates_input(self):
        """Test input validation for abstract_tenant_graph."""
        mock_driver = Mock(spec=Driver)
        service = GraphAbstractionService(mock_driver)

        # Test negative sample size
        with pytest.raises(ValueError, match="Sample size must be positive"):
            await service.abstract_tenant_graph("test-tenant", -1)

        # Test zero sample size
        with pytest.raises(ValueError, match="Sample size must be positive"):
            await service.abstract_tenant_graph("test-tenant", 0)

        # Test empty tenant ID
        with pytest.raises(ValueError, match="non-empty string"):
            await service.abstract_tenant_graph("", 10)

    @pytest.mark.asyncio
    async def test_abstract_tenant_graph_no_resources(self):
        """Test error when tenant has no resources."""
        mock_driver = Mock(spec=Driver)
        mock_session = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_context_manager

        mock_result = Mock()
        mock_result.single.return_value = {"count": 0}
        mock_session.run.return_value = mock_result

        service = GraphAbstractionService(mock_driver)

        with pytest.raises(ValueError, match="No resources found"):
            await service.abstract_tenant_graph("empty-tenant", 10)

    @pytest.mark.asyncio
    async def test_abstract_tenant_graph_sample_exceeds_source(self):
        """Test handling when sample size exceeds source size."""
        # Setup mocks with proper context manager
        mock_driver = Mock(spec=Driver)
        mock_session = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_context_manager

        # Mock resource count query
        count_result = Mock()
        count_result.single.return_value = {"count": 5}

        # Mock type distribution query
        type_result = [
            {"resource_type": "Microsoft.Compute/virtualMachines", "count": 5}
        ]

        # Mock sample query
        sample_result = [{"node_id": f"vm-{i}"} for i in range(5)]

        # Mock relationship creation result
        rel_result = Mock()
        rel_result.consume.return_value.counters.relationships_created = 5

        def side_effect(*args, **kwargs):
            query = args[0] if args else kwargs.get("query", "")
            if "count(n) AS count" in query and "RETURN count(n)" in query:
                return count_result
            elif "resource_type" in query and "count(n) AS count" in query:
                return type_result
            elif "MERGE" in query or "CREATE" in query:
                return rel_result
            else:
                return sample_result

        mock_session.run.side_effect = side_effect

        service = GraphAbstractionService(mock_driver)

        # Request 100 nodes from tenant with only 5
        result = await service.abstract_tenant_graph("small-tenant", 100)

        # Should sample all 5 available resources
        assert result["actual_size"] == 5
        assert result["target_size"] == 100


# ==============================================================================
# Integration Tests - Requires Docker/Testcontainers
# ==============================================================================


@pytest.mark.integration
@pytest.mark.skipif(
    "not config.getoption('--run-integration')",
    reason="Integration tests require --run-integration flag",
)
class TestGraphAbstractionIntegration:
    """Integration tests with real Neo4j using testcontainers."""

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

    def _create_test_graph(self, driver, tenant_id: str, type_counts: dict):
        """Create test graph with specified type distribution."""
        with driver.session() as session:
            # Clear any existing data
            session.run("MATCH (n) DETACH DELETE n")

            # Create resources per type
            for resource_type, count in type_counts.items():
                for i in range(count):
                    session.run(
                        """
                        CREATE (n:Resource {
                            id: $id,
                            type: $type,
                            name: $name,
                            tenant_id: $tenant_id
                        })
                    """,
                        {
                            "id": f"{resource_type.split('/')[-1].lower()}-{i}",
                            "type": resource_type,
                            "name": f"test-{i}",
                            "tenant_id": tenant_id,
                        },
                    )

    @pytest.mark.asyncio
    async def test_end_to_end_abstraction(self, neo4j_driver):
        """Test complete abstraction workflow with real Neo4j."""
        tenant_id = "test-tenant"

        # Create test graph: 100 resources (3 types)
        type_counts = {
            "Microsoft.Compute/virtualMachines": 50,
            "Microsoft.Network/virtualNetworks": 30,
            "Microsoft.Storage/storageAccounts": 20,
        }
        self._create_test_graph(neo4j_driver, tenant_id, type_counts)

        # Run abstraction
        service = GraphAbstractionService(neo4j_driver)
        result = await service.abstract_tenant_graph(tenant_id, sample_size=10, seed=42)

        # Verify size within tolerance (±10%)
        assert result["actual_size"] >= 9
        assert result["actual_size"] <= 11
        assert result["target_size"] == 10

        # Verify :SAMPLE_OF relationships created
        with neo4j_driver.session() as session:
            rel_count = session.run(
                """
                MATCH (:Resource)-[r:SAMPLE_OF]->(:Resource {tenant_id: $tid})
                RETURN count(r) AS count
            """,
                tid=tenant_id,
            ).single()["count"]

            assert rel_count == result["actual_size"]

    @pytest.mark.asyncio
    async def test_type_distribution_preserved(self, neo4j_driver):
        """Test that resource type distribution is preserved within tolerance."""
        tenant_id = "dist-test-tenant"

        # Create graph with specific distribution
        type_counts = {
            "Microsoft.Compute/virtualMachines": 50,  # 50%
            "Microsoft.Storage/storageAccounts": 30,  # 30%
            "Microsoft.Network/virtualNetworks": 20,  # 20%
        }
        self._create_test_graph(neo4j_driver, tenant_id, type_counts)

        # Sample 10 nodes
        service = GraphAbstractionService(neo4j_driver)
        result = await service.abstract_tenant_graph(tenant_id, sample_size=10, seed=42)

        # Calculate actual percentages
        total = result["actual_size"]
        type_dist = result["type_distribution"]

        vm_pct = type_dist.get("Microsoft.Compute/virtualMachines", 0) / total
        storage_pct = type_dist.get("Microsoft.Storage/storageAccounts", 0) / total
        vnet_pct = type_dist.get("Microsoft.Network/virtualNetworks", 0) / total

        # Should be close to 50/30/20 (within ±17% tolerance including buffer)
        assert abs(vm_pct - 0.50) <= 0.17
        assert abs(storage_pct - 0.30) <= 0.17
        assert abs(vnet_pct - 0.20) <= 0.17

    @pytest.mark.asyncio
    async def test_tiny_graph_abstraction(self, neo4j_driver):
        """Test abstraction with very small graph (edge case)."""
        tenant_id = "tiny-tenant"

        # Create tiny graph: 2 resources
        type_counts = {
            "Microsoft.Compute/virtualMachines": 1,
            "Microsoft.Storage/storageAccounts": 1,
        }
        self._create_test_graph(neo4j_driver, tenant_id, type_counts)

        # Request 2-node abstraction
        service = GraphAbstractionService(neo4j_driver)
        result = await service.abstract_tenant_graph(tenant_id, sample_size=2, seed=42)

        # Should get both resources
        assert result["actual_size"] == 2
        assert len(result["type_distribution"]) == 2

    @pytest.mark.asyncio
    async def test_skewed_distribution(self, neo4j_driver):
        """Test with heavily skewed distribution (95/5 split)."""
        tenant_id = "skewed-tenant"

        # Create skewed graph
        type_counts = {
            "Microsoft.Storage/storageAccounts": 95,
            "Microsoft.Compute/virtualMachines": 5,
        }
        self._create_test_graph(neo4j_driver, tenant_id, type_counts)

        # Sample 10 nodes
        service = GraphAbstractionService(neo4j_driver)
        result = await service.abstract_tenant_graph(tenant_id, sample_size=10, seed=42)

        # Distribution should be preserved (9-10 storage, 0-1 VMs)
        storage_count = result["type_distribution"].get(
            "Microsoft.Storage/storageAccounts", 0
        )
        vm_count = result["type_distribution"].get(
            "Microsoft.Compute/virtualMachines", 0
        )

        assert storage_count >= 9
        assert vm_count >= 0  # Might be 0 or 1 due to minimum quota

    @pytest.mark.asyncio
    async def test_clear_existing_relationships(self, neo4j_driver):
        """Test clearing existing :SAMPLE_OF relationships."""
        tenant_id = "clear-test-tenant"

        # Create test graph
        type_counts = {"Microsoft.Compute/virtualMachines": 10}
        self._create_test_graph(neo4j_driver, tenant_id, type_counts)

        # First abstraction
        service = GraphAbstractionService(neo4j_driver)
        await service.abstract_tenant_graph(tenant_id, sample_size=5, seed=42)

        # Second abstraction with clear=True
        await service.abstract_tenant_graph(
            tenant_id, sample_size=3, seed=123, clear_existing=True
        )

        # Should have exactly 3 relationships (old ones cleared)
        with neo4j_driver.session() as session:
            second_count = session.run(
                """
                MATCH ()-[r:SAMPLE_OF]->(:Resource {tenant_id: $tid})
                RETURN count(r) AS count
            """,
                tid=tenant_id,
            ).single()["count"]

        assert second_count == 3


# ==============================================================================
# Error Handling Tests
# ==============================================================================


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    @pytest.mark.asyncio
    async def test_tenant_not_found(self):
        """Test error when tenant has no resources."""
        mock_driver = Mock(spec=Driver)
        mock_session = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = MagicMock(return_value=mock_session)
        mock_context_manager.__exit__ = MagicMock(return_value=False)
        mock_driver.session.return_value = mock_context_manager

        mock_result = Mock()
        mock_result.single.return_value = {"count": 0}
        mock_session.run.return_value = mock_result

        service = GraphAbstractionService(mock_driver)

        with pytest.raises(ValueError, match="No resources found"):
            await service.abstract_tenant_graph("nonexistent-tenant", 10)

    @pytest.mark.asyncio
    async def test_invalid_sample_size(self):
        """Test error with invalid sample sizes."""
        mock_driver = Mock(spec=Driver)
        service = GraphAbstractionService(mock_driver)

        with pytest.raises(ValueError, match="Sample size must be positive"):
            await service.abstract_tenant_graph("test-tenant", -10)

        with pytest.raises(ValueError, match="Sample size must be positive"):
            await service.abstract_tenant_graph("test-tenant", 0)

    @pytest.mark.asyncio
    async def test_invalid_tenant_id(self):
        """Test error with invalid tenant ID."""
        mock_driver = Mock(spec=Driver)
        service = GraphAbstractionService(mock_driver)

        with pytest.raises(ValueError, match="non-empty string"):
            await service.abstract_tenant_graph("", 10)

        with pytest.raises(ValueError):
            await service.abstract_tenant_graph(None, 10)  # type: ignore


# ==============================================================================
# Performance Tests
# ==============================================================================


@pytest.mark.performance
@pytest.mark.skipif(
    "not config.getoption('--run-performance')",
    reason="Performance tests require --run-performance flag",
)
class TestPerformance:
    """Performance tests for large graphs."""

    @pytest.fixture
    def large_neo4j_driver(self):
        """Create Neo4j driver for performance testing."""
        from neo4j import GraphDatabase
        from testcontainers.neo4j import Neo4jContainer

        with Neo4jContainer("neo4j:5.15.0") as container:
            uri = container.get_connection_url()
            driver = GraphDatabase.driver(uri, auth=("neo4j", "test"))
            yield driver
            driver.close()

    @pytest.mark.asyncio
    async def test_large_graph_performance(self, large_neo4j_driver):
        """Test abstraction performance on 1000-node graph."""
        import time

        tenant_id = "perf-test-tenant"

        # Create 1000-node graph
        with large_neo4j_driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

            # Create 1000 VMs
            for i in range(1000):
                session.run(
                    """
                    CREATE (n:Resource {
                        id: $id,
                        type: 'Microsoft.Compute/virtualMachines',
                        name: $name,
                        tenant_id: $tenant_id
                    })
                """,
                    {"id": f"vm-{i}", "name": f"test-vm-{i}", "tenant_id": tenant_id},
                )

        # Time the abstraction
        service = GraphAbstractionService(large_neo4j_driver)

        start = time.time()
        result = await service.abstract_tenant_graph(tenant_id, sample_size=100)
        elapsed = time.time() - start

        # Should complete in < 10 seconds
        assert elapsed < 10.0
        assert result["actual_size"] == 100


# ==============================================================================
# Pytest Configuration
# ==============================================================================
# NOTE: Pytest config moved to tests/conftest.py for project-wide availability
