"""
Debug utility module for Azure Tenant Grapher

This module provides utilities for controlling debug output throughout the application.
Debug output is only shown when the --debug flag is passed to the CLI.
"""

import os
from typing import Any


class DebugState:
    """Global debug state management."""

    _debug_enabled = False
    _initialized = False

    @classmethod
    def enable_debug(cls) -> None:
        """Enable debug output."""
        cls._debug_enabled = True
        cls._initialized = True

    @classmethod
    def disable_debug(cls) -> None:
        """Disable debug output."""
        cls._debug_enabled = False
        cls._initialized = True

    @classmethod
    def is_debug_enabled(cls) -> bool:
        """Check if debug output is enabled."""
        return cls._debug_enabled

    @classmethod
    def is_initialized(cls) -> bool:
        """Check if debug state has been initialized."""
        return cls._initialized


def debug_print(*args: Any, **kwargs: Any) -> None:
    """
    Print debug output only if debug mode is enabled.

    Args:
        *args: Arguments to pass to print()
        **kwargs: Keyword arguments to pass to print()
    """
    if DebugState.is_debug_enabled():
        print(*args, **kwargs)


def print_cli_env_block(context: str = "") -> None:
    """
    Print CLI environment variables block, only if debug is enabled.

    Args:
        context: Optional context string to add to the header
    """
    if not DebugState.is_debug_enabled():
        return

    print(f"[CLI ENV DUMP]{'[' + context + ']' if context else ''}")
    for k in [
        "NEO4J_CONTAINER_NAME",
        "NEO4J_DATA_VOLUME",
        "NEO4J_PASSWORD",
        "NEO4J_PORT",
        "NEO4J_URI",
    ]:
        print(f"[CLI ENV] {k}={os.environ.get(k)}")
