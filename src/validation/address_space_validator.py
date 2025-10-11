"""Address space validation for VNet deployments.

This module provides validation to detect overlapping VNet address spaces
and optionally auto-renumber conflicting ranges before IaC generation.
"""

import ipaddress
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AddressSpaceConflict:
    """Represents a detected address space conflict between VNets.

    Attributes:
        vnet_names: Names of VNets with overlapping address spaces
        address_space: The overlapping address space (CIDR notation)
        severity: Severity level (warning, error)
        message: Human-readable conflict description
    """

    vnet_names: List[str]
    address_space: str
    severity: str = "warning"
    message: str = ""

    def __post_init__(self):
        """Generate default message if not provided."""
        if not self.message:
            self.message = (
                f"VNets {', '.join(self.vnet_names)} share overlapping "
                f"address space: {self.address_space}"
            )


@dataclass
class ValidationResult:
    """Result of address space validation.

    Attributes:
        is_valid: True if no conflicts detected
        conflicts: List of detected conflicts
        warnings: List of warning messages
        vnets_checked: Number of VNets validated
        auto_renumbered: List of VNets that were auto-renumbered
    """

    is_valid: bool
    conflicts: List[AddressSpaceConflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    vnets_checked: int = 0
    auto_renumbered: List[str] = field(default_factory=list)


class AddressSpaceValidator:
    """Validator for VNet address space conflicts.

    This validator checks for overlapping address spaces across VNets
    and can optionally auto-renumber conflicting ranges.
    """

    # Reserved/special address spaces that should not be used
    RESERVED_RANGES = [
        "169.254.0.0/16",  # Azure link-local
        "168.63.129.16/32",  # Azure DNS
    ]

    # Common private address spaces for auto-renumbering
    PRIVATE_RANGES = [
        "10.0.0.0/16",
        "10.1.0.0/16",
        "10.2.0.0/16",
        "10.3.0.0/16",
        "172.16.0.0/16",
        "172.17.0.0/16",
        "172.18.0.0/16",
        "172.19.0.0/16",
        "192.168.0.0/16",
        "192.168.1.0/24",
        "192.168.2.0/24",
        "192.168.3.0/24",
    ]

    def __init__(self, auto_renumber: bool = False):
        """Initialize address space validator.

        Args:
            auto_renumber: If True, automatically renumber conflicting ranges
        """
        self.auto_renumber = auto_renumber
        self._used_ranges: Set[str] = set()

    def validate_resources(
        self, resources: List[Dict[str, Any]], modify_in_place: bool = False
    ) -> ValidationResult:
        """Validate address spaces across all VNet resources.

        Args:
            resources: List of resource dictionaries (tenant graph resources)
            modify_in_place: If True and auto_renumber is enabled, modify resources directly

        Returns:
            ValidationResult with conflict information

        Example:
            >>> validator = AddressSpaceValidator()
            >>> resources = [
            ...     {"type": "Microsoft.Network/virtualNetworks", "name": "vnet1", "address_space": ["10.0.0.0/16"]},
            ...     {"type": "Microsoft.Network/virtualNetworks", "name": "vnet2", "address_space": ["10.0.0.0/16"]}
            ... ]
            >>> result = validator.validate_resources(resources)
            >>> assert not result.is_valid
            >>> assert len(result.conflicts) == 1
        """
        logger.info(f"Validating address spaces across {len(resources)} resources")

        # Extract VNet resources
        vnets = self._extract_vnets(resources)
        logger.info(f"Found {len(vnets)} VNet resources to validate")

        if not vnets:
            return ValidationResult(
                is_valid=True, vnets_checked=0, warnings=["No VNet resources found"]
            )

        # Build address space mapping
        address_space_map: Dict[str, List[str]] = {}
        for vnet in vnets:
            vnet_name = vnet.get("name", "unknown")
            address_spaces = self._get_address_spaces(vnet)

            for address_space in address_spaces:
                if address_space not in address_space_map:
                    address_space_map[address_space] = []
                address_space_map[address_space].append(vnet_name)

        # Detect conflicts
        conflicts: List[AddressSpaceConflict] = []
        warnings: List[str] = []

        for address_space, vnet_names in address_space_map.items():
            # Check for duplicates
            if len(vnet_names) > 1:
                conflict = AddressSpaceConflict(
                    vnet_names=vnet_names,
                    address_space=address_space,
                    severity="warning",
                )
                conflicts.append(conflict)
                logger.warning(conflict.message)

            # Check for reserved ranges
            if address_space in self.RESERVED_RANGES:
                warnings.append(
                    f"VNet(s) {', '.join(vnet_names)} use reserved address space: {address_space}"
                )

            # Check for overlaps (not just exact duplicates)
            self._used_ranges.add(address_space)

        # Check for partial overlaps (network overlaps without exact match)
        overlap_conflicts = self._detect_overlaps(vnets)
        conflicts.extend(overlap_conflicts)

        # Auto-renumber if enabled
        auto_renumbered: List[str] = []
        if self.auto_renumber and conflicts and modify_in_place:
            auto_renumbered = self._auto_renumber_conflicts(resources, conflicts)
            logger.info(f"Auto-renumbered {len(auto_renumbered)} VNets")

        is_valid = len(conflicts) == 0

        return ValidationResult(
            is_valid=is_valid,
            conflicts=conflicts,
            warnings=warnings,
            vnets_checked=len(vnets),
            auto_renumbered=auto_renumbered,
        )

    def _extract_vnets(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract VNet resources from resource list.

        Args:
            resources: List of all resources

        Returns:
            List of VNet resources only
        """
        vnets = []
        for resource in resources:
            resource_type = resource.get("type", "")
            if resource_type == "Microsoft.Network/virtualNetworks":
                vnets.append(resource)
        return vnets

    def _get_address_spaces(self, vnet: Dict[str, Any]) -> List[str]:
        """Extract address spaces from VNet resource.

        Args:
            vnet: VNet resource dictionary

        Returns:
            List of address space CIDR strings
        """
        # Try direct address_space field first
        address_spaces = vnet.get("address_space", [])

        # Ensure it's a list
        if isinstance(address_spaces, str):
            address_spaces = [address_spaces]

        # If empty, use default
        if not address_spaces:
            logger.warning(
                f"VNet '{vnet.get('name', 'unknown')}' has no address_space, "
                f"defaulting to ['10.0.0.0/16']"
            )
            address_spaces = ["10.0.0.0/16"]

        return address_spaces

    def _detect_overlaps(
        self, vnets: List[Dict[str, Any]]
    ) -> List[AddressSpaceConflict]:
        """Detect partial overlaps between VNet address spaces.

        Args:
            vnets: List of VNet resources

        Returns:
            List of detected overlap conflicts
        """
        conflicts: List[AddressSpaceConflict] = []

        # Build list of (vnet_name, network) tuples
        vnet_networks: List[
            Tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]
        ] = []

        for vnet in vnets:
            vnet_name = vnet.get("name", "unknown")
            address_spaces = self._get_address_spaces(vnet)

            for address_space in address_spaces:
                try:
                    network = ipaddress.ip_network(address_space, strict=False)
                    vnet_networks.append((vnet_name, network))
                except ValueError as e:
                    logger.warning(
                        f"Invalid address space '{address_space}' for VNet '{vnet_name}': {e}"
                    )

        # Check all pairs for overlaps
        for i in range(len(vnet_networks)):
            vnet_name_a, network_a = vnet_networks[i]
            for j in range(i + 1, len(vnet_networks)):
                vnet_name_b, network_b = vnet_networks[j]

                # Check if networks overlap
                if network_a.overlaps(network_b):
                    # Skip if exact duplicates (already caught)
                    if network_a == network_b:
                        continue

                    conflict = AddressSpaceConflict(
                        vnet_names=[vnet_name_a, vnet_name_b],
                        address_space=f"{network_a} overlaps {network_b}",
                        severity="warning",
                        message=(
                            f"VNets '{vnet_name_a}' ({network_a}) and '{vnet_name_b}' ({network_b}) "
                            f"have overlapping address spaces"
                        ),
                    )
                    conflicts.append(conflict)
                    logger.warning(conflict.message)

        return conflicts

    def _auto_renumber_conflicts(
        self, resources: List[Dict[str, Any]], conflicts: List[AddressSpaceConflict]
    ) -> List[str]:
        """Automatically renumber conflicting VNet address spaces.

        Modifies resources in-place to resolve conflicts.

        Args:
            resources: List of all resources (will be modified)
            conflicts: List of detected conflicts

        Returns:
            List of VNet names that were renumbered
        """
        renumbered: List[str] = []
        assigned_ranges: Set[str] = set()

        # First pass: collect all currently assigned ranges
        vnets = self._extract_vnets(resources)
        for vnet in vnets:
            address_spaces = self._get_address_spaces(vnet)
            assigned_ranges.update(address_spaces)

        # Second pass: renumber conflicting VNets
        for conflict in conflicts:
            # Skip the first VNet in each conflict, renumber the rest
            vnets_to_renumber = conflict.vnet_names[1:]

            for vnet_name in vnets_to_renumber:
                # Find this VNet in resources
                for resource in resources:
                    if (
                        resource.get("type") == "Microsoft.Network/virtualNetworks"
                        and resource.get("name") == vnet_name
                    ):
                        # Find an available address space
                        new_address_space = self._find_available_range(assigned_ranges)

                        if new_address_space:
                            old_address_space = resource.get("address_space", [])
                            resource["address_space"] = [new_address_space]
                            assigned_ranges.add(new_address_space)
                            renumbered.append(vnet_name)

                            logger.info(
                                f"Auto-renumbered VNet '{vnet_name}': "
                                f"{old_address_space} -> [{new_address_space}]"
                            )
                        else:
                            logger.error(
                                f"Could not find available address space for VNet '{vnet_name}'"
                            )

        return renumbered

    def _find_available_range(self, used_ranges: Set[str]) -> Optional[str]:
        """Find an available private address range.

        Args:
            used_ranges: Set of already-used CIDR ranges

        Returns:
            Available CIDR range or None if exhausted
        """
        # Try common private ranges first
        for candidate in self.PRIVATE_RANGES:
            if candidate not in used_ranges:
                return candidate

        # Generate additional 10.x.0.0/16 ranges
        for i in range(4, 256):
            candidate = f"10.{i}.0.0/16"
            if candidate not in used_ranges:
                return candidate

        logger.error("Exhausted all available private address ranges")
        return None

    def format_conflict_warning(self, conflict: AddressSpaceConflict) -> str:
        """Format a rich, actionable warning message for a conflict.

        Args:
            conflict: The address space conflict to format

        Returns:
            Multi-line formatted warning message with remediation guidance

        Example:
            >>> validator = AddressSpaceValidator()
            >>> conflict = AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16")
            >>> warning = validator.format_conflict_warning(conflict)
            >>> print(warning)
        """
        lines = []
        lines.append("")
        lines.append("=" * 60)
        lines.append("  VNet Address Space Conflict Detected")
        lines.append("=" * 60)
        lines.append("")

        # Show VNet names
        if len(conflict.vnet_names) == 2:
            lines.append(
                f"  VNets:       '{conflict.vnet_names[0]}' <-> '{conflict.vnet_names[1]}'"
            )
        else:
            lines.append(
                f"  VNets:       {', '.join(repr(n) for n in conflict.vnet_names)}"
            )

        # Show conflict details
        if " overlaps " in conflict.address_space:
            lines.append(f"  Conflict:    {conflict.address_space}")
        else:
            lines.append(
                f"  Conflict:    Both use address space {conflict.address_space}"
            )

        lines.append("")

        # Impact description
        lines.append("  Impact:")
        lines.append("    - VNet peering will FAIL")
        lines.append("    - IP routing conflicts will occur")
        lines.append("    - Resources cannot communicate across VNets")
        lines.append("")

        # Remediation guidance
        lines.append("  Remediation:")

        # Suggest alternative range
        alternative = self._suggest_alternative_range(conflict)
        if alternative:
            lines.append(f"    1. Change '{conflict.vnet_names[-1]}' to {alternative}")
        else:
            lines.append(
                f"    1. Change '{conflict.vnet_names[-1]}' to a non-overlapping range"
            )

        lines.append("    2. Use --auto-renumber-conflicts to fix automatically")
        lines.append("")

        # Documentation link
        lines.append("  Learn more:")
        lines.append(
            "    https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-faq#can-i-have-overlapping-address-spaces-for-vnets"
        )
        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)

    def _suggest_alternative_range(
        self, conflict: AddressSpaceConflict
    ) -> Optional[str]:
        """Suggest an alternative address range for conflict resolution.

        Args:
            conflict: The conflict to suggest an alternative for

        Returns:
            Suggested CIDR range or None if none available

        Example:
            >>> validator = AddressSpaceValidator()
            >>> conflict = AddressSpaceConflict(["vnet1", "vnet2"], "10.0.0.0/16")
            >>> suggestion = validator._suggest_alternative_range(conflict)
            >>> print(suggestion)  # e.g., "10.1.0.0/16"
        """
        # Try to find an available range from private ranges
        return self._find_available_range(self._used_ranges)

    def generate_conflict_report(
        self, result: ValidationResult, output_path: Optional[Path] = None
    ) -> str:
        """Generate a markdown report of address space conflicts.

        Args:
            result: ValidationResult with conflict information
            output_path: Optional path to write the report to

        Returns:
            Markdown-formatted conflict report

        Example:
            >>> validator = AddressSpaceValidator()
            >>> result = validator.validate_resources(resources)
            >>> report = validator.generate_conflict_report(result, Path("report.md"))
        """
        lines = []
        lines.append("# VNet Address Space Conflict Report")
        lines.append("")
        lines.append(f"**Generated**: {self._get_timestamp()}")
        lines.append("")

        # Summary section
        lines.append("## Summary")
        lines.append("")
        lines.append(f"- **Total VNets**: {result.vnets_checked}")
        lines.append(f"- **Conflicts Detected**: {len(result.conflicts)}")
        lines.append(
            f"- **Validation Status**: {'PASS' if result.is_valid else 'FAIL'}"
        )

        if result.auto_renumbered:
            lines.append(f"- **Auto-Renumbered**: {len(result.auto_renumbered)} VNets")

        lines.append("")

        # Conflict details
        if result.conflicts:
            lines.append("## Conflicts")
            lines.append("")

            for idx, conflict in enumerate(result.conflicts, 1):
                lines.append(f"### Conflict {idx}: {conflict.address_space}")
                lines.append("")
                lines.append("**VNets Affected**:")
                for vnet_name in conflict.vnet_names:
                    lines.append(f"- `{vnet_name}`")
                lines.append("")

                lines.append(f"**Severity**: {conflict.severity.upper()}")
                lines.append("")

                lines.append("**Impact**:")
                lines.append("- VNet peering will fail between these VNets")
                lines.append("- IP routing conflicts will occur")
                lines.append("- Cross-VNet resource communication is not possible")
                lines.append("")

                # Remediation
                lines.append("**Remediation**:")
                alternative = self._suggest_alternative_range(conflict)
                if alternative:
                    lines.append(
                        f"- Change `{conflict.vnet_names[-1]}` to `{alternative}`"
                    )
                lines.append(
                    "- Run with `--auto-renumber-conflicts` flag to fix automatically"
                )
                lines.append("")
        else:
            lines.append("## No Conflicts Detected")
            lines.append("")
            lines.append("All VNet address spaces are non-overlapping.")
            lines.append("")

        # Warnings section
        if result.warnings:
            lines.append("## Warnings")
            lines.append("")
            for warning in result.warnings:
                lines.append(f"- {warning}")
            lines.append("")

        # Auto-renumbered VNets
        if result.auto_renumbered:
            lines.append("## Auto-Renumbered VNets")
            lines.append("")
            lines.append("The following VNets were automatically renumbered:")
            lines.append("")
            for vnet_name in result.auto_renumbered:
                lines.append(f"- `{vnet_name}`")
            lines.append("")

        # Footer
        lines.append("---")
        lines.append("")
        lines.append(
            "**Documentation**: [Azure VNet Address Spaces](https://learn.microsoft.com/en-us/azure/virtual-network/virtual-networks-faq#can-i-have-overlapping-address-spaces-for-vnets)"
        )
        lines.append("")

        report_text = "\n".join(lines)

        # Write to file if path provided
        if output_path:
            output_path.write_text(report_text)
            logger.info(f"Conflict report written to: {output_path}")

        return report_text

    def _get_timestamp(self) -> str:
        """Get current timestamp for report generation.

        Returns:
            ISO format timestamp string
        """
        from datetime import datetime

        return datetime.now().isoformat()


def validate_address_spaces(
    resources: List[Dict[str, Any]], auto_renumber: bool = False
) -> ValidationResult:
    """Convenience function to validate address spaces.

    Args:
        resources: List of resource dictionaries
        auto_renumber: If True, automatically renumber conflicting ranges

    Returns:
        ValidationResult with conflict information

    Example:
        >>> from validation.address_space_validator import validate_address_spaces
        >>> result = validate_address_spaces(resources, auto_renumber=True)
        >>> if not result.is_valid:
        ...     print(f"Found {len(result.conflicts)} conflicts")
    """
    validator = AddressSpaceValidator(auto_renumber=auto_renumber)
    return validator.validate_resources(resources, modify_in_place=auto_renumber)
