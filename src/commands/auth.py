"""Authentication/app registration command.

This module provides the 'app-registration' command for creating
Azure AD app registrations for Azure Tenant Grapher.

Issue #482: CLI Modularization
Issue #539: Add input validation for subprocess calls
"""

import json
import os
import re
import subprocess
import tempfile
from typing import Optional

import click


def validate_app_name(name: str) -> str:
    """Validate and sanitize app registration name.

    Args:
        name: The app registration name to validate

    Returns:
        Validated name (stripped of whitespace)

    Raises:
        ValueError: If name is empty or contains invalid characters

    Note:
        subprocess.run() with list arguments handles shell escaping automatically,
        so we don't use shlex.quote() here. The validation ensures only safe
        characters are present.
    """
    if not name or not name.strip():
        raise ValueError("App name cannot be empty")

    # Allow alphanumeric, spaces, hyphens, underscores
    if not re.match(r"^[a-zA-Z0-9\s\-_]+$", name):
        raise ValueError(
            f"Invalid app name format: {name}. "
            "Use only letters, numbers, spaces, hyphens, underscores."
        )

    return name.strip()


def validate_redirect_uri(uri: str) -> str:
    """Validate and sanitize redirect URI.

    Args:
        uri: The redirect URI to validate

    Returns:
        Validated URI (stripped of whitespace)

    Raises:
        ValueError: If URI is empty or has invalid format

    Note:
        subprocess.run() with list arguments handles shell escaping automatically.
    """
    if not uri or not uri.strip():
        raise ValueError("Redirect URI cannot be empty")

    # Strip whitespace before validation
    uri_stripped = uri.strip()

    # Basic URI validation (http/https)
    if not re.match(r"^https?://", uri_stripped):
        raise ValueError(
            f"Invalid redirect URI format: {uri_stripped}. "
            "Must start with http:// or https://"
        )

    return uri_stripped


