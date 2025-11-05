"""Terraform emitter for Infrastructure-as-Code generation.

This module provides Terraform-specific template generation from
tenant graph data.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from azure.identity import DefaultAzureCredential

from ..dependency_analyzer import DependencyAnalyzer
from ..translators import TranslationContext, TranslationCoordinator
from ..translators.private_endpoint_translator import PrivateEndpointTranslator
from ..traverser import TenantGraph
from ..validators import ResourceExistenceValidator
from . import register_emitter
from .base import IaCEmitter
from .private_endpoint_emitter import (
    emit_private_dns_zone,
    emit_private_dns_zone_vnet_link,
    emit_private_endpoint,
)

logger = logging.getLogger(__name__)


class TerraformEmitter(IaCEmitter):
    """Emitter for generating Terraform templates."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        resource_group_prefix: Optional[str] = None,
        target_subscription_id: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        source_subscription_id: Optional[str] = None,
        source_tenant_id: Optional[str] = None,
        identity_mapping: Optional[Dict[str, Any]] = None,
        identity_mapping_file: Optional[str] = None,
        strict_mode: bool = False,
        auto_import_existing: bool = False,
        import_strategy: Optional[str] = None,
        credential: Optional[Any] = None,
    ):
        """Initialize the TerraformEmitter.

        Args:
            config: Optional configuration dictionary
            resource_group_prefix: Optional prefix to add to all resource group names (e.g., "ITERATION15_")
            target_subscription_id: Target subscription ID for cross-tenant translation (opt-in)
            target_tenant_id: Target tenant ID for cross-tenant translation (opt-in)
            source_subscription_id: Source subscription ID (auto-detected if not provided)
            source_tenant_id: Source tenant ID (auto-detected if not provided)
            identity_mapping: Identity mapping dictionary for Entra ID translation
            identity_mapping_file: Path to identity mapping JSON file
            strict_mode: If True, fail on missing mappings. If False, warn.
            auto_import_existing: If True, generate import blocks for existing resources (Issue #412)
            import_strategy: Strategy for importing ("resource_groups", "all_resources", "selective")
            credential: Azure credential for resource existence validation (Issue #422)
        """
        super().__init__(config)
        self.resource_group_prefix = resource_group_prefix or ""
        # Track NSG associations to emit as separate resources
        # Format: [(subnet_tf_name, nsg_tf_name, subnet_name, nsg_name)]
        self._nsg_associations: List[tuple[str, str, str, str]] = []
        # Track all resource names that will be emitted (for reference validation)
        self._available_resources: Dict[str, set] = {}
        # Track missing resource references for reporting
        self._missing_references: List[Dict[str, str]] = []
        # Translator for cross-subscription resource IDs (initialized in emit())
        self._translator: Optional[PrivateEndpointTranslator] = None

        # Store translation parameters for later initialization
        self.target_subscription_id = target_subscription_id
        self.target_tenant_id = target_tenant_id
        self.source_subscription_id = source_subscription_id
        self.source_tenant_id = source_tenant_id
        self.identity_mapping = identity_mapping
        self.identity_mapping_file = identity_mapping_file
        self.strict_mode = strict_mode

        # Translation coordinator (initialized in emit() when resources are available)
        self._translation_coordinator: Optional[TranslationCoordinator] = None

        # Import configuration (Issue #412, #422)
        self.auto_import_existing = auto_import_existing
        self.import_strategy = import_strategy or "resource_groups"
        self.credential = credential

        # Resource existence validator (Issue #422)
        self._existence_validator: Optional[ResourceExistenceValidator] = None

        # Generation metrics tracking (Issue #413)
        self._resource_count: int = 0
        self._files_created: int = 0

        # Import blocks tracking (Issue #412)
        self._import_blocks_generated: int = 0

    # Azure resource type to Terraform resource type mapping
    AZURE_TO_TERRAFORM_MAPPING: ClassVar[Dict[str, str]] = {
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
        "Microsoft.Compute/disks": "azurerm_managed_disk",
        "Microsoft.Compute/virtualMachines/extensions": "azurerm_virtual_machine_extension",
        "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
        "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
        "Microsoft.Network/subnets": "azurerm_subnet",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Network/bastionHosts": "azurerm_bastion_host",
        "Microsoft.Network/privateEndpoints": "azurerm_private_endpoint",
        "Microsoft.Network/privateDnsZones": "azurerm_private_dns_zone",
        "Microsoft.Network/privateDnsZones/virtualNetworkLinks": "azurerm_private_dns_zone_virtual_network_link",
        # Note: Microsoft.Web/sites mapping handled dynamically in _convert_resource
        "Microsoft.Web/serverFarms": "azurerm_service_plan",
        "Microsoft.Sql/servers": "azurerm_mssql_server",
        "Microsoft.KeyVault/vaults": "azurerm_key_vault",
        "Microsoft.OperationalInsights/workspaces": "azurerm_log_analytics_workspace",
        "microsoft.insights/components": "azurerm_application_insights",
        "microsoft.alertsmanagement/smartDetectorAlertRules": "azurerm_monitor_smart_detector_alert_rule",
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
        # DevTestLab resources
        "microsoft.devtestlab/labs": "azurerm_dev_test_lab",
        "Microsoft.DevTestLab/labs": "azurerm_dev_test_lab",
        "Microsoft.DevTestLab/labs/virtualMachines": "azurerm_dev_test_linux_virtual_machine",
        # Machine Learning and AI resources
        "Microsoft.MachineLearningServices/workspaces": "azurerm_machine_learning_workspace",
        "Microsoft.CognitiveServices/accounts": "azurerm_cognitive_account",
        # Additional resource types found in scan
        "Microsoft.Kusto/clusters": "azurerm_kusto_cluster",
        "Microsoft.EventHub/namespaces": "azurerm_eventhub_namespace",
        "Microsoft.Network/networkWatchers": "azurerm_network_watcher",
        "Microsoft.ManagedIdentity/userAssignedIdentities": "azurerm_user_assigned_identity",
        "Microsoft.Insights/dataCollectionRules": "azurerm_monitor_data_collection_rule",
        "microsoft.insights/dataCollectionRules": "azurerm_monitor_data_collection_rule",  # Lowercase variant
        "Microsoft.Insights/dataCollectionEndpoints": "azurerm_monitor_data_collection_endpoint",
        "Microsoft.OperationsManagement/solutions": "azurerm_log_analytics_solution",
        "Microsoft.Automation/automationAccounts": "azurerm_automation_account",
        # Additional resource types found in full tenant scan
        "microsoft.insights/actiongroups": "azurerm_monitor_action_group",
        "Microsoft.Insights/actionGroups": "azurerm_monitor_action_group",
        "Microsoft.Search/searchServices": "azurerm_search_service",
        "microsoft.operationalInsights/querypacks": "azurerm_log_analytics_query_pack",
        "Microsoft.OperationalInsights/queryPacks": "azurerm_log_analytics_query_pack",
        "Microsoft.Compute/sshPublicKeys": "azurerm_ssh_public_key",
        "Microsoft.DevTestLab/schedules": "azurerm_dev_test_schedule",
        # Microsoft.SecurityCopilot/capacities - No Terraform support yet, will be skipped
        "Microsoft.Automation/automationAccounts/runbooks": "azurerm_automation_runbook",
        # Microsoft.Resources/templateSpecs - These are template metadata, not deployments - will be skipped
        # Microsoft.Resources/templateSpecs/versions - Child resources - will be skipped
        # Microsoft.MachineLearningServices/workspaces/serverlessEndpoints - No direct Terraform equivalent yet, will be skipped
        # Azure AD / Entra ID / Microsoft Graph resource mappings
        "Microsoft.AAD/User": "azuread_user",
        "Microsoft.AAD/Group": "azuread_group",
        "Microsoft.AAD/ServicePrincipal": "azuread_service_principal",
        "Microsoft.AAD/Application": "azuread_application",
        "Microsoft.Graph/users": "azuread_user",
        "Microsoft.Graph/groups": "azuread_group",
        "Microsoft.Graph/servicePrincipals": "azuread_service_principal",
        "Microsoft.Graph/applications": "azuread_application",
        "Microsoft.ManagedIdentity/managedIdentities": "azurerm_user_assigned_identity",
        # Neo4j label-based mappings for Entra ID
        "User": "azuread_user",
        "Group": "azuread_group",
        "ServicePrincipal": "azuread_service_principal",
        "Application": "azuread_application",
        # Role-Based Access Control (RBAC)
        "Microsoft.Authorization/roleAssignments": "azurerm_role_assignment",
        "Microsoft.Authorization/roleDefinitions": "azurerm_role_definition",
    }

    def _extract_resource_groups(
        self, resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract unique resource groups from all resources.

        Returns list of RG resource dictionaries with properties:
        - id: RG azure resource ID
        - name: RG name (with prefix applied)
        - location: Azure region
        - type: "Microsoft.Resources/resourceGroups"
        - _original_rg_name: Original RG name before prefix (for mapping)
        """
        rg_map = {}
        for resource in resources:
            # Try both field names (resource_group and resourceGroup)
            rg_name = resource.get("resource_group") or resource.get("resourceGroup")
            if rg_name and rg_name not in rg_map:
                # APPLY PREFIX HERE
                prefixed_name = self._apply_rg_prefix(rg_name)

                # Extract location from first resource in this RG
                location = resource.get("location", "westus2")
                subscription = resource.get("subscription_id") or resource.get(
                    "subscriptionId", ""
                )

                rg_map[rg_name] = {
                    "id": f"/subscriptions/{subscription}/resourceGroups/{prefixed_name}",
                    "name": prefixed_name,  # Prefixed name
                    "location": location,
                    "type": "Microsoft.Resources/resourceGroups",
                    "subscriptionId": subscription,
                    "subscription_id": subscription,
                    "resourceGroup": prefixed_name,  # Prefixed
                    "resource_group": prefixed_name,  # Prefixed
                    "_original_rg_name": rg_name,  # Track original for mapping
                }

        return list(rg_map.values())

    def emit(
        self,
        graph: TenantGraph,
        out_dir: Path,
        domain_name: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> List[Path]:
        """Generate Terraform template from tenant graph."""
        # If a domain name is specified, set it for all user account entities
        if domain_name:
            for resource in graph.resources:
                if resource.get("type", "").lower() in (
                    "user",
                    "aaduser",
                    "microsoft.aad/user",
                ):
                    base_name = resource.get("name", "user")
                    base_name = base_name.split("@")[0]
                    resource["userPrincipalName"] = f"{base_name}@{domain_name}"
                    resource["email"] = f"{base_name}@{domain_name}"

        logger.info(f"Generating Terraform templates to {out_dir}")

        # Ensure output directory exists
        out_dir.mkdir(parents=True, exist_ok=True)

        # Check if we have any Azure AD resources
        has_azuread_resources = any(
            resource.get("type", "").startswith("Microsoft.AAD/")
            or resource.get("type", "").startswith("Microsoft.Graph/")
            or resource.get("type", "").lower()
            in ("user", "aaduser", "group", "aadgroup", "serviceprincipal")
            for resource in graph.resources
        )

        # Build Terraform JSON structure
        terraform_config: Dict[str, Any] = {
            "terraform": {
                "required_providers": {
                    "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"},
                    "random": {"source": "hashicorp/random", "version": ">=3.1"},
                    "tls": {"source": "hashicorp/tls", "version": ">=4.0"},
                }
            },
            "provider": {
                "azurerm": {
                    "features": {},
                    "resource_provider_registrations": "none",
                    "subscription_id": "${var.subscription_id}",
                }
            },
            "variable": {
                "subscription_id": {
                    "description": "Azure subscription ID for deployment",
                    "type": "string",
                    "default": subscription_id or "",
                }
            },
            "resource": {},
        }

        # Add Azure AD provider if needed
        if has_azuread_resources:
            # Add azuread to required providers
            terraform_config["terraform"]["required_providers"]["azuread"] = {
                "source": "hashicorp/azuread",
                "version": ">=2.0",
            }
            # Convert provider to list format for multiple providers
            terraform_config["provider"] = [
                {
                    "azurerm": {
                        "features": {},
                        "subscription_id": "${var.subscription_id}",
                    }
                },
                {"azuread": {}},
            ]

        # Clear NSG associations and tracking from previous runs
        self._nsg_associations = []
        self._available_resources = {}
        self._missing_references = []
        # Track available subnets separately (needs VNet-scoped names)
        self._available_subnets = set()

        # First pass: Build index of available resources
        logger.info("Building resource index for reference validation")
        for resource in graph.resources:
            azure_type = resource.get("type", "")
            resource_name = resource.get("name", "")

            # Handle simple type names for Azure AD resources
            if azure_type.lower() in ("user", "aaduser"):
                azure_type = "Microsoft.Graph/users"
            elif azure_type.lower() in ("group", "aadgroup", "identitygroup"):
                azure_type = "Microsoft.Graph/groups"
            elif azure_type.lower() == "serviceprincipal":
                azure_type = "Microsoft.Graph/servicePrincipals"
            elif azure_type.lower() == "managedidentity":
                azure_type = "Microsoft.ManagedIdentity/managedIdentities"

            # Get Terraform resource type (with dynamic handling for App Services)
            if azure_type == "Microsoft.Web/sites":
                terraform_type = self._get_app_service_terraform_type(resource)
            else:
                terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(azure_type)
            if terraform_type:
                # Skip NICs without ip_configurations - they will be skipped during generation
                if azure_type == "Microsoft.Network/networkInterfaces":
                    properties = self._parse_properties(resource)
                    ip_configs = properties.get("ipConfigurations", [])
                    if not ip_configs:
                        logger.debug(
                            f"Excluding NIC '{resource_name}' from resource index - "
                            "missing ip_configurations (will be skipped during generation)"
                        )
                        continue

                if terraform_type not in self._available_resources:
                    self._available_resources[terraform_type] = set()
                safe_name = self._sanitize_terraform_name(resource_name)
                self._available_resources[terraform_type].add(safe_name)

                # For subnets, also track VNet-scoped names
                if azure_type == "Microsoft.Network/subnets":
                    subnet_id = resource.get("id", "")
                    vnet_name = self._extract_resource_name_from_id(
                        subnet_id, "virtualNetworks"
                    )
                    if vnet_name != "unknown" and "/subnets/" in subnet_id:
                        vnet_name_safe = self._sanitize_terraform_name(vnet_name)
                        subnet_name_safe = safe_name
                        scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"
                        self._available_subnets.add(scoped_subnet_name)

            # Also track subnets from VNet properties (inline subnets)
            if azure_type == "Microsoft.Network/virtualNetworks":
                properties = self._parse_properties(resource)
                subnets = properties.get("subnets", [])
                vnet_safe_name = self._sanitize_terraform_name(resource_name)
                for subnet in subnets:
                    subnet_name = subnet.get("name")
                    if subnet_name:
                        subnet_safe_name = self._sanitize_terraform_name(subnet_name)
                        scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"
                        self._available_subnets.add(scoped_subnet_name)

        logger.debug(
            f"Resource index built: {sum(len(v) for v in self._available_resources.values())} resources tracked"
        )
        logger.debug(
            f"Subnet index built: {len(self._available_subnets)} subnets tracked"
        )

        # Initialize translator if target subscription differs from source
        source_subscription_id = self._extract_source_subscription(graph.resources)
        if (
            source_subscription_id
            and subscription_id
            and source_subscription_id != subscription_id
        ):
            logger.info(
                f"Initializing translator for cross-subscription deployment: "
                f"source={source_subscription_id}, target={subscription_id}"
            )
            # Convert _available_resources (Dict[str, set]) to Dict[str, Dict[str, Any]]
            # format expected by translator
            resources_dict: Dict[str, Dict[str, Any]] = {}
            for resource_type, resource_names in self._available_resources.items():
                resources_dict[resource_type] = {name: {} for name in resource_names}

            self._translator = PrivateEndpointTranslator(
                source_subscription_id=source_subscription_id,
                target_subscription_id=subscription_id,
                available_resources=resources_dict,
            )
        else:
            self._translator = None
            if source_subscription_id and subscription_id:
                logger.debug(
                    f"No translator needed - source and target subscriptions match: {subscription_id}"
                )
            else:
                logger.debug(
                    f"No translator needed - source_sub={source_subscription_id}, target_sub={subscription_id}"
                )

        # Extract and generate resource group resources
        logger.info("Extracting resource groups from discovered resources")
        rg_resources = self._extract_resource_groups(graph.resources)
        logger.info(f"Found {len(rg_resources)} unique resource groups")

        # Build RG name mapping (original -> prefixed) for updating resource references
        rg_name_mapping = {}
        if self.resource_group_prefix:
            for rg_resource in rg_resources:
                original_rg = rg_resource.get("_original_rg_name")
                prefixed_rg = rg_resource.get("name")
                if original_rg and prefixed_rg:
                    rg_name_mapping[original_rg] = prefixed_rg

            logger.info(f"Resource group prefix: '{self.resource_group_prefix}'")
            logger.info(f"Will transform {len(rg_name_mapping)} resource group names")

            # Apply RG name transform to all resources
            for resource in graph.resources:
                # Update resource_group field
                original_rg = resource.get("resource_group") or resource.get(
                    "resourceGroup"
                )
                if original_rg in rg_name_mapping:
                    prefixed_rg = rg_name_mapping[original_rg]
                    resource["resource_group"] = prefixed_rg
                    resource["resourceGroup"] = prefixed_rg

                # Update resource IDs containing RG names
                resource_id = resource.get("id", "")
                if "/resourceGroups/" in resource_id:
                    # Extract and replace RG name in ID
                    parts = resource_id.split("/resourceGroups/")
                    if len(parts) == 2:
                        after_rg = parts[1].split("/", 1)
                        original_rg_in_id = after_rg[0]
                        if original_rg_in_id in rg_name_mapping:
                            prefixed_rg_in_id = rg_name_mapping[original_rg_in_id]
                            rest_of_id = after_rg[1] if len(after_rg) > 1 else ""
                            resource["id"] = (
                                f"{parts[0]}/resourceGroups/{prefixed_rg_in_id}"
                                f"{'/' + rest_of_id if rest_of_id else ''}"
                            )

        # Add RG resources to the available resources index
        for rg_resource in rg_resources:
            rg_name_sanitized = self._sanitize_terraform_name(rg_resource["name"])
            if "azurerm_resource_group" not in self._available_resources:
                self._available_resources["azurerm_resource_group"] = set()
            self._available_resources["azurerm_resource_group"].add(rg_name_sanitized)

        # Prepend RG resources to the resource list for dependency analysis
        all_resources = rg_resources + graph.resources

        # Initialize and run TranslationCoordinator if cross-tenant translation is enabled
        # This is opt-in behavior - only runs if target_subscription_id or target_tenant_id is provided
        if self.target_subscription_id or self.target_tenant_id:
            logger.info("=" * 70)
            logger.info("Cross-tenant translation enabled")
            logger.info("=" * 70)

            # Extract source subscription ID from resources if not provided
            detected_source_subscription = self._extract_source_subscription(
                all_resources
            )
            final_source_subscription = (
                self.source_subscription_id or detected_source_subscription
            )

            # Convert _available_resources (Dict[str, set]) to Dict[str, Dict[str, Any]]
            # format expected by TranslationContext
            resources_dict: Dict[str, Dict[str, Any]] = {}
            for resource_type, resource_names in self._available_resources.items():
                resources_dict[resource_type] = {name: {} for name in resource_names}

            # Create TranslationContext
            translation_context = TranslationContext(
                source_subscription_id=final_source_subscription,
                target_subscription_id=self.target_subscription_id or "",
                source_tenant_id=self.source_tenant_id,
                target_tenant_id=self.target_tenant_id,
                available_resources=resources_dict,
                identity_mapping=self.identity_mapping,
                identity_mapping_file=self.identity_mapping_file,
                strict_mode=self.strict_mode,
            )

            # Initialize TranslationCoordinator
            logger.info(
                f"Source Subscription: {final_source_subscription or 'Not specified'}"
            )
            logger.info(
                f"Target Subscription: {self.target_subscription_id or 'Not specified'}"
            )
            logger.info(f"Source Tenant: {self.source_tenant_id or 'Not specified'}")
            logger.info(f"Target Tenant: {self.target_tenant_id or 'Not specified'}")
            logger.info(f"Strict Mode: {self.strict_mode}")
            logger.info("=" * 70)

            self._translation_coordinator = TranslationCoordinator(translation_context)

            # Translate all resources
            logger.info(f"Translating {len(all_resources)} resources...")
            try:
                translated_resources = (
                    self._translation_coordinator.translate_resources(all_resources)
                )
                all_resources = translated_resources
                logger.info("Translation complete!")
            except Exception as e:
                logger.error(
                    f"Translation failed with error: {e}. Continuing with untranslated resources.",
                    exc_info=True,
                )
                # Continue with untranslated resources (graceful degradation)

        # Analyze dependencies and sort resources by tier
        logger.info("Analyzing resource dependencies and calculating tiers")
        analyzer = DependencyAnalyzer()
        resource_dependencies = analyzer.analyze(all_resources)

        # Second pass: Process resources with validation (sorted by tier)
        for resource_dep in resource_dependencies:
            resource = resource_dep.resource
            terraform_resource = self._convert_resource(resource, terraform_config)
            if terraform_resource:
                resource_type, resource_name, resource_config = terraform_resource

                # Add depends_on if resource has dependencies
                if resource_dep.depends_on:
                    resource_config["depends_on"] = sorted(resource_dep.depends_on)
                    logger.debug(
                        f"Added dependencies for {resource_type}.{resource_name}: "
                        f"{resource_dep.depends_on}"
                    )

                if resource_type not in terraform_config["resource"]:
                    terraform_config["resource"][resource_type] = {}

                terraform_config["resource"][resource_type][resource_name] = (
                    resource_config
                )
                # Track resource count for generation report (Issue #413)
                self._resource_count += 1

        # Emit NSG association resources after all resources are processed
        if self._nsg_associations:
            if (
                "azurerm_subnet_network_security_group_association"
                not in terraform_config["resource"]
            ):
                terraform_config["resource"][
                    "azurerm_subnet_network_security_group_association"
                ] = {}

            for (
                subnet_tf_name,
                nsg_tf_name,
                subnet_name,
                nsg_name,
            ) in self._nsg_associations:
                # Association resource name: subnet_name + "_nsg_association"
                assoc_name = f"{subnet_tf_name}_nsg_association"
                terraform_config["resource"][
                    "azurerm_subnet_network_security_group_association"
                ][assoc_name] = {
                    "subnet_id": f"${{azurerm_subnet.{subnet_tf_name}.id}}",
                    "network_security_group_id": f"${{azurerm_network_security_group.{nsg_tf_name}.id}}",
                }
                # Track NSG association resource for generation report (Issue #413)
                self._resource_count += 1
                logger.debug(
                    f"Generated NSG association: {assoc_name} (Subnet: {subnet_name}, NSG: {nsg_name})"
                )

        # Generate import blocks if requested (Issue #412)
        if self.auto_import_existing:
            import_blocks = self._generate_import_blocks(
                terraform_config, graph.resources
            )
            if import_blocks:
                terraform_config["import"] = import_blocks
                self._import_blocks_generated = len(import_blocks)
                logger.info(f"Generated {len(import_blocks)} import blocks")

        # Write main.tf.json
        output_file = out_dir / "main.tf.json"
        with open(output_file, "w") as f:
            json.dump(terraform_config, f, indent=2)
        # Track file creation for generation report (Issue #413)
        self._files_created += 1

        # Report summary of missing references
        if self._missing_references:
            # Separate by type
            nic_refs = [
                r
                for r in self._missing_references
                if r.get("resource_type") == "network_interface"
            ]
            subnet_refs = [
                r
                for r in self._missing_references
                if r.get("resource_type") == "subnet"
            ]

            logger.warning(
                f"\n{'=' * 80}\n"
                f"MISSING RESOURCE REFERENCES DETECTED: {len(self._missing_references)} issue(s)\n"
                f"{'=' * 80}"
            )

            if nic_refs:
                logger.warning(
                    f"\nMissing Network Interface References ({len(nic_refs)} issues):"
                )
                for ref in nic_refs:
                    logger.warning(
                        f"\n  VM '{ref['vm_name']}' references missing NIC:\n"
                        f"    Missing NIC: {ref['missing_resource_name']}\n"
                        f"    Azure ID: {ref['missing_resource_id']}\n"
                        f"    VM ID: {ref['vm_id']}"
                    )

            if subnet_refs:
                logger.warning(
                    f"\nMissing Subnet References ({len(subnet_refs)} issues):"
                )
                # Group by VNet to make it easier to understand
                subnets_by_vnet = {}
                for ref in subnet_refs:
                    vnet = ref.get("missing_vnet_name", "unknown")
                    if vnet not in subnets_by_vnet:
                        subnets_by_vnet[vnet] = []
                    subnets_by_vnet[vnet].append(ref)

                for vnet, refs in subnets_by_vnet.items():
                    logger.warning(
                        f"\n  VNet '{vnet}' (referenced by {len(refs)} resource(s)):"
                    )
                    # Show first subnet details
                    first_ref = refs[0]
                    logger.warning(
                        f"    Missing subnet: {first_ref['missing_resource_name']}\n"
                        f"    Expected Terraform name: {first_ref['expected_terraform_name']}\n"
                        f"    Azure ID: {first_ref['missing_resource_id']}"
                    )
                    # List all resources referencing this subnet
                    logger.warning("    Resources referencing this subnet:")
                    for ref in refs[:10]:  # Limit to first 10
                        logger.warning(f"      - {ref['resource_name']}")
                    if len(refs) > 10:
                        logger.warning(f"      ... and {len(refs) - 10} more")

            logger.warning(
                f"\n{'=' * 80}\n"
                f"These resources exist in resource properties but were not discovered/stored in Neo4j.\n"
                f"This may indicate:\n"
                f"  1. Parent resources (VNets) in different resource groups weren't fully discovered\n"
                f"  2. Discovery service filtered these resources\n"
                f"  3. Resources were deleted after dependent resources were created\n"
                f"  4. Subnet extraction rule skipped subnets without address prefixes\n"
                f"{'=' * 80}\n"
            )

        # Generate and save translation report if translation was performed
        if self._translation_coordinator:
            logger.info("=" * 70)
            logger.info("Generating translation report...")
            logger.info("=" * 70)

            try:
                # Save human-readable text report
                text_report_path = out_dir / "translation_report.txt"
                self._translation_coordinator.save_translation_report(
                    str(text_report_path), format="text"
                )
                logger.info(f"Translation report (text) saved to: {text_report_path}")

                # Save machine-readable JSON report
                json_report_path = out_dir / "translation_report.json"
                self._translation_coordinator.save_translation_report(
                    str(json_report_path), format="json"
                )
                logger.info(f"Translation report (JSON) saved to: {json_report_path}")

                # Print summary to console
                formatted_report = (
                    self._translation_coordinator.format_translation_report()
                )
                print(formatted_report)

                # Log translation statistics
                stats = self._translation_coordinator.get_translation_statistics()
                logger.info(
                    f"Translation statistics: {stats['resources_processed']} resources processed, "
                    f"{stats['resources_translated']} translated, "
                    f"{stats['total_warnings']} warnings, "
                    f"{stats['total_errors']} errors"
                )

            except Exception as e:
                logger.error(
                    f"Failed to generate translation report: {e}", exc_info=True
                )
                # Don't fail the entire generation if report generation fails

        logger.info(
            f"Generated Terraform template with {len(graph.resources)} resources"
        )
        return [output_file]

    async def emit_template(
        self, tenant_graph: TenantGraph, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate Terraform template from tenant graph (legacy method).

        Args:
            tenant_graph: Input tenant graph data
            output_path: Optional output file path

        Returns:
            Dictionary containing generated Terraform template data
        """
        # Use the new emit method for actual implementation
        if output_path:
            out_dir = Path(output_path)
        else:
            out_dir = Path("./terraform_output")

        written_files = self.emit(tenant_graph, out_dir)

        return {
            "files_written": [str(f) for f in written_files],
            "resource_count": len(tenant_graph.resources),
        }

    def _generate_import_blocks(
        self, terraform_config: Dict[str, Any], resources: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate Terraform 1.5+ import blocks for existing resources (Issue #412, #422).

        With Issue #422 enhancements:
        - Checks resource existence before generating import blocks
        - Uses Azure SDK to verify resources actually exist in target
        - Caches existence checks to minimize API calls
        - Graceful error handling for transient failures

        Args:
            terraform_config: The generated Terraform configuration
            resources: Original resources from graph

        Returns:
            List of import blocks in Terraform 1.5+ format (only for existing resources)
        """
        import_blocks = []

        # Get subscription ID for validation
        subscription_id = self.target_subscription_id or self.source_subscription_id
        if not subscription_id:
            logger.warning(
                "Cannot validate resource existence: no subscription ID available"
            )
            # Fall back to old behavior (no validation)
            return self._generate_import_blocks_no_validation(terraform_config)

        # Initialize existence validator if needed (Issue #422)
        if self._existence_validator is None:
            credential = self.credential or DefaultAzureCredential()
            self._existence_validator = ResourceExistenceValidator(
                subscription_id=subscription_id, credential=credential
            )
            logger.info(
                f"Initialized resource existence validator for subscription {subscription_id}"
            )

        # Get all resource groups from terraform config
        tf_resources = terraform_config.get("resource", {})
        resource_groups = tf_resources.get("azurerm_resource_group", {})

        if self.import_strategy == "resource_groups":
            # Import only resource groups (with existence validation)
            candidate_imports = []

            for rg_tf_name, rg_config in resource_groups.items():
                rg_name = rg_config.get("name")
                rg_location = rg_config.get("location")
                if rg_name and rg_location:
                    # Build Azure resource ID
                    azure_id = (
                        f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"
                    )
                    candidate_imports.append(
                        {
                            "to": f"azurerm_resource_group.{rg_tf_name}",
                            "id": azure_id,
                            "name": rg_name,
                        }
                    )

            # Batch validate existence (Issue #422)
            if candidate_imports:
                logger.info(
                    f"Validating existence of {len(candidate_imports)} resource groups..."
                )
                resource_ids = [imp["id"] for imp in candidate_imports]
                existence_results = self._existence_validator.batch_check_resources(
                    resource_ids
                )

                # Filter to only existing resources
                for candidate in candidate_imports:
                    result = existence_results.get(candidate["id"])
                    if result and result.exists:
                        import_blocks.append(
                            {"to": candidate["to"], "id": candidate["id"]}
                        )
                        logger.debug(
                            f"✓ Resource exists: {candidate['name']} (cached: {result.cached})"
                        )
                    else:
                        error_msg = (
                            f" (error: {result.error})"
                            if result and result.error
                            else ""
                        )
                        logger.warning(
                            f"✗ Resource does not exist, skipping import: {candidate['name']}{error_msg}"
                        )

        elif self.import_strategy == "all_resources":
            # Import all resources (aggressive strategy)
            # TODO: Implement full resource ID construction for all resource types
            logger.warning(
                "all_resources strategy with existence validation not yet implemented"
            )

        # Log cache statistics
        if self._existence_validator:
            cache_stats = self._existence_validator.get_cache_stats()
            logger.info(
                f"Existence validation cache: {cache_stats['valid']} valid, "
                f"{cache_stats['expired']} expired entries"
            )

        validated_count = len(import_blocks)
        logger.info(
            f"Import strategy '{self.import_strategy}' generated {validated_count} "
            f"validated import blocks (existence-checked)"
        )
        return import_blocks

    def _generate_import_blocks_no_validation(
        self, terraform_config: Dict[str, Any]
    ) -> List[Dict[str, str]]:
        """Generate import blocks without existence validation (fallback).

        Used when subscription ID is not available for validation.

        Args:
            terraform_config: The generated Terraform configuration

        Returns:
            List of import blocks without validation
        """
        import_blocks = []
        tf_resources = terraform_config.get("resource", {})
        resource_groups = tf_resources.get("azurerm_resource_group", {})

        if self.import_strategy == "resource_groups":
            subscription_id = self.target_subscription_id or self.source_subscription_id
            for rg_tf_name, rg_config in resource_groups.items():
                rg_name = rg_config.get("name")
                if rg_name and subscription_id:
                    azure_id = (
                        f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}"
                    )
                    import_blocks.append(
                        {
                            "to": f"azurerm_resource_group.{rg_tf_name}",
                            "id": azure_id,
                        }
                    )

        logger.warning(
            f"Generated {len(import_blocks)} import blocks WITHOUT existence validation"
        )
        return import_blocks

    def _parse_tags(self, tags: Any, resource_name: str) -> Optional[Dict[str, str]]:
        """Parse and validate resource tags from Neo4j (JSON string or dict)."""
        if not tags:
            return None

        if isinstance(tags, str):
            try:
                parsed = json.loads(tags)
                return parsed if isinstance(parsed, dict) and parsed else None
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid tags JSON for '{resource_name}': {str(tags)[:100]} ({e})"
                )
                return None

        if isinstance(tags, dict):
            return tags if tags else None

        logger.warning(f"Unexpected tags type for '{resource_name}': {type(tags)}")
        return None

    def _convert_resource(
        self, resource: Dict[str, Any], terraform_config: Dict[str, Any]
    ) -> Optional[tuple[str, str, Dict[str, Any]]]:
        """Convert Azure resource to Terraform resource.

        Args:
            resource: Azure resource data
            terraform_config: The main Terraform configuration dict to add helper resources to

        Returns:
            Tuple of (terraform_type, resource_name, resource_config) or None
        """
        azure_type = resource.get("type", "")
        resource_name = resource.get("name", "unknown")

        # Handle simple type names for Azure AD resources
        if azure_type.lower() in ("user", "aaduser"):
            azure_type = "Microsoft.Graph/users"
        elif azure_type.lower() in ("group", "aadgroup", "identitygroup"):
            azure_type = "Microsoft.Graph/groups"
        elif azure_type.lower() == "serviceprincipal":
            azure_type = "Microsoft.Graph/servicePrincipals"
        elif azure_type.lower() == "managedidentity":
            azure_type = "Microsoft.ManagedIdentity/managedIdentities"

        # Get Terraform resource type (with dynamic handling for App Services)
        if azure_type == "Microsoft.Web/sites":
            terraform_type = self._get_app_service_terraform_type(resource)
        else:
            terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(azure_type)

        if not terraform_type:
            logger.warning(
                f"Skipping unsupported Azure resource type '{azure_type}' "
                f"for resource '{resource_name}'. Add mapping to AZURE_TO_TERRAFORM_MAPPING."
            )
            return None

        # Sanitize resource name for Terraform
        safe_name = self._sanitize_terraform_name(resource_name)

        # Build basic resource configuration
        # Ensure location is never null - default to eastus if missing
        location = resource.get("location")
        if not location or location.lower() == "none" or location.lower() == "null":
            location = "eastus"

        # Resource groups don't have a resource_group_name field
        if azure_type == "Microsoft.Resources/resourceGroups":
            resource_config = {
                "name": resource_name,
                "location": location,
            }
        # Smart Detector Alert Rules are global and don't have a location field
        elif azure_type == "microsoft.alertsmanagement/smartDetectorAlertRules":
            resource_config = {
                "name": resource_name,
                "resource_group_name": resource.get("resource_group", "default-rg"),
            }
        else:
            resource_config = {
                "name": resource_name,
                "location": location,
                "resource_group_name": resource.get("resource_group", "default-rg"),
            }

        # Add tags if present
        if "tags" in resource:
            parsed_tags = self._parse_tags(resource["tags"], resource_name)
            if parsed_tags:
                resource_config["tags"] = parsed_tags

        # Add type-specific properties to ensure all required fields are present
        if azure_type == "Microsoft.Storage/storageAccounts":
            resource_config.update(
                {
                    "account_tier": resource.get("account_tier", "Standard"),
                    "account_replication_type": resource.get(
                        "account_replication_type", "LRS"
                    ),
                }
            )
        elif azure_type == "Microsoft.Network/virtualNetworks":
            # Parse properties first to extract address space
            properties = self._parse_properties(resource)

            # Extract address space from properties.addressSpace.addressPrefixes
            address_space_obj = properties.get("addressSpace", {})
            address_prefixes = address_space_obj.get("addressPrefixes", [])

            # Fallback 1: Try top-level addressSpace property (stored separately to avoid truncation)
            if not address_prefixes and resource.get("addressSpace"):
                try:
                    # addressSpace is stored as JSON string
                    address_space_str = resource.get("addressSpace")
                    if isinstance(address_space_str, str):
                        address_prefixes = json.loads(address_space_str)
                        logger.debug(
                            f"VNet '{resource_name}' using top-level addressSpace property: {address_prefixes}"
                        )
                    elif isinstance(address_space_str, list):
                        address_prefixes = address_space_str
                        logger.debug(
                            f"VNet '{resource_name}' using top-level addressSpace property: {address_prefixes}"
                        )
                except (json.JSONDecodeError, TypeError) as e:
                    logger.warning(
                        f"Failed to parse top-level addressSpace for VNet '{resource_name}': {e}"
                    )

            # Fallback 2: Use hardcoded default if still not found
            if not address_prefixes:
                address_prefixes = ["10.0.0.0/16"]
                logger.warning(
                    f"VNet '{resource_name}' has no addressSpace in properties or top-level field, "
                    f"using fallback: {address_prefixes}"
                )

            resource_config["address_space"] = address_prefixes

            # Extract and emit subnets from vnet properties

            subnets = properties.get("subnets", [])
            for subnet in subnets:
                subnet_name = subnet.get("name")
                if not subnet_name:
                    continue  # Skip subnets without names

                subnet_props = subnet.get("properties", {})
                # Handle both addressPrefix (singular) and addressPrefixes (array)
                address_prefixes = (
                    [subnet_props.get("addressPrefix")]
                    if subnet_props.get("addressPrefix")
                    else subnet_props.get("addressPrefixes", [])
                )
                if not address_prefixes or not address_prefixes[0]:
                    logger.warning(
                        f"Subnet '{subnet_name}' in vnet '{resource_name}' has no addressPrefix or addressPrefixes, skipping"
                    )
                    continue

                # Use first address prefix for subnet config
                address_prefix = address_prefixes[0]

                # Build VNet-scoped subnet resource name
                # Pattern: {vnet_name}_{subnet_name}
                vnet_safe_name = safe_name  # Already computed: self._sanitize_terraform_name(resource_name)
                subnet_safe_name = self._sanitize_terraform_name(subnet_name)
                scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"

                # Build subnet resource config (name field remains original Azure name)
                subnet_config = {
                    "name": subnet_name,  # Azure resource name (unchanged)
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_safe_name}.name}}",
                    "address_prefixes": [address_prefix],
                }

                # Check for NSG association (store for later emission as separate resource)
                nsg_info = subnet_props.get("networkSecurityGroup", {})
                if nsg_info and "id" in nsg_info:
                    nsg_name = self._extract_resource_name_from_id(
                        nsg_info["id"], "networkSecurityGroups"
                    )
                    if nsg_name != "unknown":
                        nsg_name_safe = self._sanitize_terraform_name(nsg_name)
                        # Store association for later emission
                        self._nsg_associations.append(
                            (scoped_subnet_name, nsg_name_safe, subnet_name, nsg_name)
                        )
                        logger.debug(
                            f"Tracked NSG association for inline subnet: {subnet_name} -> {nsg_name}"
                        )

                # Add to terraform config with scoped key
                if "azurerm_subnet" not in terraform_config["resource"]:
                    terraform_config["resource"]["azurerm_subnet"] = {}

                # Log if overwriting (shouldn't happen with scoped names)
                if scoped_subnet_name in terraform_config["resource"]["azurerm_subnet"]:
                    logger.warning(
                        f"Subnet resource name collision: {scoped_subnet_name} already exists. "
                        f"This indicates identical VNet and subnet names."
                    )

                terraform_config["resource"]["azurerm_subnet"][scoped_subnet_name] = (
                    subnet_config
                )

                logger.debug(
                    f"Generated subnet resource: {scoped_subnet_name} "
                    f"(VNet: {resource_name}, Subnet: {subnet_name})"
                )

        elif azure_type == "Microsoft.Compute/virtualMachines":
            # Validate network interfaces FIRST before creating any resources
            properties = self._parse_properties(resource)
            network_profile = properties.get("networkProfile", {})
            nics = network_profile.get("networkInterfaces", [])

            if nics:
                nic_refs = []
                missing_nics = []
                for nic in nics:
                    nic_id = nic.get("id", "")
                    if nic_id:
                        # Extract NIC name from ID using helper
                        nic_name = self._extract_resource_name_from_id(
                            nic_id, "networkInterfaces"
                        )
                        if nic_name != "unknown":
                            nic_name_safe = self._sanitize_terraform_name(nic_name)

                            # Validate that the NIC resource exists in the graph
                            if self._validate_resource_reference(
                                "azurerm_network_interface", nic_name_safe
                            ):
                                nic_refs.append(
                                    f"${{azurerm_network_interface.{nic_name_safe}.id}}"
                                )
                            else:
                                # Track missing NIC
                                missing_nics.append(
                                    {
                                        "nic_name": nic_name,
                                        "nic_id": nic_id,
                                        "nic_terraform_name": nic_name_safe,
                                    }
                                )
                                self._missing_references.append(
                                    {
                                        "vm_name": resource_name,
                                        "vm_id": resource.get("id", ""),
                                        "resource_type": "network_interface",
                                        "missing_resource_name": nic_name,
                                        "missing_resource_id": nic_id,
                                    }
                                )

                if missing_nics:
                    # Log detailed information about missing NICs
                    for missing_nic in missing_nics:
                        logger.warning(
                            f"Skipping VM '{resource_name}' because NIC '{missing_nic['nic_name']}' was removed\n"
                            f"    Azure ID: {missing_nic['nic_id']}\n"
                            f"    Expected Terraform name: {missing_nic['nic_terraform_name']}"
                        )
                    # Cascade deletion: Skip VM if any NIC is missing
                    logger.warning(
                        f"VM '{resource_name}' references {len(missing_nics)} network interface(s) "
                        f"that were removed: {[n['nic_name'] for n in missing_nics]}"
                    )
                    return None

                if nic_refs:
                    resource_config["network_interface_ids"] = nic_refs
            else:
                logger.warning(
                    f"VM '{resource_name}' has no network interfaces in properties. "
                    "Generated Terraform may be invalid."
                )

            # Generate SSH key pair for VM authentication using Terraform's tls_private_key resource
            ssh_key_resource_name = f"{safe_name}_ssh_key"

            # Add the tls_private_key resource to terraform config
            if "resource" not in terraform_config:
                terraform_config["resource"] = {}
            if "tls_private_key" not in terraform_config["resource"]:
                terraform_config["resource"]["tls_private_key"] = {}

            terraform_config["resource"]["tls_private_key"][ssh_key_resource_name] = {
                "algorithm": "RSA",
                "rsa_bits": 4096,
            }

            # Ensure required VM properties with SSH key authentication
            resource_config.update(
                {
                    "size": resource.get("size", "Standard_B2s"),
                    "admin_username": resource.get("admin_username", "azureuser"),
                    "admin_ssh_key": {
                        "username": resource.get("admin_username", "azureuser"),
                        "public_key": f"${{tls_private_key.{ssh_key_resource_name}.public_key_openssh}}",
                    },
                    "os_disk": {
                        "caching": "ReadWrite",
                        "storage_account_type": "Standard_LRS",
                    },
                    "source_image_reference": {
                        "publisher": "Canonical",
                        "offer": "0001-com-ubuntu-server-jammy",
                        "sku": "22_04-lts",
                        "version": "latest",
                    },
                }
            )
        elif azure_type == "Microsoft.Network/publicIPAddresses":
            resource_config["allocation_method"] = resource.get(
                "allocation_method", "Static"
            )
        elif azure_type == "Microsoft.Network/bastionHosts":
            # Bastion Hosts require IP configuration with subnet and public IP
            properties = self._parse_properties(resource)

            ip_configurations = properties.get("ipConfigurations", [])
            if ip_configurations:
                # Use first IP configuration
                ip_config = ip_configurations[0]
                ip_config_name = ip_config.get("name", "IpConf")
                ip_props = ip_config.get("properties", {})

                # Extract subnet reference
                subnet_info = ip_props.get("subnet", {})
                subnet_id = subnet_info.get("id", "")

                # Use helper method to resolve VNet-scoped subnet reference
                subnet_reference = self._resolve_subnet_reference(
                    subnet_id, resource_name
                )

                # Extract public IP reference
                public_ip_info = ip_props.get("publicIPAddress", {})
                public_ip_id = public_ip_info.get("id", "")
                public_ip_name = self._extract_resource_name_from_id(
                    public_ip_id, "publicIPAddresses"
                )

                # Build IP configuration block (public_ip_address_id is REQUIRED for Bastion Host)
                ip_config_block = {
                    "name": ip_config_name,
                    "subnet_id": subnet_reference,  # Always set (even if placeholder)
                }

                # Add public IP reference - REQUIRED for Bastion Host
                if public_ip_name != "unknown":
                    public_ip_name_safe = self._sanitize_terraform_name(public_ip_name)
                    # Validate that the public IP exists in the graph
                    if self._validate_resource_reference(
                        "azurerm_public_ip", public_ip_name_safe
                    ):
                        ip_config_block["public_ip_address_id"] = (
                            f"${{azurerm_public_ip.{public_ip_name_safe}.id}}"
                        )
                    else:
                        logger.error(
                            f"Bastion Host '{resource_name}' references public IP '{public_ip_name}' "
                            f"that doesn't exist in Neo4j graph. Azure ID: {public_ip_id}"
                        )
                        # Add placeholder to satisfy Terraform syntax
                        ip_config_block["public_ip_address_id"] = (
                            f"${{azurerm_public_ip.{public_ip_name_safe}.id}}"
                        )
                        self._missing_references.append(
                            {
                                "resource_name": resource_name,
                                "resource_type": "public_ip",
                                "missing_resource_name": public_ip_name,
                                "missing_resource_id": public_ip_id,
                            }
                        )
                else:
                    # No public IP found in properties - this is a critical error
                    logger.error(
                        f"Bastion Host '{resource_name}' has no publicIPAddress in ip_configuration properties. "
                        f"Bastion Hosts require a public IP. This resource is missing critical data from Neo4j and will fail validation."
                    )
                    # Skip this bastion host - it cannot be deployed without a public IP
                    return None

                resource_config["ip_configuration"] = ip_config_block

                # Validate reference (warn if placeholder)
                if "unknown" in subnet_reference:
                    logger.warning(
                        f"Bastion Host '{resource_name}' has invalid subnet reference. "
                        f"Generated Terraform may be invalid."
                    )
            else:
                logger.warning(
                    f"Bastion Host '{resource_name}' has no IP configurations in properties. "
                    "Generated Terraform may be invalid."
                )

            # Add SKU if present
            sku = properties.get("sku", {})
            if sku and "name" in sku:
                resource_config["sku"] = sku["name"]

        elif azure_type == "Microsoft.Network/networkSecurityGroups":
            # NSGs don't need additional required properties beyond name, location, and resource_group
            pass
        elif azure_type == "Microsoft.Network/networkInterfaces":
            # NICs require ip_configuration blocks
            # Parse properties field to get ipConfigurations
            properties = self._parse_properties(resource)

            ip_configurations = properties.get("ipConfigurations", [])
            if ip_configurations:
                # Use first IP configuration
                ip_config = ip_configurations[0]
                ip_props = ip_config.get("properties", {})
                subnet_info = ip_props.get("subnet", {})
                subnet_id = subnet_info.get("id", "")

                # Use helper method to resolve VNet-scoped subnet reference
                subnet_reference = self._resolve_subnet_reference(
                    subnet_id, resource_name
                )

                private_ip = ip_props.get("privateIPAddress", "")
                allocation_method = ip_props.get("privateIPAllocationMethod", "Dynamic")

                ip_config_block = {
                    "name": ip_config.get("name", "internal"),
                    "subnet_id": subnet_reference,
                    "private_ip_address_allocation": allocation_method,
                }

                # Add private IP if static allocation
                if allocation_method == "Static" and private_ip:
                    ip_config_block["private_ip_address"] = private_ip

                resource_config["ip_configuration"] = ip_config_block

                # Validate reference (warn if placeholder)
                if "unknown" in subnet_reference:
                    logger.warning(
                        f"NIC '{resource_name}' has invalid subnet reference. "
                        f"Generated Terraform may be invalid."
                    )
            else:
                # NICs without ipConfigurations in properties are missing critical data from Neo4j
                # Skip these NICs entirely - they cannot be deployed without subnet information
                logger.error(
                    f"NIC '{resource_name}' has no ip_configurations in properties. "
                    "This NIC is missing critical subnet configuration data from Neo4j. "
                    "Skipping this NIC as it cannot be deployed without ip_configuration block."
                )
                return None
        elif azure_type == "Microsoft.Network/subnets":
            properties = self._parse_properties(resource)

            # Extract parent VNet name from subnet ID
            subnet_id = resource.get("id", "")
            vnet_name = self._extract_resource_name_from_id(
                subnet_id, "virtualNetworks"
            )

            # Build VNet-scoped resource name
            if vnet_name != "unknown" and "/subnets/" in subnet_id:
                vnet_name_safe = self._sanitize_terraform_name(vnet_name)
                subnet_name_safe = self._sanitize_terraform_name(resource_name)
                # Override safe_name to use scoped naming
                safe_name = f"{vnet_name_safe}_{subnet_name_safe}"

                resource_config = {
                    "name": resource_name,  # Original Azure name
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_name_safe}.name}}",
                }

                logger.debug(
                    f"Generated standalone subnet: {safe_name} "
                    f"(VNet: {vnet_name}, Subnet: {resource_name})"
                )
            else:
                logger.warning(
                    f"Standalone subnet '{resource_name}' has no parent VNet in ID: {subnet_id}. "
                    f"Using fallback naming (may cause collisions)."
                )
                # Fallback to old behavior
                safe_name = self._sanitize_terraform_name(resource_name)
                resource_config = {
                    "name": resource_name,
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": "unknown_vnet",
                }

            # Handle address prefixes with fallback
            address_prefixes = (
                [properties.get("addressPrefix")]
                if properties.get("addressPrefix")
                else properties.get("addressPrefixes", [])
            )
            if not address_prefixes:
                logger.warning(f"Subnet '{resource_name}' has no address prefixes")
                address_prefixes = ["10.0.0.0/24"]
            resource_config["address_prefixes"] = address_prefixes

            # Check for NSG association (store for later emission as separate resource)
            nsg_info = properties.get("networkSecurityGroup", {})
            if nsg_info and "id" in nsg_info:
                nsg_name = self._extract_resource_name_from_id(
                    nsg_info["id"], "networkSecurityGroups"
                )
                if nsg_name != "unknown":
                    nsg_name_safe = self._sanitize_terraform_name(nsg_name)
                    # Store association for later emission
                    self._nsg_associations.append(
                        (safe_name, nsg_name_safe, resource_name, nsg_name)
                    )
                    logger.debug(
                        f"Tracked NSG association for standalone subnet: {resource_name} -> {nsg_name}"
                    )

            # Optional: Service Endpoints
            service_endpoints = properties.get("serviceEndpoints", [])
            if service_endpoints:
                resource_config["service_endpoints"] = [
                    ep["service"] for ep in service_endpoints if "service" in ep
                ]
        elif azure_type == "Microsoft.Web/sites":
            # Modern App Service resources require site_config block
            properties = self._parse_properties(resource)

            # Determine if Linux or Windows based on kind property
            kind = properties.get("kind", "").lower()
            is_linux = "linux" in kind

            # Build site_config block
            site_config = {}
            site_config_props = properties.get("siteConfig", {})

            if is_linux:
                # Linux-specific: linux_fx_version for runtime stack
                if "linuxFxVersion" in site_config_props:
                    site_config["application_stack"] = {
                        "docker_image": site_config_props["linuxFxVersion"]
                    }

            # Extract subscription ID from resource data (multiple fallback sources)
            subscription_id = (
                resource.get("subscription_id")
                or resource.get("subscriptionId")
                or self._extract_subscription_from_resource_id(resource.get("id", ""))
                or "00000000-0000-0000-0000-000000000000"
            )

            # Build service plan ID with proper subscription
            service_plan_id = resource.get("app_service_plan_id")
            if not service_plan_id:
                # Construct default service plan ID with actual subscription
                resource_group = resource.get("resource_group", "default-rg")
                service_plan_id = (
                    f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/"
                    f"providers/Microsoft.Web/serverFarms/default-plan"
                )

            resource_config.update(
                {
                    "service_plan_id": service_plan_id,
                    "site_config": site_config if site_config else {},
                }
            )
        elif azure_type == "Microsoft.Sql/servers":
            # Generate a unique password for each SQL server using Terraform's random_password resource
            password_resource_name = f"{safe_name}_password"

            # Add the random_password resource to terraform config
            if "resource" not in terraform_config:
                terraform_config["resource"] = {}
            if "random_password" not in terraform_config["resource"]:
                terraform_config["resource"]["random_password"] = {}

            terraform_config["resource"]["random_password"][password_resource_name] = {
                "length": 20,
                "special": True,
                "override_special": "!@#$%&*()-_=+[]{}<>:?",
                "min_lower": 1,
                "min_upper": 1,
                "min_numeric": 1,
                "min_special": 1,
            }

            resource_config.update(
                {
                    "version": resource.get("version", "12.0"),
                    "administrator_login": resource.get(
                        "administrator_login", "sqladmin"
                    ),
                    "administrator_login_password": f"${{random_password.{password_resource_name}.result}}",
                }
            )
        elif azure_type == "Microsoft.EventHub/namespaces":
            # EventHub namespaces require sku argument
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Extract sku name, default to Standard if not found
            sku_name = sku.get("name", "Standard") if sku else "Standard"

            resource_config["sku"] = sku_name

            # Optionally add capacity if present in sku
            if sku and "capacity" in sku:
                resource_config["capacity"] = sku["capacity"]

        elif azure_type == "Microsoft.Kusto/clusters":
            # Kusto clusters require sku block
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Extract sku properties, use defaults if not found
            sku_name = (
                sku.get("name", "Dev(No SLA)_Standard_D11_v2")
                if sku
                else "Dev(No SLA)_Standard_D11_v2"
            )
            sku_capacity = sku.get("capacity", 1) if sku else 1

            resource_config["sku"] = {"name": sku_name, "capacity": sku_capacity}

        elif azure_type == "Microsoft.KeyVault/vaults":
            # Extract tenant_id from multiple sources with proper fallback
            # Priority: resource.tenant_id > properties.tenantId > data.current.tenant_id
            properties = self._parse_properties(resource)

            # Try to get tenant_id from resource data
            tenant_id = (
                resource.get("tenant_id")
                or resource.get("tenantId")
                or properties.get("tenantId")
            )

            # If still not found, use Terraform data source to get current tenant_id
            # This ensures we use the actual Azure tenant ID from the environment
            if not tenant_id or tenant_id == "00000000-0000-0000-0000-000000000000":
                # Add data source for current client config if not already present
                if "data" not in terraform_config:
                    terraform_config["data"] = {}
                if "azurerm_client_config" not in terraform_config["data"]:
                    terraform_config["data"]["azurerm_client_config"] = {"current": {}}

                # Use data source reference for tenant_id
                tenant_id = "${data.azurerm_client_config.current.tenant_id}"

            resource_config.update(
                {
                    "tenant_id": tenant_id,
                    "sku_name": resource.get("sku_name", "standard"),
                }
            )
        elif azure_type in ("Microsoft.AAD/User", "Microsoft.Graph/users"):
            # Azure AD User specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "user_principal_name": resource.get(
                    "userPrincipalName", f"{resource_name}@example.com"
                ),
                "mail_nickname": resource.get("mailNickname", resource_name),
            }
            if "password" in resource:
                resource_config["password"] = resource["password"]
        elif azure_type in ("Microsoft.AAD/Group", "Microsoft.Graph/groups"):
            # Azure AD Group specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "security_enabled": resource.get("securityEnabled", True),
            }
            if "description" in resource:
                resource_config["description"] = resource["description"]
        elif azure_type in (
            "Microsoft.AAD/ServicePrincipal",
            "Microsoft.Graph/servicePrincipals",
        ):
            # Azure AD Service Principal specific properties
            resource_config = {
                "application_id": resource.get("applicationId", ""),
            }
            if "displayName" in resource:
                resource_config["display_name"] = resource["displayName"]
        elif azure_type == "Microsoft.ManagedIdentity/managedIdentities":
            # Managed Identity specific properties
            resource_config = {
                "name": resource_name,
                "location": location,
                "resource_group_name": resource.get("resource_group", "default-rg"),
            }
        elif azure_type == "Microsoft.Network/privateEndpoints":
            # Private Endpoint specific properties
            # Ensure _available_subnets exists (for direct _convert_resource calls in tests)
            available_subnets = getattr(self, "_available_subnets", set())
            missing_references = getattr(self, "_missing_references", [])
            translator = getattr(self, "_translator", None)
            resource_config = emit_private_endpoint(
                resource,
                sanitize_name_fn=self._sanitize_terraform_name,
                extract_name_fn=self._extract_resource_name_from_id,
                available_subnets=available_subnets,
                missing_references=missing_references,
                translator=translator,
            )
        elif azure_type == "Microsoft.Network/privateDnsZones":
            # Private DNS Zone specific properties
            resource_config = emit_private_dns_zone(resource)
        elif azure_type == "Microsoft.Network/privateDnsZones/virtualNetworkLinks":
            # Private DNS Zone Virtual Network Link specific properties
            # Need to build set of available VNets for validation
            available_vnets = (
                self._available_resources.get("azurerm_virtual_network", set())
                if self._available_resources
                else set()
            )
            missing_references = getattr(self, "_missing_references", [])
            resource_config = emit_private_dns_zone_vnet_link(
                resource,
                sanitize_name_fn=self._sanitize_terraform_name,
                extract_name_fn=self._extract_resource_name_from_id,
                available_vnets=available_vnets,
                missing_references=missing_references,
            )
            if resource_config is None:
                # Invalid link configuration, skip it
                return None
            # Override safe_name with the link name from the config
            safe_name = resource_config.get("name", safe_name)
        elif azure_type == "Microsoft.Web/serverFarms":
            # App Service Plan (Server Farm) specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Determine OS type from kind property
            kind = properties.get("kind", "").lower()
            os_type = "Linux" if "linux" in kind else "Windows"

            resource_config.update(
                {
                    "os_type": os_type,
                    "sku_name": sku.get("name", "B1"),
                }
            )
        elif azure_type == "Microsoft.Compute/disks":
            # Managed Disk specific properties
            properties = self._parse_properties(resource)

            # Get disk size and storage account type
            disk_size_gb = properties.get("diskSizeGB", 30)
            storage_account_type = properties.get("sku", {}).get("name", "Standard_LRS")

            resource_config.update(
                {
                    "storage_account_type": storage_account_type,
                    "create_option": "Empty",
                    "disk_size_gb": disk_size_gb,
                }
            )
        elif azure_type == "Microsoft.Compute/virtualMachines/extensions":
            # VM Extension specific properties
            properties = self._parse_properties(resource)

            # Extract parent VM name from extension ID
            extension_id = resource.get("id", "")
            vm_name = self._extract_resource_name_from_id(
                extension_id, "virtualMachines"
            )

            if vm_name != "unknown":
                vm_name_safe = self._sanitize_terraform_name(vm_name)

                # Validate that the VM resource exists in the generated Terraform config
                # (not just in _available_resources, which may include VMs that were later skipped)
                vm_exists = False
                for vm_type in [
                    "azurerm_linux_virtual_machine",
                    "azurerm_windows_virtual_machine",
                ]:
                    if (
                        vm_type in terraform_config.get("resource", {})
                        and vm_name_safe in terraform_config["resource"][vm_type]
                    ):
                        vm_exists = True
                        # Use the actual VM type found
                        vm_terraform_type = vm_type
                        break

                if not vm_exists:
                    logger.warning(
                        f"VM Extension '{resource_name}' references VM '{vm_name}' "
                        f"that doesn't exist in the generated Terraform config (may have been skipped due to missing dependencies). Skipping extension."
                    )
                    return None

                # Get extension properties
                publisher = properties.get("publisher", "Microsoft.Azure.Extensions")
                extension_type = properties.get("type", "CustomScript")
                type_handler_version = properties.get("typeHandlerVersion", "2.0")

                # IMPORTANT: VM extension names in Azure can contain "/" (e.g., "VM001/ExtensionName")
                # but Terraform doesn't allow "/" in resource names. Extract just the extension name part.
                extension_name = (
                    resource_name.split("/")[-1]
                    if "/" in resource_name
                    else resource_name
                )

                resource_config = {
                    "name": extension_name,  # Use sanitized name without VM prefix
                    "virtual_machine_id": f"${{{vm_terraform_type}.{vm_name_safe}.id}}",
                    "publisher": publisher,
                    "type": extension_type,
                    "type_handler_version": type_handler_version,
                }

                # Add settings if present
                if "settings" in properties:
                    resource_config["settings"] = json.dumps(properties["settings"])
            else:
                logger.warning(
                    f"VM Extension '{resource_name}' has no parent VM in ID: {extension_id}. Skipping."
                )
                return None
        elif azure_type == "Microsoft.OperationalInsights/workspaces":
            # Log Analytics Workspace specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Get SKU name and normalize to proper case (Azure returns lowercase but Terraform requires PascalCase)
            sku_name = sku.get("name", "PerGB2018")
            # Map lowercase variants to proper Terraform values
            sku_mapping = {
                "pergb2018": "PerGB2018",
                "pernode": "PerNode",
                "premium": "Premium",
                "standalone": "Standalone",
                "standard": "Standard",
                "capacityreservation": "CapacityReservation",
                "lacluster": "LACluster",
                "unlimited": "Unlimited",
            }
            sku_name = sku_mapping.get(sku_name.lower(), sku_name)

            resource_config.update(
                {
                    "sku": sku_name,
                    "retention_in_days": properties.get("retentionInDays", 30),
                }
            )
        elif azure_type == "Microsoft.OperationsManagement/solutions":
            # Log Analytics Solution specific properties
            properties = self._parse_properties(resource)

            # Extract solution name and workspace info
            # Solution name format is typically "SolutionType(WorkspaceName)"
            solution_full_name = resource.get("name", "")
            if "(" in solution_full_name and ")" in solution_full_name:
                solution_type = solution_full_name.split("(")[0]
                workspace_name_from_solution = solution_full_name.split("(")[1].rstrip(
                    ")"
                )
            else:
                solution_type = solution_full_name
                workspace_name_from_solution = "unknown"

            # Get workspace resource ID from properties
            workspace_resource_id = properties.get("workspaceResourceId", "")
            workspace_name = (
                self._extract_resource_name_from_id(workspace_resource_id, "workspaces")
                if workspace_resource_id
                else workspace_name_from_solution
            )
            workspace_name_safe = self._sanitize_terraform_name(workspace_name)

            # Get plan details from properties
            plan = properties.get("plan", {})
            publisher = plan.get("publisher", "Microsoft")
            product = plan.get("product", solution_type)

            # For azurerm_log_analytics_solution, we don't use "name" - instead solution_name, workspace_name, workspace_resource_id
            resource_config = {
                "solution_name": solution_type,
                "resource_group_name": resource.get("resource_group", "unknown"),
                "location": resource.get("location", "westus"),
                "workspace_name": workspace_name,
                "workspace_resource_id": workspace_resource_id
                if workspace_resource_id
                else f"${{azurerm_log_analytics_workspace.{workspace_name_safe}.id}}",
                "plan": {
                    "publisher": publisher,
                    "product": product,
                },
            }
        elif azure_type == "microsoft.insights/components":
            # Application Insights specific properties
            properties = self._parse_properties(resource)

            # Application Insights requires a workspace ID or uses legacy mode
            application_type = properties.get("Application_Type", "web")

            resource_config.update(
                {
                    "application_type": application_type,
                }
            )

            # Try to link to Log Analytics workspace if available
            workspace_resource_id = properties.get("WorkspaceResourceId")
            if workspace_resource_id:
                workspace_name = self._extract_resource_name_from_id(
                    workspace_resource_id, "workspaces"
                )
                if workspace_name != "unknown":
                    workspace_name_safe = self._sanitize_terraform_name(workspace_name)
                    if self._validate_resource_reference(
                        "azurerm_log_analytics_workspace", workspace_name_safe
                    ):
                        resource_config["workspace_id"] = (
                            f"${{azurerm_log_analytics_workspace.{workspace_name_safe}.id}}"
                        )
        elif azure_type == "Microsoft.DevTestLab/labs/virtualMachines":
            # DevTest Lab Virtual Machine specific properties
            properties = self._parse_properties(resource)

            # Extract lab name from the resource name (format: "labname/vmname")
            full_name = resource.get("name", "")
            lab_name = full_name.split("/")[0] if "/" in full_name else "unknown-lab"
            vm_name = full_name.split("/")[1] if "/" in full_name else full_name

            # Get size from properties
            size = properties.get("size", "Standard_B2s")

            # Get username from properties (osProfile or galleryImageReference)
            username = properties.get("userName", "labuser")

            # Get storage type
            storage_type = properties.get("storageType", "Standard")

            # Get subnet info from properties
            lab_subnet_name = properties.get("labSubnetName", "default")

            # Try to get virtual network ID from properties
            lab_virtual_network_id = properties.get("labVirtualNetworkId")
            if not lab_virtual_network_id:
                # Construct it from resource group and lab name
                rg_name = resource.get("resource_group", "unknown-rg")
                subscription_id = resource.get(
                    "subscription_id", "00000000-0000-0000-0000-000000000000"
                )
                lab_virtual_network_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.DevTestLab/labs/{lab_name}/virtualnetworks/{lab_name}Vnet"

            # Get gallery image reference from properties
            gallery_image_ref = properties.get("galleryImageReference", {})

            resource_config.update(
                {
                    "lab_name": lab_name,
                    "size": size,
                    "username": username,
                    "storage_type": storage_type,
                    "lab_subnet_name": lab_subnet_name,
                    "lab_virtual_network_id": lab_virtual_network_id,
                    # SSH key is required
                    "ssh_key": f"var.devtest_vm_ssh_key_{self._sanitize_terraform_name(vm_name)}",
                    # Gallery image reference is required (at least 1 block)
                    "gallery_image_reference": {
                        "offer": gallery_image_ref.get(
                            "offer", "0001-com-ubuntu-server-jammy"
                        ),
                        "publisher": gallery_image_ref.get("publisher", "Canonical"),
                        "sku": gallery_image_ref.get("sku", "22_04-lts-gen2"),
                        "version": gallery_image_ref.get("version", "latest"),
                    },
                }
            )

            # Override name to just be the VM name (not labname/vmname)
            resource_config["name"] = vm_name

        elif azure_type == "microsoft.alertsmanagement/smartDetectorAlertRules":
            # Smart Detector Alert Rule specific properties
            properties = self._parse_properties(resource)

            # Get detector configuration
            detector = properties.get("detector", {})
            detector_id = detector.get("id", "FailureAnomaliesDetector")

            # Get action groups (optional - smart detectors can work without action groups)
            action_groups = properties.get("actionGroups", {})
            action_group_ids = action_groups.get("groupIds", [])

            # Get scope (Application Insights resource IDs)
            scope_resource_ids = properties.get("scope", [])

            # Keep severity in Azure format (Sev0-Sev4) - Terraform expects this format
            severity = properties.get("severity", "Sev3")

            # Get frequency (check interval)
            frequency = properties.get("frequency", "PT1M")

            resource_config.update(
                {
                    "detector_type": detector_id,
                    "scope_resource_ids": scope_resource_ids
                    if scope_resource_ids
                    else [],
                    "severity": severity,  # Keep as "SevN" format
                    "frequency": frequency,
                    "description": properties.get("description", ""),
                    "enabled": properties.get("state", "Enabled") == "Enabled",
                }
            )

            # Add action group block if action groups exist
            # Note: Action group IDs need to be formatted correctly for Terraform
            if action_group_ids:
                # Extract and format action group IDs
                formatted_ids = []
                for ag_id in action_group_ids:
                    # Action group IDs come in various casings from Azure
                    # Terraform requires: /subscriptions/{sid}/resourceGroups/{rg}/providers/microsoft.insights/actionGroups/{name}
                    # Note the capital 'G' in actionGroups
                    parts = ag_id.split("/")
                    if len(parts) >= 9:
                        # Reconstruct with proper casing
                        subscription_id = parts[2]
                        rg_name = parts[4]
                        ag_name = parts[8] if len(parts) > 8 else ""
                        formatted_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/microsoft.insights/actionGroups/{ag_name}"
                        formatted_ids.append(formatted_id)
                        logger.debug(f"Formatted action group ID: {formatted_id}")
                    else:
                        # Use original if can't parse
                        logger.warning(
                            f"Could not parse action group ID (unexpected format): {ag_id}"
                        )

                if formatted_ids:
                    resource_config["action_group"] = {"ids": formatted_ids}
        elif azure_type == "Microsoft.MachineLearningServices/workspaces":
            # Machine Learning Workspace specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Get required resource IDs from properties or construct placeholders
            rg_name = resource.get("resource_group", "unknown-rg")
            subscription_id = resource.get(
                "subscription_id", "00000000-0000-0000-0000-000000000000"
            )

            # Storage account ID (required)
            storage_account_id = properties.get("storageAccount")
            if not storage_account_id:
                # Create placeholder - should be replaced with actual storage account reference
                storage_account_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/mlworkspace{resource_name[:8]}"
            else:
                # Normalize casing in resource ID
                storage_account_id = self._normalize_resource_id(storage_account_id)

            # Key Vault ID (required)
            key_vault_id = properties.get("keyVault")
            if not key_vault_id:
                # Create placeholder
                key_vault_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.KeyVault/vaults/mlworkspace{resource_name[:8]}"
            else:
                # Normalize casing in resource ID (Microsoft.Keyvault -> Microsoft.KeyVault)
                key_vault_id = self._normalize_resource_id(key_vault_id)

            # Application Insights ID (required)
            application_insights_id = properties.get("applicationInsights")
            if not application_insights_id:
                # Create placeholder - note: provider must be Microsoft.Insights (capital M and I)
                application_insights_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.Insights/components/mlworkspace{resource_name[:8]}"
            else:
                # Normalize casing in resource ID (Microsoft.insights -> Microsoft.Insights)
                application_insights_id = self._normalize_resource_id(
                    application_insights_id
                )

            resource_config.update(
                {
                    "sku_name": sku.get("name", "Basic"),
                    "identity": {"type": "SystemAssigned"},
                    "storage_account_id": storage_account_id,
                    "key_vault_id": key_vault_id,
                    "application_insights_id": application_insights_id,
                }
            )
        elif (
            azure_type
            == "Microsoft.MachineLearningServices/workspaces/serverlessEndpoints"
        ):
            # ML Serverless Endpoints mapped to compute instance (closest available)
            properties = self._parse_properties(resource)

            # Extract workspace name from resource name (format: "workspacename/serverlessEndpoints/endpointname")
            full_name = resource.get("name", "")
            parts = full_name.split("/")
            if len(parts) >= 3:
                workspace_name = parts[0]
                endpoint_name = parts[2]
            else:
                workspace_name = "unknown-workspace"
                endpoint_name = full_name

            # Get required properties
            rg_name = resource.get("resource_group", "unknown-rg")
            subscription_id = resource.get(
                "subscription_id", "00000000-0000-0000-0000-000000000000"
            )

            # Construct workspace ID
            machine_learning_workspace_id = f"/subscriptions/{subscription_id}/resourceGroups/{rg_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"

            resource_config.update(
                {
                    "machine_learning_workspace_id": machine_learning_workspace_id,
                    "virtual_machine_size": properties.get("vmSize", "STANDARD_DS3_V2"),
                    # Compute instance expects "name" to be the instance name
                }
            )

            # Override name to just be the endpoint name
            resource_config["name"] = endpoint_name

        elif azure_type in [
            "microsoft.insights/actiongroups",
            "Microsoft.Insights/actionGroups",
        ]:
            # Monitor Action Group specific properties
            properties = self._parse_properties(resource)

            # short_name is required (max 12 characters)
            short_name = properties.get("groupShortName", resource_name[:12])

            resource_config.update(
                {
                    "short_name": short_name,
                }
            )

        elif azure_type == "Microsoft.CognitiveServices/accounts":
            # Cognitive Services Account specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})
            kind = properties.get("kind", "OpenAI")

            resource_config.update(
                {
                    "kind": kind,
                    "sku_name": sku.get("name", "S0"),
                }
            )

            # Add custom_subdomain_name if present
            if properties.get("customSubDomainName"):
                resource_config["custom_subdomain_name"] = properties[
                    "customSubDomainName"
                ]
        elif azure_type == "Microsoft.Automation/automationAccounts":
            # Automation Account specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            resource_config.update(
                {
                    "sku_name": sku.get("name", "Basic"),
                }
            )
        elif azure_type == "Microsoft.Search/searchServices":
            # Search Service specific properties
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            resource_config.update(
                {
                    "sku": sku.get("name", "standard"),
                }
            )
        elif azure_type == "Microsoft.Automation/automationAccounts/runbooks":
            # Automation Runbook specific properties
            properties = self._parse_properties(resource)

            # Extract automation account name from resource name (format: "accountname/runbookname")
            full_name = resource.get("name", "")
            account_name = (
                full_name.split("/")[0] if "/" in full_name else "unknown-account"
            )
            runbook_name = full_name.split("/")[1] if "/" in full_name else full_name

            resource_config.update(
                {
                    "automation_account_name": account_name,
                    "runbook_type": properties.get("runbookType", "PowerShell"),
                    "log_progress": properties.get("logProgress", True),
                    "log_verbose": properties.get("logVerbose", False),
                }
            )

            # Runbooks require either content, draft, or publish_content_link
            # For now, provide a placeholder publish_content_link since we don't have the actual runbook content
            publish_content_link = properties.get("publishContentLink", {})
            if publish_content_link and "uri" in publish_content_link:
                resource_config["publish_content_link"] = {
                    "uri": publish_content_link["uri"]
                }
                # Add version if present
                if "version" in publish_content_link:
                    resource_config["publish_content_link"]["version"] = (
                        publish_content_link["version"]
                    )
            else:
                # Provide placeholder content for empty runbook
                # This prevents validation errors but won't replicate actual runbook logic
                logger.warning(
                    f"Runbook '{runbook_name}' has no publishContentLink in properties. "
                    "Using placeholder empty content. Actual runbook logic won't be replicated."
                )
                resource_config["content"] = (
                    "# Placeholder runbook content\n# Original runbook content not available in graph\n"
                )

            # Override name to just be the runbook name (not accountname/runbookname)
            resource_config["name"] = runbook_name
        elif azure_type == "Microsoft.DevTestLab/schedules":
            # DevTest Lab Schedule specific properties
            properties = self._parse_properties(resource)

            # Extract lab name from resource name if format is "labname/schedules/schedulename"
            full_name = resource.get("name", "")
            parts = full_name.split("/")
            if len(parts) >= 3:
                lab_name = parts[0]
                schedule_name = parts[2]
            else:
                lab_name = "unknown-lab"
                schedule_name = full_name

            # Get task type (shutdown, startup, etc.)
            task_type = properties.get("taskType", "LabVmsShutdownTask")

            # Get time zone ID
            time_zone_id = properties.get("timeZoneId", "UTC")

            # Get daily recurrence time
            daily_recurrence_time = properties.get("dailyRecurrence", {}).get(
                "time", "1900"
            )

            resource_config.update(
                {
                    "lab_name": lab_name,
                    "task_type": task_type,
                    "time_zone_id": time_zone_id,
                    "daily_recurrence": {"time": daily_recurrence_time},
                    # notification_settings block is required
                    # Note: "enabled" field is not valid in azurerm_dev_test_schedule
                    # Status is controlled by the task_type and schedule presence
                    "notification_settings": {
                        "time_in_minutes": properties.get(
                            "notificationSettings", {}
                        ).get("timeInMinutes", 30),
                    },
                }
            )

            # Override name to just be the schedule name
            resource_config["name"] = schedule_name

        elif azure_type == "Microsoft.Compute/sshPublicKeys":
            # SSH Public Key specific properties
            properties = self._parse_properties(resource)

            resource_config.update(
                {
                    "public_key": properties.get(
                        "publicKey",
                        "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQC... placeholder",
                    ),
                }
            )
        elif azure_type == "Microsoft.Authorization/roleAssignments":
            # Role Assignments - RBAC configuration (no location, scoped resources)
            properties = self._parse_properties(resource)

            resource_config = {
                "scope": properties.get("scope", resource.get("scope", "")),
                "role_definition_id": properties.get(
                    "roleDefinitionId", resource.get("roleDefinitionId", "")
                ),
                "principal_id": properties.get(
                    "principalId", resource.get("principalId", "")
                ),
            }

            # Note: Role assignments don't have a location property (global/scoped)
            # Remove location from resource_config if present
            resource_config.pop("location", None)
        elif azure_type in [
            "Microsoft.Insights/dataCollectionRules",
            "microsoft.insights/dataCollectionRules",
        ]:
            # Data Collection Rule - requires complex nested blocks
            properties = self._parse_properties(resource)

            # Extract destinations from properties
            destinations_prop = properties.get("destinations", {})
            destinations_config = {}

            # Log Analytics destinations
            if "logAnalytics" in destinations_prop:
                log_analytics_list = []
                for la_dest in destinations_prop["logAnalytics"]:
                    workspace_resource_id = la_dest.get("workspaceResourceId", "")
                    dest_name = la_dest.get("name", "default")
                    if workspace_resource_id:
                        # Normalize resource ID casing (fixes Problem 5)
                        workspace_resource_id = self._normalize_azure_resource_id(
                            workspace_resource_id
                        )
                        log_analytics_list.append(
                            {
                                "workspace_resource_id": workspace_resource_id,
                                "name": dest_name,
                            }
                        )
                if log_analytics_list:
                    destinations_config["log_analytics"] = log_analytics_list

            # Azure Monitor Metrics destinations
            if "azureMonitorMetrics" in destinations_prop:
                am_dest = destinations_prop["azureMonitorMetrics"]
                dest_name = am_dest.get("name", "azureMonitorMetrics-default")
                destinations_config["azure_monitor_metrics"] = {"name": dest_name}

            # Extract data flows from properties
            data_flows_prop = properties.get("dataFlows", [])
            data_flows_config = []
            for flow in data_flows_prop:
                flow_config = {
                    "streams": flow.get("streams", ["Microsoft-Perf"]),
                    "destinations": flow.get("destinations", ["default"]),
                }
                # Add output_stream if present
                if "outputStream" in flow:
                    flow_config["output_stream"] = flow["outputStream"]
                # Add transform_kql if present
                if "transformKql" in flow:
                    flow_config["transform_kql"] = flow["transformKql"]
                data_flows_config.append(flow_config)

            # If no destinations or data_flows found, skip this DCR
            # DCRs without destinations are incomplete and can't be deployed
            if not destinations_config:
                logger.warning(
                    f"Data Collection Rule '{resource_name}' has no destinations in properties. "
                    f"Skipping this DCR as it cannot be deployed without a valid Log Analytics workspace. "
                    f"This may indicate incomplete data in the graph or a DCR that was being configured."
                )
                return None
            if not data_flows_config:
                logger.warning(
                    f"Data Collection Rule '{resource_name}' has no dataFlows in properties. "
                    f"Skipping this DCR as it cannot be deployed without data flow configuration."
                )
                return None

            resource_config.update(
                {"destinations": destinations_config, "data_flow": data_flows_config}
            )
        elif azure_type in ["User", "Microsoft.AAD/User", "Microsoft.Graph/users"]:
            # Entra ID User
            # Users from Neo4j may have different property names than ARM resources
            user_principal_name = resource.get("userPrincipalName") or resource.get(
                "name", "unknown"
            )
            display_name = (
                resource.get("displayName")
                or resource.get("display_name")
                or user_principal_name
            )
            mail_nickname = (
                resource.get("mailNickname")
                or resource.get("mail_nickname")
                or user_principal_name.split("@")[0]
            )

            resource_config = {
                "user_principal_name": user_principal_name,
                "display_name": display_name,
                "mail_nickname": mail_nickname,
                # Password must be set via variable - never hardcode
                "password": f"var.azuread_user_password_{self._sanitize_terraform_name(user_principal_name)}",
                "force_password_change": True,
            }

            # Optionally add other properties if present
            if resource.get("accountEnabled") is not None:
                resource_config["account_enabled"] = resource.get("accountEnabled")

        elif azure_type in ["Group", "Microsoft.AAD/Group", "Microsoft.Graph/groups"]:
            # Entra ID Group
            display_name = (
                resource.get("displayName")
                or resource.get("display_name")
                or resource.get("name", "unknown")
            )
            mail_enabled = resource.get("mailEnabled", False)
            security_enabled = resource.get("securityEnabled", True)

            resource_config = {
                "display_name": display_name,
                "mail_enabled": mail_enabled,
                "security_enabled": security_enabled,
            }

            # Add description if present
            if resource.get("description"):
                resource_config["description"] = resource.get("description")

        elif azure_type in [
            "ServicePrincipal",
            "Microsoft.AAD/ServicePrincipal",
            "Microsoft.Graph/servicePrincipals",
        ]:
            # Entra ID Service Principal
            app_id = (
                resource.get("appId")
                or resource.get("application_id")
                or "00000000-0000-0000-0000-000000000000"
            )
            display_name = (
                resource.get("displayName")
                or resource.get("display_name")
                or resource.get("name", "unknown")
            )

            resource_config = {
                "application_id": app_id,
                # Note: In real scenario, this would reference an azuread_application resource
                # For now, use the app_id directly
            }

            # Add optional properties
            if resource.get("accountEnabled") is not None:
                resource_config["account_enabled"] = resource.get("accountEnabled")

        elif azure_type in [
            "Application",
            "Microsoft.AAD/Application",
            "Microsoft.Graph/applications",
        ]:
            # Entra ID Application
            display_name = (
                resource.get("displayName")
                or resource.get("display_name")
                or resource.get("name", "unknown")
            )

            resource_config = {
                "display_name": display_name,
            }

            # Add sign_in_audience if present
            sign_in_audience = resource.get("signInAudience", "AzureADMyOrg")
            resource_config["sign_in_audience"] = sign_in_audience

        return terraform_type, safe_name, resource_config

    def _get_app_service_terraform_type(self, resource: Dict[str, Any]) -> str:
        """Determine correct App Service Terraform type based on OS.

        Args:
            resource: Azure Web App resource

        Returns:
            "azurerm_linux_web_app" or "azurerm_windows_web_app"
        """
        properties = self._parse_properties(resource)
        kind = properties.get("kind", "").lower()

        # Check kind property for Linux indicator
        if "linux" in kind:
            return "azurerm_linux_web_app"
        else:
            # Default to Windows if no clear Linux indicator
            return "azurerm_windows_web_app"

    def _parse_properties(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Parse properties JSON from resource.

        Args:
            resource: Azure resource with properties field

        Returns:
            Parsed properties dict (empty dict if parsing fails)
        """
        properties_str = resource.get("properties", "{}")
        if isinstance(properties_str, str):
            try:
                return json.loads(properties_str)
            except json.JSONDecodeError:
                return {}
        return properties_str

    def _apply_rg_prefix(self, rg_name: str) -> str:
        """Apply resource group prefix with validation.

        Args:
            rg_name: Original resource group name

        Returns:
            Prefixed name, validated against Azure limits

        Raises:
            ValueError: If prefixed name exceeds 90 characters
        """
        if not self.resource_group_prefix:
            return rg_name

        prefixed_name = f"{self.resource_group_prefix}{rg_name}"

        # Validate Azure RG name length (90 chars max)
        if len(prefixed_name) > 90:
            raise ValueError(
                f"Prefixed resource group name exceeds Azure limit (90 chars): "
                f"'{prefixed_name}' ({len(prefixed_name)} chars). "
                f"Original: '{rg_name}', Prefix: '{self.resource_group_prefix}'"
            )

        return prefixed_name

    def _normalize_resource_id(self, resource_id: str) -> str:
        """Normalize Azure resource ID by fixing provider namespace casing.

        Azure resource IDs use inconsistent casing for provider namespaces.
        Terraform requires correct casing (PascalCase for provider namespaces).

        Args:
            resource_id: Azure resource ID with potentially incorrect casing

        Returns:
            Normalized resource ID with correct provider namespace casing

        Example:
            >>> emitter._normalize_resource_id(
            ...     "/subscriptions/.../providers/Microsoft.Keyvault/vaults/vault1"
            ... )
            '/subscriptions/.../providers/Microsoft.KeyVault/vaults/vault1'
        """
        if not resource_id:
            return resource_id

        # Map of incorrect casing to correct casing for provider namespaces
        provider_casing_map = {
            "Microsoft.Keyvault": "Microsoft.KeyVault",
            "microsoft.keyvault": "Microsoft.KeyVault",
            "Microsoft.insights": "Microsoft.Insights",
            "microsoft.insights": "Microsoft.Insights",
            "Microsoft.operationalinsights": "Microsoft.OperationalInsights",
            "microsoft.operationalinsights": "Microsoft.OperationalInsights",
            "Microsoft.operationalInsights": "Microsoft.OperationalInsights",
            "microsoft.operationalInsights": "Microsoft.OperationalInsights",
        }

        normalized_id = resource_id
        for incorrect, correct in provider_casing_map.items():
            # Use case-insensitive replacement in the provider segment
            # Format: /providers/Microsoft.Keyvault/ or /providers/microsoft.insights/
            incorrect_segment = f"/providers/{incorrect}/"
            correct_segment = f"/providers/{correct}/"
            # Case-insensitive search and replace
            import re

            pattern = re.compile(re.escape(incorrect_segment), re.IGNORECASE)
            normalized_id = pattern.sub(correct_segment, normalized_id)

        return normalized_id

    def _extract_resource_name_from_id(
        self, resource_id: str, resource_type: str
    ) -> str:
        """Extract resource name from Azure resource ID path.

        Args:
            resource_id: Full Azure resource ID
            resource_type: Azure resource type segment (e.g., "subnets", "networkInterfaces")

        Returns:
            Extracted resource name or "unknown"
        """
        path_segment = f"/{resource_type}/"
        if path_segment in resource_id:
            return resource_id.split(path_segment)[-1].split("/")[0]
        return "unknown"

    def _extract_subscription_from_resource_id(self, resource_id: str) -> Optional[str]:
        """Extract subscription ID from Azure resource ID.

        Args:
            resource_id: Full Azure resource ID
                Format: /subscriptions/{subscription-id}/resourceGroups/{rg}/...

        Returns:
            Subscription ID or None if not found

        Example:
            >>> emitter._extract_subscription_from_resource_id(
            ...     "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/rg/..."
            ... )
            '9b00bc5e-9abc-45de-9958-02a9d9277b16'
        """
        if not resource_id or "/subscriptions/" not in resource_id:
            return None

        try:
            # Extract subscription ID: /subscriptions/{id}/...
            parts = resource_id.split("/subscriptions/")
            if len(parts) > 1:
                # Get everything after /subscriptions/ and before next /
                sub_id = parts[1].split("/")[0]
                if sub_id:
                    return sub_id
        except (IndexError, AttributeError):
            pass

        return None

    def _sanitize_terraform_name(self, name: str) -> str:
        """Sanitize resource name for Terraform compatibility.

        Args:
            name: Original resource name

        Returns:
            Sanitized name safe for Terraform
        """
        # Replace invalid characters with underscores
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        return sanitized or "unnamed_resource"

    def _normalize_azure_resource_id(self, resource_id: str) -> str:
        """Normalize Azure resource ID casing to match Terraform expectations.

        Azure API returns inconsistent casing in resource IDs (e.g.,
        'microsoft.OperationalInsights/Workspaces' instead of
        'Microsoft.OperationalInsights/workspaces'). This function normalizes
        them to the canonical Azure Resource Provider format.

        Args:
            resource_id: Azure resource ID to normalize

        Returns:
            Normalized resource ID with correct casing

        Example:
            Input:  /subscriptions/.../microsoft.OperationalInsights/Workspaces/name
            Output: /subscriptions/.../Microsoft.OperationalInsights/workspaces/name
        """
        if not resource_id:
            return resource_id

        import re

        # Known provider normalizations (pattern → correct casing)
        # Format: (regex_pattern, replacement_string)
        provider_normalizations = [
            (
                r"/microsoft\.operationalinsights/workspaces/",
                "/Microsoft.OperationalInsights/workspaces/",
            ),
            (r"/microsoft\.insights/", "/Microsoft.Insights/"),
            (r"/microsoft\.compute/", "/Microsoft.Compute/"),
            (r"/microsoft\.network/", "/Microsoft.Network/"),
            (r"/microsoft\.storage/", "/Microsoft.Storage/"),
            (r"/microsoft\.keyvault/", "/Microsoft.KeyVault/"),
            (r"/microsoft\.web/", "/Microsoft.Web/"),
            (r"/microsoft\.sql/", "/Microsoft.Sql/"),
            (r"/microsoft\.automation/", "/Microsoft.Automation/"),
            (r"/microsoft\.devtestlab/", "/Microsoft.DevTestLab/"),
        ]

        normalized = resource_id
        for pattern, replacement in provider_normalizations:
            normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

        return normalized

    def _validate_resource_reference(
        self, terraform_type: str, resource_name: str
    ) -> bool:
        """Validate that a referenced resource exists in the graph.

        Args:
            terraform_type: Terraform resource type (e.g., "azurerm_network_interface")
            resource_name: Sanitized Terraform resource name

        Returns:
            True if resource exists, False otherwise
        """
        return (
            terraform_type in self._available_resources
            and resource_name in self._available_resources[terraform_type]
        )

    def _resolve_subnet_reference(self, subnet_id: str, resource_name: str) -> str:
        """Resolve subnet reference to VNet-scoped Terraform resource name.

        Extracts both VNet and subnet names from Azure resource ID and constructs
        the scoped Terraform reference: ${azurerm_subnet.{vnet}_{subnet}.id}

        Validates that the subnet exists in the graph and tracks missing references.

        Args:
            subnet_id: Azure subnet resource ID
                Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/
                        Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
            resource_name: Name of the resource referencing this subnet (for logging)

        Returns:
            Terraform reference string with VNet-scoped subnet name

        Example:
            >>> emitter._resolve_subnet_reference(
            ...     "/subscriptions/.../virtualNetworks/infra-vnet/subnets/AzureBastionSubnet",
            ...     "bastion-host-1"
            ... )
            '${azurerm_subnet.infra_vnet_AzureBastionSubnet.id}'
        """
        if not subnet_id or "/subnets/" not in subnet_id:
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet ID: {subnet_id}"
            )
            return "${azurerm_subnet.unknown_subnet.id}"

        # Extract VNet name from ID
        vnet_name = self._extract_resource_name_from_id(subnet_id, "virtualNetworks")
        if vnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' subnet ID missing VNet segment: {subnet_id}"
            )
            # Fallback: use only subnet name (old behavior for compatibility)
            subnet_name = self._extract_resource_name_from_id(subnet_id, "subnets")
            if subnet_name != "unknown":
                subnet_name_safe = self._sanitize_terraform_name(subnet_name)
                return f"${{azurerm_subnet.{subnet_name_safe}.id}}"
            return "${azurerm_subnet.unknown_subnet.id}"

        # Extract subnet name from ID
        subnet_name = self._extract_resource_name_from_id(subnet_id, "subnets")
        if subnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet name in ID: {subnet_id}"
            )
            return "${azurerm_subnet.unknown_subnet.id}"

        # Construct VNet-scoped reference
        vnet_name_safe = self._sanitize_terraform_name(vnet_name)
        subnet_name_safe = self._sanitize_terraform_name(subnet_name)
        scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"

        # Validate subnet exists in the graph
        if scoped_subnet_name not in self._available_subnets:
            logger.error(
                f"Resource '{resource_name}' references subnet that doesn't exist in graph:\n"
                f"  Subnet Terraform name: {scoped_subnet_name}\n"
                f"  Subnet Azure name: {subnet_name}\n"
                f"  VNet Azure name: {vnet_name}\n"
                f"  Azure ID: {subnet_id}"
            )
            # Track missing subnet reference
            self._missing_references.append(
                {
                    "resource_name": resource_name,
                    "resource_type": "subnet",
                    "missing_resource_name": subnet_name,
                    "missing_resource_id": subnet_id,
                    "missing_vnet_name": vnet_name,
                    "expected_terraform_name": scoped_subnet_name,
                }
            )

        logger.debug(
            f"Resolved subnet reference for '{resource_name}': "
            f"VNet='{vnet_name}', Subnet='{subnet_name}' -> {scoped_subnet_name}"
        )

        return f"${{azurerm_subnet.{scoped_subnet_name}.id}}"

    def _extract_source_subscription(
        self, resources: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract source subscription ID from discovered resources.

        Examines resource IDs to determine the source subscription ID
        from which resources were discovered.

        Args:
            resources: List of discovered resources from graph

        Returns:
            Source subscription ID or None if not found
        """
        # Pattern to match Azure resource IDs
        resource_id_pattern = re.compile(
            r"^/subscriptions/([a-f0-9-]+)/", re.IGNORECASE
        )

        for resource in resources:
            resource_id = resource.get("id", "")
            if resource_id:
                match = resource_id_pattern.match(resource_id)
                if match:
                    subscription_id = match.group(1)
                    logger.debug(
                        f"Extracted source subscription ID from resource ID: {subscription_id}"
                    )
                    return subscription_id

        logger.debug("Could not extract source subscription ID from resources")
        return None

    def get_supported_resource_types(self) -> List[str]:
        """Get list of Azure resource types supported by Terraform provider.

        Returns:
            List of supported Azure resource type strings
        """
        return list(self.AZURE_TO_TERRAFORM_MAPPING.keys())

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate generated Terraform template for correctness.

        Args:
            template_data: Generated Terraform template data

        Returns:
            True if template is valid, False otherwise
        """
        required_keys = ["terraform", "provider", "resource"]

        for key in required_keys:
            if key not in template_data:
                logger.error(f"Missing required key in Terraform template: {key}")
                return False

        # Basic validation passed
        return True

    def get_resource_count(self) -> int:
        """Get the count of resources generated by this emitter.

        Returns:
            Number of Terraform resources generated.
        """
        return self._resource_count

    def get_files_created_count(self) -> int:
        """Get the count of files created by this emitter.

        Returns:
            Number of files created.
        """
        return self._files_created

    def get_import_blocks_count(self) -> int:
        """Get the count of import blocks generated by this emitter.

        Returns:
            Number of import blocks generated (Issue #412).
        """
        return self._import_blocks_generated

    def get_translation_stats(self) -> Optional[Dict[str, int]]:
        """Get translation statistics if cross-tenant translation is enabled.

        Returns:
            Dictionary with translation stats or None if not applicable.
        """
        if not self._translation_coordinator:
            return None

        return {
            "users_mapped": len(
                self._translation_coordinator.context.identity_mapping.get("users", {})
                if self._translation_coordinator.context.identity_mapping
                else {}
            ),
            "groups_mapped": len(
                self._translation_coordinator.context.identity_mapping.get("groups", {})
                if self._translation_coordinator.context.identity_mapping
                else {}
            ),
            "service_principals_mapped": len(
                self._translation_coordinator.context.identity_mapping.get(
                    "service_principals", {}
                )
                if self._translation_coordinator.context.identity_mapping
                else {}
            ),
        }


# Auto-register this emitter
register_emitter("terraform", TerraformEmitter)
