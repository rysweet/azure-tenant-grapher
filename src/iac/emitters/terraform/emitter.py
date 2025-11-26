"""TerraformEmitter - Main orchestrator for handler-based Terraform generation.

This module provides the main TerraformEmitter class that orchestrates
resource-to-Terraform conversion using registered handlers. It replaces
the monolithic _convert_resource() method with handler delegation.

Architecture:
    Emitter (this file) -> HandlerRegistry -> Individual Handlers
                       |
                       v
                  EmitterContext (shared state)
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from .context import EmitterContext
from .handlers import HandlerRegistry, ensure_handlers_registered

logger = logging.getLogger(__name__)


class TerraformEmitter:
    """Main orchestrator for Terraform IaC generation.

    Delegates resource conversion to registered handlers while managing
    overall configuration structure and output.

    Responsibilities:
    - Initialize context with target configuration
    - Iterate resources and dispatch to handlers
    - Collect and structure handler output
    - Emit deferred resources (NSG associations, etc.)
    - Generate final Terraform configuration

    Usage:
        emitter = TerraformEmitter(
            target_subscription_id="xxx",
            target_tenant_id="yyy",
        )
        config = emitter.emit(resources)
        emitter.write(config, output_dir)
    """

    def __init__(
        self,
        target_subscription_id: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        source_subscription_id: Optional[str] = None,
        source_tenant_id: Optional[str] = None,
        identity_mapping: Optional[Dict[str, Any]] = None,
        resource_group_prefix: str = "",
        strict_mode: bool = False,
        graph: Optional[Any] = None,
        translation_coordinator: Optional[Any] = None,
    ):
        """Initialize emitter with target configuration.

        Args:
            target_subscription_id: Target Azure subscription ID for cross-tenant
            target_tenant_id: Target Azure tenant ID for cross-tenant
            source_subscription_id: Source subscription ID from scan
            source_tenant_id: Source tenant ID from scan
            identity_mapping: Entra ID identity translation mapping
            resource_group_prefix: Prefix to add to resource group names
            strict_mode: If True, fail on validation errors
            graph: Neo4j graph client for reference lookups
            translation_coordinator: Cross-tenant translation coordinator
        """
        self.context = EmitterContext(
            target_subscription_id=target_subscription_id,
            target_tenant_id=target_tenant_id,
            source_subscription_id=source_subscription_id,
            source_tenant_id=source_tenant_id,
            identity_mapping=identity_mapping or {},
            resource_group_prefix=resource_group_prefix,
            strict_mode=strict_mode,
            graph=graph,
            translation_coordinator=translation_coordinator,
        )

        # Ensure handlers are registered
        ensure_handlers_registered()

        # Track statistics
        self.stats = {
            "total_resources": 0,
            "emitted_resources": 0,
            "skipped_resources": 0,
            "unsupported_types": set(),
            "handler_errors": [],
        }

    def emit(self, resources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Convert list of Azure resources to Terraform configuration.

        Args:
            resources: List of Azure resource dictionaries from graph

        Returns:
            Complete Terraform configuration dict
        """
        logger.info(f"Starting Terraform emission for {len(resources)} resources")
        self.stats["total_resources"] = len(resources)

        # Initialize terraform config structure
        self.context.terraform_config = {
            "terraform": {
                "required_version": ">= 1.5.0",
                "required_providers": {
                    "azurerm": {
                        "source": "hashicorp/azurerm",
                        "version": "~> 3.80",
                    },
                    "azuread": {
                        "source": "hashicorp/azuread",
                        "version": "~> 2.45",
                    },
                    "random": {
                        "source": "hashicorp/random",
                        "version": "~> 3.5",
                    },
                    "tls": {
                        "source": "hashicorp/tls",
                        "version": "~> 4.0",
                    },
                },
            },
            "provider": {
                "azurerm": {"features": {}},
                "azuread": {},
            },
            "resource": {},
            "variable": {},
            "output": {},
        }

        # Phase 1: Emit main resources
        self._emit_resources(resources)

        # Phase 2: Emit deferred resources (NSG associations, etc.)
        self._emit_deferred_resources()

        # Phase 3: Call post_emit on all handlers
        self._post_emit_handlers()

        # Log statistics
        self._log_statistics()

        return self.context.terraform_config

    def _emit_resources(self, resources: List[Dict[str, Any]]) -> None:
        """Emit all resources using registered handlers.

        Args:
            resources: List of Azure resource dictionaries
        """
        for resource in resources:
            azure_type = resource.get("type", "unknown")

            # Get handler for this resource type
            handler = HandlerRegistry.get_handler(azure_type)

            if handler is None:
                self.stats["unsupported_types"].add(azure_type)
                self.stats["skipped_resources"] += 1
                logger.debug(f"No handler for type: {azure_type}")
                continue

            try:
                # Emit the resource
                result = handler.emit(resource, self.context)

                if result is None:
                    self.stats["skipped_resources"] += 1
                    logger.debug(
                        f"Handler skipped resource: {resource.get('name')} "
                        f"({azure_type})"
                    )
                    continue

                # Unpack result
                terraform_type, terraform_name, config = result

                # Add to terraform config
                self._add_resource(terraform_type, terraform_name, config)
                self.stats["emitted_resources"] += 1

            except Exception as e:
                self.stats["handler_errors"].append(
                    {
                        "resource": resource.get("name", "unknown"),
                        "type": azure_type,
                        "error": str(e),
                    }
                )
                logger.warning(
                    f"Handler error for {resource.get('name')} ({azure_type}): {e}"
                )
                if self.context.strict_mode:
                    raise

    def _add_resource(
        self,
        terraform_type: str,
        terraform_name: str,
        config: Dict[str, Any],
    ) -> None:
        """Add a resource to terraform configuration.

        Args:
            terraform_type: Terraform resource type
            terraform_name: Terraform resource name
            config: Resource configuration dict
        """
        resources = self.context.terraform_config.setdefault("resource", {})
        type_resources = resources.setdefault(terraform_type, {})
        type_resources[terraform_name] = config

        # Track in context for reference validation
        self.context.add_resource(terraform_type, terraform_name)

    def _emit_deferred_resources(self) -> None:
        """Emit deferred resources like NSG associations.

        These are emitted after main resources to ensure all referenced
        resources exist.
        """
        # Emit subnet-NSG associations
        for subnet_tf, nsg_tf, subnet_name, nsg_name in self.context.nsg_associations:
            # Validate both resources exist
            if not self.context.resource_exists("azurerm_subnet", subnet_tf):
                logger.warning(
                    f"Skipping NSG association: subnet '{subnet_name}' not emitted"
                )
                continue
            if not self.context.resource_exists(
                "azurerm_network_security_group", nsg_tf
            ):
                logger.warning(
                    f"Skipping NSG association: NSG '{nsg_name}' not emitted"
                )
                continue

            assoc_name = f"{subnet_tf}_to_{nsg_tf}"
            self._add_resource(
                "azurerm_subnet_network_security_group_association",
                assoc_name,
                {
                    "subnet_id": f"${{azurerm_subnet.{subnet_tf}.id}}",
                    "network_security_group_id": (
                        f"${{azurerm_network_security_group.{nsg_tf}.id}}"
                    ),
                },
            )
            logger.debug(f"Emitted NSG association: {subnet_name} -> {nsg_name}")

        # Emit NIC-NSG associations (Bug #57)
        for nic_tf, nsg_tf, nic_name, nsg_name in self.context.nic_nsg_associations:
            # Validate both resources exist
            if not self.context.resource_exists("azurerm_network_interface", nic_tf):
                logger.warning(
                    f"Skipping NIC-NSG association: NIC '{nic_name}' not emitted"
                )
                continue
            if not self.context.resource_exists(
                "azurerm_network_security_group", nsg_tf
            ):
                logger.warning(
                    f"Skipping NIC-NSG association: NSG '{nsg_name}' not emitted"
                )
                continue

            assoc_name = f"{nic_tf}_to_{nsg_tf}"
            self._add_resource(
                "azurerm_network_interface_security_group_association",
                assoc_name,
                {
                    "network_interface_id": f"${{azurerm_network_interface.{nic_tf}.id}}",
                    "network_security_group_id": (
                        f"${{azurerm_network_security_group.{nsg_tf}.id}}"
                    ),
                },
            )
            logger.debug(f"Emitted NIC-NSG association: {nic_name} -> {nsg_name}")

    def _post_emit_handlers(self) -> None:
        """Call post_emit on all handlers.

        Some handlers need to emit additional resources after all main
        resources have been processed.
        """
        for handler_class in HandlerRegistry.get_all_handlers():
            try:
                handler = handler_class()
                handler.post_emit(self.context)
            except Exception as e:
                logger.warning(f"Error in post_emit for {handler_class.__name__}: {e}")
                if self.context.strict_mode:
                    raise

    def _log_statistics(self) -> None:
        """Log emission statistics."""
        logger.info(
            f"Terraform emission complete: "
            f"{self.stats['emitted_resources']}/{self.stats['total_resources']} "
            f"resources emitted"
        )

        if self.stats["skipped_resources"] > 0:
            logger.info(
                f"Skipped {self.stats['skipped_resources']} resources "
                f"({len(self.stats['unsupported_types'])} unsupported types)"
            )

        if self.stats["unsupported_types"]:
            sorted_types = sorted(self.stats["unsupported_types"])
            logger.debug(f"Unsupported types: {sorted_types[:10]}...")

        if self.stats["handler_errors"]:
            logger.warning(
                f"Handler errors: {len(self.stats['handler_errors'])} "
                f"resources had errors"
            )

        if self.context.missing_references:
            logger.warning(
                f"Missing references: {len(self.context.missing_references)} "
                f"references could not be resolved"
            )

    def write(
        self,
        config: Dict[str, Any],
        output_dir: Path,
        filename: str = "main.tf.json",
    ) -> Path:
        """Write Terraform configuration to file.

        Args:
            config: Terraform configuration dict
            output_dir: Output directory path
            filename: Output filename (default: main.tf.json)

        Returns:
            Path to written file
        """
        import json

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        output_file = output_dir / filename

        with open(output_file, "w") as f:
            json.dump(config, f, indent=2, sort_keys=False)

        logger.info(f"Terraform configuration written to {output_file}")
        return output_file

    def get_supported_types(self) -> List[str]:
        """Get list of supported Azure resource types.

        Returns:
            Sorted list of supported Azure resource types
        """
        return HandlerRegistry.get_all_supported_types()

    def get_statistics(self) -> Dict[str, Any]:
        """Get emission statistics.

        Returns:
            Dictionary with emission statistics
        """
        return {
            "total_resources": self.stats["total_resources"],
            "emitted_resources": self.stats["emitted_resources"],
            "skipped_resources": self.stats["skipped_resources"],
            "unsupported_types_count": len(self.stats["unsupported_types"]),
            "handler_errors_count": len(self.stats["handler_errors"]),
            "missing_references_count": len(self.context.missing_references),
        }

    def add_variable(
        self,
        name: str,
        var_type: str = "string",
        description: str = "",
        default: Optional[Any] = None,
        sensitive: bool = False,
    ) -> None:
        """Add a variable to terraform configuration.

        Args:
            name: Variable name
            var_type: Variable type (string, number, bool, list, map)
            description: Variable description
            default: Default value (None = required)
            sensitive: Whether variable is sensitive
        """
        var_config: Dict[str, Any] = {"type": var_type}

        if description:
            var_config["description"] = description
        if default is not None:
            var_config["default"] = default
        if sensitive:
            var_config["sensitive"] = True

        self.context.terraform_config.setdefault("variable", {})[name] = var_config

    def add_output(
        self,
        name: str,
        value: str,
        description: str = "",
        sensitive: bool = False,
    ) -> None:
        """Add an output to terraform configuration.

        Args:
            name: Output name
            value: Output value expression
            description: Output description
            sensitive: Whether output is sensitive
        """
        output_config: Dict[str, Any] = {"value": value}

        if description:
            output_config["description"] = description
        if sensitive:
            output_config["sensitive"] = True

        self.context.terraform_config.setdefault("output", {})[name] = output_config
