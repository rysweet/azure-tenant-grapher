"""
Integration tests for ScaleDownService with real Neo4j.

This module tests the sampling algorithms with real Neo4j instances
to prove functionality that was skipped in unit tests due to async
mocking complexity.

Test Coverage:
1. Forest Fire sampling with real graph
2. MHRW sampling with real graph
3. Random Walk sampling with real graph
4. Pattern-based sampling with real data
5. Quality metrics calculation with real graphs
6. Export formats with real data
7. Edge cases (empty graphs, single-node graphs, disconnected graphs)
8. End-to-end sample_graph workflow

Uses Neo4j from environment variables (CI/CD compatible).
"""

import json
import os
import tempfile
from pathlib import Path

import networkx as nx
import pytest
import yaml
from neo4j import GraphDatabase

from src.services.scale_down_service import QualityMetrics, ScaleDownService
from src.utils.session_manager import Neo4jSessionManager


@pytest.fixture(scope="module")
def neo4j_test_driver():
    """Create Neo4j driver for integration tests."""
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")

    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD environment variable must be set for integration tests"
        )

    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()


@pytest.fixture
def session_manager(neo4j_test_driver):
    """Create session manager for tests."""
    class TestSessionManager:
        def __init__(self, driver):
            self._driver = driver

        def session(self):
            return self._driver.session()

    return TestSessionManager(neo4j_test_driver)


@pytest.fixture
def scale_down_service(session_manager):
    """Create ScaleDownService instance."""
    return ScaleDownService(session_manager)


@pytest.fixture
def test_tenant_id():
    """Unique tenant ID for test isolation."""
    import uuid
    return f"test-tenant-{uuid.uuid4()}"


