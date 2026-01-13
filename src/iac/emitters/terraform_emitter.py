"""Terraform emitter for Infrastructure-as-Code generation.

This module provides Terraform-specific template generation from
tenant graph data.
"""

import json
import logging
import re
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ..community_detector import CommunityDetector
from ..dependency_analyzer import DependencyAnalyzer
from ..resource_id_builder import AzureResourceIdBuilder
from ..translators import TranslationContext, TranslationCoordinator
from ..translators.private_endpoint_translator import PrivateEndpointTranslator
from ..traverser import TenantGraph
from ..validators import DependencyValidator, ResourceExistenceValidator
from . import register_emitter
from .base import IaCEmitter
from .terraform.context import EmitterContext
from .terraform.handlers import HandlerRegistry, ensure_handlers_registered

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
        # Track NIC NSG associations (similar to subnet NSG associations)
        # Format: [(nic_tf_name, nsg_tf_name, nic_name, nsg_name)]
        self._nic_nsg_associations: List[tuple[str, str, str, str]] = []
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
        self.import_strategy = (
            import_strategy or "all_resources"
        )  # Changed default from resource_groups
        self.credential = credential

        # Resource existence validator (Issue #422)
        self._existence_validator: Optional[ResourceExistenceValidator] = None

        # Generation metrics tracking (Issue #413)
        self._resource_count: int = 0
        self._files_created: int = 0

        # Import blocks tracking (Issue #412)
        self._import_blocks_generated: int = 0

        # Resource ID builder (Issue #502)
        self._resource_id_builder = AzureResourceIdBuilder(self)

        # Initialize attributes that tests expect to exist (Issue #296 - Standalone subnets)
        # These are also re-initialized in emit() but need to exist for direct _convert_resource() calls
        self._available_subnets: set = set()
        self._vnet_id_to_terraform_name: Dict[str, str] = {}
        self._graph: Optional[Any] = None

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

    def _normalize_azure_type(self, azure_type: str) -> str:
        """Normalize Azure resource type casing to match mapping keys.

        Azure API returns inconsistent casing (e.g., microsoft.insights vs Microsoft.Insights).
        This method normalizes to the canonical casing used in AZURE_TO_TERRAFORM_MAPPING.

        Args:
            azure_type: Azure resource type string (e.g., "microsoft.insights/components")

        Returns:
            Normalized azure_type with correct casing
        """
        # Provider namespace casing corrections
        provider_casing_map = {
            "microsoft.keyvault": "Microsoft.KeyVault",
            "Microsoft.Keyvault": "Microsoft.KeyVault",
            "microsoft.insights": "Microsoft.Insights",
            "Microsoft.insights": "Microsoft.Insights",
            "microsoft.operationalinsights": "Microsoft.OperationalInsights",
            "Microsoft.operationalinsights": "Microsoft.OperationalInsights",
            "Microsoft.operationalInsights": "Microsoft.OperationalInsights",
            "microsoft.operationalInsights": "Microsoft.OperationalInsights",
            "microsoft.documentdb": "Microsoft.DocumentDB",
            "Microsoft.documentdb": "Microsoft.DocumentDB",
            "Microsoft.DocumentDb": "Microsoft.DocumentDB",
            "microsoft.devtestlab": "Microsoft.DevTestLab",
            "Microsoft.devtestlab": "Microsoft.DevTestLab",
            "microsoft.alertsmanagement": "Microsoft.AlertsManagement",
            "Microsoft.alertsmanagement": "Microsoft.AlertsManagement",
            "microsoft.compute": "Microsoft.Compute",
            # Bug #66: Microsoft.Web support
            "microsoft.web": "Microsoft.Web",
            "Microsoft.web": "Microsoft.Web",
        }

        normalized_type = azure_type
        for incorrect, correct in provider_casing_map.items():
            if normalized_type.startswith(incorrect + "/"):
                normalized_type = correct + normalized_type[len(incorrect) :]
                break

        return normalized_type

    # Azure resource type to Terraform resource type mapping
    AZURE_TO_TERRAFORM_MAPPING: ClassVar[Dict[str, str]] = {
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",  # Fix #594: Re-add to prevent UNSUPPORTED marking (handler dynamically chooses linux/windows)
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
        "Microsoft.Insights/components": "azurerm_application_insights",
        "microsoft.insights/components": "azurerm_application_insights",  # Bug #91: Lowercase variant
        "Microsoft.AlertsManagement/smartDetectorAlertRules": "azurerm_monitor_smart_detector_alert_rule",
        "microsoft.alertsmanagement/smartDetectorAlertRules": "azurerm_monitor_smart_detector_alert_rule",  # Bug #91: Lowercase variant
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
        # DevTestLab resources
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
        "Microsoft.Insights/dataCollectionEndpoints": "azurerm_monitor_data_collection_endpoint",
        "Microsoft.OperationsManagement/solutions": "azurerm_log_analytics_solution",
        "Microsoft.Automation/automationAccounts": "azurerm_automation_account",
        # Additional resource types found in full tenant scan
        "Microsoft.Insights/actionGroups": "azurerm_monitor_action_group",
        "microsoft.insights/actiongroups": "azurerm_monitor_action_group",  # Bug #98: All lowercase
        "Microsoft.Insights/actiongroups": "azurerm_monitor_action_group",  # Bug #98 REAL: Mixed case
        "Microsoft.Search/searchServices": "azurerm_search_service",
        "Microsoft.OperationalInsights/queryPacks": "azurerm_log_analytics_query_pack",
        "microsoft.operationalinsights/querypacks": "azurerm_log_analytics_query_pack",  # Bug #99: All lowercase
        "Microsoft.OperationalInsights/querypacks": "azurerm_log_analytics_query_pack",  # Bug #99 REAL: Mixed case
        "Microsoft.Compute/sshPublicKeys": "azurerm_ssh_public_key",
        "Microsoft.DevTestLab/schedules": "azurerm_dev_test_schedule",
        # Bug #36: Add support for additional resource types
        "Microsoft.DocumentDB/databaseAccounts": "azurerm_cosmosdb_account",
        "Microsoft.Network/applicationGateways": "azurerm_application_gateway",
        "Microsoft.Network/dnsZones": "azurerm_dns_zone",
        "Microsoft.Network/dnszones": "azurerm_dns_zone",  # Bug #91: Lowercase variant
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
        # Additional supported types discovered during tenant replication (Iteration 19+)
        "Microsoft.Network/routeTables": "azurerm_route_table",
        # TEMPORARILY COMMENTED - Need emitter implementation (Iteration 22 validation found missing required fields)
        "Microsoft.RecoveryServices/vaults": "azurerm_recovery_services_vault",  # NOW HAS EMITTER (added SKU handler)
        "Microsoft.Portal/dashboards": "azurerm_portal_dashboard",
        "Microsoft.Purview/accounts": "azurerm_purview_account",
        "Microsoft.Databricks/workspaces": "azurerm_databricks_workspace",  # NOW HAS EMITTER (added SKU handler)
        "Microsoft.Databricks/accessConnectors": "azurerm_databricks_access_connector",
        "Microsoft.Synapse/workspaces": "azurerm_synapse_workspace",  # NOW HAS EMITTER (Iteration 27)
        "Microsoft.Communication/CommunicationServices": "azurerm_communication_service",
        "Microsoft.Communication/EmailServices": "azurerm_email_communication_service",  # NOW HAS EMITTER (data_location handler)
        "Microsoft.AppConfiguration/configurationStores": "azurerm_app_configuration",
        "Microsoft.Insights/scheduledqueryrules": "azurerm_monitor_scheduled_query_rules_alert",  # NOW HAS EMITTER (data_source_id, frequency, time_window, query, action, trigger)
        # "Microsoft.Insights/workbooks": "azurerm_application_insights_workbook",  # Missing: display_name, data_json
        "Microsoft.Compute/images": "azurerm_image",
        "Microsoft.Compute/galleries": "azurerm_shared_image_gallery",
        "Microsoft.Compute/galleries/images": "azurerm_shared_image",
        "Microsoft.Web/staticSites": "azurerm_static_web_app",
        "Microsoft.App/jobs": "azurerm_container_app_job",  # NOW HAS EMITTER (container_app_environment_id handler)
        # Microsoft.Resources/templateSpecs - These are template metadata, not deployments - will be skipped
        # Microsoft.Resources/templateSpecs/versions - Child resources - will be skipped
        # Microsoft.MachineLearningServices/workspaces/serverlessEndpoints - No direct Terraform equivalent yet, will be skipped
        # Microsoft.CognitiveServices/accounts/projects - Child resources, need parent account handling
        # Microsoft.Communication/EmailServices/Domains - Child resources
        # Microsoft.App/builders - Internal resource, may not need deployment
        # Microsoft.SentinelPlatformServices/* - Sentinel-specific, may need special handling
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
        "Microsoft.ContainerService/managedClusters": "azurerm_kubernetes_cluster",
        # Additional Compute resources
        "Microsoft.Compute/virtualMachineScaleSets": "azurerm_linux_virtual_machine_scale_set",
        "Microsoft.Compute/snapshots": "azurerm_snapshot",
        # Additional Network resources
        "Microsoft.Network/loadBalancers": "azurerm_lb",
        # Additional Monitoring resources
        "Microsoft.Insights/metricAlerts": "azurerm_monitor_metric_alert",
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
        split_by_community: bool = False,  # Fix #593: Default to True for parallel deployment
        location: Optional[str] = None,  # Fix #601: Target region override
    ) -> List[Path]:
        """Generate Terraform template from tenant graph.

        Args:
            graph: Tenant graph to generate from
            out_dir: Directory to write files
            domain_name: Optional domain name for user accounts
            subscription_id: Optional subscription ID for deployment
            comparison_result: Optional comparison with target tenant (NEW in Phase 1E)
                              If provided, enables smart import generation
            split_by_community: If True, split resources into separate files per community
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

        logger.info(str(f"Generating Terraform templates to {out_dir}"))

        # Store target location for handlers (Fix #601 - missing piece!)
        self.target_location = location

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
        # Bug #112: Map terraform resource names to their resource IDs for community splitting
        # Format: {sanitized_terraform_name: resource_id}
        self._terraform_name_to_resource_id: Dict[str, str] = {}
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

            # Normalize casing before lookup (fixes case-sensitivity issues)
            azure_type = self._normalize_azure_type(azure_type)

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
        logger.info(str(f"Found {len(rg_resources)} unique resource groups"))

        # Build RG name mapping (original -> prefixed) for updating resource references
        rg_name_mapping = {}
        if self.resource_group_prefix:
            for rg_resource in rg_resources:
                original_rg = rg_resource.get("_original_rg_name")
                prefixed_rg = rg_resource.get("name")
                if original_rg and prefixed_rg:
                    rg_name_mapping[original_rg] = prefixed_rg

            logger.info(f"Resource group prefix: '{self.resource_group_prefix}'")
            logger.info(
                str(f"Will transform {len(rg_name_mapping)} resource group names")
            )

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
            logger.info(str(f"Strict Mode: {self.strict_mode}"))
            logger.info("=" * 70)

            self._translation_coordinator = TranslationCoordinator(translation_context)

            # Translate all resources
            logger.info(str(f"Translating {len(all_resources)} resources..."))
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

                # Bug #66: Defensive check - if resource_config is None, skip this resource
                # This can happen if a handler returns (type, name, None) instead of returning None
                if resource_config is None:
                    logger.error(
                        f"BUG: _convert_resource returned None config for {resource_type}.{resource_name}. "
                        f"This is a bug in the emitter - should return None for entire tuple, not (type, name, None). "
                        f"Skipping resource."
                    )
                    continue

                # Validate all references in resource config before adding
                all_refs_valid, missing_refs = self._validate_all_references_in_config(
                    resource_config, resource_name, terraform_config
                )
                if not all_refs_valid:
                    logger.warning(
                        f"Skipping resource {resource_type}.{resource_name} - "
                        f"has {len(missing_refs)} undeclared reference(s): {', '.join(missing_refs)}"
                    )
                    continue

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

                        name_hash = hashlib.md5(
                            resource_name.encode(), usedforsecurity=False
                        ).hexdigest()[:5]
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

                # Bug #112: Map terraform name to resource ID for community splitting
                resource_id = resource.get("id", "")
                if resource_id:
                    self._terraform_name_to_resource_id[resource_name] = resource_id
                    logger.debug(
                        f"Mapped terraform name '{resource_name}' -> resource ID '{resource_id}'"
                    )

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
                # Validate both subnet and NSG exist before creating association
                subnet_exists = self._validate_resource_reference(
                    "azurerm_subnet", subnet_tf_name, terraform_config
                )
                nsg_exists = self._validate_resource_reference(
                    "azurerm_network_security_group", nsg_tf_name, terraform_config
                )

                if not subnet_exists:
                    logger.warning(
                        f"Skipping NSG association for subnet '{subnet_name}' - "
                        f"subnet resource azurerm_subnet.{subnet_tf_name} not emitted"
                    )
                    continue

                if not nsg_exists:
                    logger.warning(
                        f"Skipping NSG association for subnet '{subnet_name}' - "
                        f"NSG resource azurerm_network_security_group.{nsg_tf_name} not emitted"
                    )
                    continue

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

        # Emit NIC NSG association resources (Bug #57: deprecated network_security_group_id field)
        if self._nic_nsg_associations:
            if (
                "azurerm_network_interface_security_group_association"
                not in terraform_config["resource"]
            ):
                terraform_config["resource"][
                    "azurerm_network_interface_security_group_association"
                ] = {}

            for (
                nic_tf_name,
                nsg_tf_name,
                nic_name,
                nsg_name,
            ) in self._nic_nsg_associations:
                # Validate NSG exists before creating association (Bug #58)
                nsg_available = (
                    "azurerm_network_security_group" in self._available_resources
                    and nsg_tf_name
                    in self._available_resources["azurerm_network_security_group"]
                )

                if not nsg_available:
                    logger.warning(
                        f"Skipping NIC NSG association for '{nic_name}' - "
                        f"NSG '{nsg_name}' not emitted. Association cannot be created."
                    )
                    continue

                # Association resource name: nic_name + "_nsg_association"
                assoc_name = f"{nic_tf_name}_nsg_association"
                terraform_config["resource"][
                    "azurerm_network_interface_security_group_association"
                ][assoc_name] = {
                    "network_interface_id": f"${{azurerm_network_interface.{nic_tf_name}.id}}",
                    "network_security_group_id": f"${{azurerm_network_security_group.{nsg_tf_name}.id}}",
                }
                # Track NIC NSG association resource for generation report
                self._resource_count += 1
                logger.debug(
                    f"Generated NIC NSG association: {assoc_name} (NIC: {nic_name}, NSG: {nsg_name})"
                )

        # Generate import blocks if requested (Issue #412)
        if self.auto_import_existing:
            import_blocks = self._generate_import_blocks(
                terraform_config, graph.resources
            )
            if import_blocks:
                terraform_config["import"] = import_blocks
                self._import_blocks_generated = len(import_blocks)
                logger.info(str(f"Generated {len(import_blocks)} import blocks"))

        # Determine if we should split by community
        output_files = []
        if split_by_community:
            try:
                logger.info("Starting community split process...")
                # Need Neo4j driver to detect communities
                # Get driver from session manager
                from src.config_manager import create_neo4j_config_from_env
                from src.utils.session_manager import create_session_manager

                logger.debug("Creating Neo4j config from environment")
                config = create_neo4j_config_from_env()
                logger.debug("Creating session manager")
                manager = create_session_manager(config.neo4j)
                logger.debug("Connecting to Neo4j")
                manager.connect()
                logger.debug("Neo4j connected")
                # pyright: ignore[reportPrivateUsage]
                if manager._driver is None:  # pyright: ignore[reportPrivateUsage]
                    logger.warning(
                        "Cannot split by community: Neo4j driver not available. Writing single file."
                    )
                    split_by_community = False
                else:
                    driver = manager._driver  # pyright: ignore[reportPrivateUsage]
                    logger.debug("Creating CommunityDetector")
                    detector = CommunityDetector(driver)
                    logger.debug("Detecting communities...")
                    communities = detector.detect_communities()
                    logger.debug(
                        f"Communities detected, returned {len(communities)} communities"
                    )

                    logger.info(
                        f"Detected {len(communities)} communities for splitting"
                    )
                    logger.info(
                        str(f"Community sizes: {[len(c) for c in communities]}")
                    )

                    # Split resources by community
                    for i, community_ids in enumerate(communities, start=1):
                        logger.debug(
                            f"Processing community {i} with {len(community_ids)} resource IDs"
                        )
                        # Filter resources for this community
                        community_resources = {
                            resource_type: {
                                resource_name: resource_config
                                for resource_name, resource_config in resources.items()
                                if self._is_resource_in_community(
                                    resource_type,
                                    resource_name,
                                    community_ids,
                                    graph.resources,
                                )
                            }
                            for resource_type, resources in terraform_config.get(
                                "resource", {}
                            ).items()
                        }
                        logger.debug(
                            f"Filtered community {i}: {list(community_resources.keys())}"
                        )

                        # Remove empty resource types
                        community_resources = {
                            rt: res for rt, res in community_resources.items() if res
                        }

                        # Skip empty communities
                        if not community_resources:
                            logger.debug(
                                f"Community {i} has no resources after filtering, skipping"
                            )
                            continue

                        # Create community-specific config
                        community_config = {
                            "terraform": terraform_config["terraform"],
                            "provider": terraform_config["provider"],
                            "variable": terraform_config["variable"],
                            "resource": community_resources,
                        }

                        # Add import blocks for this community if present
                        if "import" in terraform_config:
                            community_imports = [
                                imp
                                for imp in terraform_config["import"]
                                if self._is_import_in_community(
                                    imp, community_ids, graph.resources
                                )
                            ]
                            if community_imports:
                                community_config["import"] = community_imports

                        # Write community file
                        community_file = out_dir / f"community_{i}.tf.json"
                        with open(community_file, "w") as f:
                            json.dump(community_config, f, indent=2)
                        output_files.append(community_file)
                        self._files_created += 1
                        logger.info(
                            f"Generated {community_file.name} with {len(community_resources)} resource types"
                        )

                    manager.disconnect()
            except Exception as e:
                logger.exception(
                    f"Failed to split by community (debugging traceback above): {type(e).__name__}: {e}"
                )
                split_by_community = False

        if not split_by_community:
            # Write single main.tf.json file
            output_file = out_dir / "main.tf.json"
            with open(output_file, "w") as f:
                json.dump(terraform_config, f, indent=2)
            output_files.append(output_file)
            # Track file creation for generation report (Issue #413)
            self._files_created += 1

        # Bug #112 fix: DO NOT write separate imports.tf file
        # Import blocks are already inline in terraform_config["import"]
        # Writing them twice causes "Duplicate import configuration" errors
        # if comparison_result is not None and "smart_import_blocks" in locals():
        #     self._write_import_blocks_filtered(
        #         smart_import_blocks, terraform_config, out_dir
        #     )

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
                        logger.warning(str(f"      ... and {len(refs) - 10} more"))

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
                logger.info(
                    str(f"Translation report (text) saved to: {text_report_path}")
                )

                # Save machine-readable JSON report
                json_report_path = out_dir / "translation_report.json"
                self._translation_coordinator.save_translation_report(
                    str(json_report_path), format="json"
                )
                logger.info(
                    str(f"Translation report (JSON) saved to: {json_report_path}")
                )

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

        # Validate Terraform dependencies before returning
        logger.info("=" * 70)
        logger.info("Validating Terraform resource dependencies...")
        logger.info("=" * 70)

        dependency_validator = DependencyValidator()
        validation_result = dependency_validator.validate(out_dir, skip_init=True)

        if validation_result.terraform_available:
            if validation_result.valid:
                logger.info(
                    "✅ Dependency validation passed - all resource references are declared"
                )
            else:
                logger.error(
                    f"❌ Dependency validation failed - found {len(validation_result.errors)} undeclared resource reference(s)"
                )
                for error in validation_result.errors:
                    logger.error(
                        f"  • Resource {error.resource_type}.{error.resource_name} references missing {error.missing_reference}"
                    )
                logger.warning(
                    "⚠️  The generated Terraform configuration has dependency errors. "
                    "Terraform apply will fail unless these references are fixed."
                )
        else:
            logger.warning(
                "⚠️  Terraform CLI not found - skipping dependency validation"
            )

        logger.info(
            f"Generated Terraform template with {len(graph.resources)} resources"
        )
        return output_files

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

        Delegates to AzureResourceIdBuilder for pattern-based ID construction.
        Supports 4 resource ID patterns (Phase 1 & 2):
        - Resource Group Level: Standard Azure resources
        - Child Resources: Subnets (266 resources)
        - Subscription Level: Role assignments (1,017 resources)
        - Association Resources: NSG associations (86 resources)

        Args:
            tf_resource_type: Terraform resource type (e.g., "azurerm_storage_account")
            resource_config: Terraform resource configuration dict
            subscription_id: Azure subscription ID

        Returns:
            Azure resource ID string or None if cannot be constructed
        """
        return self._resource_id_builder.build(
            tf_resource_type, resource_config, subscription_id
        )

    def _build_original_id_map(self, resources: List[Dict[str, Any]]) -> Dict[str, str]:
        """Build map of Terraform resource names to original Azure IDs.

        Bug #10 Fix: Extracts original Azure IDs from Neo4j resources for use in import blocks.

        Args:
            resources: Original resources from graph

        Returns:
            Map of {terraform_resource_name: original_azure_id}
        """
        original_id_map = {}
        for resource in resources:
            original_id = resource.get("original_id")
            if original_id:
                azure_type = resource.get("type")
                if azure_type:
                    normalized_type = self._normalize_azure_type(azure_type)
                    tf_type = self.AZURE_TO_TERRAFORM_MAPPING.get(normalized_type)
                    if tf_type:
                        resource_name = resource.get("name", "")
                        if resource_name:
                            tf_name = self._sanitize_terraform_name(resource_name)
                            map_key = f"{tf_type}.{tf_name}"
                            original_id_map[map_key] = original_id
                            logger.debug(
                                f"Added to original_id_map: {map_key} -> {original_id}"
                            )

        logger.info(
            f"Built original_id_map with {len(original_id_map)} entries from Neo4j"
        )
        return original_id_map

    def _generate_import_blocks(
        self, terraform_config: Dict[str, Any], resources: List[Dict[str, Any]]
    ) -> List[Dict[str, str]]:
        """Generate Terraform 1.5+ import blocks for existing resources (Issue #412, #422).

        With Issue #422 enhancements:
        - Checks resource existence before generating import blocks
        - Uses Azure SDK to verify resources actually exist in target
        - Caches existence checks to minimize API calls
        - Graceful error handling for transient failures

        Bug #10 Fix:
        - Builds original_id_map from resources list (Neo4j data)
        - Passes map to resource_id_builder for child resource import blocks
        - Enables import blocks for 177/177 resources (not just 67/177)

        Args:
            terraform_config: The generated Terraform configuration
            resources: Original resources from graph

        Returns:
            List of import blocks in Terraform 1.5+ format (only for existing resources)
        """
        import_blocks = []

        # Bug #10 Fix: Build original_id_map from resources
        original_id_map = self._build_original_id_map(resources)

        # Get subscription ID for validation
        subscription_id = self.target_subscription_id or self.source_subscription_id
        if not subscription_id:
            logger.warning(
                "Cannot validate resource existence: no subscription ID available"
            )
            # Fall back to old behavior (no validation)
            return self._generate_import_blocks_no_validation(
                terraform_config, original_id_map, resources
            )

        # Initialize existence validator if needed (Issue #422)
        if self._existence_validator is None:
            # Fix #608: DON'T pass self.credential - it's for source tenant!
            # Let ResourceExistenceValidator create the right credential for target tenant
            self._existence_validator = ResourceExistenceValidator(
                subscription_id=subscription_id,
                credential=None,  # Let validator create tenant-specific credential
                tenant_id=self.target_tenant_id,
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
                    # Bug #66: Skip if resource_config is None (defensive check)
                    if resource_config is None:
                        logger.error(
                            f"BUG: Null resource_config found for {tf_resource_type}.{tf_name} in terraform_config. "
                            f"This indicates a bug in resource generation. Skipping import for this resource."
                        )
                        continue

                    # Build Azure resource ID based on resource type
                    # Bug #10: Pass original_id_map and source_subscription_id
                    azure_id = self._resource_id_builder.build(
                        tf_resource_type,
                        resource_config,
                        subscription_id,
                        original_id_map=original_id_map,
                        source_subscription_id=self.source_subscription_id,
                    )

                    if azure_id:
                        # Bug #NEW: Normalize provider casing in import IDs (fix lowercase providers)
                        normalized_azure_id = self._normalize_azure_resource_id(
                            azure_id
                        )
                        resource_name = resource_config.get("name", tf_name)
                        candidate_imports.append(
                            {
                                "to": f"{tf_resource_type}.{tf_name}",
                                "id": normalized_azure_id,
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
        self,
        terraform_config: Dict[str, Any],
        original_id_map: Optional[Dict[str, str]] = None,
        resources: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        """Generate import blocks without existence validation (fallback).

        Used when subscription ID is not available for validation.

        Bug #10 Fix: Accepts resources to build original_id_map or accepts pre-built map.

        Args:
            terraform_config: The generated Terraform configuration
            original_id_map: Optional pre-built map of {terraform_resource_name: original_azure_id}
            resources: Optional resources list from Neo4j to build original_id_map

        Returns:
            List of import blocks without validation
        """
        import_blocks = []
        tf_resources = terraform_config.get("resource", {})
        subscription_id = self.target_subscription_id or self.source_subscription_id

        # Bug #10: Build original_id_map from resources if not provided
        if not original_id_map and resources:
            original_id_map = self._build_original_id_map(resources)

        if self.import_strategy == "resource_groups":
            resource_groups = tf_resources.get("azurerm_resource_group", {})
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
        elif self.import_strategy == "all_resources":
            # Bug #10 Fix: Generate import blocks for ALL resources using original_id_map
            for tf_resource_type, resources_of_type in tf_resources.items():
                if not isinstance(resources_of_type, dict):
                    continue

                for tf_name, resource_config in resources_of_type.items():
                    if resource_config is None:
                        continue

                    # Build Azure resource ID with original_id_map support
                    azure_id = self._resource_id_builder.build(
                        tf_resource_type,
                        resource_config,
                        subscription_id,
                        original_id_map=original_id_map,
                        source_subscription_id=self.source_subscription_id,
                    )

                    if azure_id:
                        import_blocks.append(
                            {
                                "to": f"{tf_resource_type}.{tf_name}",
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

    def _create_emitter_context(self) -> EmitterContext:
        """Create EmitterContext from current emitter state.

        This builds a context object containing all the shared state that
        handlers need for resource emission.

        Returns:
            EmitterContext populated with current emitter state
        """
        return EmitterContext(
            target_subscription_id=self.target_subscription_id,
            target_tenant_id=self.target_tenant_id,
            target_location=getattr(
                self, "target_location", None
            ),  # Fix #601: Pass target location
            source_subscription_id=self.source_subscription_id,
            source_tenant_id=self.source_tenant_id,
            identity_mapping=self.identity_mapping,
            resource_group_prefix=self.resource_group_prefix,
            strict_mode=self.strict_mode,
            terraform_config={},  # Will be populated by handlers
            available_resources=self._available_resources.copy(),
            available_subnets=self._available_subnets.copy(),
            available_resource_groups=self._available_resource_groups.copy(),
            vnet_id_to_terraform_name=self._vnet_id_to_terraform_name.copy(),
            nsg_associations=self._nsg_associations.copy(),
            nic_nsg_associations=self._nic_nsg_associations.copy(),
            missing_references=self._missing_references.copy(),
            graph=self._graph,
            translation_coordinator=self._translation_coordinator,
        )

    def _sync_context_to_emitter(self, context: EmitterContext) -> None:
        """Sync modified context state back to emitter instance.

        After a handler emits a resource, it may have modified the context
        (e.g., tracked new resources, added associations). This syncs those
        changes back to the emitter's internal state.

        Args:
            context: EmitterContext with potentially modified state
        """
        self._available_resources = context.available_resources
        self._available_subnets = context.available_subnets
        self._available_resource_groups = context.available_resource_groups
        self._vnet_id_to_terraform_name = context.vnet_id_to_terraform_name
        self._nsg_associations = context.nsg_associations
        self._nic_nsg_associations = context.nic_nsg_associations
        self._missing_references = context.missing_references

    def _convert_resource(
        self, resource: Dict[str, Any], terraform_config: Dict[str, Any]
    ) -> Optional[tuple[str, str, Dict[str, Any]]]:
        """Convert Azure resource to Terraform resource.

        This method delegates to specialized handlers for all resource types.

        Migration Status: COMPLETE (54 handlers available, legacy removed)

        Args:
            resource: Azure resource data
            terraform_config: The main Terraform configuration dict to add helper resources to

        Returns:
            Tuple of (terraform_type, resource_name, resource_config) or None if no handler available
        """
        azure_type = resource.get("type", "")
        resource_name = resource.get("name", "unknown")

        # Ensure handlers are registered
        ensure_handlers_registered()

        # Get handler for this resource type
        handler = HandlerRegistry.get_handler(azure_type)

        if handler:
            try:
                # Create context from current state
                context = self._create_emitter_context()

                # Let handler emit the resource
                result = handler.emit(resource, context)

                if result:
                    # Sync context state back to emitter
                    self._sync_context_to_emitter(context)

                    # Merge any helper resources into main config
                    if context.terraform_config.get("resource"):
                        for res_type, resources in context.terraform_config[
                            "resource"
                        ].items():
                            if res_type not in terraform_config.get("resource", {}):
                                terraform_config.setdefault("resource", {})[
                                    res_type
                                ] = {}
                            terraform_config["resource"][res_type].update(resources)

                    logger.info(
                        f"✅ Handler emission successful for {azure_type}: {resource_name}"
                    )
                    return result
                else:
                    logger.warning(
                        f"⚠️  Handler returned None for {azure_type}: {resource_name}"
                    )
                    return None

            except Exception as e:
                logger.error(
                    f"❌ Handler failed for {azure_type}: {resource_name}. Error: {e}"
                )
                return None

        # No handler available for this resource type
        logger.warning(str(f"No handler available for {azure_type}: {resource_name}"))
        return None

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

    def _translate_principal_id(
        self, principal_id: str, principal_type: str, resource_name: str
    ) -> Optional[str]:
        """Translate a principal ID using the identity mapping.

        Bug #67 fix: When identity_mapping is provided, translate source tenant
        principal IDs to target tenant principal IDs for cross-tenant deployments.

        Args:
            principal_id: Source tenant principal ID (GUID)
            principal_type: Type of principal (User, Group, ServicePrincipal, Unknown)
            resource_name: Name of the resource (for logging)

        Returns:
            Translated principal ID, or None if translation failed
        """
        if not self.identity_mapping:
            return None

        # Try to find the principal ID in identity mapping
        # The mapping format is:
        # {
        #   "identity_mappings": {
        #     "users": { "source-id": { "target_object_id": "target-id" } },
        #     "groups": { ... },
        #     "service_principals": { ... }
        #   }
        # }
        identity_mappings = self.identity_mapping.get("identity_mappings", {})

        # Normalize principal_type to lowercase for matching
        type_lower = principal_type.lower() if principal_type else "unknown"

        # Map principal type to identity mapping key
        type_mapping = {
            "user": "users",
            "group": "groups",
            "serviceprincipal": "service_principals",
            "unknown": None,  # Will try all types
        }

        mapping_key = type_mapping.get(type_lower)

        # Try specific type first if known
        if mapping_key and mapping_key in identity_mappings:
            type_mappings = identity_mappings.get(mapping_key, {})
            if principal_id in type_mappings:
                mapping = type_mappings[principal_id]
                target_id = mapping.get("target_object_id")
                if target_id and target_id != "MANUAL_INPUT_REQUIRED":
                    return target_id

        # If type unknown or not found, try all types
        for id_type in ["users", "groups", "service_principals"]:
            type_mappings = identity_mappings.get(id_type, {})
            if principal_id in type_mappings:
                mapping = type_mappings[principal_id]
                target_id = mapping.get("target_object_id")
                if target_id and target_id != "MANUAL_INPUT_REQUIRED":
                    logger.debug(
                        f"Found principal {principal_id} in {id_type} mapping -> {target_id}"
                    )
                    return target_id

        # Not found in any mapping
        logger.warning(
            f"Principal ID '{principal_id}' not found in identity mapping for "
            f"resource '{resource_name}' (type: {principal_type})"
        )
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

            name_hash = hashlib.md5(
                sanitized.encode(), usedforsecurity=False
            ).hexdigest()[:5]
            sanitized = sanitized[:74] + "_" + name_hash
            logger.debug(str(f"Truncated long name to 80 chars: ...{sanitized[-20:]}"))

        return sanitized or "unnamed_resource"

    def _add_unique_suffix(
        self, name: str, resource_id: str, resource_type: str | None = None
    ) -> str:
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
            # Bug #108: Redis must be lowercase 'redis' not 'Redis'
            (
                r"/Microsoft\.Cache/Redis/",
                "/Microsoft.Cache/redis/",
            ),
            # Bug #19: QueryPacks must be camelCase 'queryPacks' (both variants)
            (
                r"/Microsoft\.OperationalInsights/querypacks/",
                "/Microsoft.OperationalInsights/queryPacks/",
            ),
            (
                r"/Microsoft\.OperationalInsights/QueryPacks/",
                "/Microsoft.OperationalInsights/queryPacks/",
            ),
            (r"/microsoft\.insights/", "/Microsoft.Insights/"),
            (r"/microsoft\.alertsmanagement/", "/Microsoft.AlertsManagement/"),
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

        # Bug #88: Fix lowercase resourceGroups and actionGroups in resource IDs
        normalized = re.sub(
            r"/resourcegroups/", "/resourceGroups/", normalized, flags=re.IGNORECASE
        )
        normalized = re.sub(
            r"/actiongroups/", "/actionGroups/", normalized, flags=re.IGNORECASE
        )
        # Bug #NEW3: Fix lowercase dnszones
        normalized = re.sub(
            r"/dnszones/", "/dnsZones/", normalized, flags=re.IGNORECASE
        )

        return normalized

    def _validate_resource_reference(
        self,
        terraform_type: str,
        resource_name: str,
        terraform_config: Dict[str, Any] | None = None,
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

    def _validate_all_references_in_config(
        self,
        resource_config: Dict[str, Any],
        resource_name: str,
        terraform_config: Dict[str, Any],
    ) -> tuple[bool, list[str]]:
        """Validate all Terraform resource references in a resource configuration.

        Recursively searches for ${azurerm_*.*} and ${azuread_*.*} references and
        validates that each referenced resource exists in _available_resources.

        Args:
            resource_config: Resource configuration dictionary to validate
            resource_name: Name of the resource being validated (for logging)
            terraform_config: Full terraform config to check emitted resources

        Returns:
            Tuple of (all_valid: bool, missing_refs: list[str])
            - all_valid: True if all references are valid
            - missing_refs: List of missing reference strings
        """
        import re

        missing_refs = []

        def extract_references(obj: Any) -> None:
            """Recursively extract Terraform references from config object."""
            if isinstance(obj, str):
                # Pattern: ${azurerm_type.name.field} or ${azuread_type.name.field}
                pattern = r"\$\{(azurerm_\w+|azuread_\w+)\.(\w+)\.[\w]+\}"
                matches = re.findall(pattern, obj)
                for terraform_type, ref_name in matches:
                    # Validate reference exists
                    if not self._validate_resource_reference(
                        terraform_type, ref_name, terraform_config
                    ):
                        ref_str = f"{terraform_type}.{ref_name}"
                        if ref_str not in missing_refs:
                            missing_refs.append(ref_str)
                            logger.warning(
                                f"Resource '{resource_name}' references undeclared "
                                f"resource: {ref_str}"
                            )
            elif isinstance(obj, dict):
                for value in obj.values():
                    extract_references(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_references(item)

        extract_references(resource_config)
        return (len(missing_refs) == 0, missing_refs)

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
                logger.error(str(f"Missing required key in Terraform template: {key}"))
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

    def _is_resource_in_community(
        self,
        terraform_type: str,
        terraform_name: str,
        community_ids: set,
        all_resources: List[Dict[str, Any]],
    ) -> bool:
        """Check if a terraform resource belongs to a community.

        Args:
            terraform_type: Terraform resource type (e.g., azurerm_virtual_network)
            terraform_name: Terraform resource name (sanitized)
            community_ids: Set of resource IDs in the community
            all_resources: All resources from the graph (not used with mapping approach)

        Returns:
            True if the resource belongs to the community
        """
        # Bug #112: Use pre-built mapping of terraform names to resource IDs
        # This avoids the mismatch between sanitized terraform names and unsanitized graph names
        if terraform_name in self._terraform_name_to_resource_id:
            resource_id = self._terraform_name_to_resource_id[terraform_name]
            in_community = resource_id in community_ids
            logger.debug(
                f"Resource {terraform_name} (id={resource_id}) "
                f"in_community={in_community}"
            )
            return in_community
        else:
            logger.debug(
                f"WARNING: Terraform name '{terraform_name}' not in mapping. "
                f"Available names sample: {list(self._terraform_name_to_resource_id.keys())[:5]}"
            )
            return False

    def _is_import_in_community(
        self,
        import_block: Dict[str, Any],
        community_ids: set,
        all_resources: List[Dict[str, Any]],
    ) -> bool:
        """Check if an import block belongs to a community.

        Args:
            import_block: Import block with 'to' and 'id' fields
            community_ids: Set of resource IDs in the community
            all_resources: All resources from the graph

        Returns:
            True if the import belongs to the community
        """
        # Extract terraform resource name from import block
        # Format: "azurerm_resource_group.my_rg"
        to_address = import_block.get("to", "")
        if "." not in to_address:
            return False

        _, terraform_name = to_address.rsplit(".", 1)

        # Find matching resource in graph
        for resource in all_resources:
            resource_name = resource.get("name", "")
            safe_name = self._sanitize_terraform_name(resource_name)

            if safe_name == terraform_name:
                resource_id = resource.get("id", "")
                if resource_id in community_ids:
                    return True

        return False


# Auto-register this emitter
register_emitter("terraform", TerraformEmitter)
