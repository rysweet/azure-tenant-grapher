"""VNet Link dependency validator for Private DNS Zones.

This module validates that Private DNS Zones exist before VNet Links,
preventing ParentResourceNotFound errors (22 errors).

Azure requires:
- Private DNS Zone must exist before Virtual Network Link
- Explicit depends_on relationship in Terraform
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class VNetLinkValidationResult:
    """Result of VNet Link validation."""

    total_vnet_links: int
    valid_links: int
    invalid_links: int
    missing_dns_zones: Set[str] = field(default_factory=set)
    validation_messages: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed."""
        return self.invalid_links == 0


class VNetLinkDependencyValidator:
    """Validate Private DNS Zones exist before VNet Links.

    Ensures proper dependency order for Terraform deployment.
    """

    def __init__(self) -> None:
        """Initialize VNet Link dependency validator."""
        logger.info("VNetLinkDependencyValidator initialized")

    def validate_and_fix_dependencies(
        self, resources: List[Dict[str, Any]]
    ) -> VNetLinkValidationResult:
        """Validate and fix VNet Link dependencies.

        Args:
            resources: List of resources to validate (modified in place)

        Returns:
            VNetLinkValidationResult with validation statistics
        """
        # Extract Private DNS Zones and VNet Links
        dns_zones = self._extract_dns_zones(resources)
        vnet_links = self._extract_vnet_links(resources)

        total_vnet_links = len(vnet_links)
        valid_links = 0
        invalid_links = 0
        missing_dns_zones = set()
        validation_messages = []

        logger.info(
            f"Validating {total_vnet_links} VNet Links against {len(dns_zones)} DNS Zones"
        )

        # Validate each VNet Link
        for link in vnet_links:
            link_name = link.get("name", "unknown")
            parent_zone = self._extract_parent_zone_name(link)

            if not parent_zone:
                invalid_links += 1
                msg = f"VNet Link '{link_name}' has no parent DNS zone reference"
                validation_messages.append(msg)
                logger.warning(msg)
                continue

            # Check if parent DNS zone exists
            if parent_zone not in dns_zones:
                invalid_links += 1
                missing_dns_zones.add(parent_zone)
                msg = f"VNet Link '{link_name}' references missing DNS zone '{parent_zone}'"
                validation_messages.append(msg)
                logger.warning(msg)
            else:
                valid_links += 1

                # Add explicit depends_on if not present
                self._add_dependency(link, dns_zones[parent_zone])

                logger.debug(
                    f"VNet Link '{link_name}' validated: depends on '{parent_zone}'"
                )

        result = VNetLinkValidationResult(
            total_vnet_links=total_vnet_links,
            valid_links=valid_links,
            invalid_links=invalid_links,
            missing_dns_zones=missing_dns_zones,
            validation_messages=validation_messages,
        )

        logger.info(
            f"VNet Link validation complete: {valid_links}/{total_vnet_links} valid"
        )

        return result

    def _extract_dns_zones(self, resources: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """Extract Private DNS Zones from resources.

        Args:
            resources: List of resources

        Returns:
            Dictionary mapping DNS zone name to resource
        """
        dns_zones = {}

        for resource in resources:
            resource_type = resource.get("type", "")

            if resource_type == "Microsoft.Network/privateDnsZones":
                zone_name = resource.get("name", "")
                if zone_name:
                    dns_zones[zone_name] = resource

        logger.debug(f"Found {len(dns_zones)} Private DNS Zones")
        return dns_zones

    def _extract_vnet_links(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract VNet Links from resources.

        Args:
            resources: List of resources

        Returns:
            List of VNet Link resources
        """
        vnet_links = []

        for resource in resources:
            resource_type = resource.get("type", "")

            if resource_type == "Microsoft.Network/privateDnsZones/virtualNetworkLinks":
                vnet_links.append(resource)

        logger.debug(f"Found {len(vnet_links)} VNet Links")
        return vnet_links

    def _extract_parent_zone_name(self, vnet_link: Dict[str, Any]) -> str:
        """Extract parent DNS zone name from VNet Link.

        Args:
            vnet_link: VNet Link resource

        Returns:
            Parent DNS zone name, or empty string if not found
        """
        # Try to extract from resource ID
        resource_id = vnet_link.get("id", "")

        if "/privateDnsZones/" in resource_id:
            # Extract zone name from ID format:
            # /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/privateDnsZones/{zone}/virtualNetworkLinks/{link}
            parts = resource_id.split("/privateDnsZones/")
            if len(parts) > 1:
                zone_part = parts[1].split("/virtualNetworkLinks/")[0]
                return zone_part

        # Try to extract from name (format: zone/link)
        name = vnet_link.get("name", "")
        if "/" in name:
            return name.split("/")[0]

        # Try properties
        properties = vnet_link.get("properties", {})
        if isinstance(properties, dict):
            # Check for privateDnsZone reference
            if "privateDnsZone" in properties:
                zone_ref = properties["privateDnsZone"]
                if isinstance(zone_ref, str):
                    # Extract zone name from reference
                    if "/privateDnsZones/" in zone_ref:
                        parts = zone_ref.split("/privateDnsZones/")
                        if len(parts) > 1:
                            return parts[1].rstrip("/")

        return ""

    def _add_dependency(
        self, vnet_link: Dict[str, Any], dns_zone: Dict[str, Any]
    ) -> None:
        """Add explicit dependency from VNet Link to DNS Zone.

        Args:
            vnet_link: VNet Link resource (modified in place)
            dns_zone: DNS Zone resource
        """
        # Add terraform_depends_on field for Terraform emitter to use
        if "terraform_depends_on" not in vnet_link:
            vnet_link["terraform_depends_on"] = []

        zone_id = dns_zone.get("id", "")
        if zone_id and zone_id not in vnet_link["terraform_depends_on"]:
            vnet_link["terraform_depends_on"].append(zone_id)
            logger.debug(
                f"Added dependency: {vnet_link.get('name')} depends on {zone_id}"
            )

    def get_validation_summary(self, result: VNetLinkValidationResult) -> str:
        """Generate human-readable summary of validation results.

        Args:
            result: Validation result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "VNet Link Dependency Validation Summary",
            "=" * 50,
            f"Total VNet Links: {result.total_vnet_links}",
            f"Valid Links: {result.valid_links}",
            f"Invalid Links: {result.invalid_links}",
            "",
        ]

        if result.missing_dns_zones:
            summary.append("Missing DNS Zones:")
            for zone in sorted(result.missing_dns_zones):
                summary.append(f"  - {zone}")
            summary.append("")

        if result.validation_messages:
            summary.append("Validation Messages:")
            for msg in result.validation_messages:
                summary.append(f"  - {msg}")

        return "\n".join(summary)
