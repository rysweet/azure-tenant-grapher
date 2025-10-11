"""Transformation engine for converting graph data to IaC templates.

This module provides the core transformation logic for converting
tenant graph data into Infrastructure-as-Code representations.
"""

import copy
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ruamel.yaml import YAML

from .subset import SubsetFilter, SubsetSelector
from .traverser import TenantGraph
from .validators.subnet_validator import SubnetValidator, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class TransformationRule:
    """Defines a transformation rule for converting resources to IaC."""

    resource_type: str
    actions: Dict[str, Any] = field(default_factory=dict)


class TransformationEngine:
    """Engine for transforming tenant graphs into IaC templates."""

    def __init__(
        self, rules_file: Optional[str] = None, aad_mode: str = "manual"
    ) -> None:
        """Initialize transformation engine.

        Args:
            rules_file: Optional path to rules configuration file
            aad_mode: AAD object creation/replication mode (none, manual, auto)
        """
        self.rules: List[TransformationRule] = []
        self.aad_mode: str = aad_mode
        if rules_file:
            self.rules = self._parse_rules(rules_file)

    def _parse_rules(self, rules_file: str) -> List[TransformationRule]:
        """Parse transformation rules from configuration file.

        Args:
            rules_file: Path to rules configuration file

        Returns:
            List of parsed transformation rules
        """
        rules = []
        try:
            yaml = YAML(typ="safe")
            rules_path = Path(rules_file)

            if not rules_path.exists():
                logger.warning(f"Rules file not found: {rules_file}")
                return rules

            with open(rules_path) as f:
                rules_data = yaml.load(f)

            if not rules_data or "rules" not in rules_data:
                logger.warning(f"No rules found in file: {rules_file}")
                return rules

            for rule_data in rules_data["rules"]:
                if "resource_type" in rule_data and "actions" in rule_data:
                    rule = TransformationRule(
                        resource_type=rule_data["resource_type"],
                        actions=rule_data["actions"],
                    )
                    rules.append(rule)

            logger.info(f"Loaded {len(rules)} transformation rules from {rules_file}")

        except Exception as e:
            logger.error(f"Error parsing rules file {rules_file}: {e}")

        return rules

    def apply(self, resource_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Apply transformation rules to a resource.

        Args:
            resource_dict: Resource data to transform

        Returns:
            Transformed resource data (copy of original)
        """
        result = copy.deepcopy(resource_dict)
        resource_type = resource_dict.get("type", "")

        # Find matching rules
        for rule in self.rules:
            if self._matches_rule(resource_type, rule.resource_type):
                result = self._apply_rule_actions(result, rule.actions)

        return result

    def generate_iac(
        self,
        graph: TenantGraph,
        emitter: Any,
        out_dir: Path | str,
        subset_filter: Optional[SubsetFilter] = None,
        validate_subnet_containment: bool = True,
        auto_fix_subnets: bool = False,
        tenant_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> List[str]:
        """Generate IaC templates from tenant graph.

        Args:
            graph: The full tenant graph
            emitter: The IaCEmitter instance (e.g., BicepEmitter)
            out_dir: Output directory for templates (Path or str)
            subset_filter: Optional SubsetFilter for resource selection
            validate_subnet_containment: Validate subnets are within VNet address space
            auto_fix_subnets: Automatically fix subnet addresses outside VNet range
            tenant_id: Optional tenant ID (for metadata)
            subscription_id: Optional subscription ID (for metadata)

        Returns:
            List of output file paths

        Raises:
            ValueError: If subnet validation fails and auto_fix_subnets is False
        """
        filtered_graph = graph
        if subset_filter is not None and SubsetSelector().has_filters(subset_filter):
            selector = SubsetSelector()
            filtered_graph = selector.apply(graph, subset_filter)
            logger.info(f"Filtered graph: {len(filtered_graph.resources)} resources")

        # Apply transformation rules to each resource
        transformed_resources = []
        for resource in filtered_graph.resources:
            transformed = self.apply(resource)
            transformed_resources.append(transformed)
        filtered_graph.resources = transformed_resources

        # Validate subnet containment (Issue #333)
        if validate_subnet_containment:
            logger.info("Validating subnet address space containment...")

            subnet_validator = SubnetValidator(auto_fix=auto_fix_subnets)
            validation_results = self._validate_subnet_containment(
                filtered_graph.resources, subnet_validator
            )

            # Log results
            for result in validation_results:
                if not result.valid:
                    logger.error(
                        f"VNet '{result.vnet_name}': {len(result.issues)} subnet issues"
                    )
                    for issue in result.issues:
                        if issue.issue_type in (
                            "out_of_range",
                            "overlap",
                            "invalid_prefix",
                        ):
                            logger.error(f"  ❌ {issue.subnet_name}: {issue.message}")
                        else:
                            logger.warning(f"  ⚠️  {issue.subnet_name}: {issue.message}")

            # Check for critical failures
            critical_issues = [
                r for r in validation_results if not r.valid and not r.auto_fixed
            ]

            if critical_issues:
                error_report = subnet_validator.format_validation_report(
                    validation_results
                )
                logger.error(error_report)
                raise ValueError(
                    f"Subnet validation failed for {len(critical_issues)} VNets. "
                    "Use --skip-subnet-validation to bypass (not recommended), "
                    "or fix subnet address spaces in source data."
                )

            # Log auto-fix success
            auto_fixed = [r for r in validation_results if r.auto_fixed]
            if auto_fixed:
                logger.info(f"✅ Auto-fixed subnets in {len(auto_fixed)} VNets")

        return emitter.emit(filtered_graph, out_dir)

    def _matches_rule(self, resource_type: str, rule_pattern: str) -> bool:
        """Check if resource type matches rule pattern.

        Args:
            resource_type: The resource type to check
            rule_pattern: The rule pattern (supports wildcards)

        Returns:
            True if resource type matches the rule pattern
        """
        if rule_pattern == "*":
            return True

        # Exact match
        if resource_type == rule_pattern:
            return True

        # Azure type prefix match (e.g., "Microsoft.Compute" matches "Microsoft.Compute/virtualMachines")
        if resource_type.startswith(rule_pattern + "/"):
            return True

        return False

    def _apply_rule_actions(
        self, resource: Dict[str, Any], actions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply rule actions to a resource.

        Args:
            resource: Resource to modify
            actions: Actions to apply

        Returns:
            Modified resource
        """
        result = copy.deepcopy(resource)

        # Apply rename action
        if "rename" in actions:
            rename_config = actions["rename"]
            if "pattern" in rename_config:
                pattern = rename_config["pattern"]
                original_name = result.get("name", "")

                # Support {orig} and {index} tokens
                new_name = pattern.replace("{orig}", original_name)
                # For {index}, we'll use a simple counter (could be enhanced)
                new_name = new_name.replace("{index}", "1")

                result["name"] = new_name

        # Apply region action
        if "region" in actions:
            region_config = actions["region"]
            if "target" in region_config:
                result["location"] = region_config["target"]

        # Apply tag action
        if "tag" in actions:
            tag_config = actions["tag"]
            if "add" in tag_config:
                if "tags" not in result:
                    result["tags"] = {}
                result["tags"].update(tag_config["add"])

        return result

    def _validate_subnet_containment(
        self, resources: List[Dict[str, Any]], validator: SubnetValidator
    ) -> List[ValidationResult]:
        """Validate subnet containment for all VNets.

        Args:
            resources: List of resources to validate
            validator: SubnetValidator instance to use

        Returns:
            List of ValidationResult for each VNet
        """
        results = []

        # Extract VNets
        vnets = [
            r for r in resources if r.get("type") == "Microsoft.Network/virtualNetworks"
        ]

        for vnet in vnets:
            vnet_name = vnet.get("name", "unknown")
            vnet_address_space = vnet.get("address_space", [])

            # Extract subnets
            subnets = self._extract_subnets_from_vnet(vnet)

            # Validate
            result = validator.validate_vnet_subnets(
                vnet_name=vnet_name,
                vnet_address_space=vnet_address_space,
                subnets=subnets,
            )

            results.append(result)

        return results

    def _extract_subnets_from_vnet(self, vnet: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract subnet configurations from VNet resource.

        Args:
            vnet: VNet resource dictionary

        Returns:
            List of subnet configurations
        """
        properties = vnet.get("properties", {})

        # Handle JSON string from Neo4j
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse properties for VNet '{vnet.get('name')}'"
                )
                return []

        subnets = properties.get("subnets", [])

        # Normalize subnet format
        normalized_subnets = []
        for subnet in subnets:
            subnet_props = subnet.get("properties", {})

            normalized = {"name": subnet.get("name"), "address_prefixes": []}

            # Extract address prefix(es)
            if "addressPrefix" in subnet_props:
                normalized["address_prefixes"] = [subnet_props["addressPrefix"]]
            elif "addressPrefixes" in subnet_props:
                normalized["address_prefixes"] = subnet_props["addressPrefixes"]

            if normalized["address_prefixes"]:
                normalized_subnets.append(normalized)

        return normalized_subnets
