"""Test fixtures for deployment tests (Issue #610).

Shared fixtures for testing AgentDeployer and related components.
"""

import asyncio
from unittest.mock import MagicMock, Mock

import pytest


@pytest.fixture
def mock_deploy_iac_success():
    """Mock successful deploy_iac call."""

    def _mock(*args, **kwargs):
        return {
            "status": "deployed",
            "format": "terraform",
            "output": "Deployment successful",
        }

    return _mock


@pytest.fixture
def mock_deploy_iac_failure():
    """Mock failed deploy_iac call."""

    def _mock(*args, **kwargs):
        raise RuntimeError("Deployment failed")

    return _mock


@pytest.fixture
def mock_deploy_iac_auth_error():
    """Mock deploy_iac with authentication error."""

    def _mock(*args, **kwargs):
        raise RuntimeError(
            "ERROR: Please run 'az login' to setup account. Authentication required."
        )

    return _mock


@pytest.fixture
def mock_deploy_iac_provider_error():
    """Mock deploy_iac with provider registration error."""

    def _mock(*args, **kwargs):
        raise RuntimeError(
            "ERROR: Provider Microsoft.Compute is not registered in subscription"
        )

    return _mock


@pytest.fixture
def mock_claude_sdk_client():
    """Mock Claude SDK AutoMode client."""

    class MockClaudeClient:
        def __init__(self):
            self.queries = []
            self.responses = ["Applied fix for deployment issue"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def query(self, prompt: str):
            """Mock query method."""
            self.queries.append(prompt)
            if self.responses:
                return self.responses.pop(0)
            return "Generic fix applied"

        async def receive_response(self):
            """Mock receive_response generator."""
            yield Mock(content=[Mock(text="Fix applied")])

    return MockClaudeClient


@pytest.fixture
def sample_iac_dir(tmp_path):
    """Create a sample IaC directory with Terraform files."""
    iac_dir = tmp_path / "iac"
    iac_dir.mkdir()

    # Create sample Terraform file
    main_tf = iac_dir / "main.tf"
    main_tf.write_text(
        """
resource "azurerm_resource_group" "example" {
  name     = "test-rg"
  location = "eastus"
}
"""
    )

    return iac_dir


@pytest.fixture
def sample_deployment_error_log():
    """Sample error log for testing."""
    return [
        {
            "iteration": 1,
            "error_type": "AuthenticationError",
            "message": "Azure authentication required",
            "timestamp": "2024-01-01T00:00:00Z",
        },
        {
            "iteration": 2,
            "error_type": "ProviderRegistrationError",
            "message": "Provider Microsoft.Compute not registered",
            "timestamp": "2024-01-01T00:01:00Z",
        },
    ]


@pytest.fixture
def mock_subprocess_success():
    """Mock successful subprocess run."""

    def _mock(*args, **kwargs):
        return MagicMock(returncode=0, stdout="Success", stderr="")

    return _mock


@pytest.fixture
def mock_subprocess_failure():
    """Mock failed subprocess run."""

    def _mock(*args, **kwargs):
        return MagicMock(returncode=1, stdout="", stderr="Command failed")

    return _mock


@pytest.fixture
async def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def deployment_result_success():
    """Sample successful deployment result."""
    try:
        from src.deployment.agent_deployer import DeploymentResult

        return DeploymentResult(
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
                "output": "Success",
            },
        )
    except ImportError:
        # Module not implemented yet
        return None


@pytest.fixture
def deployment_result_failure():
    """Sample failed deployment result."""
    try:
        from src.deployment.agent_deployer import DeploymentResult

        return DeploymentResult(
            success=False,
            iteration_count=5,
            final_status="max_iterations_reached",
            error_log=[
                {
                    "iteration": i,
                    "error_type": "DeploymentError",
                    "message": f"Error {i}",
                }
                for i in range(1, 6)
            ],
            deployment_output=None,
        )
    except ImportError:
        # Module not implemented yet
        return None
