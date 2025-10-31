"""
Storage Account Translator for Cross-Tenant Translation

Translates Azure Storage Account cross-tenant references including:
- Resource IDs in storage account properties
- Connection strings (AccountName, EndpointSuffix, etc.)
- Blob, File, Table, and Queue endpoint URIs
- Custom domain endpoints

This translator does NOT handle private endpoint connections - those are
handled by PrivateEndpointTranslator.

Example Translations:
    Resource ID:
        /subscriptions/SOURCE/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1
        -> /subscriptions/TARGET/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1

    Connection String:
        DefaultEndpointsProtocol=https;AccountName=sourcestorage;AccountKey=xxx;EndpointSuffix=core.windows.net
        -> DefaultEndpointsProtocol=https;AccountName=targetstorage;AccountKey=xxx;EndpointSuffix=core.windows.net

    Blob Endpoint:
        https://sourcestorage.blob.core.windows.net/
        -> https://targetstorage.blob.core.windows.net/
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from .base_translator import BaseTranslator
from .registry import register_translator

logger = logging.getLogger(__name__)

# Patterns for storage account endpoints
BLOB_ENDPOINT_PATTERN = re.compile(
    r"https?://([a-z0-9]+)\.blob\.core\.windows\.net(/?.*)",
    re.IGNORECASE,
)
FILE_ENDPOINT_PATTERN = re.compile(
    r"https?://([a-z0-9]+)\.file\.core\.windows\.net(/?.*)",
    re.IGNORECASE,
)
TABLE_ENDPOINT_PATTERN = re.compile(
    r"https?://([a-z0-9]+)\.table\.core\.windows\.net(/?.*)",
    re.IGNORECASE,
)
QUEUE_ENDPOINT_PATTERN = re.compile(
    r"https?://([a-z0-9]+)\.queue\.core\.windows\.net(/?.*)",
    re.IGNORECASE,
)
DFS_ENDPOINT_PATTERN = re.compile(
    r"https?://([a-z0-9]+)\.dfs\.core\.windows\.net(/?.*)",
    re.IGNORECASE,
)

# Storage account resource ID pattern
STORAGE_ACCOUNT_ID_PATTERN = re.compile(
    r"/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/Microsoft\.Storage/storageAccounts/([^/]+)",
    re.IGNORECASE,
)


@register_translator
class StorageAccountTranslator(BaseTranslator):
    """
    Translates Azure Storage Account cross-tenant references.

    Handles translation of:
    - Storage account resource IDs
    - Connection strings with account names
    - Endpoint URIs (blob, file, table, queue, dfs)

    This translator focuses on storage accounts themselves and references TO
    storage accounts from other resources. It does not handle private endpoints
    (handled by PrivateEndpointTranslator).

    Design Philosophy:
    - Conservative: Only translates when necessary
    - Defensive: Validates all inputs, gracefully handles errors
    - Informative: Provides warnings for potential issues
    - Traceable: Records all translations for reporting
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """
        Get list of Terraform resource types this translator handles.

        Returns:
            List containing "azurerm_storage_account"
        """
        return ["azurerm_storage_account"]

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource needs storage account translation.

        A resource needs translation if:
        1. It's a storage account resource type
        2. It has properties that might contain cross-subscription references

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            True if translation is needed
        """
        resource_type = resource.get("type", "")

        # Check if this is a storage account
        if resource_type not in self.supported_resource_types:
            return False

        # Check if there are properties that might need translation
        # Common properties that might have cross-subscription references:
        # - id (resource ID)
        # - primary_connection_string
        # - secondary_connection_string
        # - primary_blob_endpoint
        # - primary_file_endpoint
        # - etc.

        translatable_properties = [
            "id",
            "primary_connection_string",
            "secondary_connection_string",
            "primary_blob_endpoint",
            "secondary_blob_endpoint",
            "primary_file_endpoint",
            "secondary_file_endpoint",
            "primary_table_endpoint",
            "secondary_table_endpoint",
            "primary_queue_endpoint",
            "secondary_queue_endpoint",
            "primary_dfs_endpoint",
            "secondary_dfs_endpoint",
        ]

        # Check if any translatable property exists
        for prop in translatable_properties:
            if prop in resource:
                logger.debug(
                    f"Storage account {resource.get('name', 'unknown')} has "
                    f"translatable property: {prop}"
                )
                return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate storage account cross-tenant references.

        Args:
            resource: Storage account resource to translate

        Returns:
            Translated resource dictionary

        Note:
            This method creates a deep copy to avoid modifying the original resource.
        """
        # Create a copy to avoid modifying original
        translated = resource.copy()
        resource_name = resource.get("name", "unknown")

        logger.info(f"Translating storage account: {resource_name}")

        # Translate resource ID
        if "id" in translated:
            original_id = translated["id"]
            translated_id, warnings = self._translate_resource_id(original_id, "id")
            translated["id"] = translated_id
            self._add_result("id", original_id, translated_id, warnings)

        # Translate connection strings
        for conn_str_field in [
            "primary_connection_string",
            "secondary_connection_string",
        ]:
            if conn_str_field in translated:
                original_str = translated[conn_str_field]
                translated_str, warnings = self._translate_connection_string(
                    original_str, resource_name
                )
                translated[conn_str_field] = translated_str
                self._add_result(
                    conn_str_field,
                    original_str,
                    translated_str,
                    warnings,
                    resource_type="Microsoft.Storage/storageAccounts",
                    resource_name=resource_name,
                )

        # Translate endpoint URIs
        endpoint_fields = [
            "primary_blob_endpoint",
            "secondary_blob_endpoint",
            "primary_file_endpoint",
            "secondary_file_endpoint",
            "primary_table_endpoint",
            "secondary_table_endpoint",
            "primary_queue_endpoint",
            "secondary_queue_endpoint",
            "primary_dfs_endpoint",
            "secondary_dfs_endpoint",
        ]

        for endpoint_field in endpoint_fields:
            if endpoint_field in translated:
                original_endpoint = translated[endpoint_field]
                translated_endpoint, warnings = self._translate_endpoint_uri(
                    original_endpoint, resource_name
                )
                translated[endpoint_field] = translated_endpoint
                self._add_result(
                    endpoint_field,
                    original_endpoint,
                    translated_endpoint,
                    warnings,
                    resource_type="Microsoft.Storage/storageAccounts",
                    resource_name=resource_name,
                )

        logger.info(f"Completed translation for storage account: {resource_name}")
        return translated

    def _translate_connection_string(
        self, conn_str: str, storage_account_name: str
    ) -> Tuple[str, List[str]]:
        """
        Translate Azure Storage connection string.

        Connection strings have format:
            DefaultEndpointsProtocol=https;AccountName=xxx;AccountKey=xxx;EndpointSuffix=core.windows.net

        We check if AccountName references a storage account from the source
        subscription and update it if needed.

        Args:
            conn_str: Original connection string
            storage_account_name: Name of the storage account this belongs to

        Returns:
            Tuple of (translated_string, warnings)
        """
        warnings: List[str] = []

        if not conn_str or not isinstance(conn_str, str):
            warnings.append("Connection string is empty or invalid")
            return conn_str, warnings

        # Skip Terraform variables
        if "${" in conn_str or "var." in conn_str:
            return conn_str, warnings

        # Parse connection string into key-value pairs
        try:
            parts = {}
            for pair in conn_str.split(";"):
                if "=" in pair:
                    key, value = pair.split("=", 1)
                    parts[key.strip()] = value.strip()

            # Check if AccountName needs translation
            account_name = parts.get("AccountName")
            if not account_name:
                warnings.append("Connection string missing AccountName")
                return conn_str, warnings

            # For storage accounts, the account name should match the resource name
            # If it doesn't, it might be referencing another storage account
            if account_name != storage_account_name:
                warnings.append(
                    f"Connection string references different account: {account_name} "
                    f"(resource name: {storage_account_name}). This may need manual review."
                )

            # Check if the referenced storage account exists in target
            target_exists = self._check_target_exists(
                "Microsoft.Storage/storageAccounts", account_name
            )

            if not target_exists:
                warnings.append(
                    f"Storage account '{account_name}' referenced in connection string "
                    f"not found in generated IaC."
                )

            logger.debug(
                f"Connection string translation: AccountName={account_name}, "
                f"target_exists={target_exists}"
            )

            # Connection strings typically don't contain subscription IDs,
            # so we return as-is (account names are globally unique per region)
            return conn_str, warnings

        except Exception as e:
            warnings.append(f"Failed to parse connection string: {e!s}")
            logger.error(
                f"Error parsing connection string for {storage_account_name}: {e}"
            )
            return conn_str, warnings

    def _translate_endpoint_uri(
        self, uri: str, storage_account_name: str
    ) -> Tuple[str, List[str]]:
        """
        Translate storage endpoint URI.

        Checks if URI references a storage account and updates the account name
        if it's from the source subscription.

        Examples:
            https://sourcestorage.blob.core.windows.net/container
            -> https://targetstorage.blob.core.windows.net/container

        Args:
            uri: Original endpoint URI
            storage_account_name: Name of the storage account this belongs to

        Returns:
            Tuple of (translated_uri, warnings)
        """
        warnings: List[str] = []

        if not uri or not isinstance(uri, str):
            warnings.append("Endpoint URI is empty or invalid")
            return uri, warnings

        # Skip Terraform variables
        if "${" in uri or "var." in uri:
            return uri, warnings

        # Try to match against known endpoint patterns
        patterns = [
            ("blob", BLOB_ENDPOINT_PATTERN),
            ("file", FILE_ENDPOINT_PATTERN),
            ("table", TABLE_ENDPOINT_PATTERN),
            ("queue", QUEUE_ENDPOINT_PATTERN),
            ("dfs", DFS_ENDPOINT_PATTERN),
        ]

        for service_name, pattern in patterns:
            match = pattern.match(uri)
            if match:
                account_name_in_uri = match.group(1)
                # path_suffix = match.group(2)  # Not used currently

                logger.debug(
                    f"Found {service_name} endpoint: account={account_name_in_uri}, "
                    f"resource_name={storage_account_name}"
                )

                # Check if the account name in URI matches the resource
                if account_name_in_uri != storage_account_name:
                    warnings.append(
                        f"Endpoint URI references different account: {account_name_in_uri} "
                        f"(resource name: {storage_account_name}). This may need manual review."
                    )

                # Check if target exists
                target_exists = self._check_target_exists(
                    "Microsoft.Storage/storageAccounts", account_name_in_uri
                )

                if not target_exists:
                    warnings.append(
                        f"Storage account '{account_name_in_uri}' referenced in URI "
                        f"not found in generated IaC."
                    )

                # Storage account names are globally unique, so we typically don't
                # need to modify the URI unless we're doing account name remapping
                # (which is beyond the scope of cross-subscription translation)
                logger.debug(
                    f"Endpoint URI translation: {service_name} endpoint for "
                    f"{account_name_in_uri}, target_exists={target_exists}"
                )

                return uri, warnings

        # If no pattern matched, it might be a custom domain
        if "core.windows.net" not in uri.lower():
            warnings.append(
                f"Endpoint URI uses custom domain or unrecognized format: {uri}. "
                f"Manual review may be required."
            )

        return uri, warnings
