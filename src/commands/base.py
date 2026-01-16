"""Base command infrastructure and shared utilities.

This module provides common utilities used across command modules:
- DashboardLogHandler for sending logs to the Rich dashboard
- CommandContext for shared command execution context
- Helper functions for Neo4j configuration and tenant ID resolution

Issue #482: CLI Modularization
"""

import asyncio
import functools
import logging
import os
import sys
from typing import TYPE_CHECKING, Any, Callable, Coroutine, Optional

import click

from src.cli_dashboard_manager import DashboardExitException
from src.config_manager import (
    create_config_from_env,
    create_neo4j_config_from_env,
    setup_logging,
)
from src.utils.neo4j_startup import ensure_neo4j_running

if TYPE_CHECKING:
    from src.rich_dashboard import RichDashboard


class DashboardLogHandler(logging.Handler):
    """Custom log handler that sends logs to the dashboard."""

    def __init__(self, dashboard: "RichDashboard") -> None:
        super().__init__()
        self.dashboard = dashboard

    def emit(self, record: logging.LogRecord) -> None:
        # Only emit logs that meet the handler's level threshold
        if record.levelno < self.level:
            return

        msg = self.format(record)
        # Color by level
        if record.levelno >= logging.ERROR:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.WARNING:
            self.dashboard.add_error(msg)
        elif record.levelno >= logging.INFO:
            self.dashboard.log_info(msg)
        else:
            self.dashboard.log_info(msg)


class CommandContext:
    """Shared context for command execution."""

    def __init__(
        self,
        ctx: click.Context,
        debug: bool = False,
        log_level: str = "INFO",
    ):
        self.click_ctx = ctx
        self.debug = debug
        self.log_level = log_level
        self._neo4j_ensured = False

    def ensure_neo4j(self) -> None:
        """Ensure Neo4j is running (idempotent)."""
        if not self._neo4j_ensured:
            ensure_neo4j_running(self.debug)
            self._neo4j_ensured = True

    def get_tenant_id(self, provided: Optional[str] = None) -> str:
        """Get tenant ID from argument or environment."""
        tenant_id = provided or os.environ.get("AZURE_TENANT_ID")
        if not tenant_id:
            click.echo(
                "No tenant ID provided and AZURE_TENANT_ID not set in environment.",
                err=True,
            )
            sys.exit(1)
        return tenant_id

    def get_config(self, tenant_id: str, **kwargs: Any) -> Any:
        """Get configuration from environment."""
        config = create_config_from_env(tenant_id, **kwargs)
        config.logging.level = self.log_level
        setup_logging(config.logging)
        return config

    def get_neo4j_config(self) -> Any:
        """Get Neo4j-only configuration."""
        config = create_neo4j_config_from_env()
        config.logging.level = self.log_level
        setup_logging(config.logging)
        return config


def command_context(ctx: click.Context) -> CommandContext:
    """Create CommandContext from click context."""
    return CommandContext(
        ctx=ctx,
        debug=ctx.obj.get("debug", False),
        log_level=ctx.obj.get("log_level", "INFO"),
    )


def exit_with_error(message: str, code: int = 1) -> None:
    """Exit with error message."""
    click.echo(f"Error: {message}", err=True)
    sys.exit(code)


def get_tenant_id(provided: Optional[str] = None) -> str:
    """Get tenant ID from argument or environment.

    Args:
        provided: Explicitly provided tenant ID

    Returns:
        Tenant ID string

    Raises:
        SystemExit: If no tenant ID is available
    """
    tenant_id = provided or os.environ.get("AZURE_TENANT_ID")
    if not tenant_id:
        click.echo(
            "No tenant ID provided and AZURE_TENANT_ID not set in environment.",
            err=True,
        )
        sys.exit(1)
    return tenant_id


def get_neo4j_config_from_env() -> tuple[str, str, str]:
    """Get Neo4j connection details from environment.

    Returns:
        Tuple of (uri, user, password)

    Raises:
        SystemExit: If required environment variables are not set
    """
    neo4j_uri = os.environ.get("NEO4J_URI")
    if not neo4j_uri:
        neo4j_port = os.environ.get("NEO4J_PORT")
        if not neo4j_port:
            click.echo("Either NEO4J_URI or NEO4J_PORT must be set", err=True)
            sys.exit(1)
        neo4j_uri = f"bolt://localhost:{neo4j_port}"

    neo4j_user = os.environ.get("NEO4J_USER", "neo4j")
    neo4j_password = os.environ.get("NEO4J_PASSWORD")
    if not neo4j_password:
        click.echo("NEO4J_PASSWORD environment variable is required", err=True)
        sys.exit(1)

    return neo4j_uri, neo4j_user, neo4j_password


def async_command(f: Callable[..., Coroutine[Any, Any, Any]]) -> Callable[..., Any]:
    """Decorator to make Click commands async-compatible.

    Handles both running inside and outside of existing event loops.
    Also handles special sentinel return values for dashboard exit.
    """

    @functools.wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Already in an event loop (e.g., pytest-asyncio, Jupyter)
                import nest_asyncio  # type: ignore[import-untyped]

                nest_asyncio.apply()
                task = loop.create_task(f(*args, **kwargs))
                result = loop.run_until_complete(task)
            else:
                result = asyncio.run(f(*args, **kwargs))

            # Handle dashboard exit sentinels
            if result == "__DASHBOARD_EXIT__":
                debug = (
                    getattr(args[0], "obj", {}).get("debug", False) if args else False
                )
                if debug:
                    print(
                        "[DEBUG] EXIT SENTINEL '__DASHBOARD_EXIT__' detected.",
                        file=sys.stderr,
                    )
                sys.stderr.flush()
                sys.exit(0)

            if result == "__NO_DASHBOARD_BUILD_COMPLETE__":
                debug = (
                    getattr(args[0], "obj", {}).get("debug", False) if args else False
                )
                if debug:
                    print(
                        "[DEBUG] EXIT SENTINEL '__NO_DASHBOARD_BUILD_COMPLETE__' detected.",
                        file=sys.stderr,
                    )
                sys.stderr.flush()
                sys.exit(0)

            return result
        except DashboardExitException:
            sys.exit(0)

    return wrapper


__all__ = [
    "CommandContext",
    "DashboardLogHandler",
    "async_command",
    "command_context",
    "exit_with_error",
    "get_neo4j_config_from_env",
    "get_tenant_id",
]
