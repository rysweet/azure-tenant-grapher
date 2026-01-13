"""E2E tests for deploy command with agent mode (Issue #610).

These tests verify the full CLI integration with AgentDeployer.
Written in TDD style - will fail until implementation is complete.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner

# These imports will fail initially - expected in TDD
try:
    from src.commands.deploy import deploy_command
    from src.deployment.agent_deployer import AgentDeployer, DeploymentResult
except ImportError:
    deploy_command = None
    AgentDeployer = None
    DeploymentResult = None


pytestmark = pytest.mark.skipif(
    deploy_command is None or AgentDeployer is None,
    reason="Deploy command or AgentDeployer not implemented yet (TDD)",
)


class TestDeployCommandAgentMode:
    """E2E tests for deploy command with --agent flag."""

    def test_deploy_without_agent_uses_orchestrator(self, tmp_path):
        """Test normal deploy (without --agent) uses orchestrator."""
        runner = CliRunner()

        with patch("src.commands.deploy.deploy_iac") as mock_deploy_iac:
            mock_deploy_iac.return_value = {
                "status": "deployed",
                "format": "terraform",
                "output": "Success",
            }

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                ],
            )

            assert result.exit_code == 0
            mock_deploy_iac.assert_called_once()
            # Check that agent-specific messages don't appear
            assert "autonomous" not in result.output.lower()
            assert "iteration" not in result.output.lower()

    def test_deploy_with_agent_uses_agent_deployer(self, tmp_path):
        """Test deploy with --agent flag uses AgentDeployer."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=1,
                    final_status="deployed",
                    error_log=[],
                    deployment_output={"status": "deployed"},
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code == 0
            mock_agent_class.assert_called_once()
            # Verify AgentDeployer was called with correct parameters
            call_args = mock_agent_class.call_args
            assert call_args[1]["iac_dir"] == tmp_path
            assert call_args[1]["target_tenant_id"] == "test-tenant"
            assert call_args[1]["resource_group"] == "test-rg"

    def test_agent_with_custom_max_iterations(self, tmp_path):
        """Test --max-iterations flag is passed to AgentDeployer."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=1,
                    final_status="deployed",
                    error_log=[],
                    deployment_output={"status": "deployed"},
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                    "--max-iterations",
                    "15",
                ],
            )

            assert result.exit_code == 0
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["max_iterations"] == 15

    def test_agent_with_custom_timeout(self, tmp_path):
        """Test --agent-timeout flag is passed to AgentDeployer."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=1,
                    final_status="deployed",
                    error_log=[],
                    deployment_output={"status": "deployed"},
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                    "--agent-timeout",
                    "900",
                ],
            )

            assert result.exit_code == 0
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["timeout_seconds"] == 900

    def test_agent_all_optional_params(self, tmp_path):
        """Test agent with all optional deployment parameters."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=1,
                    final_status="deployed",
                    error_log=[],
                    deployment_output={"status": "deployed"},
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--location",
                    "westus",
                    "--subscription-id",
                    "test-sub-123",
                    "--format",
                    "terraform",
                    "--agent",
                ],
            )

            assert result.exit_code == 0
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["location"] == "westus"
            assert call_kwargs["subscription_id"] == "test-sub-123"
            assert call_kwargs["iac_format"] == "terraform"


class TestDeploymentReportDisplay:
    """Test deployment report display in CLI output."""

    def test_successful_deployment_report(self, tmp_path):
        """Test report for successful deployment."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=2,
                    final_status="deployed",
                    error_log=[
                        {
                            "iteration": 1,
                            "error_type": "AuthenticationError",
                            "message": "Auth failed",
                        }
                    ],
                    deployment_output={
                        "status": "deployed",
                        "format": "terraform",
                        "output": "Applied successfully",
                    },
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code == 0
            output_lower = result.output.lower()

            # Verify report contains key information
            assert "success" in output_lower or "deployed" in output_lower
            assert "2" in result.output  # Iteration count
            assert "terraform" in output_lower

    def test_failed_deployment_report(self, tmp_path):
        """Test report for failed deployment."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=False,
                    iteration_count=5,
                    final_status="max_iterations_reached",
                    error_log=[
                        {
                            "iteration": i,
                            "error_type": "DeploymentError",
                            "message": f"Deployment failed attempt {i}",
                        }
                        for i in range(1, 6)
                    ],
                    deployment_output=None,
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code != 0
            output_lower = result.output.lower()

            # Verify failure information
            assert "failed" in output_lower or "error" in output_lower
            assert "5" in result.output  # Max iterations reached
            assert "max" in output_lower or "limit" in output_lower

    def test_report_shows_error_summary(self, tmp_path):
        """Test report shows summary of errors encountered."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=3,
                    final_status="deployed",
                    error_log=[
                        {
                            "iteration": 1,
                            "error_type": "AuthenticationError",
                            "message": "Auth failed",
                        },
                        {
                            "iteration": 2,
                            "error_type": "ProviderRegistrationError",
                            "message": "Provider not registered",
                        },
                    ],
                    deployment_output={"status": "deployed"},
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code == 0
            # Should show error summary even on success
            assert (
                "error" in result.output.lower() or "attempt" in result.output.lower()
            )


