"""
Unit tests for CLI command dispatcher.

Tests local vs remote routing logic, mode detection, and command execution
delegation following simplified architecture.

Philosophy:
- Test dispatcher logic in isolation
- Mock both local and remote execution
- Fast execution (< 100ms per test)
- Follow architecture from Specs/SIMPLIFIED_ARCHITECTURE.md Section 3.1
"""

from unittest.mock import AsyncMock, patch

import pytest

# =============================================================================
# Execution Dispatcher Tests (Architecture Section 3.1)
# =============================================================================


def test_dispatcher_detects_local_mode_by_default():
    """Test that dispatcher defaults to local mode when no config present."""
    from src.remote.dispatcher import ExecutionDispatcher

    # This class doesn't exist yet - will fail!
    dispatcher = ExecutionDispatcher()

    assert dispatcher.is_remote_mode() is False


def test_dispatcher_detects_remote_mode_from_env():
    """Test that dispatcher detects remote mode from environment variable."""
    import os

    from src.remote.dispatcher import ExecutionDispatcher

    with patch.dict(os.environ, {"ATG_REMOTE_MODE": "true"}, clear=True):
        dispatcher = ExecutionDispatcher()

    assert dispatcher.is_remote_mode() is True


def test_dispatcher_detects_remote_mode_from_config():
    """Test that dispatcher detects remote mode from config object."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)

    assert dispatcher.is_remote_mode() is True


def test_dispatcher_detects_remote_mode_from_cli_flag():
    """Test that dispatcher detects remote mode from CLI --remote flag."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher(remote_mode_override=True)

    assert dispatcher.is_remote_mode() is True


@pytest.mark.asyncio
async def test_dispatcher_routes_scan_to_local():
    """Test that dispatcher routes scan command to local execution."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()  # Local mode by default

    mock_local_executor = AsyncMock()
    mock_local_executor.scan = AsyncMock(
        return_value={"status": "success", "resources": 100}
    )

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        result = await dispatcher.execute(
            "scan", tenant_id="12345678-1234-1234-1234-123456789012"
        )

    mock_local_executor.scan.assert_called_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_dispatcher_routes_scan_to_remote():
    """Test that dispatcher routes scan command to remote execution."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)

    mock_remote_client = AsyncMock()
    mock_remote_client.scan = AsyncMock(
        return_value={"status": "success", "resources": 1523}
    )

    with patch.object(dispatcher, "_remote_client", mock_remote_client):
        result = await dispatcher.execute(
            "scan", tenant_id="12345678-1234-1234-1234-123456789012"
        )

    mock_remote_client.scan.assert_called_once()
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_dispatcher_handles_unknown_command():
    """Test that dispatcher raises error for unknown commands."""
    from src.remote.dispatcher import CommandNotFoundError, ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    with pytest.raises(CommandNotFoundError) as exc_info:
        await dispatcher.execute("unknown_command")

    assert "unknown_command" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_dispatcher_validates_required_parameters():
    """Test that dispatcher validates required parameters for commands."""
    from src.remote.dispatcher import ExecutionDispatcher, ParameterValidationError

    dispatcher = ExecutionDispatcher()

    # scan requires tenant_id
    with pytest.raises(ParameterValidationError) as exc_info:
        await dispatcher.execute("scan")  # Missing tenant_id

    assert "tenant_id" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_dispatcher_passes_all_parameters_to_executor():
    """Test that dispatcher passes all parameters to executor."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    mock_local_executor = AsyncMock()
    mock_local_executor.scan = AsyncMock(return_value={"status": "success"})

    params = {
        "tenant_id": "12345678-1234-1234-1234-123456789012",
        "resource_limit": 1000,
        "max_llm_threads": 10,
        "generate_spec": True,
    }

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        await dispatcher.execute("scan", **params)

    # Verify all parameters passed
    call_kwargs = mock_local_executor.scan.call_args[1]
    assert call_kwargs["tenant_id"] == params["tenant_id"]
    assert call_kwargs["resource_limit"] == params["resource_limit"]
    assert call_kwargs["max_llm_threads"] == params["max_llm_threads"]
    assert call_kwargs["generate_spec"] == params["generate_spec"]


# =============================================================================
# Progress Callback Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dispatcher_forwards_progress_callbacks_local():
    """Test that dispatcher forwards progress callbacks in local mode."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append((progress, message))

    mock_local_executor = AsyncMock()

    async def mock_scan(*args, **kwargs):
        callback = kwargs.get("progress_callback")
        if callback:
            callback(50.0, "Halfway done")
            callback(100.0, "Complete")
        return {"status": "success"}

    mock_local_executor.scan = mock_scan

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        await dispatcher.execute(
            "scan",
            tenant_id="12345678-1234-1234-1234-123456789012",
            progress_callback=progress_callback,
        )

    assert len(progress_updates) == 2
    assert progress_updates[0] == (50.0, "Halfway done")
    assert progress_updates[1] == (100.0, "Complete")


