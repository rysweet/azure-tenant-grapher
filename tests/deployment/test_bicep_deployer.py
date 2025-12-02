"""Tests for Bicep deployment operations."""

from unittest.mock import MagicMock, patch

import pytest

from src.deployment.bicep_deployer import deploy_bicep


class TestDeployBicep:
    """Tests for Bicep deployment."""

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_no_files(self, mock_run, tmp_path):
        """Test Bicep deployment with no bicep files."""
        with pytest.raises(RuntimeError, match="No Bicep files found"):
            deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_dry_run_success(self, mock_run, tmp_path):
        """Test Bicep dry-run deployment."""
        (tmp_path / "main.bicep").write_text(
            "resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )

        # Mock successful validation
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Validation successful", stderr=""
        )

        result = deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=True)

        assert result["status"] == "validated"
        assert result["format"] == "bicep"
        assert "Validation successful" in result["output"]

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_validation_failure(self, mock_run, tmp_path):
        """Test Bicep deployment when validation fails."""
        (tmp_path / "main.bicep").write_text("invalid bicep")

        # Mock validation failure
        mock_run.return_value = MagicMock(returncode=1, stderr="Validation failed")

        with pytest.raises(RuntimeError, match="Bicep validation failed"):
            deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=True)

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_deploy_success(self, mock_run, tmp_path):
        """Test successful Bicep deployment."""
        (tmp_path / "main.bicep").write_text(
            "resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )

        # Mock successful deployment
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Deployment successful", stderr=""
        )

        result = deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=False)

        assert result["status"] == "deployed"
        assert result["format"] == "bicep"
        assert "Deployment successful" in result["output"]

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_with_subscription(self, mock_run, tmp_path):
        """Test Bicep deployment with subscription ID."""
        (tmp_path / "main.bicep").write_text(
            "resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )

        # Mock successful deployment
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Deployment successful", stderr=""
        )

        result = deploy_bicep(
            tmp_path, "test-rg", "eastus", subscription_id="test-sub-id", dry_run=False
        )

        assert result["status"] == "deployed"
        # Verify subscription was passed in command
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "--subscription" in call_args
        assert "test-sub-id" in call_args

    @patch("src.deployment.bicep_deployer.subprocess.run")
    def test_deploy_bicep_prefers_main_file(self, mock_run, tmp_path):
        """Test that Bicep deployment prefers main.bicep over other files."""
        (tmp_path / "other.bicep").write_text(
            "resource rg1 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )
        (tmp_path / "main.bicep").write_text(
            "resource rg2 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )

        # Mock successful deployment
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Deployment successful", stderr=""
        )

        deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=False)

        # Verify main.bicep was used
        call_args = mock_run.call_args[0][0]
        assert "main.bicep" in str(call_args)
