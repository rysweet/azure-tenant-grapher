"""Tests for timeout configuration and handling.

This module tests the centralized timeout configuration including:
- Default timeout values
- Environment variable overrides
- TimeoutError exception
- Logging functions
"""

import os
from unittest.mock import patch

import pytest


class TestTimeoutDefaults:
    """Test default timeout values."""

    def test_quick_timeout_default(self):
        """Test that quick timeout has sensible default."""
        # Import fresh to avoid cached values
        with patch.dict(os.environ, {}, clear=True):
            # Force reimport to get fresh values
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.QUICK == 30
            assert tc.Timeouts.HEALTH_CHECK == 10

    def test_standard_timeout_default(self):
        """Test that standard timeout has sensible default."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.STANDARD == 60
            assert tc.Timeouts.AZ_CLI_QUERY == 60
            assert tc.Timeouts.DOCKER_COMMAND == 60

    def test_init_timeout_default(self):
        """Test that init timeout has sensible default."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.INIT == 120
            assert tc.Timeouts.TERRAFORM_INIT == 120

    def test_build_timeout_default(self):
        """Test that build timeout has sensible default."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.BUILD == 300
            assert tc.Timeouts.TERRAFORM_PLAN == 300

    def test_deploy_timeout_default(self):
        """Test that deploy timeout has sensible default."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.DEPLOY == 1800
            assert tc.Timeouts.TERRAFORM_APPLY == 1800

    def test_neo4j_timeout_defaults(self):
        """Test that Neo4j timeouts have sensible defaults."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.NEO4J_CONNECTION == 30
            assert tc.Timeouts.NEO4J_QUERY == 60
            assert tc.Timeouts.NEO4J_TRANSACTION == 120


class TestEnvironmentOverrides:
    """Test environment variable overrides."""

    def test_quick_timeout_override(self):
        """Test that QUICK timeout can be overridden via env var."""
        with patch.dict(os.environ, {"ATG_TIMEOUT_QUICK": "45"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.QUICK == 45

    def test_deploy_timeout_override(self):
        """Test that DEPLOY timeout can be overridden via env var."""
        with patch.dict(os.environ, {"ATG_TIMEOUT_DEPLOY": "3600"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.DEPLOY == 3600

    def test_invalid_timeout_uses_default(self):
        """Test that invalid timeout value falls back to default."""
        with patch.dict(os.environ, {"ATG_TIMEOUT_QUICK": "not_a_number"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.QUICK == 30  # Falls back to default

    def test_negative_timeout_uses_default(self):
        """Test that negative timeout value falls back to default."""
        with patch.dict(os.environ, {"ATG_TIMEOUT_QUICK": "-10"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.QUICK == 30  # Falls back to default

    def test_zero_timeout_uses_default(self):
        """Test that zero timeout value falls back to default."""
        with patch.dict(os.environ, {"ATG_TIMEOUT_QUICK": "0"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            assert tc.Timeouts.QUICK == 30  # Falls back to default


class TestTimeoutError:
    """Test custom TimeoutError exception."""

    def test_basic_timeout_error(self):
        """Test basic TimeoutError creation."""
        from src.timeout_config import TimeoutError as ATGTimeoutError

        err = ATGTimeoutError("Operation failed")
        assert str(err) == "Operation failed"
        assert err.operation is None
        assert err.timeout_value is None
        assert err.command is None

    def test_timeout_error_with_context(self):
        """Test TimeoutError with full context."""
        from src.timeout_config import TimeoutError as ATGTimeoutError

        err = ATGTimeoutError(
            "Terraform apply failed",
            operation="terraform_apply",
            timeout_value=1800,
            command=["terraform", "apply", "-auto-approve"],
        )

        assert "terraform_apply" in str(err)
        assert "1800s" in str(err)
        assert "terraform apply" in str(err)

    def test_timeout_error_with_long_command_truncation(self):
        """Test that long commands are truncated in error message."""
        from src.timeout_config import TimeoutError as ATGTimeoutError

        long_command = ["some_cmd"] + ["arg"] * 100
        err = ATGTimeoutError(
            "Command failed",
            command=long_command,
        )

        error_str = str(err)
        assert len(error_str) < 200  # Should be reasonably short
        assert "..." in error_str  # Should be truncated


class TestLogTimeoutEvent:
    """Test timeout event logging."""

    def test_log_timeout_event_basic(self, caplog):
        """Test basic timeout event logging."""
        from src.timeout_config import log_timeout_event

        with caplog.at_level("WARNING"):
            log_timeout_event("test_operation", 30)

        assert "test_operation" in caplog.text
        assert "30 seconds" in caplog.text
        assert "timed out" in caplog.text

    def test_log_timeout_event_with_command(self, caplog):
        """Test timeout event logging with command."""
        from src.timeout_config import log_timeout_event

        with caplog.at_level("WARNING"):
            log_timeout_event("terraform_init", 120, ["terraform", "init"])

        assert "terraform_init" in caplog.text
        assert "120 seconds" in caplog.text
        assert "terraform init" in caplog.text

    def test_log_timeout_event_different_levels(self, caplog):
        """Test timeout event logging at different levels."""
        from src.timeout_config import log_timeout_event

        with caplog.at_level("DEBUG"):
            log_timeout_event("debug_op", 10, level="debug")

        assert "debug_op" in caplog.text


class TestGetTimeoutFunction:
    """Test the _get_timeout helper function."""

    def test_get_timeout_with_valid_env(self):
        """Test _get_timeout returns env value when valid."""
        with patch.dict(os.environ, {"TEST_TIMEOUT": "100"}):
            from src.timeout_config import _get_timeout

            result = _get_timeout("TEST_TIMEOUT", 50)
            assert result == 100

    def test_get_timeout_with_missing_env(self):
        """Test _get_timeout returns default when env not set."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure the env var doesn't exist
            os.environ.pop("NONEXISTENT_TIMEOUT", None)
            from src.timeout_config import _get_timeout

            result = _get_timeout("NONEXISTENT_TIMEOUT", 50)
            assert result == 50

    def test_get_timeout_with_invalid_string(self):
        """Test _get_timeout returns default for non-numeric string."""
        with patch.dict(os.environ, {"BAD_TIMEOUT": "abc"}):
            from src.timeout_config import _get_timeout

            result = _get_timeout("BAD_TIMEOUT", 50)
            assert result == 50


class TestSubprocessTimeoutIntegration:
    """Integration tests for subprocess timeout handling."""

    def test_subprocess_respects_timeout(self):
        """Test that subprocess.run respects our timeout values."""
        import subprocess

        # Use a short timeout for testing
        with patch.dict(os.environ, {"ATG_TIMEOUT_QUICK": "1"}):
            import importlib

            import src.timeout_config as tc

            importlib.reload(tc)

            # This should timeout quickly
            with pytest.raises(subprocess.TimeoutExpired):
                subprocess.run(
                    ["sleep", "10"],
                    timeout=tc.Timeouts.QUICK,
                )

    def test_successful_command_within_timeout(self):
        """Test that successful commands complete within timeout."""
        import subprocess

        from src.timeout_config import Timeouts

        # This should complete quickly
        result = subprocess.run(
            ["echo", "hello"],
            capture_output=True,
            text=True,
            timeout=Timeouts.QUICK,
        )

        assert result.returncode == 0
        assert "hello" in result.stdout
