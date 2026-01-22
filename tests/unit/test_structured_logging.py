"""
Tests for structured logging behavior in production code.

This test suite verifies that debug print statements have been replaced
with proper structlog logger calls that respect the --debug CLI flag.
"""

import logging
from unittest.mock import patch


class TestContainerManagerLogging:
    """Test logging behavior in container_manager.py"""

    @patch("src.container_manager.logger")
    def test_neo4j_env_debug_logging(self, mock_logger):
        """Verify Neo4j environment logging uses structured logger."""
        from src.container_manager import Neo4jContainerManager

        # Create manager with debug enabled
        with patch("src.container_manager.docker.from_env"), patch.dict(
            "os.environ", {"NEO4J_PORT": "7687"}
        ):
            __manager = Neo4jContainerManager(debug=True)

        # Verify logger.debug was called (not print)
        assert mock_logger.debug.called, (
            "logger.debug should be called for Neo4j environment info"
        )

    @patch("src.container_manager.logger")
    def test_neo4j_config_debug_logging(self, mock_logger):
        """Verify Neo4j config logging uses structured logger."""
        from src.container_manager import Neo4jContainerManager

        # Create manager with debug enabled
        with patch("src.container_manager.docker.from_env"), patch.dict(
            "os.environ", {"NEO4J_PORT": "7687"}
        ):
            _manager = Neo4jContainerManager(debug=True)

        # Verify logger.debug was called for configuration
        assert mock_logger.debug.called, (
            "logger.debug should be called for Neo4j config"
        )
        # Check that we logged configuration details
        calls = [str(call) for call in mock_logger.debug.call_args_list]
        assert any(
            "uri" in str(call) or "config" in str(call).lower() for call in calls
        ), "Should log Neo4j configuration details"

    @patch("src.container_manager.logger")
    def test_no_print_statements_in_debug_mode(self, mock_logger, capsys):
        """Verify no raw print statements bypass logger in debug mode."""
        from src.container_manager import Neo4jContainerManager

        # Create manager with debug enabled
        with patch("src.container_manager.docker.from_env"), patch.dict(
            "os.environ", {"NEO4J_PORT": "7687"}
        ):
            _manager = Neo4jContainerManager(debug=True)

        # Capture any stdout output
        captured = capsys.readouterr()

        # Should NOT have [DEBUG] prefix print statements
        assert "[DEBUG][Neo4jEnv]" not in captured.out, (
            "Raw print with [DEBUG] prefix should be replaced with logger"
        )
        assert "[DEBUG][Neo4jConfig]" not in captured.out, (
            "Raw print with [DEBUG] prefix should be replaced with logger"
        )


class TestConfigManagerLogging:
    """Test logging behavior in config_manager.py"""

    @patch("src.config_manager.logger")
    def test_config_debug_logging(self, mock_logger):
        """Verify config manager uses structured logger for debug output."""
        from src.config_manager import AzureTenantGrapherConfig

        # Create config with debug=True
        with patch.dict(
            "os.environ",
            {
                "NEO4J_PORT": "7687",
                "NEO4J_PASSWORD": "test-password",  # pragma: allowlist secret
            },
        ):
            _config = AzureTenantGrapherConfig.from_environment(
                tenant_id="test-tenant-id", debug=True
            )

        # Verify logger.debug was called (not print)
        assert mock_logger.debug.called, (
            "logger.debug should be called for config debug info"
        )

    @patch("src.config_manager.logger")
    def test_no_print_in_config_debug(self, mock_logger, capsys):
        """Verify config manager doesn't use print statements in debug mode."""
        from src.config_manager import AzureTenantGrapherConfig

        with patch.dict(
            "os.environ",
            {
                "NEO4J_PORT": "7687",
                "NEO4J_PASSWORD": "test-password",  # pragma: allowlist secret
            },
        ):
            _config = AzureTenantGrapherConfig.from_environment(
                tenant_id="test-tenant-id", debug=True
            )

        captured = capsys.readouterr()

        # Should NOT have [DEBUG] prefix print statements
        assert "[DEBUG][Neo4jConfig]" not in captured.out, (
            "Raw print with [DEBUG] prefix should be replaced with logger"
        )


class TestLoggingRespectDebugFlag:
    """Test that logger respects --debug CLI flag (log level control)"""

    def test_debug_messages_at_debug_level(self, caplog):
        """Verify logger.debug() messages appear at DEBUG log level."""
        import structlog

        logger = structlog.get_logger(__name__)

        with caplog.at_level(logging.DEBUG):
            logger.debug("test debug message", key="value")
            assert "test debug message" in caplog.text

    def test_debug_messages_hidden_at_info_level(self, caplog):
        """Verify logger.debug() messages hidden at INFO log level."""
        import structlog

        logger = structlog.get_logger(__name__)

        with caplog.at_level(logging.INFO):
            logger.debug("debug message should be hidden")
            assert "debug message should be hidden" not in caplog.text


class TestSensitiveDataRedaction:
    """Test that sensitive data is redacted in logs"""

    @patch("src.container_manager.logger")
    def test_password_redaction_in_environ(self, mock_logger):
        """Verify passwords are redacted in environment logging."""
        from src.container_manager import Neo4jContainerManager

        with patch("src.container_manager.docker.from_env"), patch.dict(
            "os.environ",
            {
                "NEO4J_PASSWORD": "supersecret123",  # pragma: allowlist secret
                "NEO4J_PORT": "7687",
                "REGULAR_VAR": "safe_value",
            },
        ):
            _manager = Neo4jContainerManager(debug=True)

        # Verify logger was called
        assert mock_logger.debug.called

        # Check that sensitive values were redacted
        all_calls = str(mock_logger.debug.call_args_list)
        assert "supersecret123" not in all_calls, "Password should be redacted in logs"
        assert "***REDACTED***" in all_calls or "PASSWORD" not in all_calls, (
            "Sensitive env vars should be redacted or not logged"
        )
