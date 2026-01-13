"""Tests for ARM template deployment operations."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.deployment.arm_deployer import deploy_arm


class TestDeployARM:
    """Tests for ARM template deployment."""

    @patch("src.deployment.arm_deployer.subprocess.run")
    def test_deploy_arm_no_templates(self, mock_run, tmp_path):
        """Test ARM deployment with no template files."""
        with pytest.raises(RuntimeError, match="No ARM template files found"):
            deploy_arm(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.arm_deployer.subprocess.run")
    def test_deploy_arm_dry_run_success(self, mock_run, tmp_path):
        """Test ARM dry-run deployment."""
        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [],
        }
        (tmp_path / "template.json").write_text(json.dumps(arm_template))

        # Mock successful validation
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Validation successful", stderr=""
        )

        result = deploy_arm(tmp_path, "test-rg", "eastus", dry_run=True)

        assert result["status"] == "validated"
        assert result["format"] == "arm"
        assert "Validation successful" in result["output"]

    @patch("src.deployment.arm_deployer.subprocess.run")
    def test_deploy_arm_deploy_success(self, mock_run, tmp_path):
        """Test successful ARM deployment."""
        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [],
        }
        (tmp_path / "template.json").write_text(json.dumps(arm_template))

        # Mock successful deployment
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Deployment successful", stderr=""
        )

        result = deploy_arm(tmp_path, "test-rg", "eastus", dry_run=False)

        assert result["status"] == "deployed"
        assert result["format"] == "arm"