@pytest.mark.asyncio
async def test_dispatcher_forwards_progress_callbacks_remote():
    """Test that dispatcher forwards progress callbacks in remote mode."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)

    progress_updates = []

    def progress_callback(progress: float, message: str):
        progress_updates.append((progress, message))

    mock_remote_client = AsyncMock()

    async def mock_scan(*args, **kwargs):
        callback = kwargs.get("progress_callback")
        if callback:
            callback(25.0, "Quarter done")
            callback(75.0, "Almost done")
        return {"status": "success"}

    mock_remote_client.scan = mock_scan

    with patch.object(dispatcher, "_remote_client", mock_remote_client):
        await dispatcher.execute(
            "scan",
            tenant_id="12345678-1234-1234-1234-123456789012",
            progress_callback=progress_callback,
        )

    assert len(progress_updates) == 2


# =============================================================================
# Error Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dispatcher_handles_local_execution_errors():
    """Test that dispatcher handles errors from local execution."""
    from src.remote.dispatcher import ExecutionDispatcher, LocalExecutionError

    dispatcher = ExecutionDispatcher()

    mock_local_executor = AsyncMock()
    mock_local_executor.scan = AsyncMock(side_effect=Exception("Azure auth failed"))

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        with pytest.raises(LocalExecutionError) as exc_info:
            await dispatcher.execute(
                "scan", tenant_id="12345678-1234-1234-1234-123456789012"
            )

    assert "azure auth failed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_dispatcher_handles_remote_execution_errors():
    """Test that dispatcher handles errors from remote execution."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher, RemoteExecutionError

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)

    mock_remote_client = AsyncMock()
    mock_remote_client.scan = AsyncMock(side_effect=Exception("API timeout"))

    with patch.object(dispatcher, "_remote_client", mock_remote_client):
        with pytest.raises(RemoteExecutionError) as exc_info:
            await dispatcher.execute(
                "scan", tenant_id="12345678-1234-1234-1234-123456789012"
            )

    assert "api timeout" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_dispatcher_handles_connection_errors():
    """Test that dispatcher handles connection errors to remote service."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ConnectionError, ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)

    mock_remote_client = AsyncMock()
    mock_remote_client.scan = AsyncMock(
        side_effect=ConnectionError("Failed to connect to https://atg-dev.example.com")
    )

    with patch.object(dispatcher, "_remote_client", mock_remote_client):
        with pytest.raises(ConnectionError) as exc_info:
            await dispatcher.execute(
                "scan", tenant_id="12345678-1234-1234-1234-123456789012"
            )

    assert "failed to connect" in str(exc_info.value).lower()


# =============================================================================
# Command Registry Tests
# =============================================================================


def test_dispatcher_registers_supported_commands():
    """Test that dispatcher has all supported commands registered."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    expected_commands = [
        "scan",
        "generate-spec",
        "generate-iac",
        "create-tenant",
        "visualize",
        "threat-model",
        "agent-mode",
    ]

    for command in expected_commands:
        assert dispatcher.is_command_supported(command)


def test_dispatcher_rejects_unsupported_commands():
    """Test that dispatcher rejects unsupported commands."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    unsupported_commands = ["invalid", "hack-the-planet", "delete-everything"]

    for command in unsupported_commands:
        assert not dispatcher.is_command_supported(command)


def test_dispatcher_provides_command_metadata():
    """Test that dispatcher provides metadata for each command."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    metadata = dispatcher.get_command_metadata("scan")

    assert metadata is not None
    assert "description" in metadata
    assert "required_params" in metadata
    assert "optional_params" in metadata
    assert "tenant_id" in metadata["required_params"]


