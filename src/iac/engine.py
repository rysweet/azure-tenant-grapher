"""Transformation engine for converting graph data to IaC templates.

This module provides the core transformation logic for converting
tenant graph data into Infrastructure-as-Code representations.
"""

import copy
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ruamel.yaml import YAML

from ..validation.address_space_validator import (
    AddressSpaceValidator,
)
from .subset import SubsetFilter, SubsetSelector
from .traverser import TenantGraph

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
        validate_address_spaces: bool = True,
        auto_renumber_conflicts: bool = False,
        tenant_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> List[str]:
        """Generate IaC templates from tenant graph.

        Args:
            graph: The full tenant graph
            emitter: The IaCEmitter instance (e.g., BicepEmitter)
            out_dir: Output directory for templates (Path or str)
            subset_filter: Optional SubsetFilter for resource selection
            validate_address_spaces: If True, validate VNet address spaces (default: True)
            auto_renumber_conflicts: If True, auto-renumber conflicting address spaces (default: False)
            tenant_id: Optional SOURCE Azure tenant ID for Neo4j operations
            subscription_id: Optional TARGET subscription ID for resource deployment

        Returns:
            List of output file paths
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

        # Validate VNet address spaces before generation (GAP-012)
        if validate_address_spaces:
            logger.info("Validating VNet address spaces for conflicts...")
            validator = AddressSpaceValidator(auto_renumber=auto_renumber_conflicts)
            validation_result = validator.validate_resources(
                filtered_graph.resources, modify_in_place=auto_renumber_conflicts
            )

            # Log validation results
            if validation_result.is_valid:
                logger.info(
                    f"Address space validation passed: {validation_result.vnets_checked} VNets checked"
                )
            else:
                logger.warning(
                    f"Address space validation found {len(validation_result.conflicts)} conflicts"
                )
                # Use rich formatted warnings (Issue #334)
                for conflict in validation_result.conflicts:
                    rich_warning = validator.format_conflict_warning(conflict)
                    logger.warning(rich_warning)

            # Log warnings
            for warning in validation_result.warnings:
                logger.warning(f"  - {warning}")

            # Log auto-renumbering results
            if validation_result.auto_renumbered:
                logger.info(
                    f"Auto-renumbered {len(validation_result.auto_renumbered)} VNets: "
                    f"{', '.join(validation_result.auto_renumbered)}"
                )

        # Pass tenant_id and subscription_id to emitter if it supports them (use introspection)
        import inspect

        emit_signature = inspect.signature(emitter.emit)
        emit_kwargs = {}
        if "tenant_id" in emit_signature.parameters:
            emit_kwargs["tenant_id"] = tenant_id
        if "subscription_id" in emit_signature.parameters:
            emit_kwargs["subscription_id"] = subscription_id

        return emitter.emit(filtered_graph, out_dir, **emit_kwargs)

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