class TestAgentModeErrorHandling:
    """Test error handling in agent mode."""

    def test_invalid_iac_dir(self):
        """Test error when IaC directory doesn't exist."""
        runner = CliRunner()

        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                "/nonexistent/path",
                "--target-tenant-id",
                "test-tenant",
                "--resource-group",
                "test-rg",
                "--agent",
            ],
        )

        assert result.exit_code != 0
        assert (
            "does not exist" in result.output.lower()
            or "not found" in result.output.lower()
        )

    def test_agent_deployment_exception_handling(self, tmp_path):
        """Test graceful handling of exceptions during agent deployment."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                side_effect=RuntimeError("Critical agent failure")
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code != 0
            assert "error" in result.output.lower() or "failed" in result.output.lower()

    def test_timeout_reported_correctly(self, tmp_path):
        """Test timeout is reported clearly to user."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=False,
                    iteration_count=1,
                    final_status="timeout",
                    error_log=[
                        {
                            "iteration": 1,
                            "error_type": "TimeoutError",
                            "message": "Operation timed out after 300 seconds",
                        }
                    ],
                    deployment_output=None,
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                ],
            )

            assert result.exit_code != 0
            assert "timeout" in result.output.lower()


class TestAgentModeDryRun:
    """Test agent mode with dry-run flag."""

    def test_agent_with_dry_run(self, tmp_path):
        """Test agent mode respects --dry-run flag."""
        runner = CliRunner()

        with patch("src.commands.deploy.AgentDeployer") as mock_agent_class:
            mock_instance = Mock()
            mock_instance.deploy_with_agent = AsyncMock(
                return_value=DeploymentResult(
                    success=True,
                    iteration_count=1,
                    final_status="planned",
                    error_log=[],
                    deployment_output={
                        "status": "planned",
                        "output": "Plan successful",
                    },
                )
            )
            mock_agent_class.return_value = mock_instance

            result = runner.invoke(
                deploy_command,
                [
                    "--iac-dir",
                    str(tmp_path),
                    "--target-tenant-id",
                    "test-tenant",
                    "--resource-group",
                    "test-rg",
                    "--agent",
                    "--dry-run",
                ],
            )

            assert result.exit_code == 0
            call_kwargs = mock_agent_class.call_args[1]
            assert call_kwargs["dry_run"] is True
            assert "plan" in result.output.lower()


class TestHelpAndDocumentation:
    """Test help text and documentation for agent mode."""

    def test_help_includes_agent_flag(self):
        """Test that --help includes agent flag documentation."""
        runner = CliRunner()
        result = runner.invoke(deploy_command, ["--help"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "--agent" in output_lower
        assert (
            "autonomous" in output_lower
            or "goal" in output_lower
            or "ai" in output_lower
        )

    def test_help_includes_max_iterations(self):
        """Test that --help includes max-iterations flag."""
        runner = CliRunner()
        result = runner.invoke(deploy_command, ["--help"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "--max-iterations" in output_lower
        assert "iteration" in output_lower

    def test_help_includes_agent_timeout(self):
        """Test that --help includes agent-timeout flag."""
        runner = CliRunner()
        result = runner.invoke(deploy_command, ["--help"])

        assert result.exit_code == 0
        output_lower = result.output.lower()
        assert "--agent-timeout" in output_lower
        assert "timeout" in output_lower
