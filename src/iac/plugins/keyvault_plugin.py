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
from typing import Any, Dict, List, Optional

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
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            from azure.keyvault.keys import KeyClient
            from azure.keyvault.certificates import CertificateClient
            from azure.core.exceptions import AzureError, HttpResponseError

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
                        self.logger.debug(f"Skipping disabled secret: {secret_props.name}")
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
                self.logger.warning(f"Failed to discover certificates in {vault_name}: {e}")

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

        # Generate code for keys (placeholder)
        if keys:
            code_lines.extend(
                [
                    "# Keys",
                    "# TODO: Implement key replication code",
                    f"# Found {len(keys)} keys: {', '.join(k.name for k in keys)}",
                    "",
                ]
            )

        # Generate code for certificates (placeholder)
        if certificates:
            code_lines.extend(
                [
                    "# Certificates",
                    "# TODO: Implement certificate replication code",
                    f"# Found {len(certificates)} certificates: {', '.join(c.name for c in certificates)}",
                    "",
                ]
            )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Key Vault contents from source to target.

        This is a stub implementation. Full implementation will:
        1. Discover items from source Key Vault
        2. Connect to target Key Vault
        3. Replicate secrets, keys, and certificates
        4. Handle errors and permissions issues

        Args:
            source_resource: Source Key Vault resource
            target_resource: Target Key Vault resource

        Returns:
            ReplicationResult with operation statistics

        Example:
            >>> source = {"id": "...", "type": "Microsoft.KeyVault/vaults", ...}
            >>> target = {"id": "...", "type": "Microsoft.KeyVault/vaults", ...}
            >>> result = plugin.replicate(source, target)
            >>> result.success
            False  # Stub implementation always returns False
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        self.logger.info(
            f"Replicating from {source_resource.get('name')} "
            f"to {target_resource.get('name')}"
        )

        # TODO: Implement actual replication logic
        # 1. Discover items from source
        # source_items = self.discover(source_resource)
        #
        # 2. Connect to target Key Vault
        # target_vault_uri = target_resource.get("properties", {}).get("vaultUri")
        # credential = DefaultAzureCredential()
        #
        # 3. Replicate each item
        # for item in source_items:
        #     if item.item_type == "secret":
        #         # Get secret value from source
        #         # Set secret value in target
        #         pass

        # Stub: Return unsuccessful result
        return ReplicationResult(
            success=False,
            items_discovered=0,
            items_replicated=0,
            errors=["Replication not yet implemented - stub only"],
            warnings=[
                "This is a stub implementation. "
                "Azure SDK integration required for actual replication."
            ],
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
