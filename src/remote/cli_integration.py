"""
CLI Integration - Helper functions for integrating remote mode into CLI.

Philosophy:
- Simple wrapper functions
- Backward compatible with existing CLI
- Zero-BS implementation

Public API:
    execute_with_remote_support: Execute command with remote mode support
    is_remote_mode_enabled: Check if remote mode is enabled
"""

import os
from typing import Any, Callable, Dict

from .client.config import ATGClientConfig
from .client.progress import RemoteProgressDisplay, create_progress_callback
from .dispatcher import ExecutionDispatcher


async def execute_with_remote_support(
    command: str, remote: bool = False, show_progress: bool = True, **kwargs: Any
) -> Dict[str, Any]:
    """
    Execute CLI command with remote mode support.

    Args:
        command: Command name (scan, generate-iac, etc.)
        remote: Force remote mode (overrides config)
        show_progress: Show progress display
        **kwargs: Command parameters

    Returns:
        Command execution results

    Example:
        # Local execution (default)
        result = await execute_with_remote_support(
            "scan",
            tenant_id="12345678-1234-1234-1234-123456789012"
        )

        # Remote execution
        result = await execute_with_remote_support(
            "scan",
            remote=True,
            tenant_id="12345678-1234-1234-1234-123456789012"
        )
    """
    # Create config
    config = ATGClientConfig.from_env()

    # Override remote mode if specified
    if remote:
        config.remote_mode = True

    # Create dispatcher
    dispatcher = ExecutionDispatcher(config=config, remote_mode_override=remote)

    # Set up progress display
    progress_display = RemoteProgressDisplay(show_progress=show_progress)

    # Create progress callback
    if show_progress and dispatcher.is_remote_mode():
        progress_callback = create_progress_callback(progress_display)
        kwargs["progress_callback"] = progress_callback

        # Start progress display
        progress_display.start(f"Executing {command} remotely...")
    else:
        progress_callback = None

    try:
        # Execute command
        result = await dispatcher.execute(
            command, progress_callback=progress_callback, **kwargs
        )

        # Mark complete
        if show_progress and dispatcher.is_remote_mode():
            progress_display.complete(f"{command.capitalize()} completed successfully")

        return result

    except Exception as e:
        # Display error
        if show_progress and dispatcher.is_remote_mode():
            progress_display.error(str(e))
        raise


def is_remote_mode_enabled(remote_flag: bool = False) -> bool:
    """
    Check if remote mode is enabled from env vars or flag.

    Args:
        remote_flag: CLI --remote flag value

    Returns:
        True if remote mode enabled
    """
    # CLI flag takes precedence
    if remote_flag:
        return True

    # Check environment variable
    return os.getenv("ATG_REMOTE_MODE", "").lower() == "true"


def add_remote_option(command_func: Callable[..., Any]) -> Callable[..., Any]:
    """
    Decorator to add --remote option to Click commands.

    Args:
        command_func: Click command function

    Returns:
        Decorated command function with --remote option

    Example:
        @cli.command()
        @add_remote_option
        def scan(ctx, remote, **kwargs):
            # remote flag available
            pass
    """
    import click

    # Add --remote option
    command_func = click.option(
        "--remote",
        is_flag=True,
        default=False,
        help="Execute on remote ATG service (requires ATG_SERVICE_URL and ATG_API_KEY)",
    )(command_func)

    return command_func


__all__ = ["add_remote_option", "execute_with_remote_support", "is_remote_mode_enabled"]
