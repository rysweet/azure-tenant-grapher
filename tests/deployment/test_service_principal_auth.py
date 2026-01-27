"""Tests for service principal authentication in deployment (Issue #858)."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.deployment.orchestrator import deploy_iac


class TestServicePrincipalAuthentication:
    """Test service principal authentication flow."""

    def test_sp_credentials_passed_to_deploy_iac(self):
        """Verify SP credentials are passed from CLI to deploy_iac."""
        # This is a regression test for Bug #1
        # Previously, CLI accepted --sp-client-id and --sp-client-secret
        # but didn't pass them to deploy_iac(), causing auth to fall back
        # to interactive az login which timed out in WSL

        with patch("src.deployment.orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="tenant-id", stderr=""
            )

            with patch("src.deployment.orchestrator.deploy_terraform") as mock_deploy:
                mock_deploy.return_value = {"status": "planned"}

                result = deploy_iac(
                    iac_dir=Path("/tmp/test"),
                    target_tenant_id="test-tenant",
                    resource_group="test-rg",
                    location="eastus",
                    subscription_id="test-sub",
                    iac_format="terraform",
                    dry_run=True,
                    sp_client_id="test-client-id",
                    sp_client_secret="test-secret",
                )

                # Verify SP auth was attempted (not interactive az login)
                sp_login_calls = [
                    call
                    for call in mock_run.call_args_list
                    if "--service-principal" in str(call)
                ]
                assert len(sp_login_calls) > 0, "Service principal login should be attempted"

    def test_subscription_id_passed_to_terraform(self):
        """Verify subscription_id is passed to Terraform deployer."""
        # This is a regression test for Bug #2
        # Previously, --subscription-id flag was ignored by Terraform

        with patch("src.deployment.orchestrator.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="tenant-id", stderr=""
            )

            with patch("src.deployment.orchestrator.deploy_terraform") as mock_deploy:
                mock_deploy.return_value = {"status": "planned"}

                deploy_iac(
                    iac_dir=Path("/tmp/test"),
                    target_tenant_id="test-tenant",
                    resource_group="test-rg",
                    location="eastus",
                    subscription_id="test-subscription-id",
                    iac_format="terraform",
                    dry_run=True,
                )

                # Verify deploy_terraform was called with subscription_id
                mock_deploy.assert_called_once()
                call_args = mock_deploy.call_args
                assert call_args is not None
                # Check that subscription_id was passed (robust: check both kwargs and positional)
                subscription_passed = (
                    call_args.kwargs.get("subscription_id") == "test-subscription-id"
                    or (len(call_args.args) > 5 and call_args.args[5] == "test-subscription-id")
                )
                assert subscription_passed, "subscription_id should be passed to deploy_terraform"


class TestTerraformSubscriptionOverride:
    """Test Terraform subscription ID override functionality."""

    def test_terraform_plan_uses_subscription_var(self):
        """Verify terraform plan command includes -var subscription_id when provided."""
        from src.deployment.terraform_deployer import deploy_terraform

        with patch("src.deployment.terraform_deployer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_terraform(
                iac_dir=Path("/tmp/test"),
                resource_group="test-rg",
                location="eastus",
                dry_run=True,
                subscription_id="override-subscription",
            )

            # Find the terraform plan call
            plan_calls = [
                call
                for call in mock_run.call_args_list
                if call[0][0][0] == "terraform" and "plan" in call[0][0]
            ]

            assert len(plan_calls) > 0, "terraform plan should be called"
            plan_cmd = plan_calls[0][0][0]

            # Verify -var flag is present with subscription_id
            assert "-var" in plan_cmd, "Should include -var flag"
            assert any(
                "subscription_id=override-subscription" in arg for arg in plan_cmd
            ), "Should pass subscription_id override"

    def test_terraform_apply_uses_subscription_var(self):
        """Verify terraform apply command includes -var subscription_id when provided."""
        from src.deployment.terraform_deployer import deploy_terraform

        with patch("src.deployment.terraform_deployer.subprocess.run") as mock_run:
            # Mock both init and apply
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_terraform(
                iac_dir=Path("/tmp/test"),
                resource_group="test-rg",
                location="eastus",
                dry_run=False,
                subscription_id="override-subscription",
            )

            # Find the terraform apply call
            apply_calls = [
                call
                for call in mock_run.call_args_list
                if call[0][0][0] == "terraform" and "apply" in call[0][0]
            ]

            assert len(apply_calls) > 0, "terraform apply should be called"
            apply_cmd = apply_calls[0][0][0]

            # Verify -var flag is present with subscription_id
            assert "-var" in apply_cmd, "Should include -var flag"
            assert any(
                "subscription_id=override-subscription" in arg for arg in apply_cmd
            ), "Should pass subscription_id override"

    def test_terraform_without_subscription_override(self):
        """Verify terraform commands work without subscription_id override."""
        from src.deployment.terraform_deployer import deploy_terraform

        with patch("src.deployment.terraform_deployer.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")

            deploy_terraform(
                iac_dir=Path("/tmp/test"),
                resource_group="test-rg",
                location="eastus",
                dry_run=True,
                subscription_id=None,  # No override
            )

            # Find the terraform plan call
            plan_calls = [
                call
                for call in mock_run.call_args_list
                if call[0][0][0] == "terraform" and "plan" in call[0][0]
            ]

            assert len(plan_calls) > 0
            plan_cmd = plan_calls[0][0][0]

            # Verify -var flag is NOT present when subscription_id is None
            assert "-var" not in plan_cmd, "Should not include -var when subscription_id is None"
