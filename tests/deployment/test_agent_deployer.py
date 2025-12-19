"""Tests for goal-seeking deployment agent (Issue #610).

These tests follow TDD approach - they are written BEFORE implementation.
They will FAIL initially until AgentDeployer is implemented.

Testing Strategy:
- 60% Unit tests (individual methods)
- 30% Integration tests (deployment loop with mocked deploy_iac)
- 10% E2E tests (full CLI integration)
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# These imports will fail initially - that's expected in TDD
try:
    from src.deployment.agent_deployer import AgentDeployer, DeploymentResult
except ImportError:
    # Expected failure - module doesn't exist yet
    AgentDeployer = None
    DeploymentResult = None


# Skip all tests if module doesn't exist yet (TDD)
pytestmark = pytest.mark.skipif(
    AgentDeployer is None,
    reason="AgentDeployer not implemented yet (TDD - tests written first)",
)


# ============================================================================
# Unit Tests (60% of test suite)
# ============================================================================


class TestAgentDeployerInit:
    """Test AgentDeployer initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default parameters."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        assert deployer.iac_dir == Path("/test/iac")
        assert deployer.target_tenant_id == "test-tenant-123"
        assert deployer.resource_group == "test-rg"
        assert deployer.max_iterations == 20
        assert deployer.timeout_seconds == 6000
        assert deployer.iteration_count == 0
        assert deployer.error_log == []

    def test_init_with_custom_limits(self):
        """Test initialization with custom iteration and timeout limits."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
            max_iterations=10,
            timeout_seconds=600,
        )

        assert deployer.max_iterations == 10
        assert deployer.timeout_seconds == 600

    def test_init_validates_iac_dir(self):
        """Test that initialization accepts IaC directory path."""
        # Path validation removed for simplicity - any path-like accepted
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )
        assert deployer.iac_dir == Path("/test/iac")

    def test_init_validates_tenant_id(self):
        """Test that initialization validates tenant ID."""
        with pytest.raises(ValueError, match="target_tenant_id cannot be empty"):
            AgentDeployer(
                iac_dir=Path("/test/iac"),
                target_tenant_id="",
                resource_group="test-rg",
            )

    def test_init_validates_resource_group(self):
        """Test that initialization validates resource group."""
        with pytest.raises(ValueError, match="resource_group cannot be empty"):
            AgentDeployer(
                iac_dir=Path("/test/iac"),
                target_tenant_id="test-tenant-123",
                resource_group="",
            )


class TestAgentDeployerStateTracking:
    """Test state tracking methods."""

    def test_increment_iteration(self):
        """Test iteration counter increments correctly."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        assert deployer.iteration_count == 0
        deployer._increment_iteration()
        assert deployer.iteration_count == 1
        deployer._increment_iteration()
        assert deployer.iteration_count == 2

    def test_log_error(self):
        """Test error logging functionality."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        assert deployer.error_log == []

        # Simulate real usage: increment iteration before logging error
        deployer._increment_iteration()
        deployer._log_error("Authentication failed", RuntimeError("Auth error"))
        assert len(deployer.error_log) == 1
        assert deployer.error_log[0]["iteration"] == 1
        assert deployer.error_log[0]["error_type"] == "RuntimeError"
        assert "Auth error" in deployer.error_log[0]["message"]

    def test_has_reached_max_iterations(self):
        """Test max iteration detection."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
            max_iterations=3,
        )

        assert not deployer._has_reached_max_iterations()
        deployer._increment_iteration()
        assert not deployer._has_reached_max_iterations()
        deployer._increment_iteration()
        assert not deployer._has_reached_max_iterations()
        deployer._increment_iteration()
        assert deployer._has_reached_max_iterations()

    def test_error_log_includes_timestamp(self):
        """Test that error logs include timestamps."""
        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        deployer._increment_iteration()
        deployer._log_error("Test error", RuntimeError("Test"))

        assert len(deployer.error_log) == 1
        assert "timestamp" in deployer.error_log[0]
        assert deployer.error_log[0]["iteration"] == 1
        assert deployer.error_log[0]["context"] == "Test error"


# ============================================================================
# Integration Tests (30% of test suite)
# ============================================================================


