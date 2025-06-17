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

logger = logging.getLogger(__name__)


@dataclass
class TransformationRule:
    """Defines a transformation rule for converting resources to IaC."""

    resource_type: str
    actions: Dict[str, Any] = field(default_factory=dict)


class TransformationEngine:
    """Engine for transforming tenant graphs into IaC templates."""

    def __init__(self, rules_file: Optional[str] = None) -> None:
        """Initialize transformation engine.

        Args:
            rules_file: Optional path to rules configuration file
        """
        self.rules: List[TransformationRule] = []
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