# =============================================================================
# Mode Switching Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dispatcher_can_switch_modes_at_runtime():
    """Test that dispatcher can switch between local and remote modes."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()  # Start in local mode

    assert dispatcher.is_remote_mode() is False

    # Switch to remote mode
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher.switch_mode(config)

    assert dispatcher.is_remote_mode() is True


@pytest.mark.asyncio
async def test_dispatcher_switches_back_to_local_mode():
    """Test that dispatcher can switch back to local mode."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
    )

    dispatcher = ExecutionDispatcher(config=config)  # Start in remote mode

    assert dispatcher.is_remote_mode() is True

    # Switch to local mode
    dispatcher.switch_mode(None)

    assert dispatcher.is_remote_mode() is False


# =============================================================================
# Configuration Validation Tests
# =============================================================================


def test_dispatcher_validates_remote_config_required_fields():
    """Test that dispatcher validates remote config has required fields."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ConfigurationError, ExecutionDispatcher

    # Config missing API key
    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key=None,  # Missing!
    )

    with pytest.raises(ConfigurationError) as exc_info:
        ExecutionDispatcher(config=config)

    assert "api key" in str(exc_info.value).lower()


def test_dispatcher_validates_service_url_format():
    """Test that dispatcher validates service URL format."""
    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ConfigurationError, ExecutionDispatcher

    config = ATGClientConfig(
        remote_mode=True,
        service_url="invalid-url",  # Not valid HTTPS URL
        api_key="atg_dev_" + "a" * 64,
    )

    with pytest.raises(ConfigurationError) as exc_info:
        ExecutionDispatcher(config=config)

    assert "url" in str(exc_info.value).lower()


# =============================================================================
# Timeout Handling Tests
# =============================================================================


@pytest.mark.asyncio
async def test_dispatcher_respects_timeout_for_remote_operations():
    """Test that dispatcher respects timeout for remote operations."""
    import asyncio

    from src.remote.client.config import ATGClientConfig
    from src.remote.dispatcher import ExecutionDispatcher, TimeoutError

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
        request_timeout=1,  # 1 second timeout
    )

    dispatcher = ExecutionDispatcher(config=config)

    mock_remote_client = AsyncMock()

    async def slow_scan(*args, **kwargs):
        await asyncio.sleep(5)  # Longer than timeout
        return {"status": "success"}

    mock_remote_client.scan = slow_scan

    with patch.object(dispatcher, "_remote_client", mock_remote_client):
        with pytest.raises(TimeoutError) as exc_info:
            await dispatcher.execute(
                "scan", tenant_id="12345678-1234-1234-1234-123456789012"
            )

    assert "timeout" in str(exc_info.value).lower()


# =============================================================================
# Statistics and Monitoring Tests
# =============================================================================


def test_dispatcher_tracks_execution_statistics():
    """Test that dispatcher tracks execution statistics."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    stats = dispatcher.get_statistics()

    assert "total_executions" in stats
    assert "local_executions" in stats
    assert "remote_executions" in stats
    assert "failed_executions" in stats


@pytest.mark.asyncio
async def test_dispatcher_increments_execution_counters():
    """Test that dispatcher increments execution counters."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    mock_local_executor = AsyncMock()
    mock_local_executor.scan = AsyncMock(return_value={"status": "success"})

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        await dispatcher.execute(
            "scan", tenant_id="12345678-1234-1234-1234-123456789012"
        )

    stats = dispatcher.get_statistics()

    assert stats["total_executions"] == 1
    assert stats["local_executions"] == 1
    assert stats["remote_executions"] == 0


@pytest.mark.asyncio
async def test_dispatcher_tracks_failure_rate():
    """Test that dispatcher tracks execution failure rate."""
    from src.remote.dispatcher import ExecutionDispatcher

    dispatcher = ExecutionDispatcher()

    mock_local_executor = AsyncMock()
    # First call succeeds, second fails
    mock_local_executor.scan = AsyncMock(
        side_effect=[{"status": "success"}, Exception("Failed")]
    )

    with patch.object(dispatcher, "_local_executor", mock_local_executor):
        # Success
        await dispatcher.execute(
            "scan", tenant_id="12345678-1234-1234-1234-123456789012"
        )

        # Failure
        try:
            await dispatcher.execute(
                "scan", tenant_id="12345678-1234-1234-1234-123456789012"
            )
        except Exception:
            pass

    stats = dispatcher.get_statistics()

    assert stats["total_executions"] == 2
    assert stats["failed_executions"] == 1
    assert stats["failure_rate"] == 0.5  # 50%
