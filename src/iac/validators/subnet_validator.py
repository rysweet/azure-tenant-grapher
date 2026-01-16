"""
Subnet Address Range Validation for IaC Generation

Validates subnet address ranges to ensure they:
1. Fall within their parent VNet address space
2. Don't overlap with other subnets in the same VNet
3. Have sufficient address space for resources
4. Auto-fixes subnet addresses when VNet range is known

This prevents Terraform deployment failures due to invalid subnet configurations.
"""

import ipaddress
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SubnetValidationIssue:
    """Represents a validation issue found with a subnet."""

    subnet_name: str
    vnet_name: str
    issue_type: str  # "out_of_range", "overlap", "insufficient_space"
    message: str
    original_prefix: Optional[str] = None
    suggested_prefix: Optional[str] = None
    auto_fixable: bool = False


@dataclass
class ValidationResult:
    """Result of subnet validation for a VNet."""

    vnet_name: str
    vnet_address_space: List[str]
    valid: bool
    issues: List[SubnetValidationIssue]
    auto_fixed: bool = False


class SubnetValidator:
    """
    Validates subnet address ranges for IaC generation.

    This validator checks that:
    - Subnets fall within their VNet's address space
    - Subnets don't overlap with each other
    - Subnets have adequate address space

    It can also auto-fix subnet addresses when the VNet range is known.
    """

    def __init__(self, auto_fix: bool = True):
        """
        Initialize the subnet validator.

        Args:
            auto_fix: If True, attempt to auto-fix subnet address issues
        """
        self.auto_fix = auto_fix

    def validate_vnet_subnets(
        self,
        vnet_name: str,
        vnet_address_space: List[str],
        subnets: List[Dict[str, Any]],
    ) -> ValidationResult:
        """
        Validate all subnets for a given VNet.

        Args:
            vnet_name: Name of the VNet
            vnet_address_space: List of CIDR ranges for the VNet
            subnets: List of subnet configurations to validate

        Returns:
            ValidationResult with any issues found
        """
        issues: List[SubnetValidationIssue] = []
        auto_fixed = False

        # Parse VNet address space
        try:
            vnet_networks = [
                ipaddress.ip_network(addr, strict=False) for addr in vnet_address_space
            ]
        except ValueError as e:
            logger.error(
                f"Invalid VNet address space for '{vnet_name}': {vnet_address_space} - {e}"
            )
            return ValidationResult(
                vnet_name=vnet_name,
                vnet_address_space=vnet_address_space,
                valid=False,
                issues=[
                    SubnetValidationIssue(
                        subnet_name="N/A",
                        vnet_name=vnet_name,
                        issue_type="invalid_vnet_space",
                        message=f"Invalid VNet address space: {e}",
                    )
                ],
            )

        # Track allocated subnet networks for overlap detection
        allocated_subnets: List[
            tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]
        ] = []

        for subnet in subnets:
            subnet_name = subnet.get("name", "unknown")
            address_prefixes = self._extract_address_prefixes(subnet)

            if not address_prefixes:
                issues.append(
                    SubnetValidationIssue(
                        subnet_name=subnet_name,
                        vnet_name=vnet_name,
                        issue_type="missing_prefix",
                        message="Subnet has no address prefix defined",
                    )
                )
                continue

            # Validate each address prefix
            for prefix in address_prefixes:
                try:
                    subnet_network = ipaddress.ip_network(prefix, strict=False)
                except ValueError as e:
                    issues.append(
                        SubnetValidationIssue(
                            subnet_name=subnet_name,
                            vnet_name=vnet_name,
                            issue_type="invalid_prefix",
                            message=f"Invalid subnet prefix '{prefix}': {e}",
                            original_prefix=prefix,
                        )
                    )
                    continue

                # Check if subnet is within VNet address space
                within_vnet = any(  # type: ignore[arg-type]
                    subnet_network.subnet_of(vnet_net)  # type: ignore
                    for vnet_net in vnet_networks
                )

                if not within_vnet:
                    # Attempt auto-fix if enabled
                    if self.auto_fix and vnet_networks:
                        suggested_prefix = self._suggest_subnet_prefix(
                            subnet_network, vnet_networks[0], allocated_subnets
                        )
                        if suggested_prefix:
                            # Update subnet with corrected prefix
                            self._update_subnet_prefix(subnet, prefix, suggested_prefix)
                            auto_fixed = True
                            issues.append(
                                SubnetValidationIssue(
                                    subnet_name=subnet_name,
                                    vnet_name=vnet_name,
                                    issue_type="out_of_range",
                                    message=f"Subnet prefix '{prefix}' is outside VNet range, auto-fixed to '{suggested_prefix}'",
                                    original_prefix=prefix,
                                    suggested_prefix=suggested_prefix,
                                    auto_fixable=True,
                                )
                            )
                            # Use the corrected network for overlap detection
                            subnet_network = ipaddress.ip_network(
                                suggested_prefix, strict=False
                            )
                        else:
                            issues.append(
                                SubnetValidationIssue(
                                    subnet_name=subnet_name,
                                    vnet_name=vnet_name,
                                    issue_type="out_of_range",
                                    message=f"Subnet prefix '{prefix}' is outside VNet address space {vnet_address_space}",
                                    original_prefix=prefix,
                                )
                            )
                            continue
                    else:
                        issues.append(
                            SubnetValidationIssue(
                                subnet_name=subnet_name,
                                vnet_name=vnet_name,
                                issue_type="out_of_range",
                                message=f"Subnet prefix '{prefix}' is outside VNet address space {vnet_address_space}",
                                original_prefix=prefix,
                            )
                        )
                        continue

                # Check for overlaps with existing subnets
                for allocated_name, allocated_net in allocated_subnets:
                    if subnet_network.overlaps(allocated_net):
                        issues.append(
                            SubnetValidationIssue(
                                subnet_name=subnet_name,
                                vnet_name=vnet_name,
                                issue_type="overlap",
                                message=f"Subnet '{subnet_name}' ({prefix}) overlaps with '{allocated_name}' ({allocated_net})",
                                original_prefix=prefix,
                            )
                        )

                # Check for sufficient address space (warn if too small)
                if subnet_network.num_addresses < 16:
                    issues.append(
                        SubnetValidationIssue(
                            subnet_name=subnet_name,
                            vnet_name=vnet_name,
                            issue_type="insufficient_space",
                            message=f"Subnet '{subnet_name}' has only {subnet_network.num_addresses} addresses (recommend at least /28 or 16 addresses)",
                            original_prefix=prefix,
                        )
                    )

                # Track this subnet for overlap detection
                allocated_subnets.append((subnet_name, subnet_network))

        # Determine if validation passed
        critical_issues = [
            i
            for i in issues
            if i.issue_type
            in ("out_of_range", "overlap", "invalid_prefix", "missing_prefix")
            and not i.auto_fixable
        ]
        valid = len(critical_issues) == 0

        return ValidationResult(
            vnet_name=vnet_name,
            vnet_address_space=vnet_address_space,
            valid=valid,
            issues=issues,
            auto_fixed=auto_fixed,
        )

    def validate_terraform_resources(
        self, terraform_resources: Dict[str, Any]
    ) -> List[ValidationResult]:
        """
        Validate all VNets and subnets in a Terraform configuration.

        Args:
            terraform_resources: Terraform resources dict from configuration

        Returns:
            List of ValidationResult for each VNet
        """
        results: List[ValidationResult] = []

        # Extract VNets
        vnets = terraform_resources.get("azurerm_virtual_network", {})

        for vnet_name, vnet_config in vnets.items():
            address_space = vnet_config.get("address_space", [])

            # Find subnets for this VNet
            subnets = self._find_subnets_for_vnet(vnet_name, terraform_resources)

            # Validate subnets
            result = self.validate_vnet_subnets(vnet_name, address_space, subnets)
            results.append(result)

        return results

    def _extract_address_prefixes(self, subnet: Dict[str, Any]) -> List[str]:
        """
        Extract address prefixes from subnet configuration.

        Args:
            subnet: Subnet configuration dict

        Returns:
            List of address prefixes (CIDR strings)
        """
        # Handle different formats
        if "address_prefixes" in subnet:
            return subnet["address_prefixes"]
        elif "addressPrefixes" in subnet:
            return subnet["addressPrefixes"]
        elif "address_prefix" in subnet:
            return [subnet["address_prefix"]]
        elif "addressPrefix" in subnet:
            return [subnet["addressPrefix"]]

        # Try parsing properties if it's a JSON string
        properties = subnet.get("properties", {})
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                return []

        if isinstance(properties, dict):
            if "addressPrefixes" in properties:
                return properties["addressPrefixes"]
            elif "addressPrefix" in properties:
                return [properties["addressPrefix"]]

        return []

    def _update_subnet_prefix(
        self, subnet: Dict[str, Any], old_prefix: str, new_prefix: str
    ) -> None:
        """
        Update a subnet's address prefix in-place.

        Args:
            subnet: Subnet configuration dict to update
            old_prefix: Old prefix to replace
            new_prefix: New prefix to use
        """
        # Update in various possible locations
        if "address_prefixes" in subnet:
            subnet["address_prefixes"] = [
                new_prefix if p == old_prefix else p for p in subnet["address_prefixes"]
            ]
        elif "address_prefix" in subnet:
            subnet["address_prefix"] = new_prefix

        # Update in properties if present
        properties = subnet.get("properties")
        if isinstance(properties, dict):
            if "addressPrefixes" in properties:
                properties["addressPrefixes"] = [
                    new_prefix if p == old_prefix else p
                    for p in properties["addressPrefixes"]
                ]
            elif "addressPrefix" in properties:
                properties["addressPrefix"] = new_prefix

    def _suggest_subnet_prefix(
        self,
        original_subnet: ipaddress.IPv4Network | ipaddress.IPv6Network,
        vnet_network: ipaddress.IPv4Network | ipaddress.IPv6Network,
        allocated_subnets: List[
            tuple[str, ipaddress.IPv4Network | ipaddress.IPv6Network]
        ],
    ) -> Optional[str]:
        """
        Suggest a valid subnet prefix within the VNet range.

        Args:
            original_subnet: The original (invalid) subnet
            vnet_network: The VNet's address space
            allocated_subnets: Already allocated subnets to avoid

        Returns:
            Suggested CIDR prefix or None if no space available
        """
        # Try to preserve the same prefix length
        target_prefixlen = original_subnet.prefixlen

        # Generate candidate subnets
        try:
            for candidate in vnet_network.subnets(new_prefix=target_prefixlen):
                # Check if this candidate overlaps with any allocated subnet
                overlaps = any(
                    candidate.overlaps(allocated_net)
                    for _, allocated_net in allocated_subnets
                )
                if not overlaps:
                    return str(candidate)
        except ValueError:
            # Prefix length too small for VNet, try with larger prefix
            logger.debug(
                f"Cannot fit /{target_prefixlen} subnet in VNet, trying smaller subnets"
            )

        return None

    def _find_subnets_for_vnet(
        self, vnet_name: str, terraform_resources: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Find all subnets that belong to a specific VNet.

        Args:
            vnet_name: Name of the VNet (Terraform resource name)
            terraform_resources: All Terraform resources

        Returns:
            List of subnet configurations
        """
        subnets = []
        subnet_resources = terraform_resources.get("azurerm_subnet", {})

        for subnet_name, subnet_config in subnet_resources.items():
            # Check if virtual_network_name references this VNet
            vnet_ref = subnet_config.get("virtual_network_name", "")

            # Handle Terraform references like ${azurerm_virtual_network.vnet_name.name}
            if vnet_name in vnet_ref or vnet_ref == vnet_name:
                subnets.append({"name": subnet_name, **subnet_config})

        return subnets

    def format_validation_report(self, results: List[ValidationResult]) -> str:
        """
        Format validation results into a human-readable report.

        Args:
            results: List of validation results

        Returns:
            Formatted report string
        """
        lines = ["", "Subnet Validation Report", "=" * 50, ""]

        total_issues = sum(len(r.issues) for r in results)
        valid_vnets = sum(1 for r in results if r.valid)
        auto_fixed_vnets = sum(1 for r in results if r.auto_fixed)

        lines.append(f"Total VNets: {len(results)}")
        lines.append(f"Valid VNets: {valid_vnets}")
        lines.append(f"Auto-fixed VNets: {auto_fixed_vnets}")
        lines.append(f"Total Issues: {total_issues}")
        lines.append("")

        for result in results:
            if not result.issues:
                continue

            lines.append(f"VNet: {result.vnet_name}")
            lines.append(f"  Address Space: {', '.join(result.vnet_address_space)}")
            lines.append(f"  Status: {'VALID' if result.valid else 'INVALID'}")

            if result.auto_fixed:
                lines.append("  Auto-fixed: YES")

            lines.append(f"  Issues: {len(result.issues)}")
            lines.append("")

            for issue in result.issues:
                prefix = "  [AUTO-FIXED]" if issue.auto_fixable else "  [WARNING]"
                lines.append(f"{prefix} {issue.subnet_name}: {issue.message}")

                if issue.suggested_prefix:
                    lines.append(
                        f"    Changed: {issue.original_prefix} -> {issue.suggested_prefix}"
                    )

            lines.append("")

        return "\n".join(lines)
