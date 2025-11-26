"""
Base translator class for cross-tenant resource translation.

This module provides the abstract base class that all resource translators
must inherit from. It defines the common interface and shared functionality
for translating Azure resources between tenants/subscriptions.

Design Philosophy:
- Abstract base class defines contract
- Translators register themselves via decorator
- Each translator handles specific resource types
- Graceful error handling with comprehensive warnings
- Result tracking for reporting

Usage:
    from src.iac.translators import BaseTranslator, register_translator, TranslationContext

    @register_translator
    class MyTranslator(BaseTranslator):
        @property
        def supported_resource_types(self):
            return ["azurerm_my_resource"]

        def can_translate(self, resource):
            return resource.get("type") == "azurerm_my_resource"

        def translate(self, resource):
            # Translation logic here
            return resource
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Azure Resource ID pattern:
# /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}[/...]
RESOURCE_ID_PATTERN = re.compile(
    r"^/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/([^/]+/[^/]+)/(.+)$"
)


@dataclass
class TranslationContext:
    """
    Context passed to translators during initialization.

    This provides all the information translators need to perform
    cross-tenant translation.
    """

    source_subscription_id: Optional[str] = None
    """Source subscription ID (where resources were scanned)"""

    target_subscription_id: Optional[str] = None
    """Target subscription ID (where resources will be deployed)"""

    source_tenant_id: Optional[str] = None
    """Source tenant ID (for Entra ID translation)"""

    target_tenant_id: Optional[str] = None
    """Target tenant ID (for Entra ID translation)"""

    available_resources: Dict[str, Any] = field(default_factory=dict)
    """Resources being generated in IaC (for existence validation)"""

    identity_mapping_file: Optional[str] = None
    """Path to identity mapping file (for EntraIdTranslator)"""

    identity_mapping: Optional[Dict[str, Any]] = None
    """
    Identity mapping dictionary loaded from JSON file (for EntraIdTranslator).
    If provided, this takes precedence over identity_mapping_file.
    """

    strict_mode: bool = False
    """If True, fail on missing mappings. If False, warn."""


@dataclass
class TranslationResult:
    """Result of translating a single property or field."""

    property_path: str
    """Path to the property that was translated (e.g., 'connection_string')"""

    original_value: Any
    """Original value before translation"""

    translated_value: Any
    """Value after translation (may be same as original)"""

    was_modified: bool
    """Whether the value was actually changed"""

    warnings: List[str] = field(default_factory=list)
    """Warnings encountered during translation"""

    resource_type: str = ""
    """Azure resource type that was referenced"""

    resource_name: str = ""
    """Name of the resource that was referenced"""


class BaseTranslator(ABC):
    """
    Abstract base class for all resource translators.

    Translators handle cross-tenant/cross-subscription translation for
    specific Azure resource types. Each translator:

    1. Declares which resource types it handles (supported_resource_types)
    2. Determines if a resource needs translation (can_translate)
    3. Performs the translation (translate)
    4. Tracks results for reporting (get_translation_results)

    Thread Safety:
        Translators should be thread-safe as they may be called
        concurrently for different resources.

    Example:
        @register_translator
        class StorageAccountTranslator(BaseTranslator):
            @property
            def supported_resource_types(self):
                return ["azurerm_storage_account"]

            def can_translate(self, resource):
                return self._has_cross_subscription_references(resource)

            def translate(self, resource):
                # Translate connection strings, endpoints, etc.
                return translated_resource
    """

    def __init__(self, context: TranslationContext):
        """
        Initialize translator with context.

        Args:
            context: Translation context with source/target info
        """
        self.context = context
        self._results: List[TranslationResult] = []

    @property
    @abstractmethod
    def supported_resource_types(self) -> List[str]:
        """
        Get list of Terraform resource types this translator handles.

        Returns:
            List of resource type strings (e.g., ["azurerm_storage_account"])
        """
        pass

    @abstractmethod
    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this translator can/should translate a resource.

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            True if this translator should process this resource

        Note:
            This method is called before translate() to avoid unnecessary work.
            Check for:
            - Correct resource type
            - Presence of translatable fields
            - Cross-subscription/tenant references
        """
        pass

    @abstractmethod
    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate a resource's cross-tenant references.

        Args:
            resource: Resource dictionary to translate

        Returns:
            Translated resource dictionary

        Note:
            - Return a copy/modified version of the resource
            - Track results using _add_result()
            - Handle errors gracefully with warnings
            - Log translation actions
        """
        pass

    def get_translation_results(self) -> List[TranslationResult]:
        """
        Get list of translation results from this translator.

        Returns:
            List of TranslationResult objects
        """
        return self._results.copy()

    def get_report(self) -> Dict[str, Any]:
        """
        Generate a report of this translator's activity.

        Returns:
            Dictionary with translator statistics
        """
        total_resources = len(self._results)
        translations_performed = sum(1 for r in self._results if r.was_modified)
        total_warnings = sum(len(r.warnings) for r in self._results)
        missing_targets = sum(
            1
            for r in self._results
            if r.was_modified and "not found" in " ".join(r.warnings).lower()
        )

        return {
            "translator": self.__class__.__name__,
            "total_resources_processed": total_resources,
            "translations_performed": translations_performed,
            "warnings": total_warnings,
            "missing_targets": missing_targets,
            "results": [
                {
                    "property": r.property_path,
                    "resource_type": r.resource_type,
                    "resource_name": r.resource_name,
                    "original": str(r.original_value)[:100],  # Truncate for display
                    "translated": str(r.translated_value)[:100],
                    "warnings": r.warnings,
                }
                for r in self._results
                if r.was_modified
            ][:10],  # Limit to 10 samples
        }

    def _add_result(
        self,
        property_path: str,
        original: Any,
        translated: Any,
        warnings: Optional[List[str]] = None,
        resource_type: str = "",
        resource_name: str = "",
    ) -> None:
        """
        Add a translation result for tracking.

        Args:
            property_path: Path to translated property
            original: Original value
            translated: Translated value
            warnings: Optional list of warnings
            resource_type: Optional resource type
            resource_name: Optional resource name
        """
        result = TranslationResult(
            property_path=property_path,
            original_value=original,
            translated_value=translated,
            was_modified=(original != translated),
            warnings=warnings or [],
            resource_type=resource_type,
            resource_name=resource_name,
        )
        self._results.append(result)

    def _parse_resource_id(self, resource_id: str) -> Optional[Dict[str, str]]:
        """
        Parse an Azure resource ID into components.

        Args:
            resource_id: Azure resource ID string

        Returns:
            Dictionary with parsed components or None if invalid
            Keys: subscription_id, resource_group, resource_type, remaining_path
        """
        if not resource_id or not isinstance(resource_id, str):
            return None

        match = RESOURCE_ID_PATTERN.match(resource_id)
        if not match:
            return None

        subscription_id, resource_group, resource_type, remaining = match.groups()

        return {
            "subscription_id": subscription_id,
            "resource_group": resource_group,
            "resource_type": resource_type,
            "remaining_path": remaining,
            "resource_name": remaining.split("/")[0],
        }

    def _is_cross_subscription_reference(self, resource_id: str) -> bool:
        """
        Check if a resource ID references a different subscription.

        Args:
            resource_id: Azure resource ID to check

        Returns:
            True if the resource ID is from a different subscription
        """
        parsed = self._parse_resource_id(resource_id)
        if not parsed:
            return False

        return parsed["subscription_id"] != self.context.target_subscription_id

    def _normalize_provider_casing(self, resource_id: str) -> str:
        """
        Normalize provider names in resource IDs to proper case.

        Terraform requires proper case (Microsoft.OperationalInsights) but Neo4j/Azure
        may return lowercase (microsoft.operationalinsights). This normalizes common providers.

        Args:
            resource_id: Resource ID potentially with lowercase providers

        Returns:
            Resource ID with normalized provider casing
        """
        # Mapping of lowercase -> proper case for common providers
        # Only normalize the /providers/ segment, not the entire string
        normalizations = {
            '/providers/microsoft.operationalinsights/': '/providers/Microsoft.OperationalInsights/',
            '/providers/microsoft.insights/': '/providers/Microsoft.Insights/',
            '/providers/microsoft.keyvault/': '/providers/Microsoft.KeyVault/',
            '/providers/microsoft.storage/': '/providers/Microsoft.Storage/',
            '/providers/microsoft.compute/': '/providers/Microsoft.Compute/',
            '/providers/microsoft.network/': '/providers/Microsoft.Network/',
            '/providers/microsoft.sql/': '/providers/Microsoft.Sql/',
            '/providers/microsoft.web/': '/providers/Microsoft.Web/',
            '/providers/microsoft.authorization/': '/providers/Microsoft.Authorization/',
        }

        normalized = resource_id
        for lowercase, proper_case in normalizations.items():
            normalized = normalized.replace(lowercase, proper_case)

        return normalized

    def _translate_resource_id(
        self, resource_id: str, context_name: str = ""
    ) -> tuple[str, List[str]]:
        """
        Translate a resource ID from source to target subscription.

        Args:
            resource_id: Original resource ID
            context_name: Optional context for warnings (e.g., field name)

        Returns:
            Tuple of (translated_id, warnings)
        """
        warnings: List[str] = []

        # Skip Terraform variables/references
        if "${" in resource_id or "var." in resource_id:
            return resource_id, warnings

        parsed = self._parse_resource_id(resource_id)
        if not parsed:
            warnings.append(f"Invalid Azure resource ID format: {resource_id}")
            return resource_id, warnings

        # Check if translation is needed
        if not self._is_cross_subscription_reference(resource_id):
            # Even for same-subscription, normalize provider casing
            return self._normalize_provider_casing(resource_id), warnings

        # Perform translation
        translated_id = resource_id.replace(
            f"/subscriptions/{parsed['subscription_id']}/",
            f"/subscriptions/{self.context.target_subscription_id}/",
        )

        # Normalize provider casing (Bug #68: Terraform requires proper case)
        translated_id = self._normalize_provider_casing(translated_id)

        # Check if target exists
        target_exists = self._check_target_exists(
            parsed["resource_type"], parsed["resource_name"]
        )

        if not target_exists:
            warning = (
                f"Target resource '{parsed['resource_name']}' of type "
                f"'{parsed['resource_type']}' not found in generated IaC."
            )
            if context_name:
                warning = f"{context_name}: {warning}"
            warnings.append(warning)

        logger.info(
            f"Translated resource ID: {resource_id[:80]}... -> {translated_id[:80]}... "
            f"(target_exists={target_exists})"
        )

        return translated_id, warnings

    def _check_target_exists(self, resource_type: str, resource_name: str) -> bool:
        """
        Check if a target resource exists in the IaC being generated.

        Args:
            resource_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)
            resource_name: Resource name

        Returns:
            True if the resource exists in available_resources
        """
        terraform_type = self._azure_type_to_terraform_type(resource_type)
        if not terraform_type:
            logger.debug(
                f"Could not map Azure type '{resource_type}' to Terraform type"
            )
            return False

        resources_of_type = self.context.available_resources.get(terraform_type, {})
        exists = resource_name in resources_of_type

        logger.debug(
            f"Target check: type={terraform_type}, name={resource_name}, exists={exists}"
        )

        return exists

    def _azure_type_to_terraform_type(self, azure_type: str) -> Optional[str]:
        """
        Convert Azure resource type to Terraform resource type.

        Args:
            azure_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)

        Returns:
            Terraform resource type or None if mapping not found
        """
        type_map = {
            "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
            "Microsoft.KeyVault/vaults": "azurerm_key_vault",
            "Microsoft.Sql/servers": "azurerm_mssql_server",
            "Microsoft.DBforPostgreSQL/servers": "azurerm_postgresql_server",
            "Microsoft.DBforMySQL/servers": "azurerm_mysql_server",
            "Microsoft.ContainerRegistry/registries": "azurerm_container_registry",
            "Microsoft.Web/sites": "azurerm_app_service",
            "Microsoft.CognitiveServices/accounts": "azurerm_cognitive_account",
            "Microsoft.ServiceBus/namespaces": "azurerm_servicebus_namespace",
            "Microsoft.EventHub/namespaces": "azurerm_eventhub_namespace",
            "Microsoft.DocumentDB/databaseAccounts": "azurerm_cosmosdb_account",
            "Microsoft.Search/searchServices": "azurerm_search_service",
            "Microsoft.Cache/Redis": "azurerm_redis_cache",
            "Microsoft.ContainerService/managedClusters": "azurerm_kubernetes_cluster",
        }

        return type_map.get(azure_type)
