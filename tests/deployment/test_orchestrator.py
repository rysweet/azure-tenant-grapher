"""Tests for deployment orchestrator."""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.deployment.orchestrator import (
    deploy_arm,
    deploy_bicep,
    deploy_iac,
    deploy_terraform,
    detect_iac_format,
)


class TestDetectIaCFormat:
    """Tests for IaC format detection."""

    def test_detect_terraform_format(self, tmp_path):
        """Test Terraform format detection."""
        (tmp_path / "main.tf").write_text(
            'resource "azurerm_resource_group" "example" {}'
        )
        assert detect_iac_format(tmp_path) == "terraform"

    def test_detect_terraform_with_multiple_files(self, tmp_path):
        """Test Terraform detection with multiple .tf files."""
        (tmp_path / "main.tf").write_text("# Main")
        (tmp_path / "variables.tf").write_text("# Variables")
        assert detect_iac_format(tmp_path) == "terraform"

    def test_detect_bicep_format(self, tmp_path):
        """Test Bicep format detection."""
        (tmp_path / "main.bicep").write_text(
            "resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {}"
        )
        assert detect_iac_format(tmp_path) == "bicep"

    def test_detect_arm_format(self, tmp_path):
        """Test ARM template format detection."""
        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [],
        }
        (tmp_path / "template.json").write_text(json.dumps(arm_template))
        assert detect_iac_format(tmp_path) == "arm"

    def test_detect_unknown_format(self, tmp_path):
        """Test unknown format detection."""
        (tmp_path / "readme.txt").write_text("Not IaC")
        assert detect_iac_format(tmp_path) is None

    def test_detect_nonexistent_directory(self, tmp_path):
        """Test detection with non-existent directory."""
        nonexistent = tmp_path / "does_not_exist"
        assert detect_iac_format(nonexistent) is None

    def test_detect_file_instead_of_directory(self, tmp_path):
        """Test detection when path is a file, not directory."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("test")
        assert detect_iac_format(file_path) is None

    def test_detect_arm_with_invalid_json(self, tmp_path):
        """Test ARM detection with invalid JSON file."""
        (tmp_path / "invalid.json").write_text("{invalid json")
        assert detect_iac_format(tmp_path) is None

    def test_detect_arm_with_non_template_json(self, tmp_path):
        """Test ARM detection with JSON that's not a template."""
        (tmp_path / "data.json").write_text('{"key": "value"}')
        assert detect_iac_format(tmp_path) is None


