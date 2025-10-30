"""
Private Endpoint Resource ID Translation for IaC Generation

Translates cross-subscription resource IDs in private endpoint connections
when generating IaC for a different target subscription.

For example:
- Source: /subscriptions/SOURCE-SUB/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1
- Target: /subscriptions/TARGET-SUB/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1

This prevents Terraform deployment failures when private endpoints reference resources
from a different subscription than the deployment target.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Azure Resource ID pattern:
# /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}[/...]
RESOURCE_ID_PATTERN = re.compile(
    r"^/subscriptions/([^/]+)/resourceGroups/([^/]+)/providers/([^/]+/[^/]+)/(.+)$"
)


@dataclass
class TranslationResult:
    """Represents the result of translating a resource ID."""

    original_id: str
    """Original resource ID"""

    translated_id: str
    """Translated resource ID (may be same as original)"""

    was_translated: bool
    """Whether translation was performed"""

    target_exists: bool
    """Whether the target resource exists in the IaC being generated"""

    warnings: List[str] = field(default_factory=list)
    """Warnings encountered during translation"""

    resource_type: str = ""
    """Azure resource type (e.g., Microsoft.Storage/storageAccounts)"""

    resource_name: str = ""
    """Resource name"""


class PrivateEndpointTranslator:
    """
    Translates resource IDs in private endpoint connections.

    This translator handles the common case where:
    1. Resources are discovered from one subscription (source)
    2. IaC is being generated for a different subscription (target)
    3. Private endpoint connections reference the source subscription

    The translator updates resource IDs to point to the target subscription,
    enabling the IaC to deploy correctly.
    """

    def __init__(
        self,
        source_subscription_id: Optional[str],
        target_subscription_id: str,
        available_resources: Dict[str, Any],
    ):
        """
        Initialize the translator.

        Args:
            source_subscription_id: Source subscription ID from discovery
            target_subscription_id: Target subscription ID for IaC generation
            available_resources: Dict of resources being generated in IaC
                                Format: {resource_type: {resource_name: resource_config}}
        """
        self.source_subscription_id = source_subscription_id
        self.target_subscription_id = target_subscription_id
        self.available_resources = available_resources or {}

        # Extract source subscription from resources if not provided
        if not self.source_subscription_id:
            self.source_subscription_id = self._extract_source_subscription()

        logger.debug(
            f"Initialized translator: source={self.source_subscription_id}, "
            f"target={self.target_subscription_id}"
        )

    def should_translate(self, resource_id: str) -> bool:
        """
        Determine if a resource ID should be translated.

        Translation is needed when:
        1. The resource ID references a different subscription
        2. Source and target subscriptions are different

        Args:
            resource_id: Azure resource ID to check

        Returns:
            True if translation should be performed
        """
        if not resource_id:
            return False

        # Skip Terraform variables/references
        if "${" in resource_id or "var." in resource_id:
            return False

        # Parse the resource ID
        match = RESOURCE_ID_PATTERN.match(resource_id)
        if not match:
            return False

        subscription_id = match.group(1)

        # Check if it's a cross-subscription reference
        # If source_subscription_id is None, we can't determine if it's cross-sub
        if not self.source_subscription_id:
            return False

        is_cross_sub = subscription_id != self.target_subscription_id

        logger.debug(
            f"Translation check: resource_sub={subscription_id}, "
            f"target_sub={self.target_subscription_id}, cross_sub={is_cross_sub}"
        )

        return is_cross_sub

    def translate_resource_id(
        self, resource_id: str, resource_name: Optional[str] = None
    ) -> TranslationResult:
        """
        Translate a resource ID from source to target subscription.

        Args:
            resource_id: Original resource ID
            resource_name: Optional resource name for context

        Returns:
            TranslationResult with translated ID and metadata
        """
        warnings: List[str] = []

        # Parse the resource ID
        match = RESOURCE_ID_PATTERN.match(resource_id)
        if not match:
            warnings.append(f"Invalid Azure resource ID format: {resource_id}")
            return TranslationResult(
                original_id=resource_id,
                translated_id=resource_id,
                was_translated=False,
                target_exists=False,
                warnings=warnings,
            )

        subscription_id, _resource_group, resource_type, remaining = match.groups()

        # Check if translation is needed
        if not self.should_translate(resource_id):
            return TranslationResult(
                original_id=resource_id,
                translated_id=resource_id,
                was_translated=False,
                target_exists=True,
                resource_type=resource_type,
                resource_name=resource_name or remaining.split("/")[0],
            )

        # Perform translation
        translated_id = resource_id.replace(
            f"/subscriptions/{subscription_id}/",
            f"/subscriptions/{self.target_subscription_id}/",
        )

        # Extract resource name from path
        name_from_path = remaining.split("/")[0]
        final_name = resource_name or name_from_path

        # Check if target exists in IaC
        target_exists = self._check_target_exists(resource_type, final_name)

        if not target_exists:
            warnings.append(
                f"Target resource '{final_name}' of type '{resource_type}' "
                f"not found in generated IaC. The translated ID may not be deployable."
            )

        logger.info(
            f"Translated resource ID: {resource_id} -> {translated_id} "
            f"(target_exists={target_exists})"
        )

        return TranslationResult(
            original_id=resource_id,
            translated_id=translated_id,
            was_translated=True,
            target_exists=target_exists,
            warnings=warnings,
            resource_type=resource_type,
            resource_name=final_name,
        )

    def _check_target_exists(self, resource_type: str, resource_name: str) -> bool:
        """
        Check if a target resource exists in the IaC being generated.

        Args:
            resource_type: Azure resource type (e.g., Microsoft.Storage/storageAccounts)
            resource_name: Resource name

        Returns:
            True if the resource exists in available_resources
        """
        # Convert Azure resource type to Terraform resource type
        # E.g., Microsoft.Storage/storageAccounts -> azurerm_storage_account
        terraform_type = self._azure_type_to_terraform_type(resource_type)

        if not terraform_type:
            logger.debug(
                f"Could not map Azure type '{resource_type}' to Terraform type"
            )
            return False

        # Check if resource exists
        resources_of_type = self.available_resources.get(terraform_type, {})
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

        Note:
            This is a curated list of the most common Azure resources that support
            private endpoints. The system gracefully handles unmapped types by logging
            a debug message and returning None. Unmapped types will be skipped during
            target existence validation but translation will still occur.
        """
        # Curated mapping of common private endpoint target types.
        # Based on Azure Private Link service documentation and most frequently
        # used resources in enterprise deployments.
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

    def _extract_source_subscription(self) -> Optional[str]:
        """
        Extract source subscription ID from available resources.

        Examines resource IDs in the available resources to determine
        the source subscription ID.

        Returns:
            Source subscription ID or None if not found
        """
        for _resource_type, resources in self.available_resources.items():
            for _resource_name, resource_config in resources.items():
                # Look for ID fields in resource config
                if isinstance(resource_config, dict):
                    resource_id = resource_config.get("id")
                    if resource_id and isinstance(resource_id, str):
                        match = RESOURCE_ID_PATTERN.match(resource_id)
                        if match:
                            sub_id = match.group(1)
                            logger.debug(
                                f"Extracted source subscription from resource ID: {sub_id}"
                            )
                            return sub_id

        logger.warning("Could not extract source subscription ID from resources")
        return None

    def format_translation_report(self, translations: List[TranslationResult]) -> str:
        """
        Format translation results into a human-readable report.

        Args:
            translations: List of translation results

        Returns:
            Formatted report string
        """
        if not translations:
            return "No resource ID translations were needed."

        lines = ["", "Resource ID Translation Report", "=" * 60, ""]

        translated_count = sum(1 for t in translations if t.was_translated)
        missing_target_count = sum(
            1 for t in translations if t.was_translated and not t.target_exists
        )

        lines.append(f"Total Resource IDs Checked: {len(translations)}")
        lines.append(f"Translated: {translated_count}")
        lines.append(f"Missing Targets: {missing_target_count}")
        lines.append("")

        if translated_count > 0:
            lines.append("Translated Resources:")
            lines.append("-" * 60)

            for result in translations:
                if result.was_translated:
                    status = "✓" if result.target_exists else "⚠"
                    lines.append(
                        f"{status} {result.resource_type}/{result.resource_name}"
                    )
                    lines.append(f"  From: {result.original_id}")
                    lines.append(f"  To:   {result.translated_id}")

                    if result.warnings:
                        for warning in result.warnings:
                            lines.append(f"  Warning: {warning}")

                    lines.append("")

        return "\n".join(lines)