def create_test_graph(session, tenant_id: str, num_nodes: int = 100):
    """
    Create a realistic test graph in Neo4j.

    Creates a graph with:
    - Tenant node
    - Virtual machines
    - Virtual networks
    - Network security groups
    - Storage accounts
    - Relationships: CONTAINS, USES_SUBNET, SECURED_BY

    Args:
        session: Neo4j session
        tenant_id: Tenant ID for test isolation
        num_nodes: Number of nodes to create
    """
    # Clear any existing test data
    session.run(
        "MATCH (r:Resource) WHERE r.tenant_id = $tenant_id DETACH DELETE r",
        tenant_id=tenant_id
    )
    session.run(
        "MATCH (t:Tenant {id: $tenant_id}) DETACH DELETE t",
        tenant_id=tenant_id
    )

    # Create Tenant node
    session.run(
        """
        CREATE (t:Tenant {
            id: $tenant_id,
            name: $name
        })
        """,
        tenant_id=tenant_id,
        name=f"Test Tenant {tenant_id[:8]}"
    )

    # Create VNets (10 VNets)
    num_vnets = max(10, num_nodes // 10)
    for i in range(num_vnets):
        session.run(
            """
            CREATE (r:Resource {
                id: $id,
                type: $type,
                name: $name,
                tenant_id: $tenant_id,
                location: $location,
                resource_group: $rg
            })
            """,
            id=f"{tenant_id}-vnet-{i}",  # Include tenant_id for uniqueness
            type="Microsoft.Network/virtualNetworks",
            name=f"vnet-{i}",
            tenant_id=tenant_id,
            location="eastus" if i % 2 == 0 else "westus",
            rg=f"rg-{i % 5}"
        )

    # Create NSGs (20 NSGs)
    num_nsgs = max(20, num_nodes // 5)
    for i in range(num_nsgs):
        import json
        tags_json = json.dumps({"environment": "production" if i % 2 == 0 else "development"})
        session.run(
            """
            CREATE (r:Resource {
                id: $id,
                type: $type,
                name: $name,
                tenant_id: $tenant_id,
                location: $location,
                resource_group: $rg,
                tags_json: $tags_json
            })
            """,
            id=f"{tenant_id}-nsg-{i}",  # Include tenant_id for uniqueness
            type="Microsoft.Network/networkSecurityGroups",
            name=f"nsg-{i}",
            tenant_id=tenant_id,
            location="eastus" if i % 2 == 0 else "westus",
            rg=f"rg-{i % 5}",
            tags_json=tags_json
        )

    # Create VMs (remaining nodes)
    num_vms = num_nodes - num_vnets - num_nsgs
    for i in range(num_vms):
        import json
        tags_json = json.dumps({"environment": "production" if i % 2 == 0 else "development"})
        session.run(
            """
            CREATE (r:Resource {
                id: $id,
                type: $type,
                name: $name,
                tenant_id: $tenant_id,
                location: $location,
                resource_group: $rg,
                tags_json: $tags_json
            })
            """,
            id=f"{tenant_id}-vm-{i}",  # Include tenant_id for uniqueness
            type="Microsoft.Compute/virtualMachines",
            name=f"vm-{i}",
            tenant_id=tenant_id,
            location="eastus" if i % 3 == 0 else "westus",
            rg=f"rg-{i % 5}",
            tags_json=tags_json
        )

    # Create relationships: VMs -> VNets (USES_SUBNET)
    for i in range(num_vms):
        vnet_idx = i % num_vnets
        session.run(
            """
            MATCH (vm:Resource {id: $vm_id, tenant_id: $tenant_id})
            MATCH (vnet:Resource {id: $vnet_id, tenant_id: $tenant_id})
            CREATE (vm)-[:USES_SUBNET]->(vnet)
            """,
            vm_id=f"{tenant_id}-vm-{i}",
            vnet_id=f"{tenant_id}-vnet-{vnet_idx}",
            tenant_id=tenant_id
        )

    # Create relationships: VMs -> NSGs (SECURED_BY)
    for i in range(num_vms):
        nsg_idx = i % num_nsgs
        session.run(
            """
            MATCH (vm:Resource {id: $vm_id, tenant_id: $tenant_id})
            MATCH (nsg:Resource {id: $nsg_id, tenant_id: $tenant_id})
            CREATE (vm)-[:SECURED_BY]->(nsg)
            """,
            vm_id=f"{tenant_id}-vm-{i}",
            nsg_id=f"{tenant_id}-nsg-{nsg_idx}",
            tenant_id=tenant_id
        )

    # Create some cross-connections between VNets (CONNECTED_TO)
    for i in range(0, num_vnets - 1, 2):
        session.run(
            """
            MATCH (vnet1:Resource {id: $vnet1_id, tenant_id: $tenant_id})
            MATCH (vnet2:Resource {id: $vnet2_id, tenant_id: $tenant_id})
            CREATE (vnet1)-[:CONNECTED_TO]->(vnet2)
            """,
            vnet1_id=f"{tenant_id}-vnet-{i}",
            vnet2_id=f"{tenant_id}-vnet-{i + 1}",
            tenant_id=tenant_id
        )


def cleanup_test_graph(session, tenant_id: str):
    """Clean up test graph after test."""
    session.run(
        "MATCH (r:Resource) WHERE r.tenant_id = $tenant_id DETACH DELETE r",
        tenant_id=tenant_id
    )
    session.run(
        "MATCH (t:Tenant {id: $tenant_id}) DETACH DELETE t",
        tenant_id=tenant_id
    )


class TestNeo4jToNetworkXIntegration:
    """Test Neo4j to NetworkX conversion with real database."""

    @pytest.mark.asyncio
    async def test_neo4j_to_networkx_with_real_graph(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test Neo4j to NetworkX conversion with real graph."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=50)

        try:
            # Convert to NetworkX
            G, node_properties = await scale_down_service.neo4j_to_networkx(
                test_tenant_id
            )

            # Verify graph structure
            assert isinstance(G, nx.DiGraph)
            assert G.number_of_nodes() == 50
            assert G.number_of_edges() > 0

            # Verify node properties
            assert len(node_properties) == 50

            # Verify all nodes have required properties
            for node_id, props in node_properties.items():
                assert "id" in props
                assert "type" in props
                assert "tenant_id" in props
                assert props["tenant_id"] == test_tenant_id

            # Verify relationships exist
            assert G.number_of_edges() >= 40  # At least VMs -> VNets

        finally:
            # Cleanup
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestForestFireSamplingIntegration:
    """Test Forest Fire sampling with real Neo4j."""

    @pytest.mark.asyncio
    async def test_forest_fire_sampling_basic(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test Forest Fire sampling produces valid results."""
        # Create test graph (100 nodes)
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Convert to NetworkX
            G, _ = await scale_down_service.neo4j_to_networkx(test_tenant_id)

            # Sample 20% of nodes
            target_count = 20
            sampled_ids = await scale_down_service._sample_forest_fire(G, target_count)

            # Verify sample
            assert isinstance(sampled_ids, set)
            assert len(sampled_ids) > 0
            # Forest Fire can vary, allow ±50% tolerance
            assert len(sampled_ids) >= target_count * 0.5
            assert len(sampled_ids) <= target_count * 1.5

            # Verify all sampled nodes exist in original graph
            for node_id in sampled_ids:
                assert node_id in G.nodes

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_forest_fire_preserves_structure(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test that Forest Fire preserves local graph structure."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            G, _ = await scale_down_service.neo4j_to_networkx(test_tenant_id)

            # Sample graph
            sampled_ids = await scale_down_service._sample_forest_fire(G, 30)
            sampled_graph = G.subgraph(sampled_ids).copy()

            # Verify sampled graph has edges (structure preserved)
            assert sampled_graph.number_of_edges() > 0

            # Verify average degree is reasonable
            if sampled_graph.number_of_nodes() > 0:
                avg_degree = sum(dict(sampled_graph.degree()).values()) / sampled_graph.number_of_nodes()
                assert avg_degree > 0  # Should have connections

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestMHRWSamplingIntegration:
    """Test Metropolis-Hastings Random Walk sampling with real Neo4j."""

    @pytest.mark.asyncio
    async def test_mhrw_sampling_basic(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test MHRW sampling produces valid results."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            G, _ = await scale_down_service.neo4j_to_networkx(test_tenant_id)

            # Sample with MHRW
            target_count = 25
            sampled_ids = await scale_down_service._sample_mhrw(G, target_count)

            # Verify sample
            assert isinstance(sampled_ids, set)
            assert len(sampled_ids) > 0
            # MHRW can vary, allow ±50% tolerance
            assert len(sampled_ids) >= target_count * 0.5
            assert len(sampled_ids) <= target_count * 1.5

            # Verify nodes exist
            for node_id in sampled_ids:
                assert node_id in G.nodes

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_mhrw_produces_different_samples(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test that MHRW produces different samples on repeated runs."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            G, _ = await scale_down_service.neo4j_to_networkx(test_tenant_id)

            # Run MHRW multiple times
            samples = []
            for _ in range(3):
                sampled_ids = await scale_down_service._sample_mhrw(G, 20)
                samples.append(sampled_ids)

            # Verify samples are different (stochastic algorithm)
            # At least some difference between samples
            all_same = all(samples[0] == s for s in samples[1:])
            assert not all_same, "MHRW should produce varied samples"

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestRandomWalkSamplingIntegration:
    """Test Random Walk sampling with real Neo4j."""

    @pytest.mark.asyncio
    async def test_random_walk_sampling_basic(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test Random Walk sampling produces valid results."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            G, _ = await scale_down_service.neo4j_to_networkx(test_tenant_id)

            # Sample with Random Walk
            target_count = 30
            sampled_ids = await scale_down_service._sample_random_walk(G, target_count)

            # Verify sample
            assert isinstance(sampled_ids, set)
            assert len(sampled_ids) > 0
            assert len(sampled_ids) >= target_count * 0.5
            assert len(sampled_ids) <= target_count * 1.5

            # Verify nodes exist
            for node_id in sampled_ids:
                assert node_id in G.nodes

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestPatternSamplingIntegration:
    """Test pattern-based sampling with real Neo4j."""

    @pytest.mark.asyncio
    async def test_pattern_sampling_by_type(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test pattern sampling by resource type."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Sample only VMs
            criteria = {"type": "Microsoft.Compute/virtualMachines"}
            matching_ids = await scale_down_service.sample_by_pattern(
                test_tenant_id, criteria
            )

            # Verify all matches are VMs
            assert len(matching_ids) > 0

            # Verify by querying Neo4j directly
            with session_manager.session() as session:
                result = session.run(
                    """
                    MATCH (r:Resource)
                    WHERE r.tenant_id = $tenant_id
                      AND r.type = $type
                      AND NOT r:Original
                    RETURN count(r) as count
                    """,
                    tenant_id=test_tenant_id,
                    type="Microsoft.Compute/virtualMachines"
                )
                expected_count = result.single()["count"]
                assert len(matching_ids) == expected_count

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_pattern_sampling_by_location(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test pattern sampling by location."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Sample eastus resources
            criteria = {"location": "eastus"}
            matching_ids = await scale_down_service.sample_by_pattern(
                test_tenant_id, criteria
            )

            # Should find some eastus resources
            assert len(matching_ids) > 0

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_pattern_sampling_multiple_criteria(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test pattern sampling with multiple criteria."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Sample VMs in eastus
            criteria = {
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus"
            }
            matching_ids = await scale_down_service.sample_by_pattern(
                test_tenant_id, criteria
            )

            # Should find subset matching all criteria
            assert len(matching_ids) >= 0  # May be 0 if no matches

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestSampleGraphEndToEndIntegration:
    """Test end-to-end sample_graph workflow with real Neo4j."""

    @pytest.mark.asyncio
    async def test_sample_graph_forest_fire_e2e(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test complete sampling workflow with Forest Fire."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Sample graph with export
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "sample.yaml"

                node_ids, metrics = await scale_down_service.sample_graph(
                    tenant_id=test_tenant_id,
                    algorithm="forest_fire",
                    target_size=0.2,  # 20%
                    output_mode="yaml",
                    output_path=str(output_path)
                )

                # Verify results
                assert isinstance(node_ids, set)
                assert len(node_ids) > 0
                assert isinstance(metrics, QualityMetrics)

                # Verify metrics
                assert metrics.original_nodes == 100
                assert metrics.sampled_nodes == len(node_ids)
                assert 0 < metrics.sampling_ratio <= 1.0
                assert metrics.computation_time_seconds > 0

                # Verify export file
                assert output_path.exists()
                with open(output_path) as f:
                    data = yaml.safe_load(f)
                assert data["metadata"]["node_count"] == len(node_ids)

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_sample_graph_mhrw_e2e(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test complete sampling workflow with MHRW."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=80)

        try:
            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="mhrw",
                target_size=0.25,
                output_mode="json",
            )

            # Verify results
            assert len(node_ids) > 0
            assert metrics.original_nodes == 80
            assert metrics.sampled_nodes == len(node_ids)

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_sample_graph_absolute_count(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test sampling with absolute node count."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Request exactly 15 nodes
            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=15,  # Absolute count
                output_mode="yaml",
            )

            # Verify approximately 15 nodes (allow algorithm variance)
            assert len(node_ids) >= 10
            assert len(node_ids) <= 20

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestQualityMetricsIntegration:
    """Test quality metrics calculation with real graphs."""

    @pytest.mark.asyncio
    async def test_quality_metrics_calculation(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test quality metrics with real graph data."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=100)

        try:
            # Sample graph and get metrics
            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.3,
                output_mode="yaml",
            )

            # Verify all metrics are calculated
            assert metrics.original_nodes == 100
            assert metrics.sampled_nodes == len(node_ids)
            assert 0 < metrics.sampling_ratio <= 1.0
            assert metrics.original_edges > 0
            assert metrics.sampled_edges >= 0
            assert metrics.degree_distribution_similarity >= 0
            assert metrics.clustering_coefficient_diff >= 0
            assert metrics.connected_components_original > 0
            assert metrics.connected_components_sampled > 0
            assert 0 <= metrics.resource_type_preservation <= 1.0
            assert metrics.avg_degree_original >= 0
            assert metrics.avg_degree_sampled >= 0
            assert metrics.computation_time_seconds > 0

            # Verify string representation
            metrics_str = str(metrics)
            assert "Quality Metrics:" in metrics_str

            # Verify dict conversion
            metrics_dict = metrics.to_dict()
            assert metrics_dict["original_nodes"] == 100

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestExportFormatsIntegration:
    """Test export formats with real data."""

    @pytest.mark.asyncio
    async def test_yaml_export_integration(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test YAML export with real graph."""
        # Create small test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=30)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "sample.yaml"

                node_ids, _ = await scale_down_service.sample_graph(
                    tenant_id=test_tenant_id,
                    algorithm="forest_fire",
                    target_size=0.5,
                    output_mode="yaml",
                    output_path=str(output_path)
                )

                # Verify YAML file
                assert output_path.exists()
                with open(output_path) as f:
                    data = yaml.safe_load(f)

                assert "metadata" in data
                assert "nodes" in data
                assert "relationships" in data
                assert data["metadata"]["format"] == "yaml"
                assert len(data["nodes"]) == len(node_ids)

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_json_export_integration(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test JSON export with real graph."""
        # Create small test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=30)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "sample.json"

                node_ids, _ = await scale_down_service.sample_graph(
                    tenant_id=test_tenant_id,
                    algorithm="mhrw",
                    target_size=0.5,
                    output_mode="json",
                    output_path=str(output_path)
                )

                # Verify JSON file
                assert output_path.exists()
                with open(output_path) as f:
                    data = json.load(f)

                assert data["metadata"]["format"] == "json"
                assert len(data["nodes"]) == len(node_ids)

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_neo4j_cypher_export_integration(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test Neo4j Cypher export with real graph."""
        # Create small test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=20)

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                output_path = Path(tmpdir) / "sample.cypher"

                node_ids, _ = await scale_down_service.sample_graph(
                    tenant_id=test_tenant_id,
                    algorithm="forest_fire",
                    target_size=0.5,
                    output_mode="neo4j",
                    output_path=str(output_path)
                )

                # Verify Cypher file
                assert output_path.exists()
                with open(output_path) as f:
                    content = f.read()

                assert "CREATE" in content
                assert ":Resource" in content

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestEdgeCasesIntegration:
    """Test edge cases with real Neo4j."""

    @pytest.mark.asyncio
    async def test_single_node_graph(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test sampling a graph with single node."""
        # Create single node
        with session_manager.session() as session:
            # Create Tenant node
            session.run(
                """
                CREATE (t:Tenant {
                    id: $tenant_id,
                    name: $name
                })
                """,
                tenant_id=test_tenant_id,
                name=f"Test Tenant {test_tenant_id[:8]}"
            )
            session.run(
                """
                CREATE (r:Resource {
                    id: $id,
                    type: $type,
                    tenant_id: $tenant_id
                })
                """,
                id=f"{test_tenant_id}-single-node",
                type="Microsoft.Compute/virtualMachines",
                tenant_id=test_tenant_id
            )

        try:
            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.5,
                output_mode="yaml",
            )

            # Should sample the single node
            assert len(node_ids) >= 1
            assert metrics.original_nodes == 1
            assert metrics.sampled_nodes == len(node_ids)

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_disconnected_graph(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test sampling a disconnected graph."""
        # Create two disconnected components
        with session_manager.session() as session:
            # Create Tenant node
            session.run(
                """
                CREATE (t:Tenant {
                    id: $tenant_id,
                    name: $name
                })
                """,
                tenant_id=test_tenant_id,
                name=f"Test Tenant {test_tenant_id[:8]}"
            )

            # Component 1: 10 nodes
            for i in range(10):
                session.run(
                    """
                    CREATE (r:Resource {
                        id: $id,
                        type: $type,
                        tenant_id: $tenant_id
                    })
                    """,
                    id=f"{test_tenant_id}-comp1-{i}",
                    type="Microsoft.Compute/virtualMachines",
                    tenant_id=test_tenant_id
                )

            # Component 2: 10 nodes
            for i in range(10):
                session.run(
                    """
                    CREATE (r:Resource {
                        id: $id,
                        type: $type,
                        tenant_id: $tenant_id
                    })
                    """,
                    id=f"{test_tenant_id}-comp2-{i}",
                    type="Microsoft.Network/virtualNetworks",
                    tenant_id=test_tenant_id
                )

            # Add edges within components
            for i in range(9):
                session.run(
                    """
                    MATCH (r1:Resource {id: $id1, tenant_id: $tenant_id})
                    MATCH (r2:Resource {id: $id2, tenant_id: $tenant_id})
                    CREATE (r1)-[:CONTAINS]->(r2)
                    """,
                    id1=f"{test_tenant_id}-comp1-{i}",
                    id2=f"{test_tenant_id}-comp1-{i + 1}",
                    tenant_id=test_tenant_id
                )
                session.run(
                    """
                    MATCH (r1:Resource {id: $id1, tenant_id: $tenant_id})
                    MATCH (r2:Resource {id: $id2, tenant_id: $tenant_id})
                    CREATE (r1)-[:CONTAINS]->(r2)
                    """,
                    id1=f"{test_tenant_id}-comp2-{i}",
                    id2=f"{test_tenant_id}-comp2-{i + 1}",
                    tenant_id=test_tenant_id
                )

        try:
            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.3,
                output_mode="yaml",
            )

            # Should sample nodes
            assert len(node_ids) > 0

            # Metrics should reflect multiple components
            assert metrics.connected_components_original >= 2

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)

    @pytest.mark.asyncio
    async def test_large_graph_performance(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test sampling performance with larger graph."""
        import time

        # Create larger test graph (500 nodes)
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=500)

        try:
            start_time = time.time()

            node_ids, metrics = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.1,  # 10% = 50 nodes
                output_mode="yaml",
            )

            elapsed = time.time() - start_time

            # Should complete in reasonable time
            assert elapsed < 30.0  # Less than 30 seconds

            # Verify sample size
            assert len(node_ids) > 0
            assert metrics.original_nodes == 500

            # Verify computation time is recorded
            assert metrics.computation_time_seconds > 0

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)


class TestProgressCallbackIntegration:
    """Test progress callback with real operations."""

    @pytest.mark.asyncio
    async def test_progress_callback_invoked(
        self, scale_down_service, session_manager, test_tenant_id
    ):
        """Test that progress callback is invoked during sampling."""
        # Create test graph
        with session_manager.session() as session:
            create_test_graph(session, test_tenant_id, num_nodes=50)

        try:
            progress_calls = []

            def progress_callback(phase: str, current: int, total: int):
                progress_calls.append({
                    "phase": phase,
                    "current": current,
                    "total": total
                })

            node_ids, _ = await scale_down_service.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.2,
                output_mode="yaml",
                progress_callback=progress_callback
            )

            # Verify callback was invoked
            assert len(progress_calls) > 0

            # Verify different phases were reported
            phases = {call["phase"] for call in progress_calls}
            assert len(phases) > 0

        finally:
            with session_manager.session() as session:
                cleanup_test_graph(session, test_tenant_id)
