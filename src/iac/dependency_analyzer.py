"""Dependency analyzer for Infrastructure-as-Code generation.

This module analyzes resource dependencies and assigns tier levels to ensure
correct ordering in Terraform configurations. Resources are ordered by tier
to prevent deployment failures due to missing parent resources.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class ResourceDependency:
    """Represents a resource with its dependency tier and references."""

    resource: Dict[str, Any]
    tier: int
    depends_on: Set[str] = (
        None  # Terraform resource references this depends on # type: ignore[misc]
    )

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = set()


@dataclass
class ResourceGroupDependency:
    """Represents a dependency relationship between two Resource Groups."""

    source_rg: str
    """Resource Group that has the dependency"""

    target_rg: str
    """Resource Group being depended upon"""

    dependency_count: int
    """Number of dependencies from source to target"""

    resources: List[str] = field(default_factory=list)
    """List of resource names with dependencies"""


class DependencyAnalyzer:
    """Analyzes resource dependencies and assigns tier levels for ordering."""

    # Tier definitions (lower = deployed first)
    TIER_RESOURCE_GROUPS = 0
    TIER_NETWORK_PRIMITIVES = 1  # VNets, NSGs
    TIER_SUBNET_LEVEL = 2  # Subnets, Public IPs
    TIER_INFRASTRUCTURE = 3  # Storage, Key Vaults, DNS Zones
    TIER_NETWORK_COMPONENTS = 4  # NICs, Bastion Hosts
    TIER_COMPUTE = 5  # VMs, App Services
    TIER_ADVANCED = 6  # VM Extensions, Private Endpoints
    TIER_ASSOCIATIONS = 7  # NSG Associations (must be last)

    # Resource type to tier mapping
    RESOURCE_TYPE_TIERS = {
        # Tier 0: Resource Groups (foundation)
        "Microsoft.Resources/resourceGroups": TIER_RESOURCE_GROUPS,
        # Tier 1: Network primitives
        "Microsoft.Network/virtualNetworks": TIER_NETWORK_PRIMITIVES,
        "Microsoft.Network/networkSecurityGroups": TIER_NETWORK_PRIMITIVES,
        # Tier 2: Subnet-level resources
        "Microsoft.Network/subnets": TIER_SUBNET_LEVEL,
        "Microsoft.Network/publicIPAddresses": TIER_SUBNET_LEVEL,
        # Tier 3: Infrastructure resources
        "Microsoft.Storage/storageAccounts": TIER_INFRASTRUCTURE,
        "Microsoft.KeyVault/vaults": TIER_INFRASTRUCTURE,
        "Microsoft.Network/privateDnsZones": TIER_INFRASTRUCTURE,
        # Tier 4: Network components
        "Microsoft.Network/networkInterfaces": TIER_NETWORK_COMPONENTS,
        "Microsoft.Network/bastionHosts": TIER_NETWORK_COMPONENTS,
        # Tier 5: Compute resources
        "Microsoft.Compute/virtualMachines": TIER_COMPUTE,
        "Microsoft.Web/sites": TIER_COMPUTE,
        "Microsoft.Sql/servers": TIER_COMPUTE,
        # Tier 6: Advanced resources
        "Microsoft.Network/privateEndpoints": TIER_ADVANCED,
        "Microsoft.Network/privateDnsZones/virtualNetworkLinks": TIER_ADVANCED,
        "Microsoft.ManagedIdentity/managedIdentities": TIER_INFRASTRUCTURE,
        # Azure AD resources (no RG dependency, can be early)
        "Microsoft.AAD/User": TIER_RESOURCE_GROUPS,
        "Microsoft.AAD/Group": TIER_RESOURCE_GROUPS,
        "Microsoft.AAD/ServicePrincipal": TIER_RESOURCE_GROUPS,
        "Microsoft.Graph/users": TIER_RESOURCE_GROUPS,
        "Microsoft.Graph/groups": TIER_RESOURCE_GROUPS,
        "Microsoft.Graph/servicePrincipals": TIER_RESOURCE_GROUPS,
    }

    def analyze(self, resources: List[Dict[str, Any]]) -> List[ResourceDependency]:
        """Analyze resources and assign dependency tiers.

        Args:
            resources: List of resource dictionaries from Neo4j graph

        Returns:
            List of ResourceDependency objects sorted by tier
        """
        logger.info(str(f"Analyzing dependencies for {len(resources)} resources"))

        # Build resource dependencies
        dependencies = []
        for resource in resources:
            # DEFENSIVE: Skip if resource is not a dictionary
            # This can happen if translators malfunction or data corruption occurs
            if not isinstance(resource, dict):
                logger.warning(
                    f"Skipping invalid resource (expected dict, got {type(resource).__name__}): {resource}"
                )
                continue

            tier = self._calculate_tier(resource)
            depends_on = self._extract_dependencies(resource)

            dep = ResourceDependency(
                resource=resource, tier=tier, depends_on=depends_on
            )
            dependencies.append(dep)

        # Sort by tier (ascending)
        dependencies.sort(key=lambda d: d.tier)

        # Log tier distribution
        tier_counts = {}
        for dep in dependencies:
            tier_counts[dep.tier] = tier_counts.get(dep.tier, 0) + 1

        logger.info("Resource tier distribution:")
        for tier in sorted(tier_counts.keys()):
            logger.info(str(f"  Tier {tier}: {tier_counts[tier]} resources"))

        return dependencies

    def _calculate_tier(self, resource: Dict[str, Any]) -> int:
        """Calculate dependency tier for a resource.

        Args:
            resource: Resource dictionary

        Returns:
            Tier level (0 = highest priority, deployed first)
        """
        resource_type = resource.get("type", "")

        # Normalize type names for Azure AD resources
        if resource_type.lower() in ("user", "aaduser"):
            resource_type = "Microsoft.Graph/users"
        elif resource_type.lower() in ("group", "aadgroup", "identitygroup"):
            resource_type = "Microsoft.Graph/groups"
        elif resource_type.lower() == "serviceprincipal":
            resource_type = "Microsoft.Graph/servicePrincipals"
        elif resource_type.lower() == "managedidentity":
            resource_type = "Microsoft.ManagedIdentity/managedIdentities"

        # Look up tier from mapping
        tier = self.RESOURCE_TYPE_TIERS.get(resource_type)

        if tier is not None:
            return tier

        # Default tier for unmapped resources (between infrastructure and compute)
        logger.debug(
            f"Resource type '{resource_type}' not in tier mapping, "
            f"assigning default tier {self.TIER_INFRASTRUCTURE}"
        )
        return self.TIER_INFRASTRUCTURE

    def _extract_dependencies(self, resource: Dict[str, Any]) -> Set[str]:
        """Extract explicit dependencies for a resource.

        This identifies resources that must exist before this one can be created.

        Args:
            resource: Resource dictionary

        Returns:
            Set of Terraform resource references
        """
        dependencies = set()

        # Add resource group dependency for all non-RG resources
        resource_type = resource.get("type", "")

        # Normalize type names for Azure AD resources
        if resource_type.lower() in ("user", "aaduser"):
            resource_type = "Microsoft.Graph/users"
        elif resource_type.lower() in ("group", "aadgroup", "identitygroup"):
            resource_type = "Microsoft.Graph/groups"
        elif resource_type.lower() == "serviceprincipal":
            resource_type = "Microsoft.Graph/servicePrincipals"
        elif resource_type.lower() == "managedidentity":
            resource_type = "Microsoft.ManagedIdentity/managedIdentities"

        # Azure AD resources don't have resource groups
        azure_ad_types = {
            "Microsoft.AAD/User",
            "Microsoft.AAD/Group",
            "Microsoft.AAD/ServicePrincipal",
            "Microsoft.Graph/users",
            "Microsoft.Graph/groups",
            "Microsoft.Graph/servicePrincipals",
        }

        if (
            resource_type != "Microsoft.Resources/resourceGroups"
            and resource_type not in azure_ad_types
        ):
            # Try both field names (resource_group and resourceGroup)
            rg_name = resource.get("resource_group") or resource.get("resourceGroup")
            if rg_name:
                # Sanitize RG name for Terraform reference
                rg_name_sanitized = self._sanitize_terraform_name(rg_name)
                terraform_ref = f"azurerm_resource_group.{rg_name_sanitized}"
                dependencies.add(terraform_ref)
                logger.debug(
                    f"Added RG dependency for {resource.get('name', 'unknown')}: {terraform_ref}"
                )

        # VNet -> Subnet dependency (TODO #6)
        if resource_type == "Microsoft.Network/subnets":
            vnet_name = self._extract_vnet_name_from_subnet(resource)
            if vnet_name:
                safe_vnet = self._sanitize_terraform_name(vnet_name)
                dependencies.add(f"azurerm_virtual_network.{safe_vnet}")
                logger.debug(
                    f"Added VNet dependency for {resource.get('name', 'unknown')}: "
                    f"azurerm_virtual_network.{safe_vnet}"
                )

        # Subnet -> NIC dependency (TODO #6)
        if resource_type == "Microsoft.Network/networkInterfaces":
            subnet_ids = self._extract_subnet_ids_from_nic(resource)
            for subnet_id in subnet_ids:
                if subnet_id:
                    subnet_name = self._extract_resource_name_from_id(subnet_id)
                    safe_subnet = self._sanitize_terraform_name(subnet_name)
                    dependencies.add(f"azurerm_subnet.{safe_subnet}")
                    logger.debug(
                        f"Added Subnet dependency for {resource.get('name', 'unknown')}: "
                        f"azurerm_subnet.{safe_subnet}"
                    )

        # NIC -> VM dependency (TODO #6)
        if resource_type == "Microsoft.Compute/virtualMachines":
            nic_ids = self._extract_nic_ids_from_vm(resource)
            for nic_id in nic_ids:
                if nic_id:
                    nic_name = self._extract_resource_name_from_id(nic_id)
                    safe_nic = self._sanitize_terraform_name(nic_name)
                    dependencies.add(f"azurerm_network_interface.{safe_nic}")
                    logger.debug(
                        f"Added NIC dependency for {resource.get('name', 'unknown')}: "
                        f"azurerm_network_interface.{safe_nic}"
                    )

        # Storage Account -> VM diagnostics dependency (TODO #6)
        if resource_type == "Microsoft.Compute/virtualMachines":
            storage_account = self._extract_storage_from_diagnostics(resource)
            if storage_account:
                safe_storage = self._sanitize_terraform_name(storage_account)
                dependencies.add(f"azurerm_storage_account.{safe_storage}")
                logger.debug(
                    f"Added Storage Account dependency for {resource.get('name', 'unknown')}: "
                    f"azurerm_storage_account.{safe_storage}"
                )

        return dependencies

    def _sanitize_terraform_name(self, name: str) -> str:
        """Sanitize resource name for Terraform compatibility.

        This MUST match terraform_emitter._sanitize_terraform_name() exactly
        to ensure depends_on references match resource names (Bug #66 fix).

        Args:
            name: Original resource name

        Returns:
            Sanitized name safe for Terraform (max 80 chars for Azure NICs)
        """
        import hashlib
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        # Bug #66 fix: Must truncate to 80 chars to match terraform_emitter.py
        # Keep first 75 chars + hash of full name for uniqueness
        if len(sanitized) > 80:
            name_hash = hashlib.md5(sanitized.encode()).hexdigest()[:5]
            sanitized = sanitized[:74] + "_" + name_hash
            logger.debug(str(f"Truncated long name to 80 chars: ...{sanitized[-20:]}"))

        return sanitized or "unnamed_resource"

    # Resource Dependency Extraction Helper Methods (TODO #6)

    def _extract_vnet_name_from_subnet(self, resource: Dict[str, Any]) -> str:
        """Extract VNet name from subnet resource.

        Subnet IDs follow format: /subscriptions/{sub}/resourceGroups/{rg}/providers/
        Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}

        Args:
            resource: Subnet resource dictionary

        Returns:
            VNet name or empty string if not found
        """
        # Try to extract from resource ID
        resource_id = resource.get("id", "")
        if resource_id:
            # Match pattern: .../virtualNetworks/{vnet}/subnets/...
            match = re.search(
                r"/virtualNetworks/([^/]+)/subnets/", resource_id, re.IGNORECASE
            )
            if match:
                return match.group(1)

        # Fallback: check properties for vnet reference
        properties = resource.get("properties", {})
        # DEFENSIVE: Ensure properties is a dict
        if not isinstance(properties, dict):
            return ""
        vnet_id = properties.get("virtualNetwork", {}).get("id", "")
        if vnet_id:
            return self._extract_resource_name_from_id(vnet_id)

        return ""

    def _extract_subnet_ids_from_nic(self, resource: Dict[str, Any]) -> List[str]:
        """Extract subnet IDs from NIC resource.

        NICs can have multiple IP configurations, each with a subnet reference.

        Args:
            resource: NIC resource dictionary

        Returns:
            List of subnet IDs
        """
        subnet_ids = []
        properties = resource.get("properties", {})
        # DEFENSIVE: Ensure properties is a dict (can be string if data corrupted)
        if not isinstance(properties, dict):
            logger.warning(f"NIC properties is {type(properties).__name__}, expected dict")
            return []
        ip_configs = properties.get("ipConfigurations", [])

        for ip_config in ip_configs:
            subnet = ip_config.get("subnet", {})
            subnet_id = subnet.get("id", "")
            if subnet_id:
                subnet_ids.append(subnet_id)

        return subnet_ids

    def _extract_nic_ids_from_vm(self, resource: Dict[str, Any]) -> List[str]:
        """Extract NIC IDs from VM resource.

        VMs can have multiple network interfaces.

        Args:
            resource: VM resource dictionary

        Returns:
            List of NIC IDs
        """
        nic_ids = []
        properties = resource.get("properties", {})
        # DEFENSIVE: Ensure properties is a dict
        if not isinstance(properties, dict):
            logger.warning(f"VM properties is {type(properties).__name__}, expected dict")
            return []
        network_profile = properties.get("networkProfile", {})
        nic_refs = network_profile.get("networkInterfaces", [])

        for nic_ref in nic_refs:
            nic_id = nic_ref.get("id", "")
            if nic_id:
                nic_ids.append(nic_id)

        return nic_ids

    def _extract_storage_from_diagnostics(self, resource: Dict[str, Any]) -> str:
        """Extract storage account name from VM diagnostics settings.

        Boot diagnostics uses storage URI format:
        https://{storage_account}.blob.core.windows.net/

        Args:
            resource: VM resource dictionary

        Returns:
            Storage account name or empty string if not found
        """
        properties = resource.get("properties", {})
        # DEFENSIVE: Ensure properties is a dict
        if not isinstance(properties, dict):
            return ""
        diagnostics = properties.get("diagnosticsProfile", {})
        boot_diagnostics = diagnostics.get("bootDiagnostics", {})
        storage_uri = boot_diagnostics.get("storageUri", "")

        if storage_uri:
            # Extract storage account name from URI
            # Format: https://<name>.blob.core.windows.net/
            try:
                # Split on '//' to get domain part
                parts = storage_uri.split("//")
                if len(parts) > 1:
                    # Get the first part of the domain (storage account name)
                    domain = parts[1].split(".")[0]
                    return domain
            except (IndexError, AttributeError):
                logger.debug(f"Failed to parse storage URI: {storage_uri}")

        return ""

    def _extract_resource_name_from_id(self, resource_id: str) -> str:
        """Extract resource name from Azure resource ID.

        Azure ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/
        {provider}/{type}/{name}[/{subtype}/{subname}]

        Args:
            resource_id: Azure Resource ID string

        Returns:
            Resource name or empty string if not found
        """
        if not resource_id:
            return ""

        # Split by '/' and get the last segment
        parts = resource_id.split("/")
        # Filter out empty strings
        parts = [p for p in parts if p]

        # Return the last non-empty part
        return parts[-1] if parts else ""

    # Cross-Resource Group Dependency Methods

    def get_cross_rg_dependencies(
        self, resources: List[Dict[str, Any]]
    ) -> List[ResourceGroupDependency]:
        """
        Detect cross-Resource Group dependencies.

        Identifies when resources in one RG reference resources in other RGs.

        Args:
            resources: List of resource dictionaries from Neo4j graph

        Returns:
            List of ResourceGroupDependency objects representing cross-RG deps
        """
        cross_rg_deps = defaultdict(lambda: {"count": 0, "resources": []})

        # Build RG -> Resource mapping
        rg_to_resources = defaultdict(list)
        for resource in resources:
            rg = resource.get("resource_group") or resource.get("resourceGroup")
            if rg:
                rg_to_resources[rg].append(resource)

        # Analyze each resource for cross-RG references
        for resource in resources:
            source_rg = resource.get("resource_group") or resource.get("resourceGroup")
            if not source_rg:
                continue

            # Extract Azure Resource IDs from properties
            resource_ids = self._extract_azure_resource_ids(resource)

            for resource_id in resource_ids:
                # Parse RG from Azure Resource ID
                target_rg = self._extract_rg_from_azure_id(resource_id)

                if target_rg and target_rg != source_rg:
                    # Found cross-RG dependency
                    key = (source_rg, target_rg)
                    cross_rg_deps[key]["count"] += 1
                    if resource["name"] not in cross_rg_deps[key]["resources"]:
                        cross_rg_deps[key]["resources"].append(resource["name"])

        # Convert to ResourceGroupDependency objects
        result = []
        for (source_rg, target_rg), data in cross_rg_deps.items():
            result.append(
                ResourceGroupDependency(
                    source_rg=source_rg,
                    target_rg=target_rg,
                    dependency_count=data["count"],
                    resources=data["resources"],
                )
            )

        return result

    def _extract_azure_resource_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """
        Extract Azure Resource IDs from resource properties.

        Args:
            resource: Resource dictionary

        Returns:
            Set of Azure Resource IDs found in properties
        """
        resource_ids = set()

        # Recursively search properties for Azure Resource ID patterns
        def extract_from_dict(obj: Any) -> None:
            if isinstance(obj, dict):
                for value in obj.values():
                    extract_from_dict(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_from_dict(item)
            elif isinstance(obj, str):
                # Match Azure Resource ID pattern
                # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}
                if obj.startswith("/subscriptions/") and "/resourceGroups/" in obj:
                    resource_ids.add(obj)

        properties = resource.get("properties", {})
        # DEFENSIVE: Ensure properties is a dict before extracting
        if isinstance(properties, dict):
            extract_from_dict(properties)

        return resource_ids

    def _extract_rg_from_azure_id(self, resource_id: str) -> str:
        """
        Extract Resource Group name from Azure Resource ID.

        Args:
            resource_id: Azure Resource ID string

        Returns:
            Resource Group name or empty string if not found
        """
        # Pattern: /subscriptions/{sub}/resourceGroups/{rg}/...
        match = re.search(r"/resourceGroups/([^/]+)", resource_id, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def get_rg_deployment_order(self, resources: List[Dict[str, Any]]) -> List[str]:
        """
        Determine deployment order for Resource Groups based on dependencies.

        Uses topological sort to ensure RGs are deployed in correct order.

        Args:
            resources: List of resource dictionaries

        Returns:
            Ordered list of Resource Group names (dependencies first)

        Raises:
            ValueError: If circular dependency detected
        """
        cross_rg_deps = self.get_cross_rg_dependencies(resources)

        # Build adjacency list: RG -> Set of RGs it depends on
        dependencies = defaultdict(set)
        all_rgs = set()

        # Add all RGs from resources
        for resource in resources:
            rg = resource.get("resource_group") or resource.get("resourceGroup")
            if rg:
                all_rgs.add(rg)
                if rg not in dependencies:
                    dependencies[rg] = set()

        # Add cross-RG dependencies
        for dep in cross_rg_deps:
            dependencies[dep.source_rg].add(dep.target_rg)

        # Topological sort (Kahn's algorithm)
        # in_degree tracks how many RGs each RG depends on
        in_degree = {rg: len(dependencies[rg]) for rg in all_rgs}

        # Start with RGs that have no dependencies
        queue = [rg for rg in all_rgs if in_degree[rg] == 0]
        result = []

        while queue:
            # Sort for deterministic output
            queue.sort()
            current = queue.pop(0)
            result.append(current)

            # For each RG that depends on current, decrement its in_degree
            for rg in all_rgs:
                if current in dependencies[rg]:
                    in_degree[rg] -= 1
                    if in_degree[rg] == 0:
                        queue.append(rg)

        # Check for cycles
        if len(result) != len(all_rgs):
            raise ValueError(
                "Circular dependency detected in Resource Group dependencies. "
                "Cannot determine deployment order."
            )

        return result

    def check_broken_references(
        self, current_resources: List[Dict[str, Any]], proposed_rg_structure: List[str]
    ) -> List[str]:
        """
        Check if proposed RG structure would break cross-RG references.

        Args:
            current_resources: Current resource configuration
            proposed_rg_structure: List of RG names in proposed structure

        Returns:
            List of warning messages for broken references
        """
        warnings = []
        cross_rg_deps = self.get_cross_rg_dependencies(current_resources)

        for dep in cross_rg_deps:
            # Check if target RG would be removed
            if dep.target_rg not in proposed_rg_structure:
                warnings.append(
                    f"Warning: Removing Resource Group '{dep.target_rg}' would break "
                    f"{dep.dependency_count} reference(s) from '{dep.source_rg}' "
                    f"(resources: {', '.join(dep.resources)})"
                )

        return warnings

    def check_broken_references_on_move(
        self,
        current_resources: List[Dict[str, Any]],
        proposed_resources: List[Dict[str, Any]],
    ) -> List[str]:
        """
        Check if moving resources would break cross-RG references.

        Args:
            current_resources: Current resource configuration
            proposed_resources: Proposed resource configuration (with moves)

        Returns:
            List of warning messages for broken references
        """
        warnings = []

        # Build current RG mapping: resource_name -> RG
        current_rg_map = {}
        for resource in current_resources:
            rg = resource.get("resource_group") or resource.get("resourceGroup")
            if rg:
                current_rg_map[resource["name"]] = rg

        # Build proposed RG mapping
        proposed_rg_map = {}
        for resource in proposed_resources:
            rg = resource.get("resource_group") or resource.get("resourceGroup")
            if rg:
                proposed_rg_map[resource["name"]] = rg

        # Analyze resources for cross-RG references
        for resource in current_resources:
            source_rg = resource.get("resource_group") or resource.get("resourceGroup")
            if not source_rg:
                continue

            resource_ids = self._extract_azure_resource_ids(resource)

            for resource_id in resource_ids:
                current_target_rg = self._extract_rg_from_azure_id(resource_id)

                # Find resource name from ID (simple extraction)
                resource_name_match = re.search(r"/([^/]+)$", resource_id)
                if not resource_name_match:
                    continue
                target_resource_name = resource_name_match.group(1)

                # Check if target resource moved
                if target_resource_name in proposed_rg_map:
                    proposed_target_rg = proposed_rg_map[target_resource_name]

                    if current_target_rg != proposed_target_rg:
                        warnings.append(
                            f"Warning: Moving resource '{target_resource_name}' from "
                            f"'{current_target_rg}' to '{proposed_target_rg}' would break "
                            f"reference from '{resource['name']}' in '{source_rg}'"
                        )

        return warnings

    def group_by_cross_rg_deps(
        self, resources: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, List[str]]]:
        """
        Group Resource Groups by their cross-RG dependency relationships.

        Args:
            resources: List of resource dictionaries

        Returns:
            Dict mapping RG name to {'dependencies': [...], 'dependents': [...]}
        """
        result = defaultdict(lambda: {"dependencies": [], "dependents": []})

        cross_rg_deps = self.get_cross_rg_dependencies(resources)

        # Get all RGs
        all_rgs = set()
        for resource in resources:
            rg = resource.get("resource_group") or resource.get("resourceGroup")
            if rg:
                all_rgs.add(rg)

        # Initialize all RGs
        for rg in all_rgs:
            if rg not in result:
                result[rg] = {"dependencies": [], "dependents": []}

        # Populate dependencies and dependents
        for dep in cross_rg_deps:
            if dep.target_rg not in result[dep.source_rg]["dependencies"]:
                result[dep.source_rg]["dependencies"].append(dep.target_rg)
            if dep.source_rg not in result[dep.target_rg]["dependents"]:
                result[dep.target_rg]["dependents"].append(dep.source_rg)

        return dict(result)