class TestDeployTerraform:
    """Tests for Terraform deployment."""

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_terraform_init_failure(self, mock_run, tmp_path):
        """Test Terraform deployment when init fails."""
        (tmp_path / "main.tf").write_text("# Terraform config")

        # Mock terraform init failure
        mock_run.return_value = MagicMock(returncode=1, stderr="Init failed")

        with pytest.raises(RuntimeError, match="Terraform init failed"):
            deploy_terraform(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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


class TestDeployBicep:
    """Tests for Bicep deployment."""

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_bicep_no_files(self, mock_run, tmp_path):
        """Test Bicep deployment with no bicep files."""
        with pytest.raises(RuntimeError, match="No Bicep files found"):
            deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_bicep_validation_failure(self, mock_run, tmp_path):
        """Test Bicep deployment when validation fails."""
        (tmp_path / "main.bicep").write_text("invalid bicep")

        # Mock validation failure
        mock_run.return_value = MagicMock(returncode=1, stderr="Validation failed")

        with pytest.raises(RuntimeError, match="Bicep validation failed"):
            deploy_bicep(tmp_path, "test-rg", "eastus", dry_run=True)

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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


class TestDeployARM:
    """Tests for ARM template deployment."""

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_arm_no_templates(self, mock_run, tmp_path):
        """Test ARM deployment with no template files."""
        with pytest.raises(RuntimeError, match="No ARM template files found"):
            deploy_arm(tmp_path, "test-rg", "eastus", dry_run=False)

    @patch("src.deployment.orchestrator.subprocess.run")
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

    @patch("src.deployment.orchestrator.subprocess.run")
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


class TestDeployIaC:
    """Integration tests for main deploy_iac function."""

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_terraform_auto_detect(self, mock_deploy_tf, mock_run, tmp_path):
        """Test deploy_iac with auto-detected Terraform format."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock Azure login
        mock_run.return_value = MagicMock(returncode=0)

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert result["format"] == "terraform"
        mock_deploy_tf.assert_called_once()

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_bicep")
    def test_deploy_iac_bicep_explicit_format(
        self, mock_deploy_bicep, mock_run, tmp_path
    ):
        """Test deploy_iac with explicitly specified Bicep format."""
        (tmp_path / "main.bicep").write_text("# Bicep")

        # Mock Azure login
        mock_run.return_value = MagicMock(returncode=0)

        # Mock Bicep deployment
        mock_deploy_bicep.return_value = {
            "status": "deployed",
            "format": "bicep",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            iac_format="bicep",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert result["format"] == "bicep"
        mock_deploy_bicep.assert_called_once()

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_iac_unknown_format(self, mock_run, tmp_path):
        """Test deploy_iac with unknown format."""
        (tmp_path / "readme.txt").write_text("Not IaC")

        with pytest.raises(ValueError, match="Could not detect IaC format"):
            deploy_iac(
                iac_dir=tmp_path,
                target_tenant_id="test-tenant",
                resource_group="test-rg",
                location="eastus",
                dry_run=False,
            )

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_iac_unsupported_format(self, mock_run, tmp_path):
        """Test deploy_iac with unsupported format."""
        with pytest.raises(ValueError, match="Unsupported IaC format"):
            deploy_iac(
                iac_dir=tmp_path,
                target_tenant_id="test-tenant",
                resource_group="test-rg",
                location="eastus",
                iac_format="unsupported",  # type: ignore
                dry_run=False,
            )

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_with_subscription(self, mock_deploy_tf, mock_run, tmp_path):
        """Test deploy_iac with subscription ID."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock Azure login and subscription set
        mock_run.return_value = MagicMock(returncode=0)

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            subscription_id="test-sub-id",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        # Verify subscription was set
        assert mock_run.call_count >= 2  # Login + subscription set

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_arm")
    def test_deploy_iac_arm_format(self, mock_deploy_arm, mock_run, tmp_path):
        """Test deploy_iac with ARM template format."""
        arm_template = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": [],
        }
        (tmp_path / "template.json").write_text(json.dumps(arm_template))

        # Mock Azure login
        mock_run.return_value = MagicMock(returncode=0)

        # Mock ARM deployment
        mock_deploy_arm.return_value = {
            "status": "deployed",
            "format": "arm",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            iac_format="arm",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert result["format"] == "arm"
        mock_deploy_arm.assert_called_once()

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_subscription_tenant_validation_success(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test subscription-tenant validation when subscription belongs to target tenant."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock sequence:
        # 1. Current tenant check (different tenant)
        # 2. Subscription validation (belongs to target tenant)
        # 3. Subscription switch (success)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(returncode=0, stdout="test-tenant\n"),  # Subscription validation
            MagicMock(returncode=0, stdout=""),  # Subscription switch
        ]

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            subscription_id="test-sub-id",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert mock_run.call_count == 3
        # Verify subscription validation was called
        validation_call = mock_run.call_args_list[1][0][0]
        assert "subscription" in validation_call
        assert "show" in validation_call
        assert "test-sub-id" in validation_call

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_subscription_tenant_mismatch(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test subscription-tenant validation when subscription belongs to different tenant."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock sequence:
        # 1. Current tenant check (different tenant)
        # 2. Subscription validation (belongs to DIFFERENT tenant)
        # 3. Skip subscription switch, go directly to login
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(
                returncode=0, stdout="wrong-tenant-id\n"
            ),  # Subscription validation
            MagicMock(returncode=0, stdout=""),  # Login (fallback)
        ]

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            subscription_id="test-sub-id",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert mock_run.call_count == 3
        # Verify az login was called (not az account set)
        login_call = mock_run.call_args_list[2][0][0]
        assert "login" in login_call
        assert "test-tenant" in login_call

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_subscription_validation_failure(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test subscription-tenant validation when validation command fails."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock sequence:
        # 1. Current tenant check (different tenant)
        # 2. Subscription validation FAILS (subscription not found)
        # 3. Attempt subscription switch anyway (falls back to login)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(
                returncode=1, stderr="Subscription not found"
            ),  # Validation fails
            MagicMock(returncode=1, stderr="Invalid subscription"),  # Switch fails
            MagicMock(returncode=0, stdout=""),  # Login (fallback)
        ]

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            subscription_id="test-sub-id",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        # Should attempt validation, switch (fails), then login
        assert mock_run.call_count == 4

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_already_authenticated_to_target_tenant(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test deploy_iac when already authenticated to target tenant."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock: already authenticated to target tenant
        mock_run.return_value = MagicMock(returncode=0, stdout="test-tenant\n")

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            subscription_id="test-sub-id",
            dry_run=False,
        )

        assert result["status"] == "deployed"
        # Only one call: current tenant check (no validation, no switch, no login)
        assert mock_run.call_count == 1

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_with_service_principal_success(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test deploy_iac with service principal authentication success."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock: current tenant check (different tenant) + SP login success
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(returncode=0, stdout=""),  # SP login success
        ]

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            sp_client_id="test-sp-client-id",
            sp_client_secret="test-sp-secret",  # pragma: allowlist secret
            dry_run=False,
        )

        assert result["status"] == "deployed"
        assert mock_run.call_count == 2

        # Verify SP login was called with correct parameters
        sp_login_call = mock_run.call_args_list[1][0][0]
        assert "login" in sp_login_call
        assert "--service-principal" in sp_login_call
        assert "-u" in sp_login_call
        assert "test-sp-client-id" in sp_login_call
        assert "-p" in sp_login_call
        assert "test-sp-secret" in sp_login_call
        assert "--tenant" in sp_login_call
        assert "test-tenant" in sp_login_call

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_with_service_principal_custom_tenant(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test deploy_iac with service principal using custom SP tenant."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock: current tenant check + SP login success
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(returncode=0, stdout=""),  # SP login success
        ]

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            sp_client_id="test-sp-client-id",
            sp_client_secret="test-sp-secret",  # pragma: allowlist secret
            sp_tenant_id="sp-specific-tenant",
            dry_run=False,
        )

        assert result["status"] == "deployed"

        # Verify SP tenant was used (not target_tenant_id)
        sp_login_call = mock_run.call_args_list[1][0][0]
        assert "sp-specific-tenant" in sp_login_call

    @patch("src.deployment.orchestrator.subprocess.run")
    def test_deploy_iac_with_service_principal_failure(self, mock_run, tmp_path):
        """Test deploy_iac with service principal authentication failure."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock: current tenant check + SP login failure
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout="source-tenant-id\n"),  # Current tenant
            MagicMock(returncode=1, stderr="Authentication failed"),  # SP login fails
        ]

        with pytest.raises(
            RuntimeError, match="Service principal authentication failed"
        ):
            deploy_iac(
                iac_dir=tmp_path,
                target_tenant_id="test-tenant",
                resource_group="test-rg",
                location="eastus",
                sp_client_id="test-sp-client-id",
                sp_client_secret="test-sp-secret",  # pragma: allowlist secret
                dry_run=False,
            )

    @patch("src.deployment.orchestrator.subprocess.run")
    @patch("src.deployment.orchestrator.deploy_terraform")
    def test_deploy_iac_sp_already_authenticated(
        self, mock_deploy_tf, mock_run, tmp_path
    ):
        """Test deploy_iac with SP credentials when already authenticated to target tenant."""
        (tmp_path / "main.tf").write_text("# Terraform")

        # Mock: already authenticated to target tenant
        mock_run.return_value = MagicMock(returncode=0, stdout="test-tenant\n")

        # Mock Terraform deployment
        mock_deploy_tf.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Success",
        }

        result = deploy_iac(
            iac_dir=tmp_path,
            target_tenant_id="test-tenant",
            resource_group="test-rg",
            location="eastus",
            sp_client_id="test-sp-client-id",
            sp_client_secret="test-sp-secret",  # pragma: allowlist secret
            dry_run=False,
        )

        assert result["status"] == "deployed"
        # Only one call: current tenant check (no SP login needed)
        assert mock_run.call_count == 1
