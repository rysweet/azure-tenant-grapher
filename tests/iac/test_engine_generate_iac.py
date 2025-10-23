"""Tests for the generate_iac method in TransformationEngine."""

from unittest.mock import Mock

import pytest

from src.iac.engine import TransformationEngine
from src.iac.subset import SubsetFilter
from src.iac.traverser import TenantGraph


class TestTransformationEngineGenerateIac:
    """Test TransformationEngine.generate_iac method."""

    @pytest.fixture
    def sample_graph(self):
        """Create a sample tenant graph for testing."""
        resources = [
            {
                "id": "storage1",
                "type": "Microsoft.Storage/storageAccounts",
                "name": "mystorageaccount",
            },
            {"id": "vm1", "type": "Microsoft.Compute/virtualMachines", "name": "myvm"},
        ]
        relationships = []
        return TenantGraph(resources=resources, relationships=relationships)

    def test_generate_iac_no_subset_filter(self, sample_graph):
        """Test generate_iac without subset filtering."""
        engine = TransformationEngine()
        mock_emitter = Mock()
        mock_emitter.emit.return_value = ["output1.bicep", "output2.bicep"]

        result = engine.generate_iac(
            graph=sample_graph,
            emitter=mock_emitter,
            out_dir="/tmp/test",
            subset_filter=None,
        )

        # Should return emitter results
        assert result == ["output1.bicep", "output2.bicep"]

        # Should call emitter with full graph
        mock_emitter.emit.assert_called_once()
        called_graph, called_dir = mock_emitter.emit.call_args[0]
        assert len(called_graph.resources) == 2
        assert called_dir == "/tmp/test"

    def test_generate_iac_with_subset_filter(self, sample_graph):
        """Test generate_iac with subset filtering."""
        engine = TransformationEngine()
        mock_emitter = Mock()
        mock_emitter.emit.return_value = ["output1.bicep"]

        # Create filter for storage accounts only
        subset_filter = SubsetFilter(resource_types=["Microsoft.Storage/*"])

        result = engine.generate_iac(
            graph=sample_graph,
            emitter=mock_emitter,
            out_dir="/tmp/test",
            subset_filter=subset_filter,
        )

        # Should return emitter results
        assert result == ["output1.bicep"]

        # Should call emitter with filtered graph
        mock_emitter.emit.assert_called_once()
        called_graph, called_dir = mock_emitter.emit.call_args[0]
        assert len(called_graph.resources) == 1
        assert called_graph.resources[0]["id"] == "storage1"
        assert called_dir == "/tmp/test"

    def test_generate_iac_with_empty_subset_filter(self, sample_graph):
        """Test generate_iac with empty subset filter (should not filter)."""
        engine = TransformationEngine()
        mock_emitter = Mock()
        mock_emitter.emit.return_value = ["output1.bicep", "output2.bicep"]

        # Create empty filter
        subset_filter = SubsetFilter()

        result = engine.generate_iac(
            graph=sample_graph,
            emitter=mock_emitter,
            out_dir="/tmp/test",
            subset_filter=subset_filter,
        )

        # Should return emitter results
        assert result == ["output1.bicep", "output2.bicep"]

        # Should call emitter with full graph (no filtering)
        mock_emitter.emit.assert_called_once()
        called_graph, called_dir = mock_emitter.emit.call_args[0]
        assert len(called_graph.resources) == 2
        assert called_dir == "/tmp/test"

    def test_generate_iac_applies_transformation_rules(self, sample_graph):
        """Test that generate_iac applies transformation rules to resources."""
        # Create engine with mock rules file
        engine = TransformationEngine()

        # Mock the apply method to add a prefix
        original_apply = engine.apply

        def mock_apply(resource):
            result = original_apply(resource)
            result["name"] = f"transformed-{result['name']}"
            return result

        engine.apply = mock_apply

        mock_emitter = Mock()
        mock_emitter.emit.return_value = ["output.bicep"]

        # Disable name generation and other transformers to test only the apply() method
        engine.generate_iac(
            graph=sample_graph,
            emitter=mock_emitter,
            out_dir="/tmp/test",
            subset_filter=None,
            enable_name_generation=False,
            enable_location_mapping=False,
            enable_bastion_nsg_rules=False,
            enable_vnet_link_validation=False,
            enable_cross_tenant_filter=False,
        )

        # Should call emitter with transformed resources
        mock_emitter.emit.assert_called_once()
        called_graph, called_dir = mock_emitter.emit.call_args[0]

        # Resources should be transformed
        assert len(called_graph.resources) == 2
        assert called_graph.resources[0]["name"] == "transformed-mystorageaccount"
        assert called_graph.resources[1]["name"] == "transformed-myvm"
