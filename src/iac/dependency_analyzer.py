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

        # Future Work: Extract additional explicit dependencies from properties
        # See src/iac/FUTURE_WORK.md - TODO #6 for implementation specifications:
        # - VNets for subnets
        # - Subnets for NICs
        # - NICs for VMs
        # - Storage accounts for VM diagnostics

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
