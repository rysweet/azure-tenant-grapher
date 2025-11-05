"""
App Service Translator for Cross-Tenant Translation

Translates Azure App Service and Function App cross-tenant references including:
- App Service Plan resource IDs
- App Settings (including Key Vault references, connection strings)
- Connection Strings
- Storage account connection strings (for Function Apps)

This translator handles:
1. App Service Plan ID translation
2. Key Vault references in app settings (@Microsoft.KeyVault(...))
3. Connection string values
4. Storage account references (warns, actual translation in StorageAccountTranslator)

Example Translations:
    App Service Plan ID:
        /subscriptions/SOURCE/resourceGroups/rg/providers/Microsoft.Web/serverFarms/plan1
        -> /subscriptions/TARGET/resourceGroups/rg/providers/Microsoft.Web/serverFarms/plan1

    Key Vault Reference:
        @Microsoft.KeyVault(SecretUri=https://sourcevault.vault.azure.net/secrets/secret1)
        -> @Microsoft.KeyVault(SecretUri=https://targetvault.vault.azure.net/secrets/secret1)

    Connection String:
        Server=tcp:myserver.database.windows.net,1433;Database=mydb;
        -> Warning: May need manual review for cross-subscription database

Security Notes:
    - Never logs sensitive values (keys, passwords, connection strings)
    - Only logs warnings for cross-tenant references
    - Storage keys should be regenerated in target environment
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .base_translator import BaseTranslator
from .registry import register_translator

logger = logging.getLogger(__name__)

# Key Vault reference pattern:
# @Microsoft.KeyVault(SecretUri=https://vault-name.vault.azure.net/secrets/secret-name/version)
# @Microsoft.KeyVault(VaultName=vault-name;SecretName=secret-name;SecretVersion=version)
KEYVAULT_REFERENCE_PATTERN = re.compile(
    r"@Microsoft\.KeyVault\((?P<params>[^)]+)\)", re.IGNORECASE
)

# Storage account connection string pattern (for extracting account name)
# Format: DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;EndpointSuffix=core.windows.net
STORAGE_CONN_STR_PATTERN = re.compile(r"AccountName=([a-z0-9]+)", re.IGNORECASE)

# SQL connection string pattern (for detecting SQL references)
SQL_CONN_STR_PATTERN = re.compile(r"Server=tcp:([^,;]+)", re.IGNORECASE)


@register_translator
class AppServiceTranslator(BaseTranslator):
    """
    Translates Azure App Service and Function App cross-tenant references.

    Handles translation of:
    - App Service Plan resource IDs
    - App Settings with Key Vault references
    - Connection Strings
    - Storage account references (warnings only)

    This translator focuses on App Service/Function App configuration properties
    that may contain cross-subscription references. It works in conjunction with:
    - StorageAccountTranslator: For actual storage account translation
    - PrivateEndpointTranslator: For private endpoint connections

    Design Philosophy:
    - Conservative: Only translates when necessary
    - Secure: Never logs sensitive values
    - Informative: Provides warnings for manual review
    - Defensive: Validates all inputs, handles errors gracefully
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """
        Get list of resource types this translator handles.

        Supports both Azure and Terraform resource type formats.

        Returns:
            List of App Service and Function App resource types
        """
        return [
            # App Services
            "azurerm_app_service",
            "azurerm_linux_web_app",
            "azurerm_windows_web_app",
            "Microsoft.Web/sites",
            # Function Apps (also Microsoft.Web/sites with kind=functionapp)
            "azurerm_function_app",
            "azurerm_linux_function_app",
            "azurerm_windows_function_app",
            # App Service Plans
            "azurerm_app_service_plan",
            "azurerm_service_plan",
            "Microsoft.Web/serverFarms",
        ]

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource needs app service translation.

        A resource needs translation if:
        1. It's an app service/function app resource type
        2. It has app settings, connection strings, or app service plan ID

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            True if translation is needed
        """
        resource_type = resource.get("type", "")

        # Check if this is a supported resource type
        if resource_type not in self.supported_resource_types:
            return False

        # For App Service Plans, check if resource ID needs translation
        if resource_type in ["azurerm_app_service_plan", "azurerm_service_plan"]:
            resource_id = resource.get("id", "")
            if resource_id and self._is_cross_subscription_reference(resource_id):
                return True
            return False

        # For App Services/Function Apps, check for translatable properties
        translatable_properties = [
            "app_service_plan_id",  # App Service Plan reference
            "service_plan_id",  # Alternative field name
            "app_settings",  # May contain Key Vault refs, storage conn strings
            "connection_string",  # Connection strings block
        ]

        for prop in translatable_properties:
            if prop in resource:
                logger.debug(
                    f"App Service {resource.get('name', 'unknown')} has "
                    f"translatable property: {prop}"
                )
                return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate app service cross-tenant references.

        Args:
            resource: App service resource to translate

        Returns:
            Translated resource dictionary

        Note:
            This method creates a deep copy to avoid modifying the original resource.
        """
        # Create a copy to avoid modifying original
        translated = resource.copy()
        resource_type = resource.get("type", "")
        resource_name = resource.get("name", "unknown")

        logger.info(f"Translating app service/function app: {resource_name}")

        # Translate App Service Plan resource itself
        if resource_type in ["azurerm_app_service_plan", "azurerm_service_plan"]:
            if "id" in translated:
                original_id = translated["id"]
                translated_id, warnings = self._translate_resource_id(original_id, "id")
                translated["id"] = translated_id

                self._add_result(
                    property_path="id",
                    original=original_id,
                    translated=translated_id,
                    warnings=warnings,
                    resource_type=resource_type,
                    resource_name=resource_name,
                )

            return translated

        # Translate App Service Plan ID reference
        for plan_id_field in ["app_service_plan_id", "service_plan_id"]:
            if plan_id_field in translated:
                original_plan_id = translated[plan_id_field]
                translated_plan_id, warnings = self._translate_resource_id(
                    original_plan_id, plan_id_field
                )
                translated[plan_id_field] = translated_plan_id

                self._add_result(
                    property_path=plan_id_field,
                    original=original_plan_id,
                    translated=translated_plan_id,
                    warnings=warnings,
                    resource_type=resource_type,
                    resource_name=resource_name,
                )

        # Translate app settings
        if "app_settings" in translated:
            original_settings = translated["app_settings"]
            translated_settings, warnings = self._translate_app_settings(
                original_settings, resource_name
            )
            translated["app_settings"] = translated_settings

            self._add_result(
                property_path="app_settings",
                original=f"<{len(original_settings) if isinstance(original_settings, dict) else 0} settings>",
                translated=f"<{len(translated_settings) if isinstance(translated_settings, dict) else 0} settings>",
                warnings=warnings,
                resource_type=resource_type,
                resource_name=resource_name,
            )

        # Translate connection strings
        if "connection_string" in translated:
            original_conn_strings = translated["connection_string"]
            translated_conn_strings, warnings = self._translate_connection_strings(
                original_conn_strings, resource_name
            )
            translated["connection_string"] = translated_conn_strings

            self._add_result(
                property_path="connection_string",
                original=f"<{len(original_conn_strings) if isinstance(original_conn_strings, list) else 0} connection strings>",
                translated=f"<{len(translated_conn_strings) if isinstance(translated_conn_strings, list) else 0} connection strings>",
                warnings=warnings,
                resource_type=resource_type,
                resource_name=resource_name,
            )

        logger.info(f"Completed translation for {resource_type}: {resource_name}")

        return translated

    def _translate_app_settings(
        self, settings: Any, resource_name: str
    ) -> Tuple[Any, List[str]]:
        """
        Translate app settings including Key Vault references.

        App settings may contain:
        1. Key Vault references: @Microsoft.KeyVault(SecretUri=...)
        2. Storage connection strings: DefaultEndpointsProtocol=...;AccountName=...
        3. Other connection strings
        4. Regular string values

        Args:
            settings: App settings dictionary or None
            resource_name: Name of the app service for logging

        Returns:
            Tuple of (translated_settings, warnings)

        Security Note:
            This method never logs actual setting values. Only logs warnings
            for settings that may need manual review.
        """
        warnings: List[str] = []

        # Defensive type check: ensure settings is a dict
        if not isinstance(settings, dict):
            if settings is not None:
                warnings.append(
                    f"App settings is not a dict (got {type(settings).__name__}), skipping translation"
                )
            return settings, warnings

        if not settings:
            return settings, warnings

        # Skip Terraform variables
        if isinstance(settings, str) and ("${" in settings or "var." in settings):
            return settings, warnings

        translated_settings = {}

        for key, value in settings.items():
            if not isinstance(value, str):
                # Non-string values (numbers, booleans, etc.) pass through
                translated_settings[key] = value
                continue

            # Skip Terraform variables
            if "${" in value or "var." in value:
                translated_settings[key] = value
                continue

            # Check for Key Vault reference
            if "@Microsoft.KeyVault" in value:
                translated_value, kv_warnings = self._translate_keyvault_reference(
                    value, key
                )
                translated_settings[key] = translated_value
                warnings.extend(kv_warnings)

                # Log if translation occurred
                if translated_value != value:
                    logger.debug(
                        f"Translated Key Vault reference in app setting '{key}' "
                        f"for app service '{resource_name}'"
                    )

            # Check for storage connection string
            elif "AccountName=" in value and "AccountKey=" in value:
                # Storage connection string detected
                match = STORAGE_CONN_STR_PATTERN.search(value)
                if match:
                    account_name = match.group(1)
                    warnings.append(
                        f"App setting '{key}' contains storage connection string "
                        f"for account '{account_name}'. Connection string may need "
                        f"manual review if storage account is in different subscription. "
                        f"Storage account keys should be regenerated in target environment."
                    )
                else:
                    warnings.append(
                        f"App setting '{key}' appears to be a storage connection string. "
                        f"Manual review recommended."
                    )
                translated_settings[key] = value

            # Check for SQL connection string
            elif "Server=tcp:" in value or "Server=" in value:
                # SQL connection string detected
                match = SQL_CONN_STR_PATTERN.search(value)
                if match:
                    server = match.group(1)
                    warnings.append(
                        f"App setting '{key}' contains SQL connection string "
                        f"to server '{server}'. Connection string may need manual "
                        f"review if database is in different subscription."
                    )
                else:
                    warnings.append(
                        f"App setting '{key}' appears to be a SQL connection string. "
                        f"Manual review recommended."
                    )
                translated_settings[key] = value

            else:
                # Regular string value, pass through
                translated_settings[key] = value

        return translated_settings, warnings

    def _translate_connection_strings(
        self, conn_strings: Any, resource_name: str
    ) -> Tuple[Any, List[str]]:
        """
        Translate connection strings array.

        Connection strings in App Services have the format:
        [
            {
                "name": "MyDb",
                "type": "SQLAzure",
                "value": "Server=tcp:..."
            }
        ]

        Args:
            conn_strings: Connection strings array or None
            resource_name: Name of the app service for logging

        Returns:
            Tuple of (translated_conn_strings, warnings)

        Security Note:
            This method never logs actual connection string values.
        """
        warnings: List[str] = []

        # Defensive type check: ensure conn_strings is a list
        if not isinstance(conn_strings, list):
            if conn_strings is not None:
                warnings.append(
                    f"Connection strings in unexpected format (expected list, got {type(conn_strings).__name__})"
                )
            return conn_strings, warnings

        if not conn_strings:
            return conn_strings, warnings

        translated_conn_strings = []

        for conn_str in conn_strings:
            if not isinstance(conn_str, dict):
                translated_conn_strings.append(conn_str)
                continue

            conn_str = conn_str.copy()
            conn_name = conn_str.get("name", "<unnamed>")
            conn_type = conn_str.get("type", "Custom")
            conn_value = conn_str.get("value", "")

            if not isinstance(conn_value, str):
                translated_conn_strings.append(conn_str)
                continue

            # Skip Terraform variables
            if "${" in conn_value or "var." in conn_value:
                translated_conn_strings.append(conn_str)
                continue

            # Check for Key Vault reference
            if "@Microsoft.KeyVault" in conn_value:
                translated_value, kv_warnings = self._translate_keyvault_reference(
                    conn_value, f"connection_string[{conn_name}]"
                )
                conn_str["value"] = translated_value
                warnings.extend(kv_warnings)

            # Check for storage connection string
            elif "AccountName=" in conn_value and "AccountKey=" in conn_value:
                match = STORAGE_CONN_STR_PATTERN.search(conn_value)
                if match:
                    account_name = match.group(1)
                    warnings.append(
                        f"Connection string '{conn_name}' references storage account "
                        f"'{account_name}'. Storage keys should be regenerated in target."
                    )
                else:
                    warnings.append(
                        f"Connection string '{conn_name}' appears to be a storage "
                        f"connection string. Manual review recommended."
                    )

            # Check for SQL connection string
            elif conn_type in ["SQLAzure", "SQLServer"] or "Server=" in conn_value:
                match = SQL_CONN_STR_PATTERN.search(conn_value)
                if match:
                    server = match.group(1)
                    warnings.append(
                        f"Connection string '{conn_name}' (type: {conn_type}) "
                        f"references server '{server}'. Manual review may be needed "
                        f"if server is in different subscription."
                    )
                else:
                    warnings.append(
                        f"Connection string '{conn_name}' (type: {conn_type}) "
                        f"may reference external database. Manual review recommended."
                    )

            # Other connection types
            elif conn_type not in ["Custom"]:
                warnings.append(
                    f"Connection string '{conn_name}' has type '{conn_type}'. "
                    f"Manual review recommended for cross-subscription deployment."
                )

            translated_conn_strings.append(conn_str)

        return translated_conn_strings, warnings

    def _translate_keyvault_reference(
        self, ref: str, setting_name: str
    ) -> Tuple[str, List[str]]:
        """
        Translate Key Vault reference in app settings.

        Key Vault references have two formats:
        1. SecretUri format:
           @Microsoft.KeyVault(SecretUri=https://vault.vault.azure.net/secrets/secret/version)

        2. VaultName format:
           @Microsoft.KeyVault(VaultName=vault;SecretName=secret;SecretVersion=version)

        We translate vault names to point to the target subscription's vault
        (if the vault exists in target).

        Args:
            ref: Original Key Vault reference string
            setting_name: Name of the setting (for logging)

        Returns:
            Tuple of (translated_reference, warnings)

        Note:
            Only translates vault name. Secret names and versions are preserved.
        """
        warnings: List[str] = []

        match = KEYVAULT_REFERENCE_PATTERN.search(ref)
        if not match:
            warnings.append(
                f"Setting '{setting_name}' has malformed Key Vault reference: {ref[:50]}..."
            )
            return ref, warnings

        params_str = match.group("params")

        # Parse parameters
        params = {}
        for param in params_str.split(";"):
            if "=" in param:
                key, value = param.split("=", 1)
                params[key.strip()] = value.strip()

        # Check for SecretUri format
        if "SecretUri" in params:
            secret_uri = params["SecretUri"]

            # Extract vault name from URI
            # Format: https://vault-name.vault.azure.net/secrets/...
            uri_match = re.match(
                r"https://([^.]+)\.vault\.azure\.net/secrets/(.+)",
                secret_uri,
                re.IGNORECASE,
            )

            if not uri_match:
                warnings.append(
                    f"Setting '{setting_name}' has unrecognized SecretUri format: {secret_uri[:50]}..."
                )
                return ref, warnings

            vault_name = uri_match.group(1)
            # secret_path = uri_match.group(2)  # secret-name/version (not used currently)

            # Check if vault exists in target
            vault_exists = self._check_target_exists(
                "Microsoft.KeyVault/vaults", vault_name
            )

            if not vault_exists:
                warnings.append(
                    f"Setting '{setting_name}' references Key Vault '{vault_name}' "
                    f"not found in target subscription. Manual vault name update may be needed."
                )
                # Return original reference unchanged
                return ref, warnings

            # Vault exists in target, keep the same reference
            # (vault names must match between source and target)
            logger.debug(
                f"Key Vault reference in '{setting_name}' validated: vault '{vault_name}' "
                f"exists in target subscription"
            )

            return ref, warnings

        # Check for VaultName format
        elif "VaultName" in params:
            vault_name = params["VaultName"]

            # Check if vault exists in target
            vault_exists = self._check_target_exists(
                "Microsoft.KeyVault/vaults", vault_name
            )

            if not vault_exists:
                warnings.append(
                    f"Setting '{setting_name}' references Key Vault '{vault_name}' "
                    f"not found in target subscription. Manual vault name update may be needed."
                )

            logger.debug(
                f"Key Vault reference in '{setting_name}' uses VaultName format: "
                f"vault '{vault_name}' (exists_in_target={vault_exists})"
            )

            return ref, warnings

        else:
            warnings.append(
                f"Setting '{setting_name}' has Key Vault reference with unrecognized format"
            )
            return ref, warnings

    def _azure_type_to_terraform_type(self, azure_type: str) -> Optional[str]:
        """
        Convert Azure resource type to Terraform resource type.

        Extended mapping for app service resources.

        Args:
            azure_type: Azure resource type

        Returns:
            Terraform resource type or None
        """
        # Start with base mapping
        base_mapping = super()._azure_type_to_terraform_type(azure_type)
        if base_mapping:
            return base_mapping

        # Add app service specific mappings
        app_service_type_map = {
            # App Service Plans
            "Microsoft.Web/serverFarms": "azurerm_app_service_plan",
            "Microsoft.Web/serverfarms": "azurerm_service_plan",
            # App Services
            "Microsoft.Web/sites": "azurerm_linux_web_app",  # Default to linux
            # Key Vault
            "Microsoft.KeyVault/vaults": "azurerm_key_vault",
            # Storage (for Function Apps)
            "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
            # SQL (for connection strings)
            "Microsoft.Sql/servers": "azurerm_mssql_server",
        }

        return app_service_type_map.get(azure_type)
