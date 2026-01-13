"""Tests for Terraform deployment operations."""

from unittest.mock import MagicMock, patch

import pytest

from src.deployment.terraform_deployer import deploy_terraform


class TestDeployTerraform:
    """Tests for Terraform deployment."""

    @patch("src.deployment.terraform_deployer.subprocess.run")
    def test_deploy_terraform_init_failure(self, mock_run, tmp_path):
        """Test Terraform deployment when init fails."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock terraform init failure
        mock_run.return_value = MagicMock(returncode=1, stderr="Init failed")

        with pytest.raises(RuntimeError, match="Terraform init failed"):
            deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.terraform_deployer.subprocess.run")
    def test_deploy_terraform_dry_run_success(self, mock_run, tmp_path):
        """Test Terraform dry-run deployment."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock successful init and plan
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init successful", stderr=""),
            MagicMock(returncode=0, stdout="Plan output", stderr=""),
        ]

        result = deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=True)

        assert result["status"] == "planned"
        assert result["format"] == "terraform"
        assert "Plan output" in result["output"]
        assert mock_run.call_count == 2

    @patch("src.deployment.terraform_deployer.subprocess.run")
    def test_deploy_terraform_plan_failure(self, mock_run, tmp_path):
        """Test Terraform deployment when plan fails."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock successful init but failed plan
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init successful", stderr=""),
            MagicMock(returncode=1, stderr="Plan failed"),
        ]

        with pytest.raises(RuntimeError, match="Terraform plan failed"):
            deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=True)

    @patch("src.deployment.terraform_deployer.subprocess.run")
    def test_deploy_terraform_apply_success(self, mock_run, tmp_path):
        """Test successful Terraform apply."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock successful init and apply
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init successful", stderr=""),
            MagicMock(returncode=0, stdout="Apply successful", stderr=""),
        ]

        result = deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=False)

        assert result["status"] == "deployed"
        assert result["format"] == "terraform"
        assert "Apply successful" in result["output"]

    @patch("src.deployment.terraform_deployer.subprocess.run")
    def test_deploy_terraform_apply_failure(self, mock_run, tmp_path):
        """Test Terraform deployment when apply fails."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock successful init but failed apply
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="Init successful", stderr=""),
            MagicMock(returncode=1, stderr="Apply failed"),
        ]

        with pytest.raises(RuntimeError, match="Terraform apply failed"):
            deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=False)