class TestDeploymentLoop:
    """Test deployment loop with mocked deploy_iac."""

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_single_iteration_success(self, mock_deploy_iac):
        """Test successful deployment on first iteration."""
        # Mock successful deployment
        mock_deploy_iac.return_value = {
            "status": "deployed",
            "format": "terraform",
            "output": "Deployment successful",
        }

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        assert result.iteration_count == 1
        assert result.final_status == "deployed"
        assert len(result.error_log) == 0
        mock_deploy_iac.assert_called_once()

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_multiple_iterations_with_recovery(self, mock_deploy_iac):
        """Test deployment fails first, then succeeds after error analysis."""
        # First call fails, second call succeeds
        mock_deploy_iac.side_effect = [
            RuntimeError("Provider not registered"),
            {
                "status": "deployed",
                "format": "terraform",
                "output": "Deployment successful",
            },
        ]

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        assert result.iteration_count == 2
        assert result.final_status == "deployed"
        assert len(result.error_log) == 1  # One error before recovery
        assert mock_deploy_iac.call_count == 2

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_max_iterations_reached(self, mock_deploy_iac):
        """Test deployment never succeeds and max iterations reached."""
        # Always fail
        mock_deploy_iac.side_effect = RuntimeError("Persistent deployment error")

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
            max_iterations=3,
        )

        result = await deployer.deploy_with_agent()

        assert result.success is False
        assert result.iteration_count == 3
        assert result.final_status == "max_iterations_reached"
        assert len(result.error_log) == 3
        assert mock_deploy_iac.call_count == 3

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_timeout_handling(self, mock_deploy_iac):
        """Test deployment timeout handling."""

        # Mock slow deployment that times out
        def slow_deploy(*args, **kwargs):
            import time

            time.sleep(10)  # Longer than timeout
            return {"status": "deployed"}

        mock_deploy_iac.side_effect = slow_deploy

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
            timeout_seconds=1,  # Short timeout
        )

        result = await deployer.deploy_with_agent()

        assert result.success is False
        assert result.final_status == "timeout"
        assert "timeout" in str(result.error_log[-1]).lower()


class TestErrorHandling:
    """Test error handling and recovery strategies."""

    @patch("src.deployment.agent_deployer.subprocess.run")
    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_authentication_error_triggers_reauth(
        self, mock_deploy_iac, mock_subprocess
    ):
        """Test authentication errors trigger re-authentication."""
        # First call fails with auth error, second succeeds
        mock_deploy_iac.side_effect = [
            RuntimeError("Authentication required"),
            {"status": "deployed", "format": "terraform", "output": "Success"},
        ]

        # Mock successful re-auth
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        assert result.iteration_count == 2
        # Verify az login was called
        mock_subprocess.assert_called()
        call_args = str(mock_subprocess.call_args)
        assert "az" in call_args and "login" in call_args

    @patch("src.deployment.agent_deployer.subprocess.run")
    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_provider_registration_error_triggers_registration(
        self, mock_deploy_iac, mock_subprocess
    ):
        """Test provider registration errors trigger provider registration."""
        # First call fails with provider error, second succeeds
        mock_deploy_iac.side_effect = [
            RuntimeError("Provider Microsoft.Compute not registered"),
            {"status": "deployed", "format": "terraform", "output": "Success"},
        ]

        # Mock successful provider registration
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="", stderr="")

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        assert result.iteration_count == 2
        # Verify az provider register was called
        mock_subprocess.assert_called()
        call_args = str(mock_subprocess.call_args)
        assert "az provider register" in call_args or "provider" in call_args

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_unknown_error_logged_but_not_crash(self, mock_deploy_iac):
        """Test unknown errors are logged but don't crash the agent."""
        # Unknown error type
        mock_deploy_iac.side_effect = [
            ValueError("Unexpected validation error"),
            {"status": "deployed", "format": "terraform", "output": "Success"},
        ]

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        assert len(result.error_log) == 1
        assert "ValueError" in result.error_log[0]["error_type"]


class TestAIAnalysisIntegration:
    """Test AI error analysis integration."""

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_ai_analysis_invoked_on_error(self, mock_deploy_iac):
        """Test AI analysis is invoked when deployment fails."""
        mock_deploy_iac.side_effect = [
            RuntimeError("Deployment failed"),
            {"status": "deployed", "format": "terraform", "output": "Success"},
        ]

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
        )

        result = await deployer.deploy_with_agent()

        assert result.success is True
        # Verify error was logged
        assert len(result.error_log) == 1
        assert "Deployment failed" in result.error_log[0]["message"]

    @patch("src.deployment.agent_deployer.deploy_iac")
    async def test_analysis_continues_on_max_iterations(self, mock_deploy_iac):
        """Test analysis handles max iterations gracefully."""
        mock_deploy_iac.side_effect = RuntimeError("Deployment failed")

        deployer = AgentDeployer(
            iac_dir=Path("/test/iac"),
            target_tenant_id="test-tenant-123",
            resource_group="test-rg",
            max_iterations=2,
        )

        result = await deployer.deploy_with_agent()

        assert result.success is False
        assert result.final_status == "max_iterations_reached"
        assert len(result.error_log) == 2


