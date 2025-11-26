"""
Centralized timeout configuration for all external operations.

This module provides consistent timeout values for subprocess calls, API requests,
database operations, and other external operations that could hang indefinitely.

Timeout values are configurable via environment variables, with sensible defaults
for each operation category.

Usage:
    from src.timeout_config import Timeouts

    # Use in subprocess calls
    subprocess.run(cmd, timeout=Timeouts.TERRAFORM_INIT)

    # Use in Neo4j driver configuration
    driver = GraphDatabase.driver(uri, auth=auth, connection_timeout=Timeouts.NEO4J_CONNECTION)

Environment Variables:
    All timeout values can be overridden via environment variables:
    - ATG_TIMEOUT_QUICK: Quick operations (default: 30s)
    - ATG_TIMEOUT_STANDARD: Standard API calls (default: 60s)
    - ATG_TIMEOUT_INIT: Infrastructure init (default: 120s)
    - ATG_TIMEOUT_BUILD: Build/plan operations (default: 300s)
    - ATG_TIMEOUT_DEPLOY: Long deployments (default: 1800s)
    - ATG_TIMEOUT_NEO4J_CONNECTION: Neo4j connection (default: 30s)
    - ATG_TIMEOUT_NEO4J_QUERY: Neo4j queries (default: 60s)
"""

import logging
import os
from typing import Final

logger = logging.getLogger(__name__)


def _get_timeout(env_var: str, default: int) -> int:
    """Get timeout value from environment variable or use default.

    Args:
        env_var: Environment variable name
        default: Default timeout in seconds

    Returns:
        Timeout value in seconds
    """
    value = os.environ.get(env_var)
    if value is not None:
        try:
            timeout = int(value)
            if timeout <= 0:
                logger.warning(
                    f"Invalid timeout value for {env_var}: {value}. "
                    f"Must be positive. Using default: {default}s"
                )
                return default
            return timeout
        except ValueError:
            logger.warning(
                f"Invalid timeout value for {env_var}: {value}. "
                f"Must be integer. Using default: {default}s"
            )
            return default
    return default


class Timeouts:
    """Centralized timeout constants for all external operations.

    Categories:
        - QUICK: Version checks, health checks, simple queries (10-30s)
        - STANDARD: Azure CLI queries, Neo4j queries (30-60s)
        - INIT: Terraform init, npm install, provider downloads (120s)
        - BUILD: Terraform plan, npm build, validation (300s)
        - DEPLOY: Terraform apply, bicep/ARM deployments (1800s)

    All values are in seconds and configurable via environment variables.
    """

    # Quick operations (10-30 seconds)
    QUICK: Final[int] = _get_timeout("ATG_TIMEOUT_QUICK", 30)
    VERSION_CHECK: Final[int] = QUICK
    HEALTH_CHECK: Final[int] = _get_timeout("ATG_TIMEOUT_HEALTH_CHECK", 10)

    # Standard operations (30-60 seconds)
    STANDARD: Final[int] = _get_timeout("ATG_TIMEOUT_STANDARD", 60)
    AZ_CLI_QUERY: Final[int] = STANDARD
    DOCKER_COMMAND: Final[int] = STANDARD

    # Infrastructure initialization (120 seconds / 2 minutes)
    INIT: Final[int] = _get_timeout("ATG_TIMEOUT_INIT", 120)
    TERRAFORM_INIT: Final[int] = INIT
    NPM_INSTALL: Final[int] = _get_timeout("ATG_TIMEOUT_NPM_INSTALL", 300)

    # Build/plan operations (300 seconds / 5 minutes)
    BUILD: Final[int] = _get_timeout("ATG_TIMEOUT_BUILD", 300)
    TERRAFORM_PLAN: Final[int] = BUILD
    TERRAFORM_VALIDATE: Final[int] = _get_timeout("ATG_TIMEOUT_TERRAFORM_VALIDATE", 60)
    NPM_BUILD: Final[int] = BUILD
    BICEP_VALIDATE: Final[int] = BUILD
    ARM_VALIDATE: Final[int] = BUILD

    # Long deployment operations (1800 seconds / 30 minutes)
    DEPLOY: Final[int] = _get_timeout("ATG_TIMEOUT_DEPLOY", 1800)
    TERRAFORM_APPLY: Final[int] = DEPLOY
    BICEP_DEPLOY: Final[int] = DEPLOY
    ARM_DEPLOY: Final[int] = DEPLOY

    # Neo4j timeouts
    NEO4J_CONNECTION: Final[int] = _get_timeout("ATG_TIMEOUT_NEO4J_CONNECTION", 30)
    NEO4J_QUERY: Final[int] = _get_timeout("ATG_TIMEOUT_NEO4J_QUERY", 60)
    NEO4J_TRANSACTION: Final[int] = _get_timeout("ATG_TIMEOUT_NEO4J_TRANSACTION", 120)

    # Azure SDK timeouts
    AZURE_SDK_CONNECTION: Final[int] = _get_timeout(
        "ATG_TIMEOUT_AZURE_SDK_CONNECTION", 30
    )
    AZURE_SDK_READ: Final[int] = _get_timeout("ATG_TIMEOUT_AZURE_SDK_READ", 60)

    # HTTP request timeouts
    HTTP_CONNECT: Final[int] = _get_timeout("ATG_TIMEOUT_HTTP_CONNECT", 10)
    HTTP_READ: Final[int] = _get_timeout("ATG_TIMEOUT_HTTP_READ", 30)

    # Migration operations
    MIGRATION: Final[int] = _get_timeout("ATG_TIMEOUT_MIGRATION", 300)


class TimeoutError(Exception):
    """Custom exception for timeout operations with context."""

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        timeout_value: int | None = None,
        command: str | list[str] | None = None,
    ):
        """Initialize TimeoutError with context.

        Args:
            message: Error message
            operation: Name of the operation that timed out
            timeout_value: Timeout value that was exceeded
            command: Command that timed out (for subprocess operations)
        """
        super().__init__(message)
        self.operation = operation
        self.timeout_value = timeout_value
        self.command = command

    def __str__(self) -> str:
        parts = [super().__str__()]
        if self.operation:
            parts.append(f"operation={self.operation}")
        if self.timeout_value:
            parts.append(f"timeout={self.timeout_value}s")
        if self.command:
            cmd_str = (
                " ".join(self.command)
                if isinstance(self.command, list)
                else self.command
            )
            # Truncate long commands
            if len(cmd_str) > 100:
                cmd_str = cmd_str[:97] + "..."
            parts.append(f"command='{cmd_str}'")
        return " | ".join(parts)


def log_timeout_event(
    operation: str,
    timeout_value: int,
    command: str | list[str] | None = None,
    level: str = "warning",
) -> None:
    """Log a timeout event with consistent formatting.

    Args:
        operation: Name of the operation that timed out
        timeout_value: Timeout value that was exceeded
        command: Optional command that timed out
        level: Log level (debug, info, warning, error)
    """
    log_func = getattr(logger, level, logger.warning)
    cmd_str = ""
    if command:
        cmd_str = " ".join(command) if isinstance(command, list) else command
        if len(cmd_str) > 100:
            cmd_str = cmd_str[:97] + "..."
        cmd_str = f" - command: '{cmd_str}'"

    log_func(
        f"Operation '{operation}' timed out after {timeout_value} seconds{cmd_str}"
    )
