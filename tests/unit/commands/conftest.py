# tests/unit/commands/conftest.py
"""Shared test fixtures for CLI command testing.

This module provides common mocks and fixtures used across all command tests,
following the project's testing philosophy (ruthless simplicity, no stubs).
"""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from click.testing import CliRunner


@pytest.fixture
def cli_runner():
    """Provide Click CLI test runner."""
    return CliRunner()


@pytest.fixture
def mock_click_context():
    """Provide mocked Click context with obj dict."""
    ctx = MagicMock()
    ctx.obj = {
        "log_level": "INFO",
        "config": None,
    }
    return ctx


@pytest.fixture
def mock_neo4j_config():
    """Provide Neo4j configuration for testing."""
    return {
        "uri": "bolt://localhost:7687",
        "user": "neo4j",
        "password": "test_password",  # pragma: allowlist secret
    }


@pytest.fixture
def mock_azure_credentials(mocker):
    """Mock Azure SDK authentication."""
    mock_cred = mocker.patch("azure.identity.DefaultAzureCredential")
    mock_cred.return_value = MagicMock()
    return mock_cred


@pytest.fixture
def mock_neo4j_session(mocker):
    """Mock Neo4j session manager."""
    mock_session = mocker.patch("src.neo4j_session_manager.Neo4jSessionManager")
    mock_instance = MagicMock()
    mock_session.return_value = mock_instance
    return mock_session


@pytest.fixture
def mock_neo4j_startup(mocker):
    """Mock Neo4j container startup utility."""
    return mocker.patch("src.utils.neo4j_startup.ensure_neo4j_running")


@pytest.fixture
def temp_output_dir():
    """Provide temporary directory for file outputs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_dashboard(mocker):
    """Mock RichDashboard for UI testing."""
    mock_dash = mocker.patch("src.rich_dashboard.RichDashboard")
    mock_instance = MagicMock()
    mock_dash.return_value = mock_instance
    return mock_dash


@pytest.fixture
def mock_dashboard_manager(mocker):
    """Mock CLI Dashboard Manager."""
    mock_manager = mocker.patch("src.cli_dashboard_manager.CLIDashboardManager")
    mock_instance = MagicMock()
    mock_manager.return_value = mock_instance
    return mock_manager


@pytest.fixture
def mock_azure_tenant_grapher(mocker):
    """Mock AzureTenantGrapher for scan testing."""
    mock_grapher = mocker.patch("src.azure_tenant_grapher.AzureTenantGrapher")
    mock_instance = AsyncMock()
    mock_grapher.return_value = mock_instance
    return mock_grapher


@pytest.fixture
def mock_graph_visualizer(mocker):
    """Mock GraphVisualizer for visualize testing."""
    mock_viz = mocker.patch("src.graph_visualizer.GraphVisualizer")
    mock_instance = MagicMock()
    mock_instance.generate_html_visualization.return_value = "/path/to/viz.html"
    mock_viz.return_value = mock_instance
    return mock_viz


@pytest.fixture
def mock_config_from_env(mocker, mock_neo4j_config):
    """Mock config creation from environment."""
    mock_config = mocker.patch("src.config_manager.create_config_from_env")

    class MockConfig:
        class Neo4jConfig:
            uri = mock_neo4j_config["uri"]
            user = mock_neo4j_config["user"]
            password = mock_neo4j_config["password"]

        class LoggingConfig:
            level = "INFO"

        neo4j = Neo4jConfig()
        logging = LoggingConfig()

    mock_config.return_value = MockConfig()
    return mock_config


@pytest.fixture
def mock_neo4j_config_from_env(mocker, mock_neo4j_config):
    """Mock Neo4j-only config creation."""
    mock_config = mocker.patch("src.config_manager.create_neo4j_config_from_env")

    class MockConfig:
        class Neo4jConfig:
            uri = mock_neo4j_config["uri"]
            user = mock_neo4j_config["user"]
            password = mock_neo4j_config["password"]

        class LoggingConfig:
            level = "INFO"

        neo4j = Neo4jConfig()
        logging = LoggingConfig()

    mock_config.return_value = MockConfig()
    return mock_config


@pytest.fixture
def mock_setup_logging(mocker):
    """Mock logging setup."""
    return mocker.patch("src.config_manager.setup_logging")


@pytest.fixture
def mock_version_detector(mocker):
    """Mock version detection for scan tests."""
    mock_detector = mocker.patch("src.version_tracking.detector.VersionDetector")
    mock_instance = MagicMock()
    mock_instance.detect_mismatch.return_value = None  # No mismatch by default
    mock_detector.return_value = mock_instance
    return mock_detector


@pytest.fixture
def mock_graph_metadata_service(mocker):
    """Mock graph metadata service for version tracking."""
    mock_service = mocker.patch("src.version_tracking.metadata.GraphMetadataService")
    mock_instance = MagicMock()
    mock_service.return_value = mock_instance
    return mock_service


@pytest.fixture
def mock_filter_config(mocker):
    """Mock FilterConfig for scan filtering tests."""
    mock_filter = mocker.patch("src.models.filter_config.FilterConfig")
    mock_instance = MagicMock()
    mock_filter.return_value = mock_instance
    return mock_filter


@pytest.fixture
def mock_agent_mode(mocker):
    """Mock agent mode runner for agent command tests."""
    return mocker.patch("src.agent_mode.run_agent_mode", new_callable=AsyncMock)


@pytest.fixture
def sample_tenant_id():
    """Provide sample tenant ID for testing."""
    return "12345678-1234-1234-1234-123456789012"


@pytest.fixture
def mock_deployment_manager(mocker):
    """Mock deployment manager for deploy/undeploy tests."""
    mock_manager = mocker.patch("src.deployment.deployment_manager.DeploymentManager")
    mock_instance = AsyncMock()
    mock_manager.return_value = mock_instance
    return mock_manager


@pytest.fixture
def mock_lighthouse_service(mocker):
    """Mock Azure Lighthouse service for lighthouse tests."""
    mock_service = mocker.patch("src.services.lighthouse_service.LighthouseService")
    mock_instance = AsyncMock()
    mock_service.return_value = mock_instance
    return mock_service


@pytest.fixture
def mock_auth_service(mocker):
    """Mock authentication service for auth tests."""
    mock_service = mocker.patch("src.services.auth_service.AuthService")
    mock_instance = AsyncMock()
    mock_service.return_value = mock_instance
    return mock_service


@pytest.fixture
def mock_mcp_server(mocker):
    """Mock MCP server for MCP command tests."""
    mock_server = mocker.patch("src.mcp_server.MCPServer")
    mock_instance = AsyncMock()
    mock_server.return_value = mock_instance
    return mock_server
