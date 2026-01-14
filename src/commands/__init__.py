"""Command registry for CLI modularization.

This module provides a plugin-based command registration system that:
1. Auto-discovers command modules in the commands directory
2. Registers commands with the main CLI group
3. Supports lazy loading for faster CLI startup

Issue #482: CLI Modularization
"""

import importlib
import logging
from typing import Callable, Optional

import click

# Re-export from base for convenience (must be at top to avoid E402)
from .base import (
    CommandContext,
    DashboardLogHandler,
    async_command,
    command_context,
    exit_with_error,
    get_neo4j_config_from_env,
    get_tenant_id,
)

logger = logging.getLogger(__name__)

# Registry of all available commands
_COMMAND_REGISTRY: dict[str, Callable] = {}

# Mapping of command names to their module paths (for lazy loading)
_COMMAND_MODULES: dict[str, str] = {
    # Core commands
    "build": "src.commands.scan",
    "scan": "src.commands.scan",
    "test": "src.commands.scan",
    "visualize": "src.commands.visualize",
    "spec": "src.commands.spec",
    "generate-spec": "src.commands.spec",
    # IaC commands
    "generate-iac": "src.commands.generate_iac",
    "deploy": "src.commands.deploy",
    "undeploy": "src.commands.undeploy",
    "list-deployments": "src.commands.list_deployments",
    "validate-deployment": "src.commands.validate_deployment",
    # Tenant management
    "create-tenant": "src.commands.tenant",
    # Agent/AI commands
    "agent-mode": "src.commands.agent",
    "threat-model": "src.commands.threat_model",
    "mcp-server": "src.commands.mcp",
    "mcp-query": "src.commands.mcp",
    # SPA commands
    "start": "src.commands.spa",
    "stop": "src.commands.spa",
    # Auth commands
    "app-registration": "src.commands.auth",
    # Monitoring/analysis commands
    "monitor": "src.commands.monitor",
    "fidelity": "src.commands.fidelity",
    # Cost commands
    "cost-analysis": "src.commands.cost",
    "cost-forecast": "src.commands.cost",
    "cost-report": "src.commands.cost",
    # Simulation commands
    "generate-sim-doc": "src.commands.simulation",
    "gensimdoc": "src.commands.simulation",
    # Database commands
    "backup": "src.commands.database",
    "restore": "src.commands.database",
    "backup-db": "src.commands.database",
    "restore-db": "src.commands.database",
    "wipe": "src.commands.database",
    "container": "src.commands.database",
    # Utility commands
    "config": "src.commands.config",
    "doctor": "src.commands.doctor",
    "check-permissions": "src.commands.doctor",
}


def register_command(name: str, command: Callable) -> None:
    """Register a command in the registry.

    Args:
        name: Command name (as used in CLI)
        command: Click command function
    """
    _COMMAND_REGISTRY[name] = command
    logger.debug(str(f"Registered command: {name}"))


def get_command(name: str) -> Optional[Callable]:
    """Get a command from the registry (with lazy loading).

    Args:
        name: Command name

    Returns:
        Click command function or None if not found
    """
    # Check if already loaded
    if name in _COMMAND_REGISTRY:
        return _COMMAND_REGISTRY[name]

    # Try lazy loading
    if name in _COMMAND_MODULES:
        module_path = _COMMAND_MODULES[name]
        try:
            module = importlib.import_module(module_path)
            # Commands should register themselves on import
            if name in _COMMAND_REGISTRY:
                return _COMMAND_REGISTRY[name]
            # Or look for a function with the command name
            cmd_func_name = name.replace("-", "_")
            if hasattr(module, cmd_func_name):
                command = getattr(module, cmd_func_name)
                register_command(name, command)
                return command
        except ImportError as e:
            logger.warning(str(f"Failed to import command module {module_path}: {e}"))

    return None


def register_all_commands(cli_group: click.Group) -> None:
    """Register all commands with a CLI group.

    This performs eager loading of all command modules.
    Use for production CLI startup.

    Args:
        cli_group: Click group to register commands with
    """
    for name, module_path in _COMMAND_MODULES.items():
        try:
            module = importlib.import_module(module_path)
            # Look for command function
            cmd_func_name = name.replace("-", "_")
            if hasattr(module, cmd_func_name):
                command = getattr(module, cmd_func_name)
                if isinstance(command, click.Command):
                    cli_group.add_command(command, name)
                    logger.debug(str(f"Added command {name} to CLI"))
        except ImportError as e:
            logger.warning(str(f"Failed to import command {name}: {e}"))


# Export public API
__all__ = [
    "CommandContext",
    "DashboardLogHandler",
    "async_command",
    "command_context",
    "exit_with_error",
    "get_command",
    "get_neo4j_config_from_env",
    "get_tenant_id",
    "register_all_commands",
    "register_command",
]