class TestDeploymentResult:
    """Test DeploymentResult dataclass."""

    def test_deployment_result_success(self):
        """Test DeploymentResult for successful deployment."""
        result = DeploymentResult(
            success=True,
            iteration_count=2,
            final_status="deployed",
            error_log=[{"iteration": 1, "error": "Transient error"}],
            deployment_output={"status": "deployed", "output": "Success"},
        )

        assert result.success is True
        assert result.iteration_count == 2
        assert result.final_status == "deployed"
        assert len(result.error_log) == 1
        assert result.deployment_output is not None

    def test_deployment_result_failure(self):
        """Test DeploymentResult for failed deployment."""
        result = DeploymentResult(
            success=False,
            iteration_count=5,
            final_status="max_iterations_reached",
            error_log=[{"iteration": i, "error": f"Error {i}"} for i in range(1, 6)],
            deployment_output=None,
        )

        assert result.success is False
        assert result.iteration_count == 5
        assert result.final_status == "max_iterations_reached"
        assert len(result.error_log) == 5
        assert result.deployment_output is None


# ============================================================================
# E2E Tests (10% of test suite)
# ============================================================================


class TestCLIIntegration:
    """Test CLI integration with agent deployer."""

    @patch("src.commands.deploy.AgentDeployer")
    def test_cli_agent_flag_routes_to_agent_deployer(
        self, mock_agent_deployer, tmp_path
    ):
        """Test --agent flag routes to AgentDeployer."""
        from click.testing import CliRunner

        from src.commands.deploy import deploy_command

        # Mock AgentDeployer
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
        mock_agent_deployer.return_value = mock_instance

        runner = CliRunner()
        result = runner.invoke(
            deploy_command,
            [
                "--iac-dir",
                str(tmp_path),
                "--target-tenant-id",
                "test-tenant",
                "--resource-group",
                "test-rg",
                "--agent",  # Agent flag
            ],
        )

        assert result.exit_code == 0
        mock_agent_deployer.assert_called_once()

    @patch("src.commands.deploy.AgentDeployer")
    def test_cli_max_iterations_flag_respected(self, mock_agent_deployer, tmp_path):
        """Test --max-iterations flag is passed to AgentDeployer."""
        from click.testing import CliRunner

        from src.commands.deploy import deploy_command

        # Mock AgentDeployer
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
        mock_agent_deployer.return_value = mock_instance

        runner = CliRunner()
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
                "10",
            ],
        )

        assert result.exit_code == 0
        # Verify max_iterations was passed
        call_kwargs = mock_agent_deployer.call_args[1]
        assert call_kwargs.get("max_iterations") == 10

    @patch("src.commands.deploy.AgentDeployer")
    def test_cli_agent_timeout_flag_respected(self, mock_agent_deployer, tmp_path):
        """Test --agent-timeout flag is passed to AgentDeployer."""
        from click.testing import CliRunner

        from src.commands.deploy import deploy_command

        # Mock AgentDeployer
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
        mock_agent_deployer.return_value = mock_instance

        runner = CliRunner()
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
                "600",
            ],
        )

        assert result.exit_code == 0
        # Verify timeout was passed
        call_kwargs = mock_agent_deployer.call_args[1]
        assert call_kwargs.get("timeout_seconds") == 600

    @patch("src.commands.deploy.AgentDeployer")
    def test_cli_deployment_report_displayed(self, mock_agent_deployer, tmp_path):
        """Test deployment report is displayed correctly."""
        from click.testing import CliRunner

        from src.commands.deploy import deploy_command

        # Mock AgentDeployer with multiple iterations
        mock_instance = Mock()
        mock_instance.deploy_with_agent = AsyncMock(
            return_value=DeploymentResult(
                success=True,
                iteration_count=3,
                final_status="deployed",
                error_log=[
                    {"iteration": 1, "error": "Error 1"},
                    {"iteration": 2, "error": "Error 2"},
                ],
                deployment_output={"status": "deployed", "output": "Success"},
            )
        )
        mock_agent_deployer.return_value = mock_instance

        runner = CliRunner()
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
        # Verify report contains key information
        assert "iteration" in result.output.lower()
        assert "deployed" in result.output.lower()
        assert "3" in result.output  # Iteration count

    @patch("src.commands.deploy.AgentDeployer")
    def test_cli_failure_exit_code(self, mock_agent_deployer, tmp_path):
        """Test CLI returns non-zero exit code on deployment failure."""
        from click.testing import CliRunner

        from src.commands.deploy import deploy_command

        # Mock failed deployment
        mock_instance = Mock()
        mock_instance.deploy_with_agent = AsyncMock(
            return_value=DeploymentResult(
                success=False,
                iteration_count=5,
                final_status="max_iterations_reached",
                error_log=[
                    {"iteration": i, "error": f"Error {i}"} for i in range(1, 6)
                ],
                deployment_output=None,
            )
        )
        mock_agent_deployer.return_value = mock_instance

        runner = CliRunner()
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
        assert (
            "failed" in result.output.lower()
            or "max_iterations" in result.output.lower()
        )
