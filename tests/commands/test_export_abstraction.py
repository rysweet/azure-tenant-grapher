"""Tests for export-abstraction CLI command (Issue #508).

Test Coverage:
- Help text
- Successful exports (GraphML, JSON, DOT)
- Error handling (invalid tenant, missing files)
- Output formatting
- Flag handling (--no-relationships)

Target: 70% coverage
"""

from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from src.commands.export_abstraction import export_abstraction_command


class TestExportAbstractionCommand:
    """Test suite for export-abstraction CLI command."""

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_export_abstraction_help(self, runner):
        """Test help text displays correctly."""
        result = runner.invoke(export_abstraction_command, ["--help"])

        assert result.exit_code == 0
        assert "Export graph abstraction" in result.output
        assert "graphml" in result.output
        assert "json" in result.output
        assert "dot" in result.output
        assert "--tenant-id" in result.output
        assert "--output" in result.output
        assert "--format" in result.output

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_graphml_success(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test successful GraphML export."""
        # Mock configuration
        mock_get_tenant_id.return_value = "test-tenant"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        # Mock service
        service_instance = Mock()
        service_instance.export_abstraction.return_value = {
            "success": True,
            "format": "graphml",
            "output_path": "test.graphml",
            "node_count": 100,
            "edge_count": 150,
        }
        mock_export_service_class.return_value = service_instance

        # Run command
        result = runner.invoke(
            export_abstraction_command,
            [
                "--tenant-id",
                "test-tenant",
                "--output",
                "test.graphml",
                "--format",
                "graphml",
            ],
        )

        assert result.exit_code == 0
        assert "Export complete" in result.output
        assert "100" in result.output  # node count
        assert "150" in result.output  # edge count
        assert "Gephi" in result.output  # usage tip

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_json_success(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test successful JSON export with D3.js tip."""
        mock_get_tenant_id.return_value = "test-tenant"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        service_instance = Mock()
        service_instance.export_abstraction.return_value = {
            "success": True,
            "format": "json",
            "output_path": "test.json",
            "node_count": 50,
            "edge_count": 75,
        }
        mock_export_service_class.return_value = service_instance

        result = runner.invoke(
            export_abstraction_command,
            ["--tenant-id", "test-tenant", "--output", "test.json", "--format", "json"],
        )

        assert result.exit_code == 0
        assert "Export complete" in result.output
        assert "D3.js" in result.output  # usage tip

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_dot_success(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test successful DOT export with Graphviz tip."""
        mock_get_tenant_id.return_value = "test-tenant"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        service_instance = Mock()
        service_instance.export_abstraction.return_value = {
            "success": True,
            "format": "dot",
            "output_path": "test.dot",
            "node_count": 25,
            "edge_count": 30,
        }
        mock_export_service_class.return_value = service_instance

        result = runner.invoke(
            export_abstraction_command,
            ["--tenant-id", "test-tenant", "--output", "test.dot", "--format", "dot"],
        )

        assert result.exit_code == 0
        assert "Export complete" in result.output
        assert "Graphviz" in result.output  # usage tip
        assert "dot -Tpng" in result.output

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_tenant_not_found(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test export with non-existent tenant."""
        mock_get_tenant_id.return_value = "nonexistent"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        # Mock service to raise error
        service_instance = Mock()
        service_instance.export_abstraction.side_effect = ValueError(
            "No abstraction found"
        )
        mock_export_service_class.return_value = service_instance

        result = runner.invoke(
            export_abstraction_command,
            ["--tenant-id", "nonexistent", "--output", "test.graphml"],
        )

        assert result.exit_code == 1
        assert "Error" in result.output

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_no_relationships(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test export with --no-relationships flag."""
        mock_get_tenant_id.return_value = "test-tenant"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        service_instance = Mock()
        service_instance.export_abstraction.return_value = {
            "success": True,
            "format": "graphml",
            "output_path": "test.graphml",
            "node_count": 100,
            "edge_count": 0,  # No edges
        }
        mock_export_service_class.return_value = service_instance

        result = runner.invoke(
            export_abstraction_command,
            [
                "--tenant-id",
                "test-tenant",
                "--output",
                "test.graphml",
                "--no-relationships",
            ],
        )

        assert result.exit_code == 0
        assert "Export complete" in result.output
        assert "Edges: 0" in result.output

        # Verify include_relationships=False was passed
        service_instance.export_abstraction.assert_called_once()
        call_args = service_instance.export_abstraction.call_args
        assert call_args[1]["include_relationships"] is False

    @patch("src.commands.export_abstraction.GraphExportService")
    @patch("src.commands.export_abstraction.Neo4jSessionManager")
    @patch("src.commands.export_abstraction.get_neo4j_config_from_env")
    @patch("src.commands.export_abstraction.get_tenant_id")
    def test_export_abstraction_unexpected_error(
        self,
        mock_get_tenant_id,
        mock_get_neo4j_config,
        mock_session_manager_class,
        mock_export_service_class,
        runner,
    ):
        """Test handling of unexpected errors."""
        mock_get_tenant_id.return_value = "test-tenant"
        mock_get_neo4j_config.return_value = (
            "bolt://localhost:7687",
            "neo4j",
            "password",
        )

        # Mock unexpected error
        service_instance = Mock()
        service_instance.export_abstraction.side_effect = RuntimeError(
            "Unexpected error"
        )
        mock_export_service_class.return_value = service_instance

        result = runner.invoke(
            export_abstraction_command,
            ["--tenant-id", "test-tenant", "--output", "test.graphml"],
        )

        assert result.exit_code == 1
        assert "Unexpected error" in result.output

    def test_export_abstraction_missing_output(self, runner):
        """Test that --output is required."""
        result = runner.invoke(
            export_abstraction_command, ["--tenant-id", "test-tenant"]
        )

        assert result.exit_code != 0
        assert "Missing option" in result.output or "required" in result.output.lower()
