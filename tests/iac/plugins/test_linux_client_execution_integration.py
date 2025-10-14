"""Integration tests for linux_client_plugin with ExecutionEngine.

Tests that the plugin correctly uses the ExecutionEngine for executing
replication steps, including dependency checking, critical failure handling,
and fidelity score calculation.
"""

import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.iac.execution.models import ExecutionConfig, ExecutionStatus
from src.iac.plugins.linux_client_plugin import LinuxClientReplicationPlugin
from src.iac.plugins.models import (
    ExtractionFormat,
    ReplicationStatus,
    ReplicationStep,
    StepResult,
    StepType,
)


@pytest.fixture
def plugin():
    """Create a LinuxClientReplicationPlugin instance."""
    return LinuxClientReplicationPlugin(
        ssh_username="testuser",
        output_dir="/tmp/test_execution",
    )


@pytest.fixture
def sample_steps():
    """Create sample replication steps for testing."""
    return [
        ReplicationStep(
            step_id="validate_target",
            step_type=StepType.VALIDATION,
            description="Validate target VM is accessible",
            script_content="ansible target -i inventory.ini -m ping",
            script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
            depends_on=[],
            is_critical=True,
        ),
        ReplicationStep(
            step_id="replicate_users",
            step_type=StepType.DATA_IMPORT,
            description="Create user accounts on target",
            script_content="# playbook content here",
            script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
            depends_on=["validate_target"],
            is_critical=True,
        ),
        ReplicationStep(
            step_id="replicate_ssh_keys",
            step_type=StepType.CONFIGURATION,
            description="Deploy SSH authorized keys",
            script_content="# playbook content here",
            script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
            depends_on=["replicate_users"],
            is_critical=True,
        ),
        ReplicationStep(
            step_id="replicate_packages",
            step_type=StepType.CONFIGURATION,
            description="Install required packages",
            script_content="# playbook content here",
            script_format=ExtractionFormat.ANSIBLE_PLAYBOOK,
            depends_on=["validate_target"],
            is_critical=False,
        ),
    ]


@pytest.mark.asyncio
async def test_apply_to_target_uses_execution_engine(plugin, sample_steps):
    """Test that apply_to_target() calls ExecutionEngine."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    # Patch where ExecutionEngine is imported (inside the method)
    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        # Mock the engine's execute_step method
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = AsyncMock(
            return_value=StepResult(
                step_id="validate_target",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.5,
                stdout="ping successful",
                stderr="",
            )
        )

        # Execute
        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # Verify ExecutionEngine was instantiated
        MockEngine.assert_called_once()
        config_arg = MockEngine.call_args[0][0]
        from src.iac.execution.models import ExecutionConfig
        assert isinstance(config_arg, ExecutionConfig)
        assert config_arg.timeout_seconds == 1800
        assert config_arg.dry_run is False
        assert config_arg.retry_count == 2

        # Verify execute_step was called for each step
        assert mock_engine_instance.execute_step.call_count == 4


@pytest.mark.asyncio
async def test_dependency_checking(plugin, sample_steps):
    """Test that dependencies are checked before execution."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    # Modify steps to have non-critical failures so execution continues
    sample_steps[1].is_critical = False  # replicate_users is not critical

    call_count = 0

    async def mock_execute_step(step, context):
        nonlocal call_count
        call_count += 1

        # First step (validate_target) succeeds
        if step.step_id == "validate_target":
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        # Second step (replicate_users) fails - but is non-critical
        elif step.step_id == "replicate_users":
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.FAILED,
                duration_seconds=2.0,
                stderr="User creation failed",
            )
        # This should never be called because replicate_ssh_keys depends on replicate_users
        else:
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # Verify that replicate_ssh_keys was skipped due to failed dependency
        skipped_step = next(
            (r for r in result.steps_executed if r.get("step_id") == "replicate_ssh_keys"),
            None
        )
        assert skipped_step is not None
        assert skipped_step["status"] == "skipped"
        assert "Unmet dependencies" in skipped_step.get("message", "")


