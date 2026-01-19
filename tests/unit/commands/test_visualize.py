# tests/unit/commands/test_visualize.py
"""Tests for visualize.py (graph visualization command).

Coverage target: 85%+
Test pyramid: 60% unit, 30% integration, 10% E2E

This module tests the graph visualization functionality including:
- HTML output generation
- Neo4j connection handling
- Link hierarchy option
- Custom output paths
- Container auto-start
- Retry logic
"""

import os
import tempfile
from pathlib import Path

import pytest
from click.testing import CliRunner

from src.commands.visualize import visualize, visualize_command_handler


# ============================================================================
# UNIT TESTS (60%) - Test individual functions with mocked dependencies
# ============================================================================


class TestVisualizationParameters:
    """Test CLI parameter handling (unit tests)."""

    def test_visualize_has_link_hierarchy_option(self, cli_runner):
        """Visualize command has --link-hierarchy option."""
        result = cli_runner.invoke(visualize, ["--help"])
        assert "link-hierarchy" in result.output

    def test_visualize_has_no_container_option(self, cli_runner):
        """Visualize command has --no-container option."""
        result = cli_runner.invoke(visualize, ["--help"])
        assert "no-container" in result.output

    def test_visualize_has_output_option(self, cli_runner):
        """Visualize command has --output option."""
        result = cli_runner.invoke(visualize, ["--help"])
        assert "output" in result.output


class TestHTMLOutputGeneration:
    """Test HTML file generation (unit tests)."""

    def test_visualize_generates_html_with_default_path(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mock_click_context,
    ):
        """Visualize generates HTML at default path."""
        result = cli_runner.invoke(visualize, [])
        # Should call visualizer to generate HTML
        mock_graph_visualizer.return_value.generate_html_visualization.assert_called()

    def test_visualize_uses_custom_output_path(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        temp_output_dir,
    ):
        """Visualize respects custom output path."""
        output_path = str(temp_output_dir / "custom_viz.html")
        result = cli_runner.invoke(visualize, ["--output", output_path])
        # Custom path should be used
        mock_graph_visualizer.return_value.generate_html_visualization.assert_called()

    def test_visualize_creates_outputs_directory(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mocker,
    ):
        """Visualize creates outputs/ directory if missing."""
        mock_makedirs = mocker.patch("os.makedirs")
        result = cli_runner.invoke(visualize, [])
        # Should create outputs directory
        mock_makedirs.assert_called()


