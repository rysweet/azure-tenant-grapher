"""
Smart Import Block Generator

Generates Terraform 1.5+ import blocks based on resource comparison results.
This module determines which resources need import blocks, which need full
resource emission, and handles all edge cases gracefully.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..resource_comparator import (
    ComparisonResult,
    ResourceClassification,
    ResourceState,
)

logger = logging.getLogger(__name__)


# Azure resource type to Terraform resource type mapping
AZURE_TO_TERRAFORM_TYPE: Dict[str, str] = {
    "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
    "Microsoft.Network/subnets": "azurerm_subnet",  # Bug #23 fix: Add missing subnet mapping
    "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
    "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
    "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
    "Microsoft.Network/loadBalancers": "azurerm_lb",
    "Microsoft.Network/applicationGateways": "azurerm_application_gateway",
    "Microsoft.Network/virtualNetworkGateways": "azurerm_virtual_network_gateway",
    "Microsoft.Network/bastionHosts": "azurerm_bastion_host",
    "Microsoft.Network/privateDnsZones": "azurerm_private_dns_zone",
    "Microsoft.Network/privateDnsZones/virtualNetworkLinks": "azurerm_private_dns_zone_virtual_network_link",
    "Microsoft.Network/privateEndpoints": "azurerm_private_endpoint",
    "Microsoft.Compute/virtualMachines": "azurerm_virtual_machine",
    "Microsoft.Compute/virtualMachineScaleSets": "azurerm_virtual_machine_scale_set",
    "Microsoft.Compute/availabilitySets": "azurerm_availability_set",
    "Microsoft.Compute/disks": "azurerm_managed_disk",
    "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
    "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
    "Microsoft.KeyVault/vaults": "azurerm_key_vault",
    "Microsoft.Sql/servers": "azurerm_sql_server",
    "Microsoft.Sql/servers/databases": "azurerm_sql_database",
    "Microsoft.DBforPostgreSQL/servers": "azurerm_postgresql_server",
    "Microsoft.DBforMySQL/servers": "azurerm_mysql_server",
    "Microsoft.Web/sites": "azurerm_app_service",
    "Microsoft.Web/serverfarms": "azurerm_app_service_plan",
    "Microsoft.ContainerRegistry/registries": "azurerm_container_registry",
    "Microsoft.Cache/Redis": "azurerm_redis_cache",
    "Microsoft.DocumentDB/databaseAccounts": "azurerm_cosmosdb_account",
}


@dataclass
class ImportBlock:
    """Terraform 1.5+ import block.

    Represents a single import block that instructs Terraform to import
    an existing Azure resource into the state without recreating it.
    """

    to: str  # Terraform resource address (e.g., azurerm_virtual_network.vnet_abc123)
    id: str  # Azure resource ID to import from


@dataclass
class ImportBlockSet:
    """Set of import blocks and resources to generate.

    Contains all the information needed to generate Terraform templates
    with import blocks. Resources in resources_needing_emission will have
    full resource blocks emitted, while import_blocks provide the import
    instructions.
    """

    import_blocks: List[ImportBlock]
    # Resource blocks that need emission (NEW + DRIFTED)
    resources_needing_emission: List[Dict[str, Any]]


class SmartImportGenerator:
    """Generates Terraform import blocks based on resource comparison.

    This service implements the core logic for determining which resources
    need import blocks vs full resource emission based on their classification.

    Classification Rules (Bug #23 update):
        - EXACT_MATCH: Generate import block AND emit resource (prevents reference errors)
        - DRIFTED: Generate import block AND include in resources_needing_emission
        - NEW: No import block, include in resources_needing_emission
        - ORPHANED: Log warning, no blocks generated
    """

    def __init__(self) -> None:
        """Initialize the smart import generator."""
        pass

    def generate_import_blocks(
        self,
        comparison_result: ComparisonResult,
    ) -> ImportBlockSet:
        """
        Generate import blocks based on comparison result.

        This method processes each resource classification and generates
        the appropriate import blocks and resource emission list based on
        the classification rules.

        Args:
            comparison_result: Result of comparing abstracted vs target resources

        Returns:
            ImportBlockSet with import blocks and resources needing emission

        Logic (Bug #23 update):
            - EXACT_MATCH: Generate import block AND emit resource (prevents cascading reference errors)
            - DRIFTED: Generate import block AND include in resources_needing_emission
            - NEW: No import block, include in resources_needing_emission
            - ORPHANED: Log warning, no blocks generated

        Note:
            Never raises exceptions - all errors are logged and handled gracefully.
            Invalid resources are skipped with warnings.
        """
        logger.info(
            f"Generating import blocks for {len(comparison_result.classifications)} "
            "resource classifications"
        )

        import_blocks: List[ImportBlock] = []
        resources_needing_emission: List[Dict[str, Any]] = []

        # Process each classification
        for classification in comparison_result.classifications:
            self._process_classification(
                classification,
                import_blocks,
                resources_needing_emission,
            )

        # Bug #17 fix: Deduplicate import blocks by terraform_address
        # Multiple classifications of the same resource can create duplicate import blocks
        seen_addresses = set()
        deduplicated_import_blocks = []
        duplicates_removed = 0

        for import_block in import_blocks:
            # Bug #21 fix: ImportBlock.to (not .terraform_address) contains the terraform resource address
            if import_block.to not in seen_addresses:
                seen_addresses.add(import_block.to)
                deduplicated_import_blocks.append(import_block)
            else:
                duplicates_removed += 1
                logger.debug(
                    f"Removed duplicate import block for {import_block.to}"
                )

        if duplicates_removed > 0:
            logger.info(
                f"Removed {duplicates_removed} duplicate import blocks "
                f"({len(import_blocks)} -> {len(deduplicated_import_blocks)})"
            )

        # Log summary
        logger.info(
            f"Generated {len(deduplicated_import_blocks)} import blocks and "
            f"{len(resources_needing_emission)} resources needing emission"
        )

        return ImportBlockSet(
            import_blocks=deduplicated_import_blocks,
            resources_needing_emission=resources_needing_emission,
        )

    def _process_classification(
        self,
        classification: ResourceClassification,
        import_blocks: List[ImportBlock],
        resources_needing_emission: List[Dict[str, Any]],
    ) -> None:
        """
        Process a single resource classification.

        Args:
            classification: Resource classification to process
            import_blocks: List to append import blocks to (modified in place)
            resources_needing_emission: List to append resources to (modified in place)
        """
        state = classification.classification
        abstracted_resource = classification.abstracted_resource
        target_resource = classification.target_resource

        if state == ResourceState.EXACT_MATCH:
            # Bug #23 fix: Generate import block AND emit resource
            self._handle_exact_match(
                abstracted_resource,
                target_resource,
                import_blocks,
                resources_needing_emission,
            )

        elif state == ResourceState.DRIFTED:
            # Generate import block AND include in resources_needing_emission
            self._handle_drifted(
                abstracted_resource,
                target_resource,
                import_blocks,
                resources_needing_emission,
            )

        elif state == ResourceState.NEW:
            # No import block, include in resources_needing_emission
            self._handle_new(
                abstracted_resource,
                resources_needing_emission,
            )

        elif state == ResourceState.ORPHANED:
            # Log warning, no blocks generated
            self._handle_orphaned(abstracted_resource)

    def _handle_exact_match(
        self,
        abstracted_resource: Dict[str, Any],
        target_resource: Any,
        import_blocks: List[ImportBlock],
        resources_needing_emission: List[Dict[str, Any]],
    ) -> None:
        """
        Handle EXACT_MATCH classification.

        Bug #23 fix: Changed to emit resources for EXACT_MATCH too (not just import blocks).
        Terraform 1.5+ supports import blocks alongside resource definitions.
        This prevents cascading "Reference to undeclared resource" errors when
        child resources reference import-only parents.

        Args:
            abstracted_resource: Resource from abstracted graph
            target_resource: Resource from target scan
            import_blocks: List to append import block to
            resources_needing_emission: List to append resource to
        """
        import_block = self._create_import_block(abstracted_resource, target_resource)

        if import_block:
            import_blocks.append(import_block)
            logger.debug(
                f"Generated import block for EXACT_MATCH resource: "
                f"{abstracted_resource.get('id', 'unknown')}"
            )
        else:
            logger.warning(
                f"Could not create import block for EXACT_MATCH resource "
                f"{abstracted_resource.get('id', 'unknown')} "
                f"(type {abstracted_resource.get('type')} not in type mapping), "
                f"will emit resource only"
            )

        # Bug #23 fix: ALWAYS emit resource definition for EXACT_MATCH
        # (moved outside if block - emit even if import block creation failed)
        resources_needing_emission.append(abstracted_resource)
        logger.debug(
            f"Added EXACT_MATCH resource to emission list: "
            f"{abstracted_resource.get('id', 'unknown')}"
        )

    def _handle_drifted(
        self,
        abstracted_resource: Dict[str, Any],
        target_resource: Any,
        import_blocks: List[ImportBlock],
        resources_needing_emission: List[Dict[str, Any]],
    ) -> None:
        """
        Handle DRIFTED classification.

        Generates import block AND includes in resource emission.

        Args:
            abstracted_resource: Resource from abstracted graph
            target_resource: Resource from target scan
            import_blocks: List to append import block to
            resources_needing_emission: List to append resource to
        """
        import_block = self._create_import_block(abstracted_resource, target_resource)

        if import_block:
            import_blocks.append(import_block)
            resources_needing_emission.append(abstracted_resource)
            logger.debug(
                f"Generated import block and resource emission for DRIFTED resource: "
                f"{abstracted_resource.get('id', 'unknown')}"
            )
        else:
            # If import block creation failed, still emit the resource
            resources_needing_emission.append(abstracted_resource)
            logger.warning(
                f"Could not create import block for DRIFTED resource "
                f"{abstracted_resource.get('id', 'unknown')}, will emit resource only"
            )

    def _handle_new(
        self,
        abstracted_resource: Dict[str, Any],
        resources_needing_emission: List[Dict[str, Any]],
    ) -> None:
        """
        Handle NEW classification.

        No import block needed, include in resource emission.

        Args:
            abstracted_resource: Resource from abstracted graph
            resources_needing_emission: List to append resource to
        """
        resources_needing_emission.append(abstracted_resource)
        logger.debug(
            f"Resource marked for emission (NEW): "
            f"{abstracted_resource.get('id', 'unknown')}"
        )

    def _handle_orphaned(self, abstracted_resource: Dict[str, Any]) -> None:
        """
        Handle ORPHANED classification.

        Logs warning, no blocks generated.

        Args:
            abstracted_resource: Resource from abstracted graph (pseudo-resource)
        """
        logger.warning(
            f"Orphaned resource detected in target tenant but not in abstracted graph: "
            f"{abstracted_resource.get('id', 'unknown')} "
            f"(type: {abstracted_resource.get('type', 'unknown')}). "
            "User should decide whether to keep or remove this resource."
        )

    def _create_import_block(
        self,
        abstracted_resource: Dict[str, Any],
        target_resource: Any,
    ) -> Optional[ImportBlock]:
        """
        Create an import block for a resource.

        Args:
            abstracted_resource: Resource from abstracted graph
            target_resource: Resource from target scan

        Returns:
            ImportBlock if successful, None if creation failed
        """
        # Extract resource details
        resource_type = abstracted_resource.get("type")
        resource_name = abstracted_resource.get("name")
        target_resource_id = target_resource.id if target_resource else None

        # Validate required fields
        if not resource_type:
            logger.warning(
                f"Cannot create import block: missing resource type for "
                f"{abstracted_resource.get('id', 'unknown')}"
            )
            return None

        if not resource_name:
            logger.warning(
                f"Cannot create import block: missing resource name for "
                f"{abstracted_resource.get('id', 'unknown')}"
            )
            return None

        if not target_resource_id:
            logger.warning(
                f"Cannot create import block: missing target resource ID for "
                f"{abstracted_resource.get('id', 'unknown')}"
            )
            return None

        # Map Azure type to Terraform type
        terraform_type = self._map_azure_to_terraform_type(resource_type)

        if not terraform_type:
            logger.warning(
                f"Unknown Azure resource type '{resource_type}', cannot create import "
                f"block for {abstracted_resource.get('id', 'unknown')}"
            )
            return None

        # Sanitize resource name for Terraform
        terraform_name = self._sanitize_resource_name(resource_name)

        # Build Terraform resource address
        terraform_address = f"{terraform_type}.{terraform_name}"

        # Normalize casing in import ID (fix lowercase provider names from Azure)
        normalized_import_id = self._normalize_import_id_casing(target_resource_id)

        # Create import block
        import_block = ImportBlock(
            to=terraform_address,
            id=normalized_import_id,
        )

        logger.debug(
            f"Created import block: to={terraform_address}, id={normalized_import_id}"
        )

        return import_block

    def _normalize_import_id_casing(self, resource_id: str) -> str:
        """
        Normalize provider casing in Azure resource IDs for Terraform import blocks.

        Azure sometimes returns lowercase provider names (microsoft.insights)
        but Terraform requires proper casing (Microsoft.Insights).

        Args:
            resource_id: Azure resource ID (may have lowercase providers)

        Returns:
            Resource ID with normalized provider casing
        """
        # Common provider casing fixes
        normalized = resource_id
        normalized = re.sub(r'/microsoft\.insights/', '/Microsoft.Insights/', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'/microsoft\.alertsmanagement/', '/Microsoft.AlertsManagement/', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'/microsoft\.network/dnszones/', '/Microsoft.Network/dnsZones/', normalized, flags=re.IGNORECASE)
        normalized = re.sub(r'/microsoft\.operationalinsights/', '/Microsoft.OperationalInsights/', normalized, flags=re.IGNORECASE)

        return normalized

    def _map_azure_to_terraform_type(self, azure_type: str) -> Optional[str]:
        """
        Map Azure resource type to Terraform resource type.

        Args:
            azure_type: Azure resource type (e.g., Microsoft.Network/virtualNetworks)

        Returns:
            Terraform resource type (e.g., azurerm_virtual_network), or None if unknown
        """
        terraform_type = AZURE_TO_TERRAFORM_TYPE.get(azure_type)

        if not terraform_type:
            logger.debug(
                f"No Terraform type mapping found for Azure type: {azure_type}"
            )
            return None

        return terraform_type

    def _sanitize_resource_name(self, name: str) -> str:
        """
        Sanitize resource name for Terraform.

        Terraform resource names must:
        - Start with a letter or underscore
        - Contain only alphanumeric characters and underscores

        Args:
            name: Original resource name

        Returns:
            Sanitized resource name suitable for Terraform
        """
        if not name:
            return "unnamed_resource"

        # Replace hyphens with underscores
        sanitized = name.replace("-", "_")

        # Remove invalid characters (keep only alphanumeric and underscore)
        sanitized = re.sub(r"[^a-zA-Z0-9_]", "", sanitized)

        # Ensure starts with letter or underscore
        if sanitized and not (sanitized[0].isalpha() or sanitized[0] == "_"):
            sanitized = f"r_{sanitized}"

        # Handle empty result
        if not sanitized:
            sanitized = "unnamed_resource"

        # Log if name was modified
        if sanitized != name:
            logger.debug(f"Sanitized resource name: '{name}' -> '{sanitized}'")

        return sanitized
