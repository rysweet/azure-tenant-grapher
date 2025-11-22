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
        # Track available resource group names (Issue: Skip VNets with missing RGs)
        self._available_resource_groups: set = set()

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

    def _get_effective_subscription_id(self, resource: Dict[str, Any]) -> str:
        """Get the subscription ID to use for resource construction.

        In cross-tenant mode, returns target subscription ID.
        Otherwise returns the resource's original subscription ID.

        Args:
            resource: Resource dictionary with subscription_id field

        Returns:
            Subscription ID to use in constructed resource IDs
        """
        # If we have a target subscription (cross-tenant), use it
        if self.target_subscription_id:
            return self.target_subscription_id
        # Otherwise use the resource's subscription
        return resource.get("subscription_id", "")

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
        # Bug #36: Add support for additional resource types
        "Microsoft.DocumentDB/databaseAccounts": "azurerm_cosmosdb_account",
        "Microsoft.DocumentDb/databaseAccounts": "azurerm_cosmosdb_account",  # Lowercase variant
        "Microsoft.Network/applicationGateways": "azurerm_application_gateway",
        "Microsoft.Network/dnszones": "azurerm_dns_zone",
        "Microsoft.Network/dnsZones": "azurerm_dns_zone",
        "Microsoft.Network/applicationGatewayWebApplicationFirewallPolicies": "azurerm_web_application_firewall_policy",
        "Microsoft.Network/natGateways": "azurerm_nat_gateway",
        "Microsoft.DBforPostgreSQL/flexibleServers": "azurerm_postgresql_flexible_server",
        "Microsoft.Sql/servers/databases": "azurerm_mssql_database",
        "Microsoft.ContainerInstance/containerGroups": "azurerm_container_group",
        "Microsoft.DataFactory/factories": "azurerm_data_factory",
        "Microsoft.ContainerRegistry/registries": "azurerm_container_registry",
        "Microsoft.ServiceBus/namespaces": "azurerm_servicebus_namespace",
        # Bug #44: Add previously "unsupported" resources that DO have azurerm provider support!
        "Microsoft.Compute/virtualMachines/runCommands": "azurerm_virtual_machine_run_command",
        "Microsoft.App/managedEnvironments": "azurerm_container_app_environment",
        "Microsoft.App/containerApps": "azurerm_container_app",
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
        # Container and Kubernetes resources (azurerm v3.43.0+)
        "Microsoft.App/containerApps": "azurerm_container_app",
        "Microsoft.ContainerService/managedClusters": "azurerm_kubernetes_cluster",
        "Microsoft.ContainerRegistry/registries": "azurerm_container_registry",
        # Additional Compute resources
        "Microsoft.Compute/virtualMachineScaleSets": "azurerm_linux_virtual_machine_scale_set",
        "Microsoft.Compute/snapshots": "azurerm_snapshot",
        # Additional Network resources
        "Microsoft.Network/loadBalancers": "azurerm_lb",
        # Additional Monitoring resources
        "Microsoft.Insights/metricAlerts": "azurerm_monitor_metric_alert",
        "Microsoft.Insights/metricalerts": "azurerm_monitor_metric_alert",  # Case variant
        # Cache resources
        "Microsoft.Cache/Redis": "azurerm_redis_cache",
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
        comparison_result: Optional[Any] = None,
    ) -> List[Path]:
        """Generate Terraform template from tenant graph.

        Args:
            graph: Tenant graph to generate from
            out_dir: Directory to write files
            domain_name: Optional domain name for user accounts
            subscription_id: Optional subscription ID for deployment
            comparison_result: Optional comparison with target tenant (NEW in Phase 1E)
                              If provided, enables smart import generation
        """
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
                    "default": self.target_subscription_id or subscription_id or "",
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
        # Bug #31: Map VNet abstracted IDs to terraform names for standalone subnets
        # Format: {abstracted_vnet_id: terraform_name}
        self._vnet_id_to_terraform_name: Dict[str, str] = {}
        # Store graph for reference in _convert_resource (needed for DCR workspace validation)
        self._graph = graph

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
                    # For abstracted nodes, use original_id which contains the full Azure resource path
                    subnet_id = resource.get("original_id") or resource.get("id", "")
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

        # Smart import generation (Phase 1E) - opt-in feature
        # When comparison_result is provided, generate import blocks and filter resources
        resource_ids_to_emit = None  # None = emit all (default behavior)
        if comparison_result is not None:
            logger.info("=" * 70)
            logger.info("Smart Import Mode Enabled (Phase 1E)")
            logger.info("=" * 70)
            try:
                from .smart_import_generator import SmartImportGenerator

                generator = SmartImportGenerator()
                import_block_set = generator.generate_import_blocks(comparison_result)

                # Bug #24 fix: Store import blocks, write them AFTER resource emission
                # (so we can filter out import blocks for resources that weren't emitted)
                smart_import_blocks = (
                    import_block_set.import_blocks
                    if import_block_set.import_blocks
                    else []
                )
                logger.info(
                    f"Generated {len(smart_import_blocks)} smart import blocks "
                    f"(will be filtered and written after resource emission)"
                )

                # Build set of resource IDs that need emission (NEW + DRIFTED only)
                # EXACT_MATCH resources are skipped (only imported, not emitted)
                resource_ids_to_emit = {
                    r["id"] for r in import_block_set.resources_needing_emission
                }

                # Special case: If no resources need emission AND no import blocks,
                # comparison result was empty - fall back to emitting all resources
                if not resource_ids_to_emit and not import_block_set.import_blocks:
                    logger.info(
                        "Comparison result was empty - falling back to standard emission"
                    )
                    resource_ids_to_emit = None  # Emit all
                else:
                    logger.info(
                        f"Resources needing emission: {len(resource_ids_to_emit)} "
                        f"(NEW + DRIFTED), others are EXACT_MATCH (import-only)"
                    )
            except ImportError as e:
                logger.warning(
                    f"Smart import generation failed (module not found): {e}. "
                    f"Continuing with standard emission."
                )
                resource_ids_to_emit = None
            except Exception as e:
                logger.error(
                    f"Smart import generation failed: {e}. "
                    f"Continuing with standard emission.",
                    exc_info=True,
                )
                resource_ids_to_emit = None

        # Second pass: Process resources with validation (sorted by tier)
        for resource_dep in resource_dependencies:
            resource = resource_dep.resource

            # Smart import filtering: Skip EXACT_MATCH resources (import-only)
            # resource_ids_to_emit is None when comparison_result was not provided (default)
            # EXCEPTION: Always emit resource groups (foundational, synthetic resources)
            if resource_ids_to_emit is not None:
                resource_type = resource.get("type")
                resource_id = resource.get("id")

                # Always emit resource groups - they're synthetic (extracted from other resources)
                # and required for all other resources to reference
                is_resource_group = (
                    resource_type == "Microsoft.Resources/resourceGroups"
                )

                if (
                    not is_resource_group
                    and resource_id
                    and resource_id not in resource_ids_to_emit
                ):
                    # Resource is EXACT_MATCH - skip emission (only imported)
                    logger.debug(
                        f"Skipping emission for EXACT_MATCH resource: {resource_id}"
                    )
                    continue
                elif is_resource_group:
                    logger.debug(
                        f"Always emitting resource group (foundational): {resource_id}"
                    )

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

                # Bug #28: Detect and resolve name collisions by appending resource group
                if resource_name in terraform_config["resource"][resource_type]:
                    # Collision detected! Append resource group to make unique
                    rg_name = resource.get("resource_group") or resource.get(
                        "resourceGroup", "default_rg"
                    )
                    rg_safe = self._sanitize_terraform_name(rg_name)
                    original_name = resource_name
                    resource_name = f"{rg_safe}_{resource_name}"

                    # Truncate if too long (Azure 80-char limit)
                    if len(resource_name) > 80:
                        import hashlib

                        name_hash = hashlib.md5(resource_name.encode()).hexdigest()[:5]
                        resource_name = resource_name[:74] + "_" + name_hash

                    logger.warning(
                        f"Resource name collision detected for {resource_type}.{original_name}! "
                        f"Resolving by appending resource group: {resource_type}.{resource_name} "
                        f"(resource_group: {rg_name})"
                    )

                    # Update config name reference (for depends_on, etc.)
                    # Note: Resource config "name" field stays as original Azure name

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

        # Bug #24 fix: Write smart import blocks AFTER resource emission completes
        # This allows us to filter out import blocks for resources that weren't emitted
        if comparison_result is not None and "smart_import_blocks" in locals():
            self._write_import_blocks_filtered(
                smart_import_blocks, terraform_config, out_dir
            )

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

    def _build_azure_resource_id(
        self,
        tf_resource_type: str,
        resource_config: Dict[str, Any],
        subscription_id: str,
    ) -> Optional[str]:
        """Build Azure resource ID from Terraform resource config.

        Args:
            tf_resource_type: Terraform resource type (e.g., "azurerm_storage_account")
            resource_config: Terraform resource configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure resource ID string or None if cannot be constructed
        """
        resource_name = resource_config.get("name")
        if not resource_name:
            return None

        # Resource groups are special - no provider namespace needed
        if tf_resource_type == "azurerm_resource_group":
            return f"/subscriptions/{subscription_id}/resourceGroups/{resource_name}"

        # All other resources need resource group and provider namespace
        resource_group = resource_config.get("resource_group_name")
        if not resource_group:
            return None

        # Map Terraform type back to Azure provider/resource type
        # Create reverse mapping from AZURE_TO_TERRAFORM_MAPPING
        terraform_to_azure = {v: k for k, v in self.AZURE_TO_TERRAFORM_MAPPING.items()}
        azure_type = terraform_to_azure.get(tf_resource_type)

        if not azure_type:
            # Unknown type - cannot construct ID
            return None

        # Standard Azure resource ID format:
        # /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
        return f"/subscriptions/{subscription_id}/resourceGroups/{resource_group}/providers/{azure_type}/{resource_name}"

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
            # Build import blocks for ALL resource types, not just resource groups
            candidate_imports = []

            logger.info(
                "Using all_resources strategy - checking existence of ALL planned resources"
            )

            # Iterate through ALL resource types in terraform config
            for tf_resource_type, resources_of_type in tf_resources.items():
                # Skip if not a dict (shouldn't happen but safety check)
                if not isinstance(resources_of_type, dict):
                    continue

                for tf_name, resource_config in resources_of_type.items():
                    # Build Azure resource ID based on resource type
                    azure_id = self._build_azure_resource_id(
                        tf_resource_type, resource_config, subscription_id
                    )

                    if azure_id:
                        resource_name = resource_config.get("name", tf_name)
                        candidate_imports.append(
                            {
                                "to": f"{tf_resource_type}.{tf_name}",
                                "id": azure_id,
                                "name": resource_name,
                                "type": tf_resource_type,
                            }
                        )

            # Batch validate existence of ALL candidates
            if candidate_imports:
                logger.info(
                    f"Validating existence of {len(candidate_imports)} resources across all types..."
                )
                resource_ids = [imp["id"] for imp in candidate_imports]

                # Process in batches to avoid overwhelming the API
                batch_size = 100
                all_existence_results = {}

                for i in range(0, len(resource_ids), batch_size):
                    batch = resource_ids[i : i + batch_size]
                    batch_results = self._existence_validator.batch_check_resources(
                        batch
                    )
                    all_existence_results.update(batch_results)
                    logger.info(
                        f"Validated batch {i // batch_size + 1}/{(len(resource_ids) + batch_size - 1) // batch_size}"
                    )

                # Filter to only existing resources
                exists_count = 0
                skip_count = 0

                for candidate in candidate_imports:
                    result = all_existence_results.get(candidate["id"])
                    if result and result.exists:
                        import_blocks.append(
                            {"to": candidate["to"], "id": candidate["id"]}
                        )
                        exists_count += 1
                        logger.debug(
                            f"✓ {candidate['type']}: {candidate['name']} exists (cached: {result.cached})"
                        )
                    else:
                        skip_count += 1
                        if skip_count <= 10:  # Only log first 10 to avoid spam
                            error_msg = (
                                f" (error: {result.error})"
                                if result and result.error
                                else ""
                            )
                            logger.debug(
                                f"✗ {candidate['type']}: {candidate['name']} does not exist{error_msg}"
                            )

                logger.info(
                    f"all_resources strategy: {exists_count} resources exist, "
                    f"{skip_count} will be created (not imported)"
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

    def _write_import_blocks_filtered(
        self,
        import_blocks: List[Any],
        terraform_config: Dict[str, Any],
        output_path: Path,
    ) -> None:
        """Write Terraform import blocks to imports.tf file in HCL format (Bug #24 fix).

        This method writes import blocks in Terraform HCL format (not JSON) to a
        separate imports.tf file, filtering out import blocks for resources that
        weren't emitted to terraform_config.

        Args:
            import_blocks: List of ImportBlock instances with 'to' and 'id' attributes
            terraform_config: The terraform configuration dict with emitted resources
            output_path: Directory to write imports.tf

        Format:
            import {
              to = azurerm_virtual_network.vnet_abc123
              id = "/subscriptions/.../virtualNetworks/my-vnet"
            }

        Raises:
            Exception: Logged but not raised - errors are non-fatal
        """
        if not import_blocks:
            logger.debug("No import blocks to write")
            return

        try:
            # Bug #24 fix: Filter import blocks to only include resources that were actually emitted
            # Collect all emitted resource addresses from terraform_config
            emitted_addresses = set()
            for resource_type, resources in terraform_config.get(
                "resource", {}
            ).items():
                for resource_name in resources.keys():
                    emitted_addresses.add(f"{resource_type}.{resource_name}")

            # Filter import blocks to only those with emitted resources
            filtered_import_blocks = []
            skipped_count = 0
            for block in import_blocks:
                if block.to in emitted_addresses:
                    filtered_import_blocks.append(block)
                else:
                    skipped_count += 1
                    logger.debug(
                        f"Skipping import block for {block.to} - resource not emitted "
                        f"(likely filtered out during emission)"
                    )

            if skipped_count > 0:
                logger.warning(
                    f"Skipped {skipped_count} import blocks for resources that were filtered "
                    f"out during emission ({len(filtered_import_blocks)} blocks will be written)"
                )

            imports_file = output_path / "imports.tf"
            logger.info(
                f"Writing {len(filtered_import_blocks)} import blocks to {imports_file}"
            )

            with open(imports_file, "w") as f:
                # Write header comment
                f.write(
                    "# Terraform 1.5+ import blocks\n"
                    "# These blocks instruct Terraform to import existing resources\n"
                    "# into state without recreating them.\n"
                    "# Generated by Smart Import Generator (Phase 1E)\n\n"
                )

                # Write each import block
                for block in filtered_import_blocks:
                    # ImportBlock dataclass has 'to' and 'id' attributes
                    to_address = block.to
                    azure_id = block.id

                    f.write("import {\n")
                    f.write(f"  to = {to_address}\n")
                    f.write(f'  id = "{azure_id}"\n')
                    f.write("}\n\n")

            # Track file creation for generation report
            self._files_created += 1
            logger.info(
                f"Successfully wrote {len(filtered_import_blocks)} import blocks (filtered from {len(import_blocks)})"
            )

        except Exception as e:
            logger.error(
                f"Failed to write import blocks to imports.tf: {e}. "
                f"Continuing with resource emission.",
                exc_info=True,
            )
            # Non-fatal error - continue with resource generation

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

        # Bug #39: Normalize azure_type to lowercase for consistent elif matching
        # Store original for logging, use lowercase for comparisons
        azure_type_original = azure_type
        azure_type_lower = azure_type.lower()

        # Bug #36: Try case-insensitive lookup for Azure types
        # Azure API returns inconsistent casing (Microsoft.Insights/components vs microsoft.insights/components)
        if azure_type == "Microsoft.Web/sites":
            terraform_type = self._get_app_service_terraform_type(resource)
        else:
            # First try exact match
            terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(azure_type)

            # Bug #36: If not found, try lowercase version for case-insensitive match
            if not terraform_type:
                terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(
                    azure_type.lower()
                )
                if terraform_type:
                    logger.debug(
                        f"Bug #36: Matched '{azure_type}' using lowercase lookup"
                    )

        if not terraform_type:
            logger.warning(
                f"Skipping unsupported Azure resource type '{azure_type}' "
                f"for resource '{resource_name}'. Add mapping to AZURE_TO_TERRAFORM_MAPPING."
            )
            return None

        # Sanitize resource name for Terraform
        safe_name = self._sanitize_terraform_name(resource_name)

        # Define globally unique resource types that need unique suffixes
        globally_unique_types = {
            "Microsoft.KeyVault/vaults",
            "Microsoft.Cache/Redis",
            "Microsoft.Web/sites",
            "Microsoft.ContainerRegistry/registries",
            "Microsoft.DocumentDB/databaseAccounts",
        }

        # Apply unique suffix for globally unique resource types
        resource_name_with_suffix = resource_name
        if azure_type in globally_unique_types or azure_type.lower() in {
            t.lower() for t in globally_unique_types
        }:
            resource_id = resource.get("id", "")

            # Key Vaults have a 24-character name limit
            # Suffix is 7 characters ("-XXXXXX"), so max base name is 17 chars
            if azure_type == "Microsoft.KeyVault/vaults" and len(resource_name) > 17:
                truncated_name = resource_name[:17]
                resource_name_with_suffix = self._add_unique_suffix(
                    truncated_name, resource_id, azure_type
                )
                logger.warning(
                    f"Truncated Key Vault name '{resource_name}' "
                    f"(length {len(resource_name)}) to '{truncated_name}' "
                    f"(length {len(truncated_name)}) to accommodate unique suffix, "
                    f"resulting in '{resource_name_with_suffix}' "
                    f"(length {len(resource_name_with_suffix)})"
                )
            else:
                resource_name_with_suffix = self._add_unique_suffix(
                    resource_name, resource_id, azure_type
                )

            safe_name = self._sanitize_terraform_name(resource_name_with_suffix)
            logger.info(
                f"Applied unique suffix to globally unique resource "
                f"'{resource_name}' -> '{resource_name_with_suffix}' (type: {azure_type})"
            )

        # Build basic resource configuration
        # Ensure location is never null - default to eastus if missing
        # Bug #20 fix: Reject 'global' location which is invalid for resource groups
        location = resource.get("location")
        if not location or location.lower() in ["none", "null", "global"]:
            location = "eastus"
            if resource.get("location", "").lower() == "global":
                logger.warning(
                    f"Resource '{resource_name}' has invalid location 'global', using 'eastus' fallback"
                )

        # Resource groups don't have a resource_group_name field
        if azure_type == "Microsoft.Resources/resourceGroups":
            resource_config = {
                "name": resource_name_with_suffix,
                "location": location,
            }
        # Smart Detector Alert Rules are global and don't have a location field
        elif azure_type == "microsoft.alertsmanagement/smartDetectorAlertRules":
            resource_config = {
                "name": resource_name_with_suffix,
                "resource_group_name": resource.get("resource_group")
                or resource.get("resourceGroup"),
            }
        # DNS Zones are global resources and don't have a location field
        elif azure_type in ("Microsoft.Network/dnszones", "Microsoft.Network/dnsZones"):
            resource_config = {
                "name": resource_name_with_suffix,
                "resource_group_name": resource.get("resource_group")
                or resource.get("resourceGroup"),
            }
        else:
            resource_config = {
                "name": resource_name_with_suffix,
                "location": location,
                "resource_group_name": resource.get("resource_group")
                or resource.get("resourceGroup"),
            }

        # Note: Resources without resource groups will get None, which Terraform will reject
        # This is intentional - better to fail fast than deploy to wrong location

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

            # Bug #35: Normalize all VNet CIDRs
            normalized_prefixes = []
            for cidr in address_prefixes:
                normalized = self._normalize_cidr_block(cidr, resource_name)
                if normalized:
                    normalized_prefixes.append(normalized)
                else:
                    # Keep original if normalization fails (better than skipping VNet)
                    normalized_prefixes.append(cidr)

            resource_config["address_space"] = normalized_prefixes

            # Skip VNets with missing resource group - these cannot be deployed
            if not resource_config.get("resource_group_name"):
                logger.warning(
                    f"Skipping VNet '{resource_name}': No resource group found. "
                    f"VNets require a valid resource group for deployment."
                )
                return None

            # Bug #31 Step 2: Populate VNet ID -> Terraform name mapping for standalone subnets
            # Map both abstracted and original IDs to handle either format
            vnet_id = resource.get("id", "")
            vnet_original_id = resource.get("original_id", "")

            if vnet_id and safe_name:
                self._vnet_id_to_terraform_name[vnet_id] = safe_name
                logger.debug(f"Bug #31: Mapped VNet ID {vnet_id} -> {safe_name}")

            if vnet_original_id and vnet_original_id != vnet_id and safe_name:
                self._vnet_id_to_terraform_name[vnet_original_id] = safe_name
                logger.debug(
                    f"Bug #31: Mapped VNet original_id {vnet_original_id} -> {safe_name}"
                )

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

                # Bug #35: Normalize subnet CIDR
                normalized_subnet_cidr = self._normalize_cidr_block(
                    address_prefix, f"{resource_name}/{subnet_name}"
                )
                if not normalized_subnet_cidr:
                    logger.warning(
                        f"Bug #35: Subnet '{subnet_name}' has invalid CIDR '{address_prefix}', skipping"
                    )
                    continue

                # Build VNet-scoped subnet resource name
                # Pattern: {vnet_name}_{subnet_name}
                vnet_safe_name = safe_name  # Already computed: self._sanitize_terraform_name(resource_name)
                subnet_safe_name = self._sanitize_terraform_name(subnet_name)
                scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"

                # Build subnet resource config (name field remains original Azure name)
                subnet_config = {
                    "name": subnet_name,  # Azure resource name (unchanged)
                    "resource_group_name": resource.get("resource_group")
                    or resource.get("resourceGroup"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_safe_name}.name}}",
                    "address_prefixes": [normalized_subnet_cidr],
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

                            # Bug #30: Validate NIC was actually emitted (not just in graph)
                            if self._validate_resource_reference(
                                "azurerm_network_interface",
                                nic_name_safe,
                                terraform_config,
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
                            f"VM '{resource_name}' references missing NIC '{missing_nic['nic_name']}'\n"
                            f"    Azure ID: {missing_nic['nic_id']}\n"
                            f"    Expected Terraform name: {missing_nic['nic_terraform_name']}\n"
                            f"    VM will be created with only valid NICs"
                        )

                if nic_refs:
                    # Include VM with only the valid NICs (partial inclusion strategy)
                    resource_config["network_interface_ids"] = nic_refs
                    if missing_nics:
                        logger.info(
                            f"VM '{resource_name}' will be created with {len(nic_refs)} valid NIC(s), "
                            f"skipping {len(missing_nics)} missing NIC(s)"
                        )
                else:
                    # All NICs are missing - skip this VM (Bug #10 fix)
                    logger.warning(
                        f"VM '{resource_name}' - all {len(nics)} NIC reference(s) are missing. "
                        f"Skipping VM (cannot create without valid network configuration)."
                    )
                    return None
            else:
                # No network interfaces in properties - skip this VM (Bug #10 fix)
                logger.warning(
                    f"VM '{resource_name}' has no networkProfile. "
                    f"Skipping VM (cannot create without valid network configuration)."
                )
                return None

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

                # Bug #29: Skip NIC if subnet doesn't exist in graph
                if subnet_reference is None:
                    logger.error(
                        f"Skipping NIC '{resource_name}' - subnet missing from graph. "
                        "NIC cannot be deployed without valid subnet reference."
                    )
                    return None

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

            # Bug #31 Step 3: Use VNet mapping to find terraform name
            # Extract parent VNet ID from subnet ID path, then look up in mapping
            subnet_id = resource.get("original_id") or resource.get("id", "")
            vnet_name_safe = None
            vnet_name = "unknown"

            # Try to extract parent VNet ID and look up in mapping
            if "/virtualNetworks/" in subnet_id and "/subnets/" in subnet_id:
                # Extract VNet ID portion: everything up to /subnets/
                vnet_id = subnet_id.split("/subnets/")[0]

                # Look up in mapping (Bug #31 fix for abstracted IDs)
                if vnet_id in self._vnet_id_to_terraform_name:
                    vnet_name_safe = self._vnet_id_to_terraform_name[vnet_id]
                    # Extract original VNet name for logging
                    vnet_name = self._extract_resource_name_from_id(
                        vnet_id, "virtualNetworks"
                    )
                    logger.debug(
                        f"Bug #31: Found VNet terraform name via mapping: {vnet_id} -> {vnet_name_safe}"
                    )

            # Fallback: Extract VNet name directly from ID (original behavior)
            if not vnet_name_safe:
                vnet_name = self._extract_resource_name_from_id(
                    subnet_id, "virtualNetworks"
                )
                if vnet_name != "unknown":
                    vnet_name_safe = self._sanitize_terraform_name(vnet_name)

            # Build VNet-scoped resource name
            if vnet_name_safe and "/subnets/" in subnet_id:
                # vnet_name_safe is already sanitized from mapping or extraction
                subnet_name_safe = self._sanitize_terraform_name(resource_name)
                # Override safe_name to use scoped naming
                safe_name = f"{vnet_name_safe}_{subnet_name_safe}"

                resource_config = {
                    "name": resource_name,  # Original Azure name
                    "resource_group_name": resource.get("resource_group")
                    or resource.get("resourceGroup"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_name_safe}.name}}",
                }

                logger.debug(
                    f"Generated standalone subnet: {safe_name} "
                    f"(VNet: {vnet_name}, Subnet: {resource_name})"
                )
            else:
                logger.warning(
                    f"Standalone subnet '{resource_name}' has no parent VNet in ID: {subnet_id}. "
                    f"Skipping subnet as it cannot be deployed without a VNet."
                )
                # Skip this subnet entirely - cannot deploy without VNet
                return None

            # Handle address prefixes with fallback
            address_prefixes = (
                [properties.get("addressPrefix")]
                if properties.get("addressPrefix")
                else properties.get("addressPrefixes", [])
            )
            if not address_prefixes:
                logger.warning(f"Subnet '{resource_name}' has no address prefixes")
                address_prefixes = ["10.0.0.0/24"]

            # Bug #35: Normalize standalone subnet CIDRs
            normalized_subnet_prefixes = []
            for cidr in address_prefixes:
                if cidr:  # Skip None/empty values
                    normalized = self._normalize_cidr_block(cidr, resource_name)
                    if normalized:
                        normalized_subnet_prefixes.append(normalized)
                    else:
                        normalized_subnet_prefixes.append(cidr)  # Keep original if failed

            resource_config["address_prefixes"] = (
                normalized_subnet_prefixes if normalized_subnet_prefixes else address_prefixes
            )

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
            (
                resource.get("subscription_id")
                or resource.get("subscriptionId")
                or self._extract_subscription_from_resource_id(resource.get("id", ""))
                or "00000000-0000-0000-0000-000000000000"
            )

            # Build service plan ID with proper subscription
            service_plan_id = resource.get("app_service_plan_id")
            if not service_plan_id:
                # If no service plan, create a default one for this App Service
                resource_group = resource.get("resource_group")
                plan_name = f"{resource_name}-plan"
                plan_safe_name = self._sanitize_terraform_name(plan_name)

                # Create the service plan resource
                if "azurerm_service_plan" not in terraform_config["resource"]:
                    terraform_config["resource"]["azurerm_service_plan"] = {}

                # Only create if not already exists
                if (
                    plan_safe_name
                    not in terraform_config["resource"]["azurerm_service_plan"]
                ):
                    terraform_config["resource"]["azurerm_service_plan"][
                        plan_safe_name
                    ] = {
                        "name": plan_name,
                        "location": location,
                        "resource_group_name": resource_group,
                        "os_type": "Windows" if not is_linux else "Linux",
                        "sku_name": "B1",  # Basic tier
                    }
                    logger.debug(
                        f"Created default service plan '{plan_name}' for App Service '{resource_name}'"
                    )

                # Reference the created plan
                service_plan_id = f"${{azurerm_service_plan.{plan_safe_name}.id}}"

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
        elif azure_type_lower == "microsoft.sql/servers/databases":
            # Bug #37: SQL Database (child resource) needs server_id, not location/rg
            # Extract parent server name from database ID
            db_id = resource.get("id", "") or resource.get("original_id", "")
            server_name = self._extract_resource_name_from_id(db_id, "servers")

            if server_name == "unknown":
                logger.warning(
                    f"Bug #37: SQL Database '{resource_name}' has no parent server in ID. Skipping."
                )
                return None

            server_name_safe = self._sanitize_terraform_name(server_name)

            # Bug #43: Database names often include server prefix (server/database)
            # Extract just the database name (after last slash)
            db_name_only = resource_name.split("/")[-1] if "/" in resource_name else resource_name

            # SQL Database config (no location or resource_group_name - these are on the server)
            resource_config = {
                "name": db_name_only,
                "server_id": f"${{azurerm_mssql_server.{server_name_safe}.id}}",
            }

            logger.debug(f"Bug #43: SQL Database '{resource_name}' → name '{db_name_only}'")

            # Add optional properties if present
            properties = self._parse_properties(resource)
            if properties.get("maxSizeBytes"):
                resource_config["max_size_gb"] = int(properties["maxSizeBytes"]) // (
                    1024**3
                )
            if properties.get("collation"):
                resource_config["collation"] = properties["collation"]

            logger.debug(f"Bug #37: SQL Database '{resource_name}' linked to server '{server_name}'")

        elif azure_type_lower == "microsoft.servicebus/namespaces":
            # Bug #38: Service Bus Namespace requires SKU (case-insensitive)
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})
            sku_name = sku.get("name", "Standard") if sku else "Standard"

            resource_config["sku"] = sku_name
            logger.debug(f"Bug #38: Service Bus '{resource_name}' using SKU '{sku_name}'")

        elif azure_type_lower == "microsoft.eventhub/namespaces":
            # EventHub namespaces require sku argument (case-insensitive)
            properties = self._parse_properties(resource)
            sku = properties.get("sku", {})

            # Extract sku name, default to Standard if not found
            sku_name = sku.get("name", "Standard") if sku else "Standard"

            resource_config["sku"] = sku_name

            # Optionally add capacity if present in sku
            if sku and "capacity" in sku:
                resource_config["capacity"] = sku["capacity"]

        elif azure_type_lower == "microsoft.kusto/clusters":
            # Kusto clusters require sku block (case-insensitive)
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

        elif azure_type_lower == "microsoft.keyvault/vaults":
            # Extract tenant_id from multiple sources with proper fallback (case-insensitive)
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
            # Bug #32 fix: Sanitize UPN to remove spaces
            raw_upn = resource.get("userPrincipalName", f"{resource_name}@example.com")
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "user_principal_name": self._sanitize_user_principal_name(raw_upn),
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
            # Bug #43: Try multiple field names for applicationId to find the client_id
            app_id = (
                resource.get("applicationId")
                or resource.get("appId")
                or resource.get("client_id")
            )

            # Skip Service Principal if no applicationId found (Bug #43)
            if not app_id:
                logger.warning(
                    f"Skipping Service Principal '{resource_name}': No applicationId found. "
                    f"Available keys: {list(resource.keys())}"
                )
                return None

            resource_config = {
                "client_id": app_id,
            }
            if "displayName" in resource:
                resource_config["display_name"] = resource["displayName"]
        elif azure_type == "Microsoft.ManagedIdentity/managedIdentities":
            # Managed Identity specific properties
            resource_config = {
                "name": resource_name,
                "location": location,
                "resource_group_name": resource.get("resource_group"),
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

            # Bug #12 fix: Validate parent storage account exists in terraform_config
            # Private endpoints reference storage accounts that may have been filtered
            if resource_config and "private_service_connection" in resource_config:
                for conn in resource_config["private_service_connection"]:
                    target_id = conn.get("private_connection_resource_id", "")
                    if "/storageAccounts/" in target_id:
                        # Extract storage account name
                        storage_name = self._extract_resource_name_from_id(
                            target_id, "storageAccounts"
                        )
                        storage_name_safe = self._sanitize_terraform_name(storage_name)

                        # Check if storage account was emitted
                        if "azurerm_storage_account" not in terraform_config.get(
                            "resource", {}
                        ) or storage_name_safe not in terraform_config["resource"].get(
                            "azurerm_storage_account", {}
                        ):
                            logger.warning(
                                f"Private Endpoint '{resource_name}' references storage account '{storage_name}' "
                                f"that doesn't exist or was filtered out. Skipping endpoint."
                            )
                            return None
        elif azure_type == "Microsoft.Network/privateDnsZones":
            # Private DNS Zone specific properties
            resource_config = emit_private_dns_zone(resource)
        elif azure_type == "Microsoft.Network/privateDnsZones/virtualNetworkLinks":
            # Private DNS Zone Virtual Network Link specific properties
            # Need to build set of available VNets and DNS Zones for validation
            available_vnets = (
                self._available_resources.get("azurerm_virtual_network", set())
                if self._available_resources
                else set()
            )
            available_dns_zones = (
                self._available_resources.get("azurerm_private_dns_zone", set())
                if self._available_resources
                else set()
            )
            missing_references = getattr(self, "_missing_references", [])
            resource_config = emit_private_dns_zone_vnet_link(
                resource,
                sanitize_name_fn=self._sanitize_terraform_name,
                extract_name_fn=self._extract_resource_name_from_id,
                available_vnets=available_vnets,
                available_dns_zones=available_dns_zones,
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

            # Bug #33: Improved OS type detection with explicit fallback
            kind = properties.get("kind", "").lower()
            if "linux" in kind:
                os_type = "Linux"
            elif "windows" in kind:
                os_type = "Windows"
            else:
                # Check for other indicators (reserved=true means Linux)
                os_type = "Linux" if properties.get("reserved") else "Windows"
                logger.debug(
                    f"Bug #33: App Service Plan '{resource_name}' has unclear OS type from kind='{kind}', "
                    f"using os_type='{os_type}' based on 'reserved' property"
                )

            # Bug #33: Validate SKU before setting
            raw_sku = sku.get("name", "B1")
            validated_sku = self._validate_app_service_sku(raw_sku, location, os_type)

            resource_config.update(
                {
                    "os_type": os_type,
                    "sku_name": validated_sku,
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

                # Validate that the VM resource was actually emitted to terraform_config
                # (Bug #11 fix: Check actual emitted VMs, not just first-pass index)
                # Extensions are processed after VMs in dependency order, so parent VM
                # will already be in terraform_config if it wasn't filtered out
                vm_exists = False
                vm_terraform_type = None
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
                        f"that doesn't exist or was filtered out. Skipping extension."
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

        elif azure_type_lower == "microsoft.compute/virtualmachines/runcommands":
            # Bug #44: VM Run Commands (22 resources!)
            # Extract parent VM name from run command ID
            rc_id = resource.get("id", "") or resource.get("original_id", "")
            vm_name = self._extract_resource_name_from_id(rc_id, "virtualMachines")

            if vm_name == "unknown":
                logger.warning(f"Bug #44: Run Command '{resource_name}' has no parent VM. Skipping.")
                return None

            vm_name_safe = self._sanitize_terraform_name(vm_name)

            # Validate that the parent VM was actually converted to Terraform config
            # VM could have been skipped if it had missing NICs or other validation errors
            vm_exists = False
            vm_terraform_type = None
            for vm_type in [
                "azurerm_linux_virtual_machine",
                "azurerm_windows_virtual_machine",
            ]:
                if (
                    vm_type in terraform_config.get("resource", {})
                    and vm_name_safe in terraform_config["resource"][vm_type]
                ):
                    vm_exists = True
                    vm_terraform_type = vm_type
                    break

            if not vm_exists:
                logger.warning(
                    f"VM Run Command '{resource_name}' references parent VM '{vm_name}' "
                    f"that doesn't exist or was filtered out during conversion. Skipping run command."
                )
                return None

            properties = self._parse_properties(resource)

            # Extract just command name (e.g., "vm/Get-AzureADToken" -> "Get-AzureADToken")
            command_name = resource_name.split("/")[-1] if "/" in resource_name else resource_name

            # Run command requires name, location, VM ID and source script
            resource_config = {
                "name": command_name,
                "location": location,
                "virtual_machine_id": f"${{{vm_terraform_type}.{vm_name_safe}.id}}",
                "source": {
                    "script": properties.get("source", {}).get("script", "# Placeholder script")
                }
            }
            logger.debug(f"Bug #44: Run Command '{resource_name}' linked to VM '{vm_name}' (type: {vm_terraform_type})")

        elif azure_type_lower == "microsoft.app/managedenvironments":
            # Bug #44: Container App Environment (10 resources!)
            # Bug #50: SKIP workspace_id entirely - field contains GUID (customerId), not full resource ID
            properties = self._parse_properties(resource)

            # DO NOT include log_analytics_workspace_id:
            # The appLogsConfiguration.logAnalyticsConfiguration.customerId field contains only
            # the workspace GUID, NOT the full Azure resource ID that Terraform requires.
            # Expected format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.OperationalInsights/workspaces/{name}
            # Actual format in properties: {workspace-guid}
            # Since we cannot construct the full resource ID from a GUID, we skip this field entirely.
            # Note: workspace_id is optional per Terraform azurerm_container_app_environment docs

            workspace_id = properties.get("appLogsConfiguration", {}).get("logAnalyticsConfiguration", {}).get("customerId")
            if workspace_id:
                logger.warning(
                    f"Bug #50: Skipping log_analytics_workspace_id for Container App Environment '{resource_name}' - "
                    f"field contains GUID '{workspace_id}' instead of full resource ID. "
                    f"Workspace linking is optional and will be configured separately if needed."
                )

            logger.debug(f"Bug #44/50: Container App Environment '{resource_name}' (workspace_id skipped)")

        elif azure_type_lower == "microsoft.operationalinsights/workspaces":
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
        elif azure_type_lower == "microsoft.insights/components":
            # Bug #39: Application Insights (case-insensitive match)
            properties = self._parse_properties(resource)

            # Application Insights requires a workspace ID or uses legacy mode
            application_type = properties.get("Application_Type") or properties.get("application_type") or properties.get("applicationType") or "web"

            resource_config.update(
                {
                    "application_type": application_type,
                }
            )
            logger.debug(f"Bug #39: App Insights '{resource_name}' using type '{application_type}'")

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
                resource.get("subscription_id", "00000000-0000-0000-0000-000000000000")
                lab_virtual_network_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/Microsoft.DevTestLab/labs/{lab_name}/virtualnetworks/{lab_name}Vnet"

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

            # Translate scope resource IDs to use target subscription in cross-tenant scenarios
            translated_scope_ids = []
            for scope_id in scope_resource_ids:
                parts = scope_id.split("/")
                if len(parts) >= 9:
                    # Reconstruct with target subscription ID
                    # Format: /subscriptions/{sid}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
                    rg_name = parts[4]
                    provider = parts[6]
                    resource_type = parts[7]
                    resource_name = parts[8] if len(parts) > 8 else ""
                    translated_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/{provider}/{resource_type}/{resource_name}"
                    translated_scope_ids.append(translated_id)
                    logger.debug(
                        f"Translated scope resource ID from {scope_id} to {translated_id}"
                    )
                else:
                    # Keep original if can't parse
                    logger.warning(
                        f"Could not parse scope resource ID (unexpected format): {scope_id}, using original"
                    )
                    translated_scope_ids.append(scope_id)

            # Keep severity in Azure format (Sev0-Sev4) - Terraform expects this format
            severity = properties.get("severity", "Sev3")

            # Get frequency (check interval)
            frequency = properties.get("frequency", "PT1M")

            resource_config.update(
                {
                    "detector_type": detector_id,
                    "scope_resource_ids": translated_scope_ids
                    if translated_scope_ids
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
                        parts[2]
                        rg_name = parts[4]
                        ag_name = parts[8] if len(parts) > 8 else ""
                        formatted_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/microsoft.insights/actionGroups/{ag_name}"
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
            resource.get("subscription_id", "00000000-0000-0000-0000-000000000000")

            # Storage account ID (required)
            storage_account_id = properties.get("storageAccount")
            if not storage_account_id:
                # Create placeholder - should be replaced with actual storage account reference
                storage_account_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/Microsoft.Storage/storageAccounts/mlworkspace{resource_name[:8]}"
            else:
                # Normalize casing in resource ID
                storage_account_id = self._normalize_resource_id(storage_account_id)

            # Key Vault ID (required)
            key_vault_id = properties.get("keyVault")
            if not key_vault_id:
                # Create placeholder
                key_vault_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/Microsoft.KeyVault/vaults/mlworkspace{resource_name[:8]}"
            else:
                # Normalize casing in resource ID (Microsoft.Keyvault -> Microsoft.KeyVault)
                key_vault_id = self._normalize_resource_id(key_vault_id)

            # Application Insights ID (required)
            application_insights_id = properties.get("applicationInsights")
            if not application_insights_id:
                # Create placeholder - note: provider must be Microsoft.Insights (capital M and I)
                application_insights_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/Microsoft.Insights/components/mlworkspace{resource_name[:8]}"
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
            resource.get("subscription_id", "00000000-0000-0000-0000-000000000000")

            # Construct workspace ID
            machine_learning_workspace_id = f"/subscriptions/{self._get_effective_subscription_id(resource)}/resourceGroups/{rg_name}/providers/Microsoft.MachineLearningServices/workspaces/{workspace_name}"

            resource_config.update(
                {
                    "machine_learning_workspace_id": machine_learning_workspace_id,
                    "virtual_machine_size": properties.get("vmSize", "STANDARD_DS3_V2"),
                    # Compute instance expects "name" to be the instance name
                }
            )

            # Override name to just be the endpoint name
            resource_config["name"] = endpoint_name

        elif azure_type_lower == "microsoft.insights/actiongroups":
            # Bug #40: Monitor Action Group (case-insensitive match)
            properties = self._parse_properties(resource)

            # short_name is required (max 12 characters)
            short_name = properties.get("groupShortName") or properties.get("short_name") or resource_name[:12]

            resource_config.update(
                {
                    "short_name": short_name,
                }
            )
            logger.debug(f"Bug #40: Action Group '{resource_name}' using short_name '{short_name}'")

        elif azure_type_lower == "microsoft.documentdb/databaseaccounts":
            # Bug #41: Cosmos DB account (case-insensitive match)
            properties = self._parse_properties(resource)

            # Required: offer_type
            resource_config["offer_type"] = "Standard"

            # Required: consistency_policy block
            consistency = properties.get("consistencyPolicy", {})
            resource_config["consistency_policy"] = {
                "consistency_level": consistency.get("defaultConsistencyLevel", "Session"),
                "max_interval_in_seconds": consistency.get("maxIntervalInSeconds", 5),
                "max_staleness_prefix": consistency.get("maxStalenessPrefix", 100),
            }

            # Required: geo_location block
            locations = properties.get("locations", [])
            if locations:
                resource_config["geo_location"] = [
                    {
                        "location": loc.get("locationName", location).lower(),
                        "failover_priority": loc.get("failoverPriority", 0),
                    }
                    for loc in locations
                ]
            else:
                # Default to resource location
                resource_config["geo_location"] = [
                    {"location": location, "failover_priority": 0}
                ]

            logger.debug(f"Bug #41: Cosmos DB '{resource_name}' with {len(resource_config.get('geo_location', []))} locations")

        elif azure_type_lower == "microsoft.containerinstance/containergroups":
            # Bug #42: Container Group (case-insensitive match)
            properties = self._parse_properties(resource)

            # Required: os_type
            os_properties = properties.get("osType", "Linux")
            resource_config["os_type"] = os_properties

            # Required: container block (at least one)
            containers = properties.get("containers", [])
            if containers and len(containers) > 0:
                container = containers[0]  # Use first container
                resource_config["container"] = {
                    "name": container.get("name", "container"),
                    "image": container.get("image", "mcr.microsoft.com/azuredocs/aci-helloworld:latest"),
                    "cpu": str(container.get("resources", {}).get("requests", {}).get("cpu", "0.5")),
                    "memory": str(container.get("resources", {}).get("requests", {}).get("memoryInGB", "1.5")),
                }
            else:
                # Default container if none specified
                resource_config["container"] = {
                    "name": "container",
                    "image": "mcr.microsoft.com/azuredocs/aci-helloworld:latest",
                    "cpu": "0.5",
                    "memory": "1.5",
                }

            logger.debug(f"Bug #42: Container Group '{resource_name}' os_type='{os_properties}'")

        elif azure_type_lower == "microsoft.network/applicationgatewaywebapplicationfirewallpolicies":
            # WAF Policy (Web Application Firewall Policy)
            properties = self._parse_properties(resource)

            # Required: managed_rules block
            resource_config["managed_rules"] = {
                "managed_rule_set": [
                    {
                        "type": "OWASP",
                        "version": "3.2"
                    }
                ]
            }

            # Optional: policy_settings
            if properties.get("policySettings"):
                settings = properties["policySettings"]
                resource_config["policy_settings"] = {
                    "enabled": settings.get("state", "Enabled") == "Enabled",
                    "mode": settings.get("mode", "Detection")
                }

            logger.debug(f"WAF Policy '{resource_name}' configured with OWASP 3.2")

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

            # Get scope and translate subscription ID for cross-tenant deployments
            scope = properties.get("scope", resource.get("scope", ""))

            # If we have a target subscription, translate subscription IDs in the scope
            if self.target_subscription_id and scope:
                # Replace source subscription ID with target subscription ID in scope
                # Scope formats:
                #   - /subscriptions/{sub-id}/resourceGroups/... (resource-level, with slash)
                #   - /subscriptions/{sub-id} (subscription-level, no trailing slash)
                import re

                scope = re.sub(
                    r"/subscriptions/[a-f0-9-]+(/|$)",
                    f"/subscriptions/{self.target_subscription_id}\\1",
                    scope,
                    flags=re.IGNORECASE,
                )
                logger.debug(
                    "Translated role assignment scope for cross-tenant deployment"
                )

            # Also translate role definition ID (contains subscription)
            role_def_id = properties.get(
                "roleDefinitionId", resource.get("roleDefinitionId", "")
            )
            if self.target_subscription_id and role_def_id:
                role_def_id = re.sub(
                    r"/subscriptions/[a-f0-9-]+/",
                    f"/subscriptions/{self.target_subscription_id}/",
                    role_def_id,
                    flags=re.IGNORECASE,
                )

            principal_id = properties.get(
                "principalId", resource.get("principalId", "")
            )

            # Bug #18 fix: Skip role assignments with untranslated principals in cross-tenant mode
            # Without identity mapping, principal_ids from source tenant don't exist in target tenant
            # Azure hangs indefinitely trying to create role assignments for non-existent principals
            if self.target_tenant_id and not self.identity_mapping:
                # Cross-tenant mode without identity mapping - skip ALL role assignments
                logger.warning(
                    f"Skipping role assignment '{resource_name}' in cross-tenant mode: "
                    f"No identity mapping provided. Principal ID '{principal_id}' from source "
                    f"tenant cannot be validated in target tenant. Use --identity-mapping-file "
                    f"to translate principals across tenants."
                )
                return None

            resource_config = {
                "scope": scope,
                "role_definition_id": role_def_id,
                "principal_id": principal_id,
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

                        # Check if the workspace exists in the graph
                        if not self._workspace_exists_in_graph(workspace_resource_id):
                            logger.warning(
                                f"Data Collection Rule '{resource_name}' references non-existent "
                                f"Log Analytics workspace: {workspace_resource_id}. "
                                f"Skipping this DCR as the workspace is not in the graph."
                            )
                            # Skip this entire DCR by returning None early
                            return None

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
        elif azure_type_lower in ["user", "microsoft.aad/user", "microsoft.graph/users"]:
            # Entra ID User (case-insensitive)
            # Users from Neo4j may have different property names than ARM resources
            raw_upn = resource.get("userPrincipalName") or resource.get(
                "name", "unknown"
            )
            # Bug #32 fix: Sanitize UPN to remove spaces
            user_principal_name = self._sanitize_user_principal_name(raw_upn)

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
            logger.debug(f"Entra ID User '{user_principal_name}' generated")

            # Optionally add other properties if present
            if resource.get("accountEnabled") is not None:
                resource_config["account_enabled"] = resource.get("accountEnabled")

        elif azure_type_lower in ["group", "microsoft.aad/group", "microsoft.graph/groups"]:
            # Entra ID Group (case-insensitive)
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

        elif azure_type_lower in [
            "serviceprincipal",
            "microsoft.aad/serviceprincipal",
            "microsoft.graph/serviceprincipals",
        ]:
            # Entra ID Service Principal (case-insensitive)
            # Bug #43: Try multiple field names for appId to find the client_id
            app_id = (
                resource.get("appId")
                or resource.get("application_id")
                or resource.get("applicationId")
                or resource.get("client_id")
            )

            # Skip Service Principal if no appId found (Bug #43)
            if not app_id:
                logger.warning(
                    f"Skipping Service Principal '{resource_name}': No appId found. "
                    f"Available keys: {list(resource.keys())}"
                )
                return None

            display_name = (
                resource.get("displayName")
                or resource.get("display_name")
                or resource.get("name", "unknown")
            )

            resource_config = {
                "client_id": app_id,
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

        elif azure_type == "Microsoft.ContainerRegistry/registries":
            # Container Registry requires SKU
            properties = self._parse_properties(resource)
            # Extract SKU from properties or use default
            sku_obj = properties.get("sku", {})
            sku_name = sku_obj.get("name") if isinstance(sku_obj, dict) else sku_obj
            if not sku_name:
                sku_name = resource.get("sku", "Basic")

            resource_config.update(
                {
                    "sku": sku_name if sku_name else "Basic",
                }
            )

            # Add admin_enabled if present
            if "adminUserEnabled" in properties:
                resource_config["admin_enabled"] = properties.get(
                    "adminUserEnabled", False
                )

        elif azure_type == "Microsoft.App/containerApps":
            # Container Apps require environment, revision mode, and template
            # For now, skip Container Apps as they require complex environment references
            # This will be handled in a future iteration
            logger.warning(
                f"Skipping Container App '{resource_name}' - Container Apps require "
                f"complex environment and template configuration that is not yet supported. "
                f"Add support for Microsoft.App/managedEnvironments first."
            )
            return None

        elif azure_type == "Microsoft.ContainerService/managedClusters":
            # AKS Clusters require default_node_pool configuration
            properties = self._parse_properties(resource)
            agent_pools = properties.get("agentPoolProfiles", [])

            if agent_pools:
                first_pool = agent_pools[0]
                # Extract node pool configuration
                node_pool = {
                    "name": first_pool.get("name", "default"),
                    "vm_size": first_pool.get("vmSize", "Standard_DS2_v2"),
                    "node_count": first_pool.get("count", 1),
                }

                # Add optional node pool properties
                if "vnetSubnetId" in first_pool:
                    node_pool["vnet_subnet_id"] = first_pool["vnetSubnetId"]
                if "osDiskSizeGB" in first_pool:
                    node_pool["os_disk_size_gb"] = first_pool["osDiskSizeGB"]
                if "maxPods" in first_pool:
                    node_pool["max_pods"] = first_pool["maxPods"]

                resource_config["default_node_pool"] = node_pool
            else:
                # Skip AKS clusters without node pools
                logger.warning(
                    f"Skipping AKS cluster '{resource_name}' - no agent pool profiles found in properties"
                )
                return None

            # Add DNS prefix (required)
            dns_prefix = properties.get("dnsPrefix") or resource_name.lower()
            resource_config["dns_prefix"] = dns_prefix

            # Add identity (required - AKS clusters must have either identity or service_principal)
            # Prefer SystemAssigned identity (modern approach)
            identity = properties.get("identity", {})
            identity_type = identity.get("type", "").lower() if identity else ""

            if "systemassigned" in identity_type or not identity:
                # Use SystemAssigned if present or if no identity specified (safer default)
                resource_config["identity"] = {"type": "SystemAssigned"}
            # Note: UserAssigned identities and service principals require additional configuration

        elif azure_type == "Microsoft.Compute/snapshots":
            # Snapshots require create_option and source_resource_id
            properties = self._parse_properties(resource)

            # create_option is required: "Copy" for snapshots
            resource_config["create_option"] = properties.get("creationData", {}).get(
                "createOption", "Copy"
            )

            # source_resource_id might be present
            source_resource_id = properties.get("creationData", {}).get(
                "sourceResourceId"
            )
            if source_resource_id:
                resource_config["source_resource_id"] = source_resource_id

            # disk_size_gb
            disk_size_gb = properties.get("diskSizeGB") or resource.get("diskSizeGB")
            if disk_size_gb:
                resource_config["disk_size_gb"] = disk_size_gb

        elif azure_type == "Microsoft.Compute/virtualMachineScaleSets":
            # VM Scale Sets require complex configuration
            properties = self._parse_properties(resource)

            # Extract VM profile
            vm_profile = properties.get("virtualMachineProfile", {})
            os_profile = vm_profile.get("osProfile", {})
            storage_profile = vm_profile.get("storageProfile", {})
            network_profile = vm_profile.get("networkProfile", {})

            # Admin username (required)
            admin_username = os_profile.get("adminUsername", "azureuser")
            resource_config["admin_username"] = admin_username

            # SKU (required)
            sku_obj = properties.get("sku", {})
            sku_name = sku_obj.get("name") if isinstance(sku_obj, dict) else sku_obj
            if not sku_name:
                sku_name = resource.get("sku", "Standard_DS2_v2")
            resource_config["sku"] = sku_name

            # Instances (optional, defaults from sku.capacity)
            instances = sku_obj.get("capacity", 1) if isinstance(sku_obj, dict) else 1
            resource_config["instances"] = instances

            # OS disk (required block)
            os_disk = storage_profile.get("osDisk", {})
            resource_config["os_disk"] = {
                "caching": os_disk.get("caching", "ReadWrite"),
                "storage_account_type": os_disk.get("managedDisk", {}).get(
                    "storageAccountType", "Standard_LRS"
                ),
            }

            # Network interface (required block)
            network_interfaces = network_profile.get(
                "networkInterfaceConfigurations", []
            )
            if network_interfaces:
                first_nic = network_interfaces[0]
                ip_configs = first_nic.get("ipConfigurations", [])
                if ip_configs:
                    first_ip_config = ip_configs[0]
                    resource_config["network_interface"] = [
                        {
                            "name": first_nic.get("name", "default"),
                            "primary": first_nic.get("primary", True),
                            "ip_configuration": [
                                {
                                    "name": first_ip_config.get("name", "internal"),
                                    "primary": first_ip_config.get("primary", True),
                                    "subnet_id": first_ip_config.get("subnet", {}).get(
                                        "id", ""
                                    ),
                                }
                            ],
                        }
                    ]
                else:
                    # No IP config - skip this VMSS
                    logger.warning(
                        f"Skipping VM Scale Set '{resource_name}' - no IP configurations found"
                    )
                    return None
            else:
                # No network interfaces - skip
                logger.warning(
                    f"Skipping VM Scale Set '{resource_name}' - no network interface configurations found"
                )
                return None

            # Source image reference
            image_reference = storage_profile.get("imageReference", {})
            if image_reference:
                resource_config["source_image_reference"] = {
                    "publisher": image_reference.get("publisher", "Canonical"),
                    "offer": image_reference.get(
                        "offer", "0001-com-ubuntu-server-jammy"
                    ),
                    "sku": image_reference.get("sku", "22_04-lts"),
                    "version": image_reference.get("version", "latest"),
                }

        elif azure_type == "Microsoft.Cache/Redis":
            # Redis Cache requires SKU configuration
            properties = self._parse_properties(resource)

            # Extract SKU - can be at top level or in properties
            sku_obj = properties.get("sku", resource.get("sku", {}))
            if isinstance(sku_obj, dict):
                sku_name = sku_obj.get("name", "Basic")
                capacity = sku_obj.get("capacity", 0)
                family = sku_obj.get("family", "C")
            else:
                # SKU might be string or missing
                sku_name = "Basic"
                capacity = 0
                family = "C"

            # Validate SKU
            if not capacity or capacity == 0:
                logger.warning(
                    f"Skipping Redis Cache '{resource_name}' - invalid SKU capacity: {capacity}"
                )
                return None

            resource_config.update(
                {
                    "capacity": capacity,
                    "sku_name": sku_name,
                    "family": family,
                }
            )

            # Note: enable_non_ssl_port and minimum_tls_version are not valid azurerm_redis_cache arguments
            # These are managed through redis_configuration block or other mechanisms

        elif azure_type == "Microsoft.Insights/metricalerts":
            # Metric Alerts require scopes and don't have location
            properties = self._parse_properties(resource)

            # Extract scopes (required - list of resource IDs to monitor)
            scopes = properties.get("scopes", [])
            if not scopes:
                logger.warning(
                    f"Skipping metric alert '{resource_name}' - no scopes found in properties"
                )
                return None

            # Remove location from resource_config (metric alerts are global)
            resource_config.pop("location", None)

            resource_config.update(
                {
                    "scopes": scopes,
                    "severity": properties.get("severity", 3),
                    "enabled": properties.get("enabled", True),
                    "frequency": properties.get("evaluationFrequency", "PT1M"),
                    "window_size": properties.get("windowSize", "PT5M"),
                }
            )

            # Add criteria (simplified - use dynamic_criteria or criteria)
            criteria = properties.get("criteria", {})
            if criteria:
                # For now, add as a simple criteria block
                # Full implementation would parse allOf, anyOf, etc.
                resource_config["criteria"] = [
                    {
                        "metric_namespace": criteria.get("odata.type", "").replace(
                            "Microsoft.Azure.Monitor.", ""
                        ),
                        "metric_name": "Percentage CPU",  # Default - should extract from criteria
                        "aggregation": "Average",
                        "operator": "GreaterThan",
                        "threshold": 80,
                    }
                ]
            else:
                # Skip alerts without criteria
                logger.warning(
                    f"Skipping metric alert '{resource_name}' - no criteria found"
                )
                return None

        elif azure_type == "Microsoft.Network/applicationGateways":
            # Application Gateway requires complex nested configuration blocks
            properties = self._parse_properties(resource)

            # Required: sku block
            sku = properties.get("sku", {})
            sku_name = sku.get("name", "Standard_v2") if isinstance(sku, dict) else "Standard_v2"
            sku_tier = sku.get("tier", "Standard_v2") if isinstance(sku, dict) else "Standard_v2"
            sku_capacity = sku.get("capacity", 2) if isinstance(sku, dict) else 2

            resource_config["sku"] = [{
                "name": sku_name,
                "tier": sku_tier,
                "capacity": sku_capacity
            }]

            # Required: gateway_ip_configuration block
            # Get gateway IP configurations from properties
            gateway_ip_configs = properties.get("gatewayIPConfigurations", [])
            if gateway_ip_configs:
                gateway_ip_config = gateway_ip_configs[0] if isinstance(gateway_ip_configs, list) else {}
                if isinstance(gateway_ip_config, dict):
                    gateway_ip_name = gateway_ip_config.get("name", "gateway-ip-config")
                    gateway_ip_props = gateway_ip_config.get("properties", {})
                    subnet_id = gateway_ip_props.get("subnet", {}).get("id", "")
                else:
                    gateway_ip_name = "gateway-ip-config"
                    subnet_id = ""
            else:
                gateway_ip_name = "gateway-ip-config"
                subnet_id = ""

            # Resolve subnet reference - SKIP AppGW if subnet not found
            if not subnet_id:
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': No subnet ID found in gatewayIPConfigurations"
                )
                return None

            subnet_reference = self._resolve_subnet_reference(subnet_id, resource_name)
            if subnet_reference is None:
                # _resolve_subnet_reference returns None when subnet doesn't exist in graph
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': Cannot resolve subnet reference '{subnet_id}'"
                )
                return None

            resource_config["gateway_ip_configuration"] = [{
                "name": gateway_ip_name,
                "subnet_id": subnet_reference
            }]

            # Required: frontend_ip_configuration block
            frontend_ip_configs = properties.get("frontendIPConfigurations", [])
            if not frontend_ip_configs:
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': No frontendIPConfigurations found"
                )
                return None

            frontend_ip_config = frontend_ip_configs[0] if isinstance(frontend_ip_configs, list) else {}
            if not isinstance(frontend_ip_config, dict):
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': Invalid frontendIPConfiguration format"
                )
                return None

            frontend_ip_name = frontend_ip_config.get("name", "frontend-ip-config")
            frontend_ip_props = frontend_ip_config.get("properties", {})

            # Check for public IP - SKIP AppGW if not found or cannot be resolved
            public_ip_id = frontend_ip_props.get("publicIPAddress", {}).get("id", "")
            if not public_ip_id:
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': No public IP ID found in frontendIPConfiguration"
                )
                return None

            public_ip_name = self._extract_resource_name_from_id(public_ip_id, "publicIPAddresses")
            if public_ip_name == "unknown":
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': Cannot extract public IP name from ID '{public_ip_id}'"
                )
                return None

            public_ip_name_safe = self._sanitize_terraform_name(public_ip_name)
            if not self._validate_resource_reference("azurerm_public_ip", public_ip_name_safe):
                logger.warning(
                    f"Skipping Application Gateway '{resource_name}': Public IP '{public_ip_name}' does not exist in graph"
                )
                return None

            frontend_ip_block = {
                "name": frontend_ip_name,
                "public_ip_address_id": f"${{azurerm_public_ip.{public_ip_name_safe}.id}}"
            }

            resource_config["frontend_ip_configuration"] = [frontend_ip_block]

            # Required: frontend_port block
            frontend_ports = properties.get("frontendPorts", [])
            if frontend_ports:
                frontend_port_blocks = []
                for port_config in frontend_ports:
                    if isinstance(port_config, dict):
                        port_name = port_config.get("name", "frontend-port-80")
                        port_props = port_config.get("properties", {})
                        port_num = port_props.get("port", 80)
                    else:
                        port_name = "frontend-port-80"
                        port_num = 80
                    frontend_port_blocks.append({
                        "name": port_name,
                        "port": port_num
                    })
                resource_config["frontend_port"] = frontend_port_blocks
            else:
                resource_config["frontend_port"] = [{
                    "name": "frontend-port-80",
                    "port": 80
                }]

            # Required: backend_address_pool block
            backend_pools = properties.get("backendAddressPools", [])
            if backend_pools:
                backend_pool_blocks = []
                for pool_config in backend_pools:
                    if isinstance(pool_config, dict):
                        pool_name = pool_config.get("name", "backend-pool")
                    else:
                        pool_name = "backend-pool"
                    backend_pool_blocks.append({
                        "name": pool_name
                    })
                resource_config["backend_address_pool"] = backend_pool_blocks
            else:
                resource_config["backend_address_pool"] = [{
                    "name": "backend-pool"
                }]

            # Required: backend_http_settings block
            backend_http_settings = properties.get("backendHttpSettingsCollection", [])
            if backend_http_settings:
                backend_http_blocks = []
                for http_settings in backend_http_settings:
                    if isinstance(http_settings, dict):
                        settings_name = http_settings.get("name", "backend-http-settings")
                        settings_props = http_settings.get("properties", {})
                        port = settings_props.get("port", 80)
                        protocol = settings_props.get("protocol", "Http")
                        cookie_affinity = settings_props.get("cookieBasedAffinity", "Disabled")
                        request_timeout = settings_props.get("requestTimeout", 60)
                    else:
                        settings_name = "backend-http-settings"
                        port = 80
                        protocol = "Http"
                        cookie_affinity = "Disabled"
                        request_timeout = 60
                    backend_http_blocks.append({
                        "name": settings_name,
                        "cookie_based_affinity": cookie_affinity,
                        "port": port,
                        "protocol": protocol,
                        "request_timeout": request_timeout
                    })
                resource_config["backend_http_settings"] = backend_http_blocks
            else:
                resource_config["backend_http_settings"] = [{
                    "name": "backend-http-settings",
                    "cookie_based_affinity": "Disabled",
                    "port": 80,
                    "protocol": "Http",
                    "request_timeout": 60
                }]

            # Required: http_listener block
            http_listeners = properties.get("httpListeners", [])
            if http_listeners:
                http_listener_blocks = []
                for listener in http_listeners:
                    if isinstance(listener, dict):
                        listener_name = listener.get("name", "http-listener")
                        listener_props = listener.get("properties", {})
                        frontend_ip_config_name = listener_props.get("frontendIPConfiguration", {}).get("id", "")
                        if frontend_ip_config_name:
                            frontend_ip_config_name = self._extract_resource_name_from_id(
                                frontend_ip_config_name, "frontendIPConfigurations"
                            )
                        else:
                            frontend_ip_config_name = "frontend-ip-config"
                        frontend_port_name = listener_props.get("frontendPort", {}).get("id", "")
                        if frontend_port_name:
                            frontend_port_name = self._extract_resource_name_from_id(
                                frontend_port_name, "frontendPorts"
                            )
                        else:
                            frontend_port_name = "frontend-port-80"
                        protocol = listener_props.get("protocol", "Http")
                    else:
                        listener_name = "http-listener"
                        frontend_ip_config_name = "frontend-ip-config"
                        frontend_port_name = "frontend-port-80"
                        protocol = "Http"
                    http_listener_blocks.append({
                        "name": listener_name,
                        "frontend_ip_configuration_name": frontend_ip_config_name,
                        "frontend_port_name": frontend_port_name,
                        "protocol": protocol
                    })
                resource_config["http_listener"] = http_listener_blocks
            else:
                resource_config["http_listener"] = [{
                    "name": "http-listener",
                    "frontend_ip_configuration_name": "frontend-ip-config",
                    "frontend_port_name": "frontend-port-80",
                    "protocol": "Http"
                }]

            # Required: request_routing_rule block
            routing_rules = properties.get("requestRoutingRules", [])
            if routing_rules:
                routing_rule_blocks = []
                priority = 100
                for rule in routing_rules:
                    if isinstance(rule, dict):
                        rule_name = rule.get("name", "routing-rule")
                        rule_props = rule.get("properties", {})
                        rule_type = rule_props.get("ruleType", "Basic")
                        http_listener_name = rule_props.get("httpListener", {}).get("id", "")
                        if http_listener_name:
                            http_listener_name = self._extract_resource_name_from_id(
                                http_listener_name, "httpListeners"
                            )
                        else:
                            http_listener_name = "http-listener"
                        backend_pool_name = rule_props.get("backendAddressPool", {}).get("id", "")
                        if backend_pool_name:
                            backend_pool_name = self._extract_resource_name_from_id(
                                backend_pool_name, "backendAddressPools"
                            )
                        else:
                            backend_pool_name = "backend-pool"
                        backend_http_settings_name = rule_props.get("backendHttpSettings", {}).get("id", "")
                        if backend_http_settings_name:
                            backend_http_settings_name = self._extract_resource_name_from_id(
                                backend_http_settings_name, "backendHttpSettingsCollection"
                            )
                        else:
                            backend_http_settings_name = "backend-http-settings"
                    else:
                        rule_name = "routing-rule"
                        rule_type = "Basic"
                        http_listener_name = "http-listener"
                        backend_pool_name = "backend-pool"
                        backend_http_settings_name = "backend-http-settings"
                    routing_rule_blocks.append({
                        "name": rule_name,
                        "rule_type": rule_type,
                        "http_listener_name": http_listener_name,
                        "backend_address_pool_name": backend_pool_name,
                        "backend_http_settings_name": backend_http_settings_name,
                        "priority": priority
                    })
                    priority += 1
                resource_config["request_routing_rule"] = routing_rule_blocks
            else:
                resource_config["request_routing_rule"] = [{
                    "name": "routing-rule",
                    "rule_type": "Basic",
                    "http_listener_name": "http-listener",
                    "backend_address_pool_name": "backend-pool",
                    "backend_http_settings_name": "backend-http-settings",
                    "priority": 100
                }]

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
            Sanitized name safe for Terraform (max 80 chars for Azure NICs)
        """
        # Replace invalid characters with underscores
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        # Bug #27 fix: Truncate to 80 chars max (Azure NIC name limit)
        # Keep first 75 chars + hash of full name for uniqueness
        if len(sanitized) > 80:
            import hashlib

            name_hash = hashlib.md5(sanitized.encode()).hexdigest()[:5]
            sanitized = sanitized[:74] + "_" + name_hash
            logger.debug(f"Truncated long name to 80 chars: ...{sanitized[-20:]}")

        return sanitized or "unnamed_resource"

    def _add_unique_suffix(self, name: str, resource_id: str, resource_type: str = None) -> str:
        """Add a unique suffix to globally unique resource names.

        Args:
            name: Original resource name
            resource_id: Azure resource ID (for deterministic hash generation)
            resource_type: Azure resource type (e.g., "Microsoft.ContainerRegistry/registries")

        Returns:
            Name with 6-character hash suffix appended
        """
        import hashlib

        # Generate deterministic hash from resource ID
        hash_suffix = hashlib.sha256(resource_id.encode()).hexdigest()[:6]

        # Container Registries don't allow dashes in names (alphanumeric only)
        if resource_type == "Microsoft.ContainerRegistry/registries":
            return f"{name}{hash_suffix}"  # No dash for Container Registry
        else:
            # Append suffix with hyphen for other types
            return f"{name}-{hash_suffix}"

    def _sanitize_user_principal_name(self, upn: str) -> str:
        """Sanitize user principal name to be a valid email address.

        Azure AD requires UPNs to be valid email addresses without special characters.
        Bug #32 fix: Remove spaces from UPNs to prevent validation errors.
        Additional fix: Replace parentheses with hyphens (e.g., User(DEX) -> User-DEX)

        Args:
            upn: User principal name (email format)

        Returns:
            Sanitized UPN with spaces removed and parentheses replaced with hyphens

        Example:
            >>> emitter._sanitize_user_principal_name("BrianHooper(DEX)@example.com")
            "BrianHooper-DEX@example.com"
            >>> emitter._sanitize_user_principal_name("User With Spaces@example.com")
            "UserWithSpaces@example.com"
        """
        if not upn or "@" not in upn:
            return upn

        # Split into local part and domain
        local_part, domain = upn.rsplit("@", 1)

        # Remove spaces from local part
        local_part = local_part.replace(" ", "")

        # Replace parentheses with hyphens (Bug fix for UPNs like "User(DEX)")
        local_part = local_part.replace("(", "-").replace(")", "")

        # Reconstruct UPN
        sanitized = f"{local_part}@{domain}"

        if sanitized != upn:
            logger.debug(f"Bug #32: Sanitized UPN '{upn}' -> '{sanitized}'")

        return sanitized

    def _validate_app_service_sku(
        self, sku_name: str, location: str, os_type: str
    ) -> str:
        """Validate App Service Plan SKU is compatible with region.

        Bug #33 fix: Prevents deployment errors from incompatible SKU/region combinations.

        Args:
            sku_name: SKU name from resource (e.g., "B1", "P1v2")
            location: Azure region (e.g., "eastus")
            os_type: OS type ("Linux" or "Windows")

        Returns:
            Validated SKU or safe fallback "B1"
        """
        # Validate SKU format (B1, S1, P1v2, F1, Y1, etc.)
        if not re.match(r"^[BSPFY]\d+v?\d*$", sku_name):
            logger.warning(
                f"Bug #33: Invalid SKU format '{sku_name}', using B1 fallback"
            )
            return "B1"

        # Known incompatible combinations (research-based)
        # v3 SKUs not available in all regions
        incompatible_skus = {
            "westeurope": ["P1v3", "P2v3", "P3v3"],
            "northeurope": ["P1v3", "P2v3", "P3v3"],
        }

        region_incompatible = incompatible_skus.get(location.lower(), [])
        if sku_name in region_incompatible:
            logger.warning(
                f"Bug #33: SKU '{sku_name}' not supported in '{location}', falling back to B1"
            )
            return "B1"

        return sku_name

    def _validate_subnet_cidr_containment(
        self, subnet_cidr: str, vnet_cidrs: list, resource_name: str
    ) -> bool:
        """Validate that subnet CIDR is contained within VNet address space.

        Bug #34 fix: Prevents NIC deployment errors from invalid subnet ranges.

        Args:
            subnet_cidr: Subnet CIDR (e.g., "10.0.1.0/24")
            vnet_cidrs: List of VNet CIDRs (e.g., ["10.0.0.0/16"])
            resource_name: Resource name for logging

        Returns:
            True if valid, False otherwise
        """
        import ipaddress

        try:
            subnet_network = ipaddress.ip_network(subnet_cidr, strict=False)

            for vnet_cidr in vnet_cidrs:
                try:
                    vnet_network = ipaddress.ip_network(vnet_cidr, strict=False)
                    if subnet_network.subnet_of(vnet_network):
                        return True
                except ValueError:
                    # Invalid VNet CIDR, skip it
                    continue

            logger.warning(
                f"Bug #34: NIC '{resource_name}' - Subnet CIDR '{subnet_cidr}' not contained "
                f"within any VNet CIDR {vnet_cidrs}"
            )
            return False

        except ValueError as e:
            logger.error(f"Bug #34: NIC '{resource_name}' - Invalid CIDR format: {e}")
            return False

    def _normalize_cidr_block(self, cidr: str, resource_name: str) -> Optional[str]:
        """Normalize CIDR block to ensure valid Azure format.

        Bug #35 fix: Prevents VNet deployment errors from malformed CIDRs.

        Args:
            cidr: Raw CIDR string (may be malformed, e.g., "172.19.20/22")
            resource_name: Resource name for logging

        Returns:
            Normalized CIDR (e.g., "172.19.0.0/22") or None if invalid
        """
        import ipaddress

        try:
            # Parse and normalize (strict=False allows "172.19.20/22" to be normalized)
            network = ipaddress.ip_network(cidr, strict=False)
            normalized = str(network)

            if normalized != cidr:
                logger.info(
                    f"Bug #35: VNet/Subnet '{resource_name}' - Normalized CIDR '{cidr}' → '{normalized}'"
                )

            return normalized

        except ValueError as e:
            logger.error(
                f"Bug #35: VNet/Subnet '{resource_name}' - Invalid CIDR '{cidr}': {e}"
            )
            return None

    def _workspace_exists_in_graph(self, workspace_resource_id: str) -> bool:
        """Check if a Log Analytics workspace exists in the graph.

        Args:
            workspace_resource_id: Azure resource ID of the workspace

        Returns:
            True if workspace exists in graph, False otherwise
        """
        if not workspace_resource_id or not hasattr(self, "_graph"):
            return False

        # Normalize the workspace ID for comparison
        normalized_workspace_id = self._normalize_azure_resource_id(
            workspace_resource_id
        ).lower()

        # Check if workspace exists in graph resources
        for resource in self._graph.resources:
            resource_type = resource.get("type", "")
            # Check for Log Analytics workspace types
            if resource_type.lower() in [
                "microsoft.operationalinsights/workspaces",
                "microsoft.operationalinsights/workspace",
            ]:
                # Check both id and original_id (for abstracted nodes)
                resource_id = (resource.get("id") or "").lower()
                original_id = (resource.get("original_id") or "").lower()

                if normalized_workspace_id in (resource_id, original_id):
                    return True

        return False

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
        self,
        terraform_type: str,
        resource_name: str,
        terraform_config: Dict[str, Any] = None,
    ) -> bool:
        """Validate that a referenced resource was actually emitted to terraform config.

        Bug #30 fix: Check terraform_config (actually emitted) not just graph (available).
        Resources may exist in graph but be skipped during emission (e.g., NICs with
        missing subnets in Bug #29).

        Args:
            terraform_type: Terraform resource type (e.g., "azurerm_network_interface")
            resource_name: Sanitized Terraform resource name
            terraform_config: Optional terraform config dict to check actual emission

        Returns:
            True if resource was emitted to config (if provided) or exists in graph
        """
        # Bug #30: Prefer terraform_config (actually emitted) over graph (available)
        if terraform_config:
            return (
                terraform_type in terraform_config.get("resource", {})
                and resource_name in terraform_config["resource"][terraform_type]
            )

        # Fallback to graph check (backward compatibility)
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

        # Bug #29: Validate subnet exists in the graph - return None if missing
        # This will cause parent NIC to be skipped (return None from _convert_resource)
        if scoped_subnet_name not in self._available_subnets:
            logger.error(
                f"Resource '{resource_name}' references subnet that doesn't exist in graph:\n"
                f"  Subnet Terraform name: {scoped_subnet_name}\n"
                f"  Subnet Azure name: {subnet_name}\n"
                f"  VNet Azure name: {vnet_name}\n"
                f"  Azure ID: {subnet_id}\n"
                f"  SKIPPING this resource to prevent validation errors."
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
            # Bug #29: Return None to signal parent resource should be skipped
            return None

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
            # Bug #49: Use original_id (real Azure ID) instead of id (abstracted hash)
            # In dual-graph: id="pe-a1b2c3d4" (hash), original_id="/subscriptions/.../..."
            resource_id = resource.get("original_id") or resource.get("id", "")
            if resource_id:
                match = resource_id_pattern.match(resource_id)
                if match:
                    subscription_id = match.group(1)
                    logger.debug(
                        f"Bug #49: Extracted source subscription ID from original_id: {subscription_id}"
                    )
                    return subscription_id

        logger.debug("Bug #49: Could not extract source subscription ID from resources")
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