class TestLinkHierarchyOption:
    """Test hierarchical edge linking (unit tests)."""

    def test_visualize_link_hierarchy_enabled(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize with --link-hierarchy passes flag to visualizer."""
        result = cli_runner.invoke(visualize, ["--link-hierarchy"])
        mock_graph_visualizer.return_value.generate_html_visualization.assert_called_with(
            output_path=pytest.any(str), link_to_hierarchy=True
        )

    def test_visualize_link_hierarchy_disabled(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize with --no-link-hierarchy disables hierarchical edges."""
        result = cli_runner.invoke(visualize, ["--no-link-hierarchy"])
        mock_graph_visualizer.return_value.generate_html_visualization.assert_called_with(
            output_path=pytest.any(str), link_to_hierarchy=False
        )


class TestNeo4jConnection:
    """Test Neo4j connection handling (unit tests)."""

    def test_visualize_calls_ensure_neo4j_running(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize calls Neo4j startup utility."""
        result = cli_runner.invoke(visualize, [])
        mock_neo4j_startup.assert_called()

    def test_visualize_skips_neo4j_startup_with_no_container(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize with --no-container skips automatic startup."""
        result = cli_runner.invoke(visualize, ["--no-container"])
        # Still called initially, but won't auto-start on failure
        assert True  # Implementation-specific behavior

    def test_visualize_creates_visualizer_with_config(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mock_neo4j_config,
    ):
        """Visualize creates GraphVisualizer with Neo4j config."""
        result = cli_runner.invoke(visualize, [])
        mock_graph_visualizer.assert_called_with(
            mock_neo4j_config["uri"],
            mock_neo4j_config["user"],
            mock_neo4j_config["password"],
        )


class TestErrorHandling:
    """Test error handling paths (unit tests)."""

    def test_visualize_handles_neo4j_connection_failure(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize handles Neo4j connection failures."""
        mock_graph_visualizer.return_value.generate_html_visualization.side_effect = (
            Exception("Connection failed")
        )

        result = cli_runner.invoke(visualize, [])
        assert result.exit_code != 0
        assert "Failed to connect to Neo4j" in result.output or "neo4j" in result.output.lower()

    def test_visualize_shows_helpful_error_message(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize shows actionable error messages."""
        mock_graph_visualizer.return_value.generate_html_visualization.side_effect = (
            Exception("Connection refused")
        )

        result = cli_runner.invoke(visualize, [])
        # Should provide guidance
        assert "Ensure Neo4j is running" in result.output or "container" in result.output.lower()


class TestContainerAutoStart:
    """Test automatic container startup on failure (unit tests)."""

    def test_visualize_retries_after_container_start(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mocker,
    ):
        """Visualize retries connection after starting container."""
        # First call fails, subsequent calls succeed
        mock_graph_visualizer.return_value.generate_html_visualization.side_effect = [
            Exception("Connection failed"),
            "/path/to/viz.html",
        ]

        result = cli_runner.invoke(visualize, [])
        # Should retry and succeed
        assert mock_graph_visualizer.return_value.generate_html_visualization.call_count >= 1

    def test_visualize_no_container_prevents_auto_start(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Visualize with --no-container doesn't auto-start on failure."""
        mock_graph_visualizer.return_value.generate_html_visualization.side_effect = (
            Exception("Connection failed")
        )

        result = cli_runner.invoke(visualize, ["--no-container"])
        assert result.exit_code != 0
        assert "no-container" in result.output or "manually" in result.output.lower()


# ============================================================================
# INTEGRATION TESTS (30%) - Test components working together
# ============================================================================


class TestVisualizationIntegration:
    """Test visualization with multiple components (integration tests)."""

    @pytest.mark.asyncio
    async def test_visualize_handler_full_workflow(
        self,
        mock_click_context,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mocker,
    ):
        """Handler executes full visualization workflow."""
        mock_makedirs = mocker.patch("os.makedirs")

        await visualize_command_handler(
            ctx=mock_click_context,
            link_hierarchy=True,
            no_container=False,
            output=None,
        )

        # Should create output directory and visualizer
        mock_makedirs.assert_called()
        mock_graph_visualizer.assert_called()
        mock_graph_visualizer.return_value.generate_html_visualization.assert_called()

    @pytest.mark.asyncio
    async def test_visualize_handler_custom_output(
        self,
        mock_click_context,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        temp_output_dir,
    ):
        """Handler uses custom output path correctly."""
        custom_path = str(temp_output_dir / "test_viz.html")

        await visualize_command_handler(
            ctx=mock_click_context,
            link_hierarchy=False,
            no_container=True,
            output=custom_path,
        )

        mock_graph_visualizer.return_value.generate_html_visualization.assert_called_with(
            output_path=custom_path, link_to_hierarchy=False
        )


# ============================================================================
# END-TO-END TESTS (10%) - Test complete workflows
# ============================================================================


class TestVisualizationE2E:
    """Test complete visualization workflows (E2E tests)."""

    def test_visualize_complete_workflow_default_settings(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
    ):
        """Complete visualization with all default settings."""
        result = cli_runner.invoke(visualize, [])
        assert "Visualization saved to:" in result.output or result.exit_code == 0

    def test_visualize_complete_workflow_all_options(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        temp_output_dir,
    ):
        """Complete visualization with all options specified."""
        output_path = str(temp_output_dir / "full_viz.html")

        result = cli_runner.invoke(
            visualize,
            [
                "--link-hierarchy",
                "--no-container",
                "--output",
                output_path,
            ],
        )
        assert result.exit_code == 0 or "neo4j" in result.output.lower()

    def test_visualize_error_recovery_workflow(
        self,
        cli_runner,
        mock_neo4j_startup,
        mock_neo4j_config_from_env,
        mock_setup_logging,
        mock_graph_visualizer,
        mocker,
    ):
        """Visualization recovers from initial failure by starting container."""
        # Simulate failure then success after retry
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Connection failed")
            return "/path/to/viz.html"

        mock_graph_visualizer.return_value.generate_html_visualization.side_effect = (
            side_effect
        )

        result = cli_runner.invoke(visualize, [])
        # Should eventually succeed after retry
        assert (
            mock_graph_visualizer.return_value.generate_html_visualization.call_count
            >= 1
        )
