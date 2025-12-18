"""Doctor and permissions checking commands.

This module provides:
- 'doctor' command: Check all CLI tools and Azure permissions
- 'check-permissions' command: Check Microsoft Graph API permissions

Issue #482: CLI Modularization
"""

import json
import os
import subprocess

import click


@click.command("doctor")
def doctor() -> None:
    """Check for all registered CLI tools and offer to install if missing.

    Also validates Azure service principal permissions for role assignment scanning.
    """
    try:
        from src.utils.cli_installer import (
            TOOL_REGISTRY,
            install_tool,
            is_tool_installed,
        )
    except ImportError:
        click.echo("Could not import TOOL_REGISTRY. Please check your installation.")
        return

    # Check CLI tools
    click.echo("=" * 60)
    click.echo("Checking CLI Tools")
    click.echo("=" * 60)
    for tool in TOOL_REGISTRY.values():
        click.echo(f"Checking for '{tool.name}' CLI...")
        if is_tool_installed(tool.name):
            click.echo(f"  {tool.name} is installed.")
        else:
            click.echo(f"  {tool.name} is NOT installed.")
            install_tool(tool.name)

    # Check Azure permissions
    click.echo("\n" + "=" * 60)
    click.echo("Checking Azure Service Principal Permissions")
    click.echo("=" * 60)

    _check_azure_permissions()

    click.echo("")
    click.echo("=" * 60)
    click.echo("Doctor check complete.")
    click.echo("=" * 60)


def _check_azure_permissions() -> None:
    """Check Azure service principal permissions."""
    try:
        client_id = os.getenv("AZURE_CLIENT_ID")
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")

        if not client_id or not subscription_id:
            click.echo(
                "  AZURE_CLIENT_ID or AZURE_SUBSCRIPTION_ID not set in environment"
            )
            click.echo("  Cannot validate permissions without these values")
            return

        click.echo(f"Service Principal: {client_id}")
        click.echo(f"Subscription: {subscription_id}")
        click.echo("")

        # Check role assignments
        result = subprocess.run(
            [
                "az",
                "role",
                "assignment",
                "list",
                "--assignee",
                client_id,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            click.echo(f"  Failed to check role assignments: {result.stderr}")
            return

        roles = json.loads(result.stdout)
        role_names = [r.get("roleDefinitionName") for r in roles]

        click.echo("Assigned Roles:")
        for role_name in role_names:
            click.echo(f"    {role_name}")

        # Check for required roles
        has_reader = (
            "Reader" in role_names
            or "Contributor" in role_names
            or "Owner" in role_names
        )
        has_security_reader = (
            "Security Reader" in role_names
            or "Owner" in role_names
            or "User Access Administrator" in role_names
        )

        click.echo("")
        click.echo("Permission Requirements for Full Functionality:")

        if has_reader:
            click.echo("    Resource Scanning: Reader, Contributor, or Owner (PRESENT)")
        else:
            click.echo("    Resource Scanning: Reader, Contributor, or Owner (MISSING)")
            click.echo("     Impact: Cannot scan Azure resources")

        if has_security_reader:
            click.echo(
                "    Role Assignment Scanning: Security Reader, User Access Administrator, or Owner (PRESENT)"
            )
        else:
            click.echo(
                "    Role Assignment Scanning: Security Reader, User Access Administrator, or Owner (MISSING)"
            )
            click.echo(
                "     Impact: Cannot scan role assignments (RBAC will not be replicated!)"
            )
            click.echo("")
            click.echo("     FIX: Run this command to add Security Reader role:")
            click.echo("     az role assignment create \\")
            click.echo(f"       --assignee {client_id} \\")
            click.echo("       --role 'Security Reader' \\")
            click.echo(f"       --scope '/subscriptions/{subscription_id}'")
            click.echo("")
            click.echo("     OR use the automated script:")
            click.echo(
                "     ./scripts/setup_service_principal.sh <TENANT_NAME> <TENANT_ID>"
            )

        click.echo("")
        if has_reader and has_security_reader:
            click.echo(
                "  ALL REQUIRED PERMISSIONS PRESENT - Ready for full E2E replication!"
            )
        else:
            click.echo("  MISSING PERMISSIONS - Scanning will be limited!")

    except subprocess.TimeoutExpired:
        click.echo("  Permission check timed out")
    except Exception as e:
        click.echo(f"  Could not validate Azure permissions: {e}")


@click.command("check-permissions")
def check_permissions() -> None:
    """Check Microsoft Graph API permissions for AAD/Entra ID discovery."""
    click.echo("Checking Microsoft Graph API Permissions")

    # Run the test script
    try:
        result = subprocess.run(
            ["uv", "run", "python", "test_graph_api.py"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Check if the command failed
        if result.returncode != 0:
            click.echo(f"  Error running test script: {result.stderr}")
            return

        # Combine stdout and stderr for parsing (logging might go to stderr)
        output = result.stdout + result.stderr

        # Parse the output for display
        if "Can read users" in output:
            click.echo("  User.Read permission granted")
        else:
            click.echo("  User.Read permission missing")

        if "Can read groups" in output:
            click.echo("  Group.Read permission granted")
        else:
            click.echo("  Group.Read permission missing")

        if "Can read service principals" in output:
            click.echo("  Application.Read permission granted")
        else:
            click.echo("  Application.Read permission missing (optional)")

        if "Can read directory roles" in output:
            click.echo("  RoleManagement.Read permission granted")
        else:
            click.echo("  RoleManagement.Read permission missing (optional)")

        # Show setup instructions if permissions are missing
        has_users = "Can read users" in output
        has_groups = "Can read groups" in output

        if not has_users or not has_groups:
            click.echo("\n  See docs/GRAPH_API_SETUP.md for setup instructions")
            click.echo(
                "Or run: uv run python test_graph_api.py for detailed diagnostics"
            )
        else:
            click.echo("\n  All required Graph API permissions are configured!")

    except subprocess.TimeoutExpired:
        click.echo("  Permission check timed out")
    except Exception as e:
        click.echo(f"  Error checking permissions: {e}")


# For backward compatibility
doctor_command = doctor
check_permissions_command = check_permissions

__all__ = ["check_permissions", "check_permissions_command", "doctor", "doctor_command"]
