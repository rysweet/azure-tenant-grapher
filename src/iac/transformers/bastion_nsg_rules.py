"""Bastion NSG rule generator for Azure Bastion subnets.

This module adds required NSG rules for Azure Bastion subnets,
preventing NetworkSecurityGroupNotCompliantForAzureBastionSubnet errors (2 errors).

Azure Bastion Requirements:
- Specific inbound and outbound rules required
- Rules must be merged with existing rules, not replaced
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class BastionRuleGenerationResult:
    """Result of Bastion NSG rule generation."""

    nsgs_processed: int
    nsgs_modified: int
    rules_added: int
    modifications: List[tuple[str, int]] = None  # (nsg_name, rules_added_count)

    def __post_init__(self):
        if self.modifications is None:
            self.modifications = []


class BastionNSGRuleGenerator:
    """Generate required NSG rules for Azure Bastion subnets.

    Adds Azure-required rules while preserving existing rules.
    """

    # Required inbound rules for Azure Bastion
    REQUIRED_INBOUND_RULES = [
        {
            "name": "AllowHttpsInbound",
            "priority": 120,
            "direction": "Inbound",
            "access": "Allow",
            "protocol": "Tcp",
            "sourcePortRange": "*",
            "destinationPortRange": "443",
            "sourceAddressPrefix": "Internet",
            "destinationAddressPrefix": "*",
            "description": "Allow HTTPS inbound from Internet",
        },
        {
            "name": "AllowGatewayManagerInbound",
            "priority": 130,
            "direction": "Inbound",
            "access": "Allow",
            "protocol": "Tcp",
            "sourcePortRange": "*",
            "destinationPortRange": "443",
            "sourceAddressPrefix": "GatewayManager",
            "destinationAddressPrefix": "*",
            "description": "Allow Gateway Manager inbound",
        },
        {
            "name": "AllowAzureLoadBalancerInbound",
            "priority": 140,
            "direction": "Inbound",
            "access": "Allow",
            "protocol": "Tcp",
            "sourcePortRange": "*",
            "destinationPortRange": "443",
            "sourceAddressPrefix": "AzureLoadBalancer",
            "destinationAddressPrefix": "*",
            "description": "Allow Azure Load Balancer inbound",
        },
        {
            "name": "AllowBastionHostCommunication",
            "priority": 150,
            "direction": "Inbound",
            "access": "Allow",
            "protocol": "*",
            "sourcePortRange": "*",
            "destinationPortRanges": ["8080", "5701"],
            "sourceAddressPrefix": "VirtualNetwork",
            "destinationAddressPrefix": "VirtualNetwork",
            "description": "Allow Bastion host communication",
        },
    ]

    # Required outbound rules for Azure Bastion
    REQUIRED_OUTBOUND_RULES = [
        {
            "name": "AllowSshRdpOutbound",
            "priority": 100,
            "direction": "Outbound",
            "access": "Allow",
            "protocol": "*",
            "sourcePortRange": "*",
            "destinationPortRanges": ["22", "3389"],
            "sourceAddressPrefix": "*",
            "destinationAddressPrefix": "VirtualNetwork",
            "description": "Allow SSH and RDP to VirtualNetwork",
        },
        {
            "name": "AllowAzureCloudOutbound",
            "priority": 110,
            "direction": "Outbound",
            "access": "Allow",
            "protocol": "Tcp",
            "sourcePortRange": "*",
            "destinationPortRange": "443",
            "sourceAddressPrefix": "*",
            "destinationAddressPrefix": "AzureCloud",
            "description": "Allow HTTPS to AzureCloud",
        },
        {
            "name": "AllowBastionCommunication",
            "priority": 120,
            "direction": "Outbound",
            "access": "Allow",
            "protocol": "*",
            "sourcePortRange": "*",
            "destinationPortRanges": ["8080", "5701"],
            "sourceAddressPrefix": "VirtualNetwork",
            "destinationAddressPrefix": "VirtualNetwork",
            "description": "Allow Bastion host communication outbound",
        },
        {
            "name": "AllowGetSessionInformation",
            "priority": 130,
            "direction": "Outbound",
            "access": "Allow",
            "protocol": "*",
            "sourcePortRange": "*",
            "destinationPortRange": "80",
            "sourceAddressPrefix": "*",
            "destinationAddressPrefix": "Internet",
            "description": "Allow session information retrieval",
        },
    ]

    def __init__(self) -> None:
        """Initialize Bastion NSG rule generator."""
        logger.info("BastionNSGRuleGenerator initialized")

    def transform_resources(self, resources: List[Dict[str, Any]]) -> BastionRuleGenerationResult:
        """Add Bastion NSG rules to appropriate NSGs.

        Args:
            resources: List of resources to transform (modified in place)

        Returns:
            BastionRuleGenerationResult with transformation statistics
        """
        # Find Bastion subnets and their associated NSGs
        bastion_nsgs = self._find_bastion_nsgs(resources)

        nsgs_processed = 0
        nsgs_modified = 0
        rules_added = 0
        modifications = []

        logger.info(f"Found {len(bastion_nsgs)} NSGs associated with Bastion subnets")

        for nsg in bastion_nsgs:
            nsgs_processed += 1
            nsg_name = nsg.get("name", "unknown")

            # Add required rules
            added_count = self._add_bastion_rules(nsg)

            if added_count > 0:
                nsgs_modified += 1
                rules_added += added_count
                modifications.append((nsg_name, added_count))

                logger.info(
                    f"Added {added_count} Bastion rules to NSG '{nsg_name}'"
                )

        logger.info(
            f"Bastion NSG rule generation complete: {nsgs_modified}/{nsgs_processed} NSGs modified, "
            f"{rules_added} rules added"
        )

        return BastionRuleGenerationResult(
            nsgs_processed=nsgs_processed,
            nsgs_modified=nsgs_modified,
            rules_added=rules_added,
            modifications=modifications,
        )

    def _find_bastion_nsgs(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Find NSGs associated with Bastion subnets.

        Args:
            resources: List of resources

        Returns:
            List of NSG resources associated with Bastion subnets
        """
        bastion_nsg_ids = set()
        nsg_map = {}

        # First pass: find Bastion subnets and collect their NSG IDs
        for resource in resources:
            resource_type = resource.get("type", "")

            # Check for Bastion subnets in VNets
            if resource_type == "Microsoft.Network/virtualNetworks":
                properties = resource.get("properties", {})
                if isinstance(properties, dict):
                    subnets = properties.get("subnets", [])

                    for subnet in subnets:
                        subnet_name = subnet.get("name", "").lower()
                        if subnet_name == "azurebastionsubnet":
                            # This is a Bastion subnet
                            subnet_props = subnet.get("properties", {})
                            if isinstance(subnet_props, dict):
                                nsg_ref = subnet_props.get("networkSecurityGroup", {})
                                if isinstance(nsg_ref, dict):
                                    nsg_id = nsg_ref.get("id", "")
                                    if nsg_id:
                                        bastion_nsg_ids.add(nsg_id)
                                        logger.debug(
                                            f"Found Bastion subnet NSG: {nsg_id}"
                                        )

            # Collect all NSGs
            if resource_type == "Microsoft.Network/networkSecurityGroups":
                nsg_id = resource.get("id", "")
                if nsg_id:
                    nsg_map[nsg_id] = resource

        # Return NSGs that are associated with Bastion subnets
        bastion_nsgs = [nsg_map[nsg_id] for nsg_id in bastion_nsg_ids if nsg_id in nsg_map]

        return bastion_nsgs

    def _add_bastion_rules(self, nsg: Dict[str, Any]) -> int:
        """Add required Bastion rules to NSG.

        Args:
            nsg: NSG resource (modified in place)

        Returns:
            Number of rules added
        """
        properties = nsg.get("properties", {})
        if not isinstance(properties, dict):
            properties = {}
            nsg["properties"] = properties

        # Get existing security rules
        security_rules = properties.get("securityRules", [])
        if not isinstance(security_rules, list):
            security_rules = []
            properties["securityRules"] = security_rules

        # Get existing rule names for deduplication
        existing_rule_names = {rule.get("name", "").lower() for rule in security_rules}

        rules_added = 0

        # Add required inbound rules
        for rule in self.REQUIRED_INBOUND_RULES:
            if rule["name"].lower() not in existing_rule_names:
                security_rules.append(self._create_rule_dict(rule))
                rules_added += 1
                logger.debug(f"Added inbound rule: {rule['name']}")

        # Add required outbound rules
        for rule in self.REQUIRED_OUTBOUND_RULES:
            if rule["name"].lower() not in existing_rule_names:
                security_rules.append(self._create_rule_dict(rule))
                rules_added += 1
                logger.debug(f"Added outbound rule: {rule['name']}")

        return rules_added

    def _create_rule_dict(self, rule_template: Dict[str, Any]) -> Dict[str, Any]:
        """Create rule dictionary with proper structure.

        Args:
            rule_template: Rule template

        Returns:
            Formatted rule dictionary
        """
        rule = {
            "name": rule_template["name"],
            "properties": {
                "priority": rule_template["priority"],
                "direction": rule_template["direction"],
                "access": rule_template["access"],
                "protocol": rule_template["protocol"],
                "sourcePortRange": rule_template.get("sourcePortRange"),
                "sourceAddressPrefix": rule_template.get("sourceAddressPrefix"),
                "destinationAddressPrefix": rule_template.get("destinationAddressPrefix"),
                "description": rule_template.get("description", ""),
            },
        }

        # Handle single or multiple destination ports
        if "destinationPortRange" in rule_template:
            rule["properties"]["destinationPortRange"] = rule_template["destinationPortRange"]
        elif "destinationPortRanges" in rule_template:
            rule["properties"]["destinationPortRanges"] = rule_template["destinationPortRanges"]

        return rule

    def get_generation_summary(self, result: BastionRuleGenerationResult) -> str:
        """Generate human-readable summary of rule generation results.

        Args:
            result: Rule generation result to summarize

        Returns:
            Formatted summary string
        """
        summary = [
            "Bastion NSG Rule Generator Summary",
            "=" * 50,
            f"NSGs processed: {result.nsgs_processed}",
            f"NSGs modified: {result.nsgs_modified}",
            f"Rules added: {result.rules_added}",
            "",
        ]

        if result.modifications:
            summary.append("NSG Modifications:")
            for nsg_name, rules_added in result.modifications:
                summary.append(f"  - {nsg_name}: {rules_added} rules added")

        return "\n".join(summary)
