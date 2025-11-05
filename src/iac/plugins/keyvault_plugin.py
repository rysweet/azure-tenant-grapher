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
import time
from typing import Any, Dict, List

from .base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

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
                        '      exportable = true',
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

    # ============ NEW MODE-AWARE METHODS ============

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return required permissions for Key Vault operations.

        Template mode: Read-only permissions to list items
        Replication mode: Read/write permissions to get and set values

        Args:
            mode: Replication mode

        Returns:
            List of required permissions
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=["Microsoft.KeyVault/vaults/read"],
                    data_actions=[
                        "Microsoft.KeyVault/vaults/secrets/getMetadata/action",
                        "Microsoft.KeyVault/vaults/keys/read",
                        "Microsoft.KeyVault/vaults/certificates/read",
                    ],
                    description="Key Vault Reader - list secrets, keys, certificates (no values)",
                )
            ]
        else:  # REPLICATION mode
            return [
                Permission(
                    scope="resource",
                    actions=["Microsoft.KeyVault/vaults/read"],
                    data_actions=[
                        "Microsoft.KeyVault/vaults/secrets/getSecret/action",
                        "Microsoft.KeyVault/vaults/secrets/setSecret/action",
                        "Microsoft.KeyVault/vaults/keys/read",
                        "Microsoft.KeyVault/vaults/keys/create/action",
                        "Microsoft.KeyVault/vaults/certificates/read",
                        "Microsoft.KeyVault/vaults/certificates/create/action",
                    ],
                    description="Key Vault Secrets Officer, Crypto Officer, Certificates Officer - read and write all items",
                )
            ]

    def discover_with_mode(
        self, resource: Dict[str, Any], mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """
        Discover Key Vault items with mode awareness.

        Both modes discover metadata only - actual secret values are never
        fetched during discovery for security reasons. Values are only
        retrieved during replication mode's replicate operation.

        Args:
            resource: Key Vault resource
            mode: Replication mode (both modes behave the same for discovery)

        Returns:
            List of discovered items
        """
        # Current discover() method already does metadata-only discovery
        # This is appropriate for both modes
        return self.discover(resource)

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate Key Vault contents with mode awareness.

        Template mode: Create empty secrets with placeholder values
        Replication mode: Copy actual secret values from source to target

        Args:
            source_resource: Source Key Vault resource
            target_resource: Target Key Vault resource
            mode: Replication mode

        Returns:
            ReplicationResult with operation statistics
        """
        start_time = time.time()

        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating Key Vault from '{source_name}' to '{target_name}' "
            f"(mode={mode.value})"
        )

        try:
            # Discover items from source
            items = self.discover(source_resource)

            if self.progress_reporter:
                self.progress_reporter.report_discovery(
                    source_resource["id"], len(items)
                )

            if mode == ReplicationMode.TEMPLATE:
                # Template mode: Create empty secrets with placeholder values
                result = self._replicate_template_mode(
                    source_resource, target_resource, items
                )
            else:
                # Replication mode: Copy actual secret values
                result = self._replicate_full_mode(
                    source_resource, target_resource, items
                )

            # Add timing information
            result.duration_seconds = time.time() - start_time

            if self.progress_reporter:
                self.progress_reporter.report_completion(result)

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Failed to replicate Key Vault: {e!s}"
            self.logger.error(error_msg)

            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                items_skipped=0,
                errors=[error_msg],
                warnings=[],
                duration_seconds=duration,
            )

    def _replicate_template_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in template mode: create empty secrets with placeholder values.

        Args:
            source_resource: Source Key Vault
            target_resource: Target Key Vault
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse target vault URI
        target_properties = target_resource.get("properties", {})
        if isinstance(target_properties, str):
            try:
                target_properties = json.loads(target_properties)
            except json.JSONDecodeError:
                target_properties = {}

        target_vault_uri = target_properties.get("vaultUri")
        if not target_vault_uri:
            target_vault_uri = f"https://{target_resource['name']}.vault.azure.net/"

        secrets = [item for item in items if item.item_type == "secret"]
        keys = [item for item in items if item.item_type == "key"]
        certificates = [item for item in items if item.item_type == "certificate"]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Create empty secrets
        if secrets:
            try:
                secret_client = SecretClient(
                    vault_url=target_vault_uri, credential=credential
                )
                for item in secrets:
                    try:
                        # Create secret with placeholder value
                        secret_client.set_secret(
                            item.name,
                            "PLACEHOLDER-VALUE-SET-MANUALLY",
                            content_type=item.properties.get("content_type"),
                            tags=item.properties.get("tags", {}),
                        )
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    except (AzureError, HttpResponseError) as e:
                        errors.append(f"Failed to create secret '{item.name}': {e!s}")
                        skipped += 1
            except Exception as e:
                errors.append(f"Failed to initialize secret client: {e!s}")
                skipped += len(secrets)

        # Create placeholder keys
        if keys:
            warnings.append(
                f"Template mode: {len(keys)} keys not created (manual creation required)"
            )
            skipped += len(keys)

        # Create placeholder certificates
        if certificates:
            warnings.append(
                f"Template mode: {len(certificates)} certificates not created (manual creation required)"
            )
            skipped += len(certificates)

        warnings.append(
            "Template mode: Secrets created with placeholder values. "
            "You must manually set actual values after deployment."
        )

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )

    def _replicate_full_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in full mode: copy actual secret values.

        Args:
            source_resource: Source Key Vault
            target_resource: Target Key Vault
            items: Items discovered from source

        Returns:
            ReplicationResult
        """
        from azure.core.exceptions import AzureError, HttpResponseError
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
        else:
            credential = DefaultAzureCredential()

        # Parse vault URIs
        source_properties = source_resource.get("properties", {})
        if isinstance(source_properties, str):
            try:
                source_properties = json.loads(source_properties)
            except json.JSONDecodeError:
                source_properties = {}

        source_vault_uri = source_properties.get("vaultUri")
        if not source_vault_uri:
            source_vault_uri = f"https://{source_resource['name']}.vault.azure.net/"

        target_properties = target_resource.get("properties", {})
        if isinstance(target_properties, str):
            try:
                target_properties = json.loads(target_properties)
            except json.JSONDecodeError:
                target_properties = {}

        target_vault_uri = target_properties.get("vaultUri")
        if not target_vault_uri:
            target_vault_uri = f"https://{target_resource['name']}.vault.azure.net/"

        secrets = [item for item in items if item.item_type == "secret"]
        keys = [item for item in items if item.item_type == "key"]
        certificates = [item for item in items if item.item_type == "certificate"]

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        # Replicate secrets
        if secrets:
            try:
                source_client = SecretClient(
                    vault_url=source_vault_uri, credential=credential
                )
                target_client = SecretClient(
                    vault_url=target_vault_uri, credential=credential
                )

                for item in secrets:
                    try:
                        # Get secret value from source
                        secret = source_client.get_secret(item.name)

                        # Set secret in target
                        target_client.set_secret(
                            item.name,
                            secret.value,
                            content_type=secret.properties.content_type,
                            tags=secret.properties.tags or {},
                        )
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )

                    except (AzureError, HttpResponseError) as e:
                        errors.append(
                            f"Failed to replicate secret '{item.name}': {e!s}"
                        )
                        skipped += 1

            except Exception as e:
                errors.append(f"Failed to initialize secret clients: {e!s}")
                skipped += len(secrets)

        # Keys replication (not fully implemented)
        if keys:
            warnings.append(
                f"Replication mode: {len(keys)} keys not replicated "
                "(key replication requires additional implementation for key types)"
            )
            skipped += len(keys)

        # Certificates replication (not fully implemented)
        if certificates:
            warnings.append(
                f"Replication mode: {len(certificates)} certificates not replicated "
                "(certificate replication requires additional implementation)"
            )
            skipped += len(certificates)

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )
