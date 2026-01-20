"""Tests for deploy command AZURE_TENANT_ID .env fallback (Issue #779).

This test verifies that the deploy command respects AZURE_TENANT_ID from .env
like all other commands (scan, spec, mcp).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from src.commands.deploy import deploy_command


class TestDeployEnvFallback:
    """Test deploy command .env fallback for AZURE_TENANT_ID."""

    @pytest.fixture
    def mock_iac_dir(self, tmp_path: Path) -> Path:
        """Create a temporary IaC directory for testing."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()
        # Create a dummy Terraform file to make it a valid IaC directory
        (iac_dir / "main.tf").write_text("# Dummy Terraform file")
        return iac_dir

    @patch("src.commands.deploy.deploy_iac")
    def test_deploy_with_explicit_tenant_id_flag(
        self, mock_deploy_iac: MagicMock, mock_iac_dir: Path
    ):
        """Test that deploy works with explicit --target-tenant-id flag."""
        mock_deploy_iac.return_value = {
            "status": "success",
            "format": "terraform",
            "output": "Deployment successful",
        }

        runner = CliRunner()
        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                str(mock_iac_dir),
                "--target-tenant-id",
                "test-tenant-123",
                "--resource-group",
                "test-rg",
            ],
        )

        assert result.exit_code == 0
        assert "Deployment completed successfully" in result.output
        mock_deploy_iac.assert_called_once()
        # Verify the tenant ID was passed correctly
        call_args = mock_deploy_iac.call_args
        assert call_args[1]["target_tenant_id"] == "test-tenant-123"

    @patch("src.commands.deploy.deploy_iac")
    def test_deploy_with_env_fallback(
        self, mock_deploy_iac: MagicMock, mock_iac_dir: Path
    ):
        """Test that deploy falls back to AZURE_TENANT_ID from environment."""
        mock_deploy_iac.return_value = {
            "status": "success",
            "format": "terraform",
            "output": "Deployment successful",
        }

        runner = CliRunner()
        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                str(mock_iac_dir),
                "--resource-group",
                "test-rg",
            ],
            env={"AZURE_TENANT_ID": "env-tenant-456"},
        )

        assert result.exit_code == 0
        assert "Deployment completed successfully" in result.output
        mock_deploy_iac.assert_called_once()
        # Verify the tenant ID from env was used
        call_args = mock_deploy_iac.call_args
        assert call_args[1]["target_tenant_id"] == "env-tenant-456"

    @patch("src.commands.deploy.deploy_iac")
    def test_deploy_flag_overrides_env(
        self, mock_deploy_iac: MagicMock, mock_iac_dir: Path
    ):
        """Test that explicit --target-tenant-id flag overrides AZURE_TENANT_ID env."""
        mock_deploy_iac.return_value = {
            "status": "success",
            "format": "terraform",
            "output": "Deployment successful",
        }

        runner = CliRunner()
        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                str(mock_iac_dir),
                "--target-tenant-id",
                "flag-tenant-789",
                "--resource-group",
                "test-rg",
            ],
            env={"AZURE_TENANT_ID": "env-tenant-456"},
        )

        assert result.exit_code == 0
        assert "Deployment completed successfully" in result.output
        mock_deploy_iac.assert_called_once()
        # Verify the flag value takes precedence
        call_args = mock_deploy_iac.call_args
        assert call_args[1]["target_tenant_id"] == "flag-tenant-789"

    def test_deploy_error_when_no_tenant_id(self, mock_iac_dir: Path):
        """Test that deploy errors when no tenant ID provided from any source."""
        runner = CliRunner()
        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                str(mock_iac_dir),
                "--resource-group",
                "test-rg",
            ],
            env={},  # No AZURE_TENANT_ID in environment
        )

        assert result.exit_code == 1
        assert "No target tenant ID provided" in result.output
        assert "AZURE_TENANT_ID not set" in result.output
