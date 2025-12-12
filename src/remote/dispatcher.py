"""
Execution Dispatcher - Routes CLI commands to local or remote execution.

Philosophy:
- Simple routing logic based on configuration
- Zero-BS - All error handling works
- Clear separation between local and remote execution

Public API:
    ExecutionDispatcher: Routes commands to local or remote execution
"""

import asyncio
import inspect
import os
from typing import Any, Callable, Dict, Optional

from ..timeout_config import TimeoutError
from .client.config import ATGClientConfig
from .client.remote_client import RemoteClient
from .common.exceptions import (
    CommandNotFoundError,
    ConfigurationError,
    ConnectionError,
    LocalExecutionError,
    ParameterValidationError,
    RemoteExecutionError,
)


class ExecutionDispatcher:
    """
    Routes CLI commands to local or remote execution based on configuration.

    Philosophy:
    - Detect mode from config, env vars, or CLI flag
    - Route to appropriate executor (local or remote)
    - Forward progress callbacks
    - Track execution statistics
    """

    # Supported commands and their required parameters
    COMMAND_REGISTRY = {
        "scan": {
            "description": "Scan Azure tenant and build graph",
            "required_params": ["tenant_id"],
            "optional_params": ["resource_limit", "max_llm_threads", "generate_spec"],
        },
        "generate-spec": {
            "description": "Generate tenant specification markdown",
            "required_params": [],
            "optional_params": ["output_file"],
        },
        "generate-iac": {
            "description": "Generate Infrastructure-as-Code from graph",
            "required_params": [],
            "optional_params": ["format", "output_dir", "tenant_id"],
        },
        "create-tenant": {
            "description": "Create tenant from specification",
            "required_params": ["spec_file"],
            "optional_params": [],
        },
        "visualize": {
            "description": "Visualize graph in GUI",
            "required_params": [],
            "optional_params": [],
        },
        "threat-model": {
            "description": "Generate threat model report",
            "required_params": [],
            "optional_params": ["output_file"],
        },
        "agent-mode": {
            "description": "Interactive agent mode",
            "required_params": [],
            "optional_params": [],
        },
    }

    def __init__(
        self,
        config: Optional[ATGClientConfig] = None,
        remote_mode_override: Optional[bool] = None,
    ):
        """
        Initialize execution dispatcher.

        Args:
            config: Client configuration (if None, loads from env)
            remote_mode_override: Override remote mode from CLI flag
        """
        # Load config if not provided (validation happens in from_env)
        if config is None:
            config = ATGClientConfig.from_env(validate=False)

        self.config = config
        self._remote_mode_override = remote_mode_override

        # Validate config if remote mode is active (after override is set)
        if self.is_remote_mode():
            self.config.validate()

        # Defer remote client initialization until first use
        # (allows tests to check mode detection without needing full config)
        self._remote_client: Optional[RemoteClient] = None

        # Initialize local executor (imports deferred to avoid circular deps)
        self._local_executor = None

        # Statistics tracking
        self._stats = {
            "total_executions": 0,
            "local_executions": 0,
            "remote_executions": 0,
            "failed_executions": 0,
        }

    def is_remote_mode(self) -> bool:
        """
        Check if remote mode is configured and enabled.

        Returns:
            True if remote mode active, False otherwise
        """
        # CLI flag override takes precedence
        if self._remote_mode_override is not None:
            return self._remote_mode_override

        # Check environment variable
        if os.getenv("ATG_REMOTE_MODE", "").lower() == "true":
            return True

        # Check config
        return self.config.remote_mode

    def is_command_supported(self, command: str) -> bool:
        """
        Check if command is supported.

        Args:
            command: Command name

        Returns:
            True if command supported, False otherwise
        """
        return command in self.COMMAND_REGISTRY

    def get_command_metadata(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a command.

        Args:
            command: Command name

        Returns:
            Command metadata dictionary or None if not found
        """
        return self.COMMAND_REGISTRY.get(command)

    async def execute(
        self,
        command: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute command in appropriate mode (local or remote).

        Args:
            command: Command name (scan, generate-iac, etc.)
            progress_callback: Optional callback for progress updates
            **kwargs: Command parameters

        Returns:
            Command execution results

        Raises:
            CommandNotFoundError: If command not supported
            ParameterValidationError: If required parameters missing
            LocalExecutionError: If local execution fails
            RemoteExecutionError: If remote execution fails
            ConnectionError: If cannot connect to remote service
        """
        # Validate command exists
        if not self.is_command_supported(command):
            raise CommandNotFoundError(
                f"Unknown command: {command}. "
                f"Supported: {', '.join(self.COMMAND_REGISTRY.keys())}"
            )

        # Validate required parameters
        metadata = self.get_command_metadata(command)
        required_params = metadata.get("required_params", [])
        for param in required_params:
            if param not in kwargs:
                raise ParameterValidationError(
                    f"Missing required parameter for '{command}': {param}"
                )

        # Track execution
        self._stats["total_executions"] += 1

        # Route to appropriate executor
        try:
            if self.is_remote_mode():
                self._stats["remote_executions"] += 1
                return await self._execute_remote(command, progress_callback, **kwargs)
            else:
                self._stats["local_executions"] += 1
                return await self._execute_local(command, progress_callback, **kwargs)
        except Exception:
            self._stats["failed_executions"] += 1
            raise

    async def _execute_local(
        self,
        command: str,
        progress_callback: Optional[Callable[[float, str], None]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute command locally using existing ATG services.

        Args:
            command: Command name
            progress_callback: Optional progress callback
            **kwargs: Command parameters

        Returns:
            Execution results

        Raises:
            LocalExecutionError: If execution fails
        """
        # Lazy import to avoid circular dependencies
        if self._local_executor is None:
            from ..cli_commands import (
                create_tenant_from_spec,
                generate_iac,
                generate_tenant_spec,
                generate_threat_model,
                scan_tenant,
                start_agent_mode,
                visualize_graph,
            )

            self._local_executor = {
                "scan": scan_tenant,
                "generate-spec": generate_tenant_spec,
                "generate-iac": generate_iac,
                "create-tenant": create_tenant_from_spec,
                "visualize": visualize_graph,
                "threat-model": generate_threat_model,
                "agent-mode": start_agent_mode,
            }

        try:
            # Get local function
            local_fn = self._local_executor.get(command)
            if not local_fn:
                raise LocalExecutionError(f"Local executor not found for: {command}")

            # Execute with progress callback if provided
            if progress_callback:
                kwargs["progress_callback"] = progress_callback

            # Call local function (may be sync or async)
            if inspect.iscoroutinefunction(local_fn):
                result = await local_fn(**kwargs)
            else:
                result = local_fn(**kwargs)

            return {"status": "success", "result": result}

        except Exception as e:
            raise LocalExecutionError(f"Local execution failed: {e}") from e

    async def _execute_remote(
        self,
        command: str,
        progress_callback: Optional[Callable[[float, str], None]],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Execute command via remote service.

        Args:
            command: Command name
            progress_callback: Optional progress callback
            **kwargs: Command parameters

        Returns:
            Execution results

        Raises:
            RemoteExecutionError: If remote execution fails
            ConnectionError: If cannot connect to service
            TimeoutError: If operation times out
        """
        # Lazy initialization of remote client
        if not self._remote_client:
            if not self.config.service_url or not self.config.api_key:
                raise ConfigurationError(
                    "Remote mode requires ATG_SERVICE_URL and ATG_API_KEY"
                )

            self._remote_client = RemoteClient(
                base_url=self.config.service_url,
                api_key=self.config.api_key,
                timeout=self.config.request_timeout,
            )

        try:
            # Map commands to remote client methods with timeout enforcement
            if command == "scan":
                coro = self._remote_client.scan(
                    progress_callback=progress_callback, **kwargs
                )
            elif command == "generate-iac":
                coro = self._remote_client.generate_iac(
                    progress_callback=progress_callback, **kwargs
                )
            else:
                raise RemoteExecutionError(
                    f"Remote execution not implemented for: {command}"
                )

            # Enforce timeout at dispatcher level
            try:
                return await asyncio.wait_for(coro, timeout=self.config.request_timeout)
            except asyncio.TimeoutError as e:
                raise TimeoutError(
                    f"Remote operation timed out after {self.config.request_timeout}s",
                    operation=f"remote_{command}",
                    timeout_value=self.config.request_timeout,
                ) from e

        except TimeoutError:
            # Re-raise our custom TimeoutError as-is
            raise
        except Exception as e:
            # Handle connection errors
            if "connect" in str(e).lower() or "connection" in str(e).lower():
                raise ConnectionError(
                    f"Failed to connect to remote service: {e}"
                ) from e
            # All other errors are remote execution errors
            raise RemoteExecutionError(f"Remote execution failed: {e}") from e

    def switch_mode(self, config: Optional[ATGClientConfig] = None) -> None:
        """
        Switch between local and remote modes at runtime.

        Args:
            config: New configuration (None for local mode)
        """
        if config is None:
            # Switch to local mode
            self.config = ATGClientConfig(remote_mode=False)
            self._remote_client = None
        else:
            # Switch to remote mode
            self.config = config
            if self.is_remote_mode():
                self._remote_client = RemoteClient(
                    base_url=self.config.service_url,
                    api_key=self.config.api_key,
                    timeout=self.config.request_timeout,
                )

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get execution statistics.

        Returns:
            Dictionary with execution stats
        """
        stats = self._stats.copy()

        # Calculate failure rate
        total = stats["total_executions"]
        failed = stats["failed_executions"]
        stats["failure_rate"] = (failed / total) if total > 0 else 0.0

        return stats


__all__ = ["ExecutionDispatcher", "TimeoutError"]
