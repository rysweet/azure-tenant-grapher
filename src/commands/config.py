"""Configuration display command.

This module provides the 'config' command for displaying current
configuration settings without sensitive data.

Issue #482: CLI Modularization
"""

from typing import Any

import click

from src.config_manager import create_config_from_env


@click.command("config")
def config() -> None:
    """Show current configuration (without sensitive data)."""
    try:
        # Create dummy configuration to show structure
        config_obj = create_config_from_env("example-tenant-id")

        click.echo("Current Configuration Template:")
        click.echo("=" * 60)

        config_dict = config_obj.to_dict()

        def print_dict(d: Any, indent: int = 0) -> None:
            for key, value in d.items():
                if isinstance(value, dict):
                    click.echo("  " * indent + f"{key}:")
                    print_dict(value, indent + 1)
                else:
                    click.echo("  " * indent + f"{key}: {value}")

        print_dict(config_dict)
        click.echo("=" * 60)
        click.echo("Set environment variables to customize configuration")

    except Exception as e:
        click.echo(f"Failed to display configuration: {e}", err=True)


# For backward compatibility with registry pattern
config_command = config

__all__ = ["config", "config_command"]
