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

from ..validation.address_space_validator import (
    AddressSpaceValidator,
)
from .filters.cross_tenant_filter import CrossTenantResourceFilter
from .filters.existing_resource_filter import ExistingResourceFilter
from .subset import SubsetFilter, SubsetSelector
from .transformers.bastion_nsg_rules import BastionNSGRuleGenerator
from .transformers.location_mapper import GlobalLocationMapper
from .transformers.name_generator import UniqueNameGenerator
from .traverser import TenantGraph
from .validators.subnet_validator import SubnetValidator, ValidationResult
from .validators.vnet_link_validator import VNetLinkDependencyValidator

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
        validate_address_spaces: bool = True,
        auto_renumber_conflicts: bool = False,
        tenant_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        source_subscription_id: Optional[str] = None,
        enable_cross_tenant_filter: bool = True,
        enable_existing_resource_filter: bool = False,
        enable_name_generation: bool = True,
        enable_location_mapping: bool = True,
        enable_bastion_nsg_rules: bool = True,
        enable_vnet_link_validation: bool = True,
        name_generation_suffix: Optional[str] = None,
    ) -> List[str]:
        """Generate IaC templates from tenant graph.

        Args:
            graph: The full tenant graph
            emitter: The IaCEmitter instance (e.g., BicepEmitter)
            out_dir: Output directory for templates (Path or str)
            subset_filter: Optional SubsetFilter for resource selection
            validate_subnet_containment: Validate subnets are within VNet address space (Issue #333)
            auto_fix_subnets: Automatically fix subnet addresses outside VNet range (Issue #333)
            validate_address_spaces: Validate VNet address spaces don't overlap (Issue #334)
            auto_renumber_conflicts: Auto-renumber conflicting VNet address spaces (Issue #334)
            tenant_id: Optional SOURCE Azure tenant ID for Neo4j operations
            subscription_id: Optional TARGET subscription ID for resource deployment
            source_subscription_id: Optional SOURCE subscription ID (for cross-tenant filtering)
            enable_cross_tenant_filter: Enable cross-tenant resource filter (fixes 130 errors)
            enable_existing_resource_filter: Enable existing resource filter (fixes 67 errors)
            enable_name_generation: Enable unique name generation (fixes 97 errors)
            enable_location_mapping: Enable global location mapping (fixes 2 errors)
            enable_bastion_nsg_rules: Enable Bastion NSG rule generation (fixes 2 errors)
            enable_vnet_link_validation: Enable VNet Link dependency validation (fixes 22 errors)
            name_generation_suffix: Optional suffix for generated names

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

        # ===== DEPLOYMENT ERROR FIX PIPELINE (Issue #374) =====
        logger.info("Starting deployment error fix pipeline...")

        # Module 1: Cross-Tenant Resource Filter (P0 - 130 errors)
        if enable_cross_tenant_filter and source_subscription_id and subscription_id:
            logger.info("Applying cross-tenant resource filter...")
            cross_tenant_filter = CrossTenantResourceFilter(
                source_subscription_id=source_subscription_id,
                target_subscription_id=subscription_id,
            )
            filter_result = cross_tenant_filter.filter_resources(filtered_graph.resources)
            filtered_graph.resources = filter_result.filtered_resources
            logger.info(
                f"Cross-tenant filter: {filter_result.resources_before} -> "
                f"{filter_result.resources_after} resources "
                f"(filtered {filter_result.filtered_count})"
            )

        # Module 6: Existing Resource Filter (Optional - 67 errors)
        if enable_existing_resource_filter and subscription_id:
            logger.info("Applying existing resource filter...")
            existing_filter = ExistingResourceFilter(
                target_subscription_id=subscription_id,
                enable_async_check=True,
            )
            filter_result = existing_filter.filter_resources(filtered_graph.resources)
            filtered_graph.resources = filter_result.filtered_resources
            logger.info(
                f"Existing resource filter: {filter_result.resources_before} -> "
                f"{filter_result.resources_after} resources "
                f"(filtered {filter_result.filtered_count})"
            )

        # Module 2: Global Location Mapper (P0 - 2 errors)
        if enable_location_mapping:
            logger.info("Applying global location mapper...")
            location_mapper = GlobalLocationMapper()
            location_result = location_mapper.transform_resources(filtered_graph.resources)
            logger.info(
                f"Location mapper: {location_result.resources_mapped} "
                f"Resource Groups mapped from 'global' to physical region"
            )

        # Module 3: Unique Name Generator (P1 - 97 errors)
        if enable_name_generation:
            logger.info("Applying unique name generator...")
            name_generator = UniqueNameGenerator(suffix=name_generation_suffix)
            name_result = name_generator.transform_resources(filtered_graph.resources)
            logger.info(
                f"Name generator: {name_result.resources_renamed} "
                f"resources renamed for global uniqueness"
            )

        # Module 5: Bastion NSG Rule Generator (P1 - 2 errors)
        if enable_bastion_nsg_rules:
            logger.info("Applying Bastion NSG rule generator...")
            bastion_generator = BastionNSGRuleGenerator()
            bastion_result = bastion_generator.transform_resources(filtered_graph.resources)
            logger.info(
                f"Bastion NSG rules: {bastion_result.rules_added} rules added "
                f"to {bastion_result.nsgs_modified} NSGs"
            )

        # Module 4: VNet Link Dependency Validator (P1 - 22 errors)
        if enable_vnet_link_validation:
            logger.info("Applying VNet Link dependency validator...")
            vnet_link_validator = VNetLinkDependencyValidator()
            vnet_link_result = vnet_link_validator.validate_and_fix_dependencies(
                filtered_graph.resources
            )
            logger.info(
                f"VNet Link validation: {vnet_link_result.valid_links}/"
                f"{vnet_link_result.total_vnet_links} valid, "
                f"{vnet_link_result.invalid_links} invalid"
            )
            if vnet_link_result.invalid_links > 0:
                logger.warning(
                    f"VNet Link validation found {vnet_link_result.invalid_links} "
                    f"invalid links with missing DNS zones"
                )

        logger.info("Deployment error fix pipeline complete")
        # ===== END DEPLOYMENT ERROR FIX PIPELINE =====

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

        # Validate VNet address spaces before generation (GAP-012, Issue #334)
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

            # Parse addressSpace from properties (same logic as terraform_emitter.py:594-598)
            vnet_address_space = self._extract_vnet_address_space(vnet)

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

    def _extract_vnet_address_space(self, vnet: Dict[str, Any]) -> List[str]:
        """Extract addressSpace from VNet resource.

        Parses the properties JSON to extract addressSpace.addressPrefixes,
        similar to terraform_emitter.py:594-598.

        Args:
            vnet: VNet resource dictionary

        Returns:
            List of address prefixes (e.g., ["10.0.0.0/16"])
        """
        vnet_name = vnet.get("name", "unknown")

        # Try top-level address_space first (if set by resource processor)
        if "address_space" in vnet and vnet["address_space"]:
            try:
                if isinstance(vnet["address_space"], str):
                    return json.loads(vnet["address_space"])
                elif isinstance(vnet["address_space"], list):
                    return vnet["address_space"]
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(
                    f"Failed to parse top-level address_space for VNet '{vnet_name}': {e}"
                )

        # Parse from properties JSON
        properties = vnet.get("properties", {})

        # Handle JSON string from Neo4j
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                logger.warning(
                    f"Failed to parse properties for VNet '{vnet_name}'"
                )
                return []

        # Extract addressSpace.addressPrefixes
        address_space_obj = properties.get("addressSpace", {})
        address_prefixes = address_space_obj.get("addressPrefixes", [])

        if not address_prefixes:
            logger.debug(
                f"VNet '{vnet_name}' has no addressSpace in properties"
            )

        return address_prefixes

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