def validate_tenant_id(tenant_id: str) -> str:
    """Validate and sanitize tenant ID.

    Args:
        tenant_id: The tenant ID to validate

    Returns:
        Validated tenant ID (stripped of whitespace)

    Raises:
        ValueError: If tenant ID is empty or has invalid format

    Note:
        subprocess.run() with list arguments handles shell escaping automatically.
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("Tenant ID cannot be empty")

    # Tenant ID should be a valid GUID
    guid_pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    if not re.match(guid_pattern, tenant_id.strip()):
        raise ValueError(
            f"Invalid tenant ID format: {tenant_id}. "
            "Must be a valid GUID (e.g., 12345678-1234-1234-1234-123456789012)"
        )

    return tenant_id.strip()


def validate_app_id(app_id: str) -> str:
    """Validate and sanitize application ID.

    Args:
        app_id: The application ID to validate

    Returns:
        Validated app ID (stripped of whitespace)

    Raises:
        ValueError: If app ID is empty or has invalid format

    Note:
        subprocess.run() with list arguments handles shell escaping automatically.
    """
    if not app_id or not app_id.strip():
        raise ValueError("Application ID cannot be empty")

    # App ID should be a valid GUID
    guid_pattern = (
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )
    if not re.match(guid_pattern, app_id.strip()):
        raise ValueError(
            f"Invalid application ID format: {app_id}. "
            "Must be a valid GUID (e.g., 12345678-1234-1234-1234-123456789012)"
        )

    return app_id.strip()


@click.command("app-registration")
@click.option(
    "--tenant-id",
    help="Azure tenant ID for the app registration",
    required=False,
)
@click.option(
    "--name",
    default="Azure Tenant Grapher",
    help="Display name for the app registration",
)
@click.option(
    "--redirect-uri",
    default="http://localhost:3000",
    help="Redirect URI for the app registration",
)
@click.option(
    "--create-secret",
    is_flag=True,
    default=True,
    help="Create a client secret for the app registration",
)
@click.option(
    "--save-to-env",
    is_flag=True,
    default=False,
    help="Automatically save configuration to .env file",
)
def app_registration(
    tenant_id: Optional[str],
    name: str,
    redirect_uri: str,
    create_secret: bool,
    save_to_env: bool,
):
    """Create an Azure AD app registration for Azure Tenant Grapher.

    This command guides you through creating an Azure AD application registration
    with the necessary permissions for Azure Tenant Grapher to function properly.

    The app registration will be configured with:
    - Microsoft Graph API permissions (User.Read, Directory.Read.All)
    - Azure Management API permissions (user_impersonation)
    - Optional client secret for authentication

    You can either:
    1. Run this command with Azure CLI installed to automatically create the registration
    2. Follow the manual instructions provided to create it through the Azure Portal
    """
    click.echo("Azure AD App Registration Setup")
    click.echo("=" * 50)

    # Validate inputs early
    try:
        validated_name = validate_app_name(name)
        validated_redirect_uri = validate_redirect_uri(redirect_uri)
        if tenant_id:
            validated_tenant_id = validate_tenant_id(tenant_id)
        else:
            validated_tenant_id = None
    except ValueError as e:
        click.echo(f"Input validation error: {e}", err=True)
        return

    # Check if Azure CLI is installed
    try:
        result = subprocess.run(
            ["az", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        has_azure_cli = result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        has_azure_cli = False

    if not has_azure_cli:
        _show_manual_instructions(validated_name, validated_redirect_uri, create_secret)
        return

    # Azure CLI is available, proceed with automated creation
    click.echo("Azure CLI detected. Proceeding with automated setup...")

    # Check current user's permissions
    _check_user_permissions()

    # Get or use provided tenant ID
    if not validated_tenant_id:
        tenant_id_from_cli = _get_current_tenant_id()
        if not tenant_id_from_cli:
            return
        # Validate the tenant ID from CLI
        try:
            validated_tenant_id = validate_tenant_id(tenant_id_from_cli)
        except ValueError as e:
            click.echo(f"Tenant ID validation error: {e}", err=True)
            return

    # Create the app registration
    _create_app_registration(
        tenant_id=validated_tenant_id,
        name=validated_name,
        redirect_uri=validated_redirect_uri,
        create_secret=create_secret,
        save_to_env=save_to_env,
    )


def _show_manual_instructions(
    name: str, redirect_uri: str, create_secret: bool
) -> None:
    """Show manual app registration instructions."""
    click.echo("Azure CLI not detected. Showing manual instructions...")
    click.echo("\nManual App Registration Steps:")
    click.echo("\n1. Navigate to Azure Portal (https://portal.azure.com)")
    click.echo(
        "2. Go to Azure Active Directory -> App registrations -> New registration"
    )
    click.echo(f"3. Name: {name}")
    click.echo("4. Supported account types: Single tenant")
    click.echo(f"5. Redirect URI: Web - {redirect_uri}")
    click.echo("\n6. After creation, go to API permissions and add:")
    click.echo("   - Microsoft Graph:")
    click.echo("     User.Read (Delegated)")
    click.echo("     Directory.Read.All (Application)")
    click.echo("   - Azure Service Management:")
    click.echo("     user_impersonation (Delegated)")
    click.echo("\n7. Grant admin consent for the permissions")
    if create_secret:
        click.echo("\n8. Go to Certificates & secrets -> New client secret")
        click.echo("   - Description: Azure Tenant Grapher")
        click.echo("   - Expires: Choose appropriate expiration")
        click.echo("\n9. Copy the following values to your .env file:")
        click.echo("   - AZURE_CLIENT_ID = <Application (client) ID>")
        click.echo("   - AZURE_CLIENT_SECRET = <Client secret value>")
        click.echo("   - AZURE_TENANT_ID = <Directory (tenant) ID>")


def _check_user_permissions() -> None:
    """Check current user's permissions."""
    click.echo("\nChecking your permissions...")

    # Get current user info
    user_result = subprocess.run(
        [
            "az",
            "ad",
            "signed-in-user",
            "show",
            "--query",
            "{id:id,displayName:displayName,userPrincipalName:userPrincipalName}",
            "-o",
            "json",
        ],
        capture_output=True,
        text=True,
    )

    if user_result.returncode == 0:
        user_info = json.loads(user_result.stdout)
        click.echo(
            f"   Signed in as: {user_info.get('displayName', 'Unknown')} ({user_info.get('userPrincipalName', 'Unknown')})"
        )

        # Validate user ID before using in subprocess call
        user_id = user_info.get("id", "")
        if not user_id:
            click.echo("   Could not retrieve user ID")
            return

        # User ID should be a GUID - validate it
        try:
            validated_user_id = validate_app_id(user_id)  # GUIDs have same format
        except ValueError:
            click.echo("   Invalid user ID format from Azure CLI")
            return

        # Check if user has admin roles
        roles_result = subprocess.run(
            [
                "az",
                "role",
                "assignment",
                "list",
                "--assignee",
                validated_user_id,
                "--query",
                "[].roleDefinitionName",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if roles_result.returncode == 0:
            roles = json.loads(roles_result.stdout)
            admin_roles = [
                r
                for r in roles
                if any(
                    admin in r.lower()
                    for admin in ["administrator", "owner", "contributor"]
                )
            ]

            if admin_roles:
                click.echo(f"   Your roles: {', '.join(admin_roles[:3])}")
                if (
                    "Global Administrator" in roles
                    or "Application Administrator" in roles
                ):
                    click.echo(
                        "   You have sufficient permissions to grant admin consent"
                    )
                else:
                    click.echo(
                        "   You can create apps but may need a Global Admin to grant consent"
                    )
            else:
                click.echo("   Limited permissions detected - some operations may fail")

        # Check if user can create applications
        can_create_apps = subprocess.run(
            ["az", "ad", "app", "list", "--query", "[0].id", "-o", "tsv"],
            capture_output=True,
            text=True,
        )

        if can_create_apps.returncode != 0:
            click.echo("   You don't have permission to create app registrations")
            click.echo("   Please contact your Azure AD administrator")
            return


def _get_current_tenant_id() -> Optional[str]:
    """Get the current tenant ID from Azure CLI."""
    try:
        result = subprocess.run(
            ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            tenant_id = result.stdout.strip()
            click.echo(f"Using current tenant: {tenant_id}")
            return tenant_id
        else:
            click.echo(
                "Could not determine tenant ID. Please provide --tenant-id",
                err=True,
            )
            return None
    except subprocess.SubprocessError as e:
        click.echo(f"Failed to get tenant ID: {e}", err=True)
        return None


def _create_app_registration(
    tenant_id: str,
    name: str,
    redirect_uri: str,
    create_secret: bool,
    save_to_env: bool,
) -> None:
    """Create the app registration using Azure CLI."""
    click.echo(f"\nCreating app registration '{name}'...")

    manifest = {
        "requiredResourceAccess": [
            {
                "resourceAppId": "00000003-0000-0000-c000-000000000000",  # Microsoft Graph
                "resourceAccess": [
                    {
                        "id": "e1fe6dd8-ba31-4d61-89e7-88639da4683d",  # User.Read
                        "type": "Scope",
                    },
                    {
                        "id": "7ab1d382-f21e-4acd-a863-ba3e13f7da61",  # Directory.Read.All
                        "type": "Role",
                    },
                ],
            },
            {
                "resourceAppId": "797f4846-ba00-4fd7-ba43-dac1f8f63013",  # Azure Service Management
                "resourceAccess": [
                    {
                        "id": "41094075-9dad-400e-a0bd-54e686782033",  # user_impersonation
                        "type": "Scope",
                    }
                ],
            },
        ],
        "web": {"redirectUris": [redirect_uri]},
    }

    # Save manifest to temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(manifest, f)
        manifest_path = f.name

    try:
        # Create the app
        result = subprocess.run(
            [
                "az",
                "ad",
                "app",
                "create",
                "--display-name",
                name,
                "--sign-in-audience",
                "AzureADMyOrg",
                "--required-resource-accesses",
                f"@{manifest_path}",
                "--query",
                "{appId:appId, objectId:id}",
                "-o",
                "json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(f"Failed to create app registration: {result.stderr}", err=True)
            return

        app_info = json.loads(result.stdout)
        app_id = app_info["appId"]
        object_id = app_info["objectId"]

        # Validate app_id from Azure CLI response before using in subsequent calls
        try:
            validated_app_id = validate_app_id(app_id)
        except ValueError as e:
            click.echo(f"Invalid app ID returned from Azure: {e}", err=True)
            return

        click.echo("App registration created successfully!")
        click.echo(f"   Client ID: {validated_app_id}")
        click.echo(f"   Object ID: {object_id}")

        # Create service principal
        click.echo("\nCreating service principal...")
        result = subprocess.run(
            ["az", "ad", "sp", "create", "--id", validated_app_id],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            click.echo(f"Failed to create service principal: {result.stderr}", err=True)
        else:
            click.echo("Service principal created")

        # Create client secret if requested
        client_secret = None
        if create_secret:
            click.echo("\nCreating client secret...")
            result = subprocess.run(
                [
                    "az",
                    "ad",
                    "app",
                    "credential",
                    "reset",
                    "--id",
                    validated_app_id,
                    "--display-name",
                    "Azure Tenant Grapher Secret",
                    "--years",
                    "2",  # Valid for 2 years
                    "--query",
                    "password",
                    "-o",
                    "tsv",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                click.echo(f"Failed to create client secret: {result.stderr}", err=True)
            else:
                client_secret = result.stdout.strip()
                click.echo("Client secret created successfully!")

        # Try to grant admin consent automatically
        click.echo("\nAttempting to grant admin consent...")
        consent_result = subprocess.run(
            [
                "az",
                "ad",
                "app",
                "permission",
                "admin-consent",
                "--id",
                validated_app_id,
            ],
            capture_output=True,
            text=True,
        )

        consent_granted = False
        if consent_result.returncode == 0:
            click.echo("Admin consent granted successfully!")
            consent_granted = True
        else:
            if (
                "AADSTS50058" in consent_result.stderr
                or "signed in" in consent_result.stderr.lower()
            ):
                click.echo(
                    "Cannot grant admin consent automatically - requires interactive login as Global Administrator"
                )
            else:
                click.echo(f"Admin consent failed: {consent_result.stderr}")

        # Save to .env file if requested
        if save_to_env:
            _save_to_env_file(tenant_id, validated_app_id, client_secret)

        # Display configuration
        _display_configuration(
            tenant_id,
            validated_app_id,
            client_secret,
            consent_granted,
            name,
            save_to_env,
        )

    finally:
        # Clean up temp file
        if os.path.exists(manifest_path):
            os.remove(manifest_path)


def _save_to_env_file(
    tenant_id: str, app_id: str, client_secret: Optional[str]
) -> None:
    """Save configuration to .env file."""
    env_file_path = os.path.join(os.getcwd(), ".env")
    click.echo(f"\nSaving configuration to {env_file_path}...")

    # Read existing .env file if it exists
    env_vars = {}
    if os.path.exists(env_file_path):
        with open(env_file_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

    # Update with new values
    env_vars["AZURE_TENANT_ID"] = tenant_id
    env_vars["AZURE_CLIENT_ID"] = app_id
    if client_secret:
        env_vars["AZURE_CLIENT_SECRET"] = client_secret

    # Write back to file
    with open(env_file_path, "w") as f:
        for key, value in env_vars.items():
            f.write(f"{key}={value}\n")

    click.echo("Configuration saved to .env file!")


def _display_configuration(
    tenant_id: str,
    app_id: str,
    client_secret: Optional[str],
    consent_granted: bool,
    name: str,
    save_to_env: bool,
) -> None:
    """Display configuration and next steps."""
    click.echo("\n" + "=" * 50)
    click.echo("Configuration for .env file:")
    click.echo("=" * 50)
    click.echo(f"AZURE_TENANT_ID={tenant_id}")
    click.echo(f"AZURE_CLIENT_ID={app_id}")
    if client_secret:
        click.echo(f"AZURE_CLIENT_SECRET={client_secret}")
    click.echo("=" * 50)

    # Display next steps with proper numbering
    click.echo("\nNext steps:")
    step_num = 1

    if not save_to_env:
        click.echo(f"{step_num}. Copy the above configuration to your .env file")
        step_num += 1

    if client_secret:
        click.echo(
            f"{step_num}. Store the client secret securely - it won't be shown again"
        )
        step_num += 1

    if not consent_granted:
        click.echo(f"{step_num}. Grant admin consent for the API permissions:")
        click.echo(
            f"   Option A: Run as Global Admin: az ad app permission admin-consent --id {app_id}"
        )
        click.echo(
            f"   Option B: Use Azure Portal: Azure AD -> App registrations -> {name} -> API permissions -> Grant admin consent"
        )
        click.echo(
            f"   Option C: Use consent URL: https://login.microsoftonline.com/{tenant_id}/adminconsent?client_id={app_id}"
        )
        step_num += 1

    click.echo("\nApp registration setup complete!")


# For backward compatibility
app_registration_command = app_registration

__all__ = ["app_registration", "app_registration_command"]
