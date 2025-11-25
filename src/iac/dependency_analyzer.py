"""Dependency analyzer for Infrastructure-as-Code generation.

This module analyzes resource dependencies and assigns tier levels to ensure
correct ordering in Terraform configurations. Resources are ordered by tier
to prevent deployment failures due to missing parent resources.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class ResourceDependency:
    """Represents a resource with its dependency tier and references."""

    resource: Dict[str, Any]
    tier: int
    depends_on: Set[str] = None  # Terraform resource references this depends on

    def __post_init__(self):
        if self.depends_on is None:
            self.depends_on = set()


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
        logger.info(f"Analyzing dependencies for {len(resources)} resources")

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
            logger.info(f"  Tier {tier}: {tier_counts[tier]} resources")

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

        # TODO: Extract additional explicit dependencies from properties
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
        import re
        import hashlib

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        # Bug #66 fix: Must truncate to 80 chars to match terraform_emitter.py
        # Keep first 75 chars + hash of full name for uniqueness
        if len(sanitized) > 80:
            name_hash = hashlib.md5(sanitized.encode()).hexdigest()[:5]
            sanitized = sanitized[:74] + "_" + name_hash
            logger.debug(f"Truncated long name to 80 chars: ...{sanitized[-20:]}")

        return sanitized or "unnamed_resource"
