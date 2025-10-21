"""
Key Vault data plane replication plugin.

This plugin handles discovery and replication of Azure Key Vault data plane
items including:
- Secrets
- Keys
- Certificates

The plugin integrates with the IaC generation process to ensure that Key Vault
contents are preserved when deploying to new environments.
"""

import json
import logging
from typing import Any, Dict, List

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class KeyVaultPlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Key Vault.

    Discovers and replicates Key Vault secrets, keys, and certificates using
    Azure SDK.

    Example:
        plugin = KeyVaultPlugin()
        items = plugin.discover(keyvault_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Key Vault."""
        return "Microsoft.KeyVault/vaults"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover Key Vault secrets, keys, and certificates.

        Uses Azure SDK to:
        1. Authenticate to the Key Vault
        2. List all secrets, keys, and certificates
        3. Retrieve metadata (not values for security)
        4. Return structured DataPlaneItem list

        Args:
            resource: Key Vault resource dictionary containing:
                - id: Key Vault resource ID
                - name: Key Vault name
                - properties: Key Vault properties (including vaultUri)

        Returns:
            List of DataPlaneItem representing Key Vault contents

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../vaults/my-kv",
            ...     "type": "Microsoft.KeyVault/vaults",
            ...     "name": "my-kv",
            ...     "properties": {"vaultUri": "https://my-kv.vault.azure.net/"}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of secrets/keys/certs
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for KeyVaultPlugin: {resource}")

        vault_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for Key Vault: {vault_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.certificates import CertificateClient
            from azure.keyvault.keys import KeyClient
            from azure.keyvault.secrets import SecretClient

            # Parse vault URI from properties
            properties = resource.get("properties", {})
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = {}

            vault_uri = properties.get("vaultUri")
            if not vault_uri:
                # Construct vault URI from name
                vault_uri = f"https://{vault_name}.vault.azure.net/"
                self.logger.warning(
                    f"vaultUri not found in properties, using constructed URI: {vault_uri}"
                )

            # Authenticate
            credential = DefaultAzureCredential()

            # Discover secrets
            try:
                secret_client = SecretClient(vault_url=vault_uri, credential=credential)
                secrets = secret_client.list_properties_of_secrets()

                for secret_props in secrets:
                    # Skip if disabled
                    if not secret_props.enabled:
                        self.logger.debug(
                            f"Skipping disabled secret: {secret_props.name}"
                        )
                        continue

                    items.append(
                        DataPlaneItem(
                            name=secret_props.name,
                            item_type="secret",
                            properties={
                                "enabled": secret_props.enabled,
                                "content_type": secret_props.content_type,
                                "tags": secret_props.tags or {},
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "created_on": (
                                    secret_props.created_on.isoformat()
                                    if secret_props.created_on
                                    else None
                                ),
                                "updated_on": (
                                    secret_props.updated_on.isoformat()
                                    if secret_props.updated_on
                                    else None
                                ),
                                "recovery_level": secret_props.recovery_level,
                            },
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(f"Failed to discover secrets in {vault_name}: {e}")

            # Discover keys
            try:
                key_client = KeyClient(vault_url=vault_uri, credential=credential)
                keys = key_client.list_properties_of_keys()

                for key_props in keys:
                    if not key_props.enabled:
                        self.logger.debug(f"Skipping disabled key: {key_props.name}")
                        continue

                    items.append(
                        DataPlaneItem(
                            name=key_props.name,
                            item_type="key",
                            properties={
                                "enabled": key_props.enabled,
                                "key_type": key_props.key_type,
                                "tags": key_props.tags or {},
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "created_on": (
                                    key_props.created_on.isoformat()
                                    if key_props.created_on
                                    else None
                                ),
                                "updated_on": (
                                    key_props.updated_on.isoformat()
                                    if key_props.updated_on
                                    else None
                                ),
                                "recovery_level": key_props.recovery_level,
                            },
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(f"Failed to discover keys in {vault_name}: {e}")

            # Discover certificates
            try:
                cert_client = CertificateClient(
                    vault_url=vault_uri, credential=credential
                )
                certificates = cert_client.list_properties_of_certificates()

                for cert_props in certificates:
                    if not cert_props.enabled:
                        self.logger.debug(
                            f"Skipping disabled certificate: {cert_props.name}"
                        )
                        continue

                    items.append(
                        DataPlaneItem(
                            name=cert_props.name,
                            item_type="certificate",
                            properties={
                                "enabled": cert_props.enabled,
                                "tags": cert_props.tags or {},
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "created_on": (
                                    cert_props.created_on.isoformat()
                                    if cert_props.created_on
                                    else None
                                ),
                                "updated_on": (
                                    cert_props.updated_on.isoformat()
                                    if cert_props.updated_on
                                    else None
                                ),
                                "thumbprint": cert_props.x509_thumbprint.hex()
                                if cert_props.x509_thumbprint
                                else None,
                            },
                        )
                    )
            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover certificates in {vault_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure Key Vault SDK not installed. Install with: "
                f"pip install azure-keyvault-secrets azure-keyvault-keys azure-keyvault-certificates. "
                f"Error: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error discovering Key Vault items: {e}")

        self.logger.info(
            f"Discovered {len(items)} data plane items in Key Vault '{vault_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate Key Vault data plane items.

        For secrets, this generates:
        - Placeholder local_file resources with documentation
        - Comments indicating manual intervention needed
        - References to external secret management systems

        Security note: Actual secret values are never included in generated
        code. Users must manually populate secrets or integrate with external
        secret management systems.

        Args:
            items: List of Key Vault data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with placeholders for data plane items

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="db-password", item_type="secret", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_key_vault_secret" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by KeyVaultPlugin"
            )

        if output_format.lower() != "terraform":
            # Future: Support Bicep and ARM templates
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} Key Vault items"
        )

        if not items:
            return "# No Key Vault data plane items to replicate\n"

        code_lines = [
            "# Key Vault Data Plane Items",
            "# Generated by Azure Tenant Grapher - KeyVaultPlugin",
            "#",
            "# SECURITY NOTE: Secret values are not included in generated code.",
            "# You must manually populate secrets after deployment or integrate",
            "# with external secret management (e.g., Azure DevOps, GitHub Secrets).",
            "",
        ]

        # Group items by type
        secrets = [item for item in items if item.item_type == "secret"]
        keys = [item for item in items if item.item_type == "key"]
        certificates = [item for item in items if item.item_type == "certificate"]

        # Generate code for secrets
        if secrets:
            code_lines.append("# Secrets")
            for item in secrets:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_key_vault_secret" "{resource_name}" {{',
                        f'  name         = "{item.name}"',
                        "  # TODO: Reference your Key Vault resource here",
                        "  key_vault_id = azurerm_key_vault.REPLACE_ME.id",
                        "",
                        "  # SECURITY: Set value via environment variable or external system",
                        f"  value = var.keyvault_secret_{resource_name}",
                        "",
                    ]
                )

                # Add optional properties
                if item.properties.get("content_type"):
                    code_lines.append(
                        f'  content_type = "{item.properties["content_type"]}"'
                    )

                if item.properties.get("tags"):
                    code_lines.append("  tags = {")
                    for key, value in item.properties["tags"].items():
                        code_lines.append(f'    "{key}" = "{value}"')
                    code_lines.append("  }")

                code_lines.append("}")
                code_lines.append("")

            # Add variable declarations
            code_lines.append("# Required variables for secrets")
            for item in secrets:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'variable "keyvault_secret_{resource_name}" {{',
                        '  description = "Value for Key Vault secret (set via environment or tfvars)"',
                        "  type        = string",
                        "  sensitive   = true",
                        "}",
                        "",
                    ]
                )

        # Generate code for keys
        if keys:
            code_lines.append("# Keys")
            for item in keys:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_key_vault_key" "{resource_name}" {{',
                        f'  name         = "{item.name}"',
                        "  # TODO: Reference your Key Vault resource here",
                        "  key_vault_id = azurerm_key_vault.REPLACE_ME.id",
                        "",
                        f'  key_type = "{item.properties.get("key_type", "RSA")}"',
                        "  key_size = 2048",
                        "",
                        "  key_opts = [",
                        '    "decrypt",',
                        '    "encrypt",',
                        '    "sign",',
                        '    "unwrapKey",',
                        '    "verify",',
                        '    "wrapKey",',
                        "  ]",
                        "",
                    ]
                )

                if item.properties.get("tags"):
                    code_lines.append("  tags = {")
                    for key, value in item.properties["tags"].items():
                        code_lines.append(f'    "{key}" = "{value}"')
                    code_lines.append("  }")

                code_lines.append("}")
                code_lines.append("")

        # Generate code for certificates
        if certificates:
            code_lines.append("# Certificates")
            for item in certificates:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_key_vault_certificate" "{resource_name}" {{',
                        f'  name         = "{item.name}"',
                        "  # TODO: Reference your Key Vault resource here",
                        "  key_vault_id = azurerm_key_vault.REPLACE_ME.id",
                        "",
                        "  certificate_policy {",
                        "    issuer_parameters {",
                        '      name = "Self"',
                        "    }",
                        "",
                        "    key_properties {",
                        "      exportable = true",
                        '      key_type   = "RSA"',
                        "      key_size   = 2048",
                        "      reuse_key  = true",
                        "    }",
                        "",
                        "    secret_properties {",
                        '      content_type = "application/x-pkcs12"',
                        "    }",
                        "",
                        "    x509_certificate_properties {",
                        f'      subject            = "CN={item.name}"',
                        "      validity_in_months = 12",
                        "",
                        "      key_usage = [",
                        '        "cRLSign",',
                        '        "dataEncipherment",',
                        '        "digitalSignature",',
                        '        "keyAgreement",',
                        '        "keyCertSign",',
                        '        "keyEncipherment",',
                        "      ]",
                        "    }",
                        "  }",
                        "",
                    ]
                )

                if item.properties.get("tags"):
                    code_lines.append("  tags = {")
                    for key, value in item.properties["tags"].items():
                        code_lines.append(f'    "{key}" = "{value}"')
                    code_lines.append("  }")

                code_lines.append("}")
                code_lines.append("")

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Key Vault contents from source to target.

        Discovers all items from the source Key Vault and replicates them to
        the target Key Vault. Handles secrets, keys, and certificates with
        appropriate error handling and permission checks.

        Args:
            source_resource: Source Key Vault resource dictionary containing:
                - id: Azure resource ID
                - type: Microsoft.KeyVault/vaults
                - name: Key Vault name
                - properties: Including vaultUri
            target_resource: Target Key Vault resource (same structure)

        Returns:
            ReplicationResult with:
                - success: True if at least one item replicated
                - items_discovered: Count of items found in source
                - items_replicated: Count of items successfully replicated
                - errors: List of error messages
                - warnings: List of warnings

        Raises:
            ValueError: If source or target resources are invalid

        Example:
            >>> source = {"id": "...", "type": "Microsoft.KeyVault/vaults", ...}
            >>> target = {"id": "...", "type": "Microsoft.KeyVault/vaults", ...}
            >>> result = plugin.replicate(source, target)
            >>> result.success
            True
            >>> result.items_replicated
            5
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating from Key Vault '{source_name}' to '{target_name}'"
        )

        # 1. Discover items from source
        try:
            source_items = self.discover(source_resource)
        except Exception as e:
            self.logger.error(f"Failed to discover items from source: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Failed to discover items from source: {e}"],
                warnings=[],
            )

        if not source_items:
            self.logger.info("No items to replicate")
            return ReplicationResult(
                success=True,
                items_discovered=0,
                items_replicated=0,
                errors=[],
                warnings=["No items found in source Key Vault"],
            )

        self.logger.info(f"Discovered {len(source_items)} items from source")

        # 2. Connect to target Key Vault
        try:
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            # Note: KeyClient and CertificateClient imports will be added when
            # key/certificate replication is implemented
        except ImportError as e:
            self.logger.error(f"Azure SDK not installed: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[
                    f"Azure SDK not installed: {e}. "
                    "Install with: pip install azure-keyvault-secrets "
                    "azure-keyvault-keys azure-keyvault-certificates"
                ],
                warnings=[],
            )

        # Parse vault URIs
        source_props = source_resource.get("properties", {})
        if isinstance(source_props, str):
            try:
                source_props = json.loads(source_props)
            except json.JSONDecodeError:
                source_props = {}

        target_props = target_resource.get("properties", {})
        if isinstance(target_props, str):
            try:
                target_props = json.loads(target_props)
            except json.JSONDecodeError:
                target_props = {}

        source_vault_uri = source_props.get("vaultUri")
        if not source_vault_uri:
            source_vault_uri = f"https://{source_name}.vault.azure.net/"
            self.logger.debug(f"Constructed source URI: {source_vault_uri}")

        target_vault_uri = target_props.get("vaultUri")
        if not target_vault_uri:
            target_vault_uri = f"https://{target_name}.vault.azure.net/"
            self.logger.debug(f"Constructed target URI: {target_vault_uri}")

        # Authenticate
        try:
            credential = DefaultAzureCredential()
        except Exception as e:
            self.logger.error(f"Failed to authenticate: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[f"Failed to authenticate with Azure: {e}"],
                warnings=[],
            )

        # Create clients
        source_secret_client = SecretClient(
            vault_url=source_vault_uri, credential=credential
        )
        target_secret_client = SecretClient(
            vault_url=target_vault_uri, credential=credential
        )
        # Note: KeyClient and CertificateClient will be needed when key/cert replication is implemented

        # 3. Replicate each item
        replicated_count = 0
        errors = []
        warnings = []

        for item in source_items:
            self.logger.debug(f"Replicating {item.item_type}: {item.name}")

            try:
                if item.item_type == "secret":
                    # Replicate secret
                    try:
                        # Get secret value from source
                        secret = source_secret_client.get_secret(item.name)

                        # Set in target
                        target_secret_client.set_secret(
                            name=item.name,
                            value=secret.value,
                            content_type=item.properties.get("content_type"),
                            tags=item.properties.get("tags", {}),
                        )

                        replicated_count += 1
                        self.logger.debug(
                            f"Successfully replicated secret: {item.name}"
                        )

                    except HttpResponseError as e:
                        if e.status_code == 403:
                            error_msg = f"Permission denied for secret '{item.name}': {e.message}"
                            errors.append(error_msg)
                            self.logger.warning(error_msg)
                        elif e.status_code == 409:
                            # Conflict - item already exists
                            warning_msg = f"Secret '{item.name}' already exists in target (skipped)"
                            warnings.append(warning_msg)
                            self.logger.debug(warning_msg)
                        else:
                            error_msg = f"HTTP error replicating secret '{item.name}': {e.message}"
                            errors.append(error_msg)
                            self.logger.warning(error_msg)

                elif item.item_type == "key":
                    # Keys cannot be easily exported/imported
                    # Azure Key Vault doesn't support exporting private key material
                    warning_msg = (
                        f"Key '{item.name}' cannot be replicated "
                        "(export of key material not supported by Azure Key Vault)"
                    )
                    warnings.append(warning_msg)
                    self.logger.debug(warning_msg)

                elif item.item_type == "certificate":
                    # Certificates are complex - they contain both public cert and private key
                    # For now, add a warning
                    warning_msg = (
                        f"Certificate '{item.name}' replication not fully implemented. "
                        "Certificates require special handling for private key material."
                    )
                    warnings.append(warning_msg)
                    self.logger.debug(warning_msg)

                else:
                    warning_msg = (
                        f"Unknown item type '{item.item_type}' for item '{item.name}'"
                    )
                    warnings.append(warning_msg)
                    self.logger.warning(warning_msg)

            except HttpResponseError as e:
                error_msg = f"HTTP error replicating {item.item_type} '{item.name}': {e.message}"
                errors.append(error_msg)
                self.logger.warning(error_msg)

            except AzureError as e:
                error_msg = (
                    f"Azure error replicating {item.item_type} '{item.name}': {e!s}"
                )
                errors.append(error_msg)
                self.logger.warning(error_msg)

            except Exception as e:
                error_msg = f"Unexpected error replicating {item.item_type} '{item.name}': {e!s}"
                errors.append(error_msg)
                self.logger.error(error_msg)

        # Determine success
        success = replicated_count > 0

        self.logger.info(
            f"Replication complete: {replicated_count}/{len(source_items)} items replicated"
        )

        if errors:
            self.logger.warning(f"Encountered {len(errors)} errors during replication")
        if warnings:
            self.logger.debug(f"Generated {len(warnings)} warnings during replication")

        return ReplicationResult(
            success=success,
            items_discovered=len(source_items),
            items_replicated=replicated_count,
            errors=errors,
            warnings=warnings,
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain hyphens, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers
        """
        # Replace hyphens and special chars with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "kv_" + sanitized

        return sanitized.lower()
