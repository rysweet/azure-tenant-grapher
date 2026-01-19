# tests/unit/services/scale_down/test_orchestrator.py
"""Comprehensive tests for orchestrator module.

Tests ScaleDownOrchestrator class following TDD methodology.
Target: 85%+ coverage for orchestrator.py (547 lines).
"""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import networkx as nx
import pytest

from src.services.scale_down.orchestrator import ScaleDownOrchestrator
from src.services.scale_down.quality_metrics import QualityMetrics


class TestScaleDownOrchestrator:
    """Test suite for ScaleDownOrchestrator class."""

    @pytest.fixture
    def orchestrator(self, mock_neo4j_session_manager):
        """Provide ScaleDownOrchestrator instance with mocked session manager."""
        return ScaleDownOrchestrator(mock_neo4j_session_manager)

    def test_initialization(self, orchestrator, mock_neo4j_session_manager):
        """Test ScaleDownOrchestrator initialization."""
        assert orchestrator.session_manager == mock_neo4j_session_manager
        assert orchestrator.logger is not None
        assert isinstance(orchestrator.logger, logging.Logger)

        # Verify components initialized
        assert orchestrator.extractor is not None
        assert orchestrator.operations is not None
        assert orchestrator.metrics_calculator is not None

        # Verify samplers initialized
        assert "forest_fire" in orchestrator.samplers
        assert "mhrw" in orchestrator.samplers
        assert "random_walk" in orchestrator.samplers
        assert "pattern" in orchestrator.samplers

        # Verify exporters initialized
        assert "yaml" in orchestrator.exporters
        assert "json" in orchestrator.exporters
        assert "neo4j" in orchestrator.exporters

    @pytest.mark.asyncio
    async def test_neo4j_to_networkx_success(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test successful Neo4j to NetworkX conversion."""
        # Mock extractor
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )

        # Execute
        G, props = await orchestrator.neo4j_to_networkx(test_tenant_id)

        # Verify
        assert G == sample_networkx_graph
        assert props == sample_node_properties
        orchestrator.extractor.extract_graph.assert_awaited_once_with(
            test_tenant_id, None
        )

    @pytest.mark.asyncio
    async def test_neo4j_to_networkx_with_progress_callback(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
        mock_progress_callback,
    ):
        """Test Neo4j to NetworkX conversion with progress callback."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )

        # Execute
        G, props = await orchestrator.neo4j_to_networkx(
            test_tenant_id, mock_progress_callback
        )

        # Verify callback passed to extractor
        orchestrator.extractor.extract_graph.assert_awaited_once_with(
            test_tenant_id, mock_progress_callback
        )

    @pytest.mark.asyncio
    async def test_neo4j_to_networkx_validation_passthrough(
        self, orchestrator, test_tenant_id
    ):
        """Test that validate_tenant_exists is passed to extractor for mocking."""
        # Setup mock validation
        mock_validate = AsyncMock(return_value=True)
        orchestrator.validate_tenant_exists = mock_validate

        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(nx.DiGraph(), {})
        )

        # Execute
        await orchestrator.neo4j_to_networkx(test_tenant_id)

        # Verify validation method was copied to extractor
        assert hasattr(orchestrator.extractor, "validate_tenant_exists")

    @pytest.mark.asyncio
    async def test_sample_graph_forest_fire_algorithm(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with forest_fire algorithm."""
        # Mock components
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2", "node3"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=3,
                original_edges=4,
                sampled_edges=2,
                sampling_ratio=0.6,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=0.6,
            output_mode="export",
            output_path=None,
        )

        # Verify
        assert len(node_ids) == 3
        assert "node1" in node_ids
        assert isinstance(metrics, QualityMetrics)
        assert deleted == 0  # No deletion in export mode

    @pytest.mark.asyncio
    async def test_sample_graph_mhrw_algorithm(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with MHRW algorithm."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["mhrw"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="mhrw",
            target_size=0.4,
            output_mode="export",
        )

        # Verify
        assert len(node_ids) == 2
        assert isinstance(metrics, QualityMetrics)

    @pytest.mark.asyncio
    async def test_sample_graph_random_walk_algorithm(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with random_walk algorithm."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["random_walk"].sample = AsyncMock(return_value={"node1"})
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=1,
                original_edges=4,
                sampled_edges=0,
                sampling_ratio=0.2,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="random_walk",
            target_size=0.2,
            output_mode="export",
        )

        # Verify
        assert len(node_ids) == 1

    @pytest.mark.asyncio
    async def test_sample_graph_pattern_algorithm(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with pattern algorithm."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["pattern"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="pattern",
            target_size=0.4,
            output_mode="export",
        )

        # Verify
        assert len(node_ids) == 2

    @pytest.mark.asyncio
    async def test_sample_graph_invalid_algorithm(self, orchestrator, test_tenant_id):
        """Test sample_graph with invalid algorithm."""
        with pytest.raises(ValueError, match="Invalid algorithm"):
            await orchestrator.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="invalid_algo",
                target_size=0.5,
                output_mode="export",
            )

    @pytest.mark.asyncio
    async def test_sample_graph_invalid_output_mode(self, orchestrator, test_tenant_id):
        """Test sample_graph with invalid output mode."""
        with pytest.raises(ValueError, match="Invalid output_mode"):
            await orchestrator.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.5,
                output_mode="invalid_mode",
            )

    @pytest.mark.asyncio
    async def test_sample_graph_invalid_target_size_zero(
        self, orchestrator, test_tenant_id
    ):
        """Test sample_graph with zero target size."""
        with pytest.raises(ValueError, match="target_size must be positive"):
            await orchestrator.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=0.0,
                output_mode="export",
            )

    @pytest.mark.asyncio
    async def test_sample_graph_invalid_target_size_negative(
        self, orchestrator, test_tenant_id
    ):
        """Test sample_graph with negative target size."""
        with pytest.raises(ValueError, match="target_size must be positive"):
            await orchestrator.sample_graph(
                tenant_id=test_tenant_id,
                algorithm="forest_fire",
                target_size=-0.5,
                output_mode="export",
            )

    @pytest.mark.asyncio
    async def test_sample_graph_fraction_target_size(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with fractional target size (< 1.0)."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute with fraction (0.4 = 40% of 5 nodes = 2 nodes)
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=0.4,
            output_mode="export",
        )

        # Verify sampler called with target_node_count=2
        orchestrator.samplers["forest_fire"].sample.assert_awaited_once()
        call_args = orchestrator.samplers["forest_fire"].sample.call_args
        assert call_args[0][1] == 2  # target_node_count

    @pytest.mark.asyncio
    async def test_sample_graph_absolute_target_size(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with absolute target size (>= 1)."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2", "node3"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=3,
                original_edges=4,
                sampled_edges=2,
                sampling_ratio=0.6,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute with absolute count (3 nodes)
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=3.0,
            output_mode="export",
        )

        # Verify sampler called with target_node_count=3
        orchestrator.samplers["forest_fire"].sample.assert_awaited_once()
        call_args = orchestrator.samplers["forest_fire"].sample.call_args
        assert call_args[0][1] == 3  # target_node_count

    @pytest.mark.asyncio
    async def test_sample_graph_delete_mode(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
    ):
        """Test sample_graph with delete output mode."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.operations.delete_non_sampled_nodes = AsyncMock(return_value=3)
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        node_ids, metrics, deleted = await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=0.4,
            output_mode="delete",
        )

        # Verify deletion occurred
        assert deleted == 3
        orchestrator.operations.delete_non_sampled_nodes.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sample_graph_with_progress_callback(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
        mock_progress_callback,
    ):
        """Test sample_graph with progress callback."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )

        # Execute
        await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=0.4,
            output_mode="export",
            progress_callback=mock_progress_callback,
        )

        # Verify progress callback was called
        assert (
            mock_progress_callback.call_count >= 3
        )  # Extracting, Sampling, Calculating

    @pytest.mark.asyncio
    async def test_sample_graph_with_export(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        sample_node_properties,
        temp_output_dir,
    ):
        """Test sample_graph with export to file."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, sample_node_properties)
        )
        orchestrator.samplers["forest_fire"].sample = AsyncMock(
            return_value={"node1", "node2"}
        )
        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=QualityMetrics(
                original_nodes=5,
                sampled_nodes=2,
                original_edges=4,
                sampled_edges=1,
                sampling_ratio=0.4,
                degree_distribution_similarity=0.1,
                clustering_coefficient_diff=0.05,
                connected_components_original=1,
                connected_components_sampled=1,
            )
        )
        orchestrator.exporters["yaml"].export = AsyncMock()

        output_path = str(temp_output_dir / "sample.yaml")

        # Execute
        await orchestrator.sample_graph(
            tenant_id=test_tenant_id,
            algorithm="forest_fire",
            target_size=0.4,
            output_mode="yaml",
            output_path=output_path,
        )

        # Verify export was called
        orchestrator.exporters["yaml"].export.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_sample_yaml(
        self,
        orchestrator,
        sample_node_properties,
        temp_output_dir,
    ):
        """Test export_sample with YAML format."""
        node_ids = {"node1", "node2"}
        sampled_graph = nx.DiGraph()
        sampled_graph.add_edge("node1", "node2")

        orchestrator.exporters["yaml"].export = AsyncMock()
        output_path = str(temp_output_dir / "sample.yaml")

        # Execute
        await orchestrator.export_sample(
            node_ids, sample_node_properties, sampled_graph, "yaml", output_path
        )

        # Verify
        orchestrator.exporters["yaml"].export.assert_awaited_once_with(
            node_ids, sample_node_properties, sampled_graph, output_path
        )

    @pytest.mark.asyncio
    async def test_export_sample_json(
        self, orchestrator, sample_node_properties, temp_output_dir
    ):
        """Test export_sample with JSON format."""
        node_ids = {"node1", "node2"}
        sampled_graph = nx.DiGraph()
        sampled_graph.add_edge("node1", "node2")

        orchestrator.exporters["json"].export = AsyncMock()
        output_path = str(temp_output_dir / "sample.json")

        # Execute
        await orchestrator.export_sample(
            node_ids, sample_node_properties, sampled_graph, "json", output_path
        )

        # Verify
        orchestrator.exporters["json"].export.assert_awaited_once_with(
            node_ids, sample_node_properties, sampled_graph, output_path
        )

    @pytest.mark.asyncio
    async def test_export_sample_neo4j(
        self, orchestrator, sample_node_properties, temp_output_dir
    ):
        """Test export_sample with Neo4j format."""
        node_ids = {"node1", "node2"}
        sampled_graph = nx.DiGraph()
        sampled_graph.add_edge("node1", "node2")

        orchestrator.exporters["neo4j"].export = AsyncMock()
        output_path = str(temp_output_dir / "sample.cypher")

        # Execute
        await orchestrator.export_sample(
            node_ids, sample_node_properties, sampled_graph, "neo4j", output_path
        )

        # Verify
        orchestrator.exporters["neo4j"].export.assert_awaited_once_with(
            node_ids, sample_node_properties, sampled_graph, output_path
        )

    @pytest.mark.asyncio
    @patch("src.services.scale_down.orchestrator.IaCExporter")
    async def test_export_sample_terraform(
        self,
        mock_iac_exporter_class,
        orchestrator,
        sample_node_properties,
        temp_output_dir,
    ):
        """Test export_sample with Terraform format."""
        node_ids = {"node1", "node2"}
        sampled_graph = nx.DiGraph()
        sampled_graph.add_edge("node1", "node2")

        mock_iac_exporter = MagicMock()
        mock_iac_exporter.export = AsyncMock()
        mock_iac_exporter_class.return_value = mock_iac_exporter

        output_path = str(temp_output_dir / "terraform")

        # Execute
        await orchestrator.export_sample(
            node_ids, sample_node_properties, sampled_graph, "terraform", output_path
        )

        # Verify IaCExporter instantiated and called
        mock_iac_exporter_class.assert_called_once_with("terraform")
        mock_iac_exporter.export.assert_awaited_once_with(
            node_ids, sample_node_properties, sampled_graph, output_path
        )

    @pytest.mark.asyncio
    async def test_export_sample_invalid_format(
        self, orchestrator, sample_node_properties, temp_output_dir
    ):
        """Test export_sample with invalid format."""
        node_ids = {"node1", "node2"}
        sampled_graph = nx.DiGraph()

        with pytest.raises(ValueError, match="Unsupported export format"):
            await orchestrator.export_sample(
                node_ids,
                sample_node_properties,
                sampled_graph,
                "invalid_format",
                str(temp_output_dir),
            )

    @pytest.mark.asyncio
    async def test_sample_by_pattern_success(self, orchestrator, test_tenant_id):
        """Test sample_by_pattern with successful pattern matching."""
        criteria = {"type": "Microsoft.Compute/virtualMachines"}
        expected_ids = {"node1", "node4"}

        orchestrator.validate_tenant_exists = AsyncMock(return_value=True)
        orchestrator.samplers["pattern"].sample_by_criteria = AsyncMock(
            return_value=expected_ids
        )

        # Execute
        node_ids = await orchestrator.sample_by_pattern(test_tenant_id, criteria)

        # Verify
        assert node_ids == expected_ids
        orchestrator.validate_tenant_exists.assert_awaited_once_with(test_tenant_id)
        orchestrator.samplers["pattern"].sample_by_criteria.assert_awaited_once_with(
            test_tenant_id, criteria, None
        )

    @pytest.mark.asyncio
    async def test_sample_by_pattern_tenant_not_found(
        self, orchestrator, test_tenant_id
    ):
        """Test sample_by_pattern with non-existent tenant."""
        criteria = {"type": "Microsoft.Compute/virtualMachines"}
        orchestrator.validate_tenant_exists = AsyncMock(return_value=False)

        with pytest.raises(ValueError, match="Tenant .* not found"):
            await orchestrator.sample_by_pattern(test_tenant_id, criteria)

    @pytest.mark.asyncio
    async def test_sample_by_pattern_with_progress_callback(
        self, orchestrator, test_tenant_id, mock_progress_callback
    ):
        """Test sample_by_pattern with progress callback."""
        criteria = {"type": "Microsoft.Compute/virtualMachines"}
        orchestrator.validate_tenant_exists = AsyncMock(return_value=True)
        orchestrator.samplers["pattern"].sample_by_criteria = AsyncMock(
            return_value={"node1"}
        )

        # Execute
        await orchestrator.sample_by_pattern(
            test_tenant_id, criteria, mock_progress_callback
        )

        # Verify callback passed through
        orchestrator.samplers["pattern"].sample_by_criteria.assert_awaited_once_with(
            test_tenant_id, criteria, mock_progress_callback
        )

    @pytest.mark.asyncio
    async def test_discover_motifs_success(
        self, orchestrator, test_tenant_id, sample_networkx_graph
    ):
        """Test discover_motifs with successful motif discovery."""
        expected_motifs = [{"node1", "node2", "node5"}]

        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, {})
        )
        orchestrator.operations.discover_motifs = AsyncMock(
            return_value=expected_motifs
        )

        # Execute
        motifs = await orchestrator.discover_motifs(
            test_tenant_id, motif_size=3, max_motifs=10
        )

        # Verify
        assert motifs == expected_motifs
        orchestrator.operations.discover_motifs.assert_awaited_once_with(
            sample_networkx_graph, 3, 10, None
        )

    @pytest.mark.asyncio
    async def test_discover_motifs_with_progress_callback(
        self,
        orchestrator,
        test_tenant_id,
        sample_networkx_graph,
        mock_progress_callback,
    ):
        """Test discover_motifs with progress callback."""
        orchestrator.extractor.extract_graph = AsyncMock(
            return_value=(sample_networkx_graph, {})
        )
        orchestrator.operations.discover_motifs = AsyncMock(return_value=[])

        # Execute
        await orchestrator.discover_motifs(
            test_tenant_id,
            motif_size=3,
            max_motifs=10,
            progress_callback=mock_progress_callback,
        )

        # Verify callback passed through extraction and discovery
        orchestrator.extractor.extract_graph.assert_awaited_once()
        orchestrator.operations.discover_motifs.assert_awaited_once_with(
            sample_networkx_graph, 3, 10, mock_progress_callback
        )

    # Backward compatibility tests
    @pytest.mark.asyncio
    async def test_sample_mhrw_backward_compatibility(
        self, orchestrator, sample_networkx_graph
    ):
        """Test _sample_mhrw backward compatibility wrapper."""
        target_count = 2
        expected_result = ["node1", "node2"]

        orchestrator.samplers["mhrw"].sample = AsyncMock(return_value=expected_result)

        # Execute
        result = await orchestrator._sample_mhrw(sample_networkx_graph, target_count)

        # Verify
        assert result == expected_result
        orchestrator.samplers["mhrw"].sample.assert_awaited_once_with(
            sample_networkx_graph, target_count, None
        )

    @pytest.mark.asyncio
    async def test_sample_random_walk_backward_compatibility(
        self, orchestrator, sample_networkx_graph
    ):
        """Test _sample_random_walk backward compatibility wrapper."""
        target_count = 3
        expected_result = ["node1", "node2", "node3"]

        orchestrator.samplers["random_walk"].sample = AsyncMock(
            return_value=expected_result
        )

        # Execute
        result = await orchestrator._sample_random_walk(
            sample_networkx_graph, target_count
        )

        # Verify
        assert result == expected_result
        orchestrator.samplers["random_walk"].sample.assert_awaited_once_with(
            sample_networkx_graph, target_count, None
        )

    def test_calculate_quality_metrics_backward_compatibility(
        self, orchestrator, sample_networkx_graph
    ):
        """Test _calculate_quality_metrics backward compatibility wrapper."""
        sampled_graph = nx.DiGraph()
        sampled_graph.add_edge("node1", "node2")

        expected_metrics = QualityMetrics(
            original_nodes=5,
            sampled_nodes=2,
            original_edges=4,
            sampled_edges=1,
            sampling_ratio=0.4,
            degree_distribution_similarity=0.1,
            clustering_coefficient_diff=0.05,
            connected_components_original=1,
            connected_components_sampled=1,
        )

        orchestrator.metrics_calculator.calculate_metrics = MagicMock(
            return_value=expected_metrics
        )

        # Execute with minimal parameters
        result = orchestrator._calculate_quality_metrics(
            sample_networkx_graph, sampled_graph
        )

        # Verify defaults applied
        assert result == expected_metrics
        call_args = orchestrator.metrics_calculator.calculate_metrics.call_args
        assert call_args[0][2] == {}  # node_properties defaults to {}
        assert call_args[0][3] == {"node1", "node2"}  # sampled_ids from graph nodes
        assert call_args[0][4] == 0.0  # computation_time defaults to 0.0

    def test_calculate_kl_divergence_backward_compatibility(self, orchestrator):
        """Test _calculate_kl_divergence backward compatibility wrapper."""
        dist1 = {0: 10, 1: 20}
        dist2 = {0: 15, 1: 15}

        orchestrator.metrics_calculator._calculate_kl_divergence = MagicMock(
            return_value=0.05
        )

        # Execute
        result = orchestrator._calculate_kl_divergence(dist1, dist2)

        # Verify
        assert result == 0.05
        orchestrator.metrics_calculator._calculate_kl_divergence.assert_called_once_with(
            dist1, dist2
        )

    @pytest.mark.asyncio
    async def test_export_yaml_backward_compatibility(
        self, orchestrator, temp_output_dir
    ):
        """Test _export_yaml backward compatibility wrapper."""
        sampled_ids = ["node1", "node2"]
        node_properties = {"node1": {}, "node2": {}}
        graph = nx.DiGraph()
        output_file = str(temp_output_dir / "test.yaml")

        orchestrator.exporters["yaml"].export = AsyncMock()

        # Execute
        await orchestrator._export_yaml(
            sampled_ids, node_properties, graph, output_file
        )

        # Verify export called with legacy format conversion
        orchestrator.exporters["yaml"].export.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_json_backward_compatibility(
        self, orchestrator, temp_output_dir
    ):
        """Test _export_json backward compatibility wrapper."""
        sampled_ids = ["node1", "node2"]
        node_properties = {"node1": {}, "node2": {}}
        graph = nx.DiGraph()
        output_file = str(temp_output_dir / "test.json")

        orchestrator.exporters["json"].export = AsyncMock()

        # Execute
        await orchestrator._export_json(
            sampled_ids, node_properties, graph, output_file
        )

        # Verify
        orchestrator.exporters["json"].export.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_export_neo4j_backward_compatibility(
        self, orchestrator, temp_output_dir
    ):
        """Test _export_neo4j backward compatibility wrapper."""
        sampled_ids = ["node1", "node2"]
        node_properties = {"node1": {}, "node2": {}}
        graph = nx.DiGraph()
        output_file = str(temp_output_dir / "test.cypher")

        orchestrator.exporters["neo4j"].export = AsyncMock()

        # Execute
        await orchestrator._export_neo4j(
            sampled_ids, node_properties, graph, output_file
        )

        # Verify
        orchestrator.exporters["neo4j"].export.assert_awaited_once()