@pytest.mark.asyncio
async def test_critical_failure_stops_execution(plugin, sample_steps):
    """Test that critical failures stop execution."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    steps_executed = []

    async def mock_execute_step(step, context):
        steps_executed.append(step.step_id)

        # First step succeeds
        if step.step_id == "validate_target":
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        # Second step (critical) fails - should stop execution
        elif step.step_id == "replicate_users":
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.FAILED,
                duration_seconds=2.0,
                stderr="Critical failure",
            )
        # These should never be executed
        else:
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # Verify only first two steps were attempted
        assert len(steps_executed) == 2
        assert steps_executed == ["validate_target", "replicate_users"]

        # Verify result reflects critical failure (PARTIAL because one succeeded, one failed)
        assert result.status == ReplicationStatus.PARTIAL
        assert result.steps_succeeded == 1
        assert result.steps_failed == 1


@pytest.mark.asyncio
async def test_fidelity_score_calculation(plugin, sample_steps):
    """Test that fidelity score is calculated correctly."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    async def mock_execute_step(step, context):
        # All steps succeed
        return StepResult(
            step_id=step.step_id,
            status=ReplicationStatus.SUCCESS,
            duration_seconds=1.5,
        )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # All 4 steps succeed
        assert result.fidelity_score == 1.0
        assert result.steps_succeeded == 4
        assert result.steps_failed == 0
        assert result.status == ReplicationStatus.SUCCESS


@pytest.mark.asyncio
async def test_partial_success_fidelity(plugin, sample_steps):
    """Test fidelity score with partial success."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    async def mock_execute_step(step, context):
        # First step succeeds, second fails (non-critical replicate_packages)
        if step.step_id in ["validate_target", "replicate_ssh_keys"]:
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        else:
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.FAILED,
                duration_seconds=1.0,
                stderr="Non-critical failure",
            )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # 2 succeed, 2 fail (but one is skipped due to dependency)
        assert result.status == ReplicationStatus.PARTIAL
        assert 0.0 < result.fidelity_score < 1.0


@pytest.mark.asyncio
async def test_dry_run_mode(plugin, sample_steps):
    """Test that dry_run mode works."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = AsyncMock(
            return_value=StepResult(
                step_id="test",
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        )

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=True)

        # Verify ExecutionEngine was configured with dry_run=True
        config_arg = MockEngine.call_args[0][0]
        assert config_arg.dry_run is True

        # Verify warning about dry-run mode
        assert any("dry-run" in w.lower() for w in result.warnings)


@pytest.mark.asyncio
async def test_context_passed_to_engine(plugin, sample_steps):
    """Test that correct context is passed to execution engine."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    captured_context = None

    async def mock_execute_step(step, context):
        nonlocal captured_context
        captured_context = context
        return StepResult(
            step_id=step.step_id,
            status=ReplicationStatus.SUCCESS,
            duration_seconds=1.0,
        )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # Verify context contains expected fields
        assert captured_context is not None
        assert captured_context["target_resource_id"] == target_id
        assert "output_dir" in captured_context
        assert captured_context["plugin_name"] == "linux_client"


@pytest.mark.asyncio
async def test_exception_handling(plugin, sample_steps):
    """Test that exceptions during execution are handled properly."""
    target_id = "/subscriptions/test/resourceGroups/test/providers/Microsoft.Compute/virtualMachines/test-vm"

    async def mock_execute_step(step, context):
        if step.step_id == "validate_target":
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )
        elif step.step_id == "replicate_users":
            # Raise exception for second step
            raise RuntimeError("Execution engine crashed")
        else:
            return StepResult(
                step_id=step.step_id,
                status=ReplicationStatus.SUCCESS,
                duration_seconds=1.0,
            )

    with patch("src.iac.execution.engine.ExecutionEngine") as MockEngine:
        mock_engine_instance = MockEngine.return_value
        mock_engine_instance.execute_step = mock_execute_step

        result = await plugin.apply_to_target(sample_steps, target_id, dry_run=False)

        # Verify exception was caught and recorded
        error_step = next(
            (r for r in result.steps_executed if r.get("step_id") == "replicate_users"),
            None
        )
        assert error_step is not None
        assert error_step["status"] == "error"
        assert "crashed" in error_step.get("error", "").lower()

        # Critical step failed, so execution stopped (PARTIAL because one succeeded before failure)
        assert result.status == ReplicationStatus.PARTIAL
