"""Global location mapper for Azure resource groups.

This module maps location='global' to valid Azure regions for Resource Groups,
preventing LocationNotAvailableForResourceGroup errors (2 errors).

Azure Resource Groups cannot have location='global'. They must be in a
physical region, even if the resources they contain are global.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


@dataclass
class LocationMapResult:
    """Result of location mapping operation."""

    resources_processed: int
    resources_mapped: int
    mappings: List[tuple[str, str, str]] = None  # (resource_id, old_location, new_location)

    def __post_init__(self):
        if self.mappings is None:
            self.mappings = []


class GlobalLocationMapper:
    """Map location='global' to valid Azure region for Resource Groups.

    Azure Resource Groups must be in a physical region, not 'global'.
    This transformer maps 'global' to a default region.
    """

    # Default region for global resources
    DEFAULT_REGION = "eastus"

    # Azure regions that support resource groups (all standard regions)
    VALID_REGIONS = {
        "eastus",
        "eastus2",
        "westus",
        "westus2",
        "westus3",
        "centralus",
        "northcentralus",
        "southcentralus",
        "westcentralus",
        "canadacentral",
        "canadaeast",
        "brazilsouth",
        "northeurope",
        "westeurope",
        "uksouth",
        "ukwest",
        "francecentral",
        "francesouth",
        "germanywestcentral",
        "norwayeast",
        "switzerlandnorth",
        "swedencentral",
        "eastasia",
        "southeastasia",
        "japaneast",
        "japanwest",
        "koreacentral",
        "koreasouth",
        "australiaeast",
        "australiasoutheast",
        "centralindia",
        "southindia",
        "westindia",
        "uaenorth",
        "southafricanorth",
    }

    def __init__(self, default_region: str = DEFAULT_REGION) -> None:
        """Initialize global location mapper.

        Args:
            default_region: Default region to use for global locations
        """
        self.default_region = default_region.lower()

        if self.default_region not in self.VALID_REGIONS:
            logger.warning(
                f"Default region '{self.default_region}' not in known regions, "
                f"using {self.DEFAULT_REGION}"
            )
            self.default_region = self.DEFAULT_REGION

        logger.info(f"GlobalLocationMapper initialized: default_region={self.default_region}")

    def transform_resources(self, resources: List[Dict[str, Any]]) -> LocationMapResult:
        """Transform resources by mapping global locations to valid regions.

        Args:
            resources: List of resources to transform (modified in place)

        Returns:
            LocationMapResult with transformation statistics
        """
        resources_processed = 0
        resources_mapped = 0
        mappings = []

        for resource in resources:
            resources_processed += 1

            # Check if resource is a Resource Group with global location
            resource_type = resource.get("type", "")
            location = resource.get("location", "").lower()

            if resource_type == "Microsoft.Resources/resourceGroups" and location == "global":
                resource_id = resource.get("id", resource.get("name", "unknown"))
                old_location = location

                # Map to default region
                resource["location"] = self.default_region
                resources_mapped += 1
                mappings.append((resource_id, old_location, self.default_region))

                logger.info(
                    f"Mapped Resource Group '{resource_id}' location: "
                    f"{old_location} -> {self.default_region}"
                )

        logger.info(
            f"Location mapping complete: {resources_processed} processed, "
            f"{resources_mapped} mapped"
        )

        return LocationMapResult(
            resources_processed=resources_processed,
            resources_mapped=resources_mapped,
            mappings=mappings,
        )

    def get_mapping_summary(self, result: LocationMapResult) -> str:
        """Generate human-readable summary of mapping results.

        Args:
            result: Mapping result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "Global Location Mapper Summary",
            "=" * 50,
            f"Resources processed: {result.resources_processed}",
            f"Resources mapped: {result.resources_mapped}",
            "",
        ]

        if result.mappings:
            summary.append("Location Mappings:")
            for resource_id, old_location, new_location in result.mappings:
                summary.append(f"  - {resource_id}")
                summary.append(f"    {old_location} -> {new_location}")

        return "\n".join(summary)
