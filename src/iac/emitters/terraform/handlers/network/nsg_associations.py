"""NSG Association handler for deferred emission.

This handler doesn't handle Azure resource types directly. Instead, it
emits azurerm_subnet_network_security_group_association and
azurerm_network_interface_security_group_association resources
after all main resources have been processed.

The associations are tracked during VNet/Subnet/NIC emission and then
emitted in bulk during post_emit() to avoid dependency ordering issues.
"""

import logging
from typing import Any, ClassVar, Dict, Optional, Set, Tuple

from ...base_handler import ResourceHandler
from ...context import EmitterContext
from .. import handler

logger = logging.getLogger(__name__)


@handler
class NSGAssociationHandler(ResourceHandler):
    """Handler for NSG associations (subnet and NIC).

    This is a special handler that doesn't handle Azure resource types.
    Instead, it emits Terraform association resources during post_emit()
    based on tracked associations in the EmitterContext.

    Emits (during post_emit):
        - azurerm_subnet_network_security_group_association
        - azurerm_network_interface_security_group_association
    """

    HANDLED_TYPES: ClassVar[Set[str]] = set()  # No direct Azure types

    TERRAFORM_TYPES: ClassVar[Set[str]] = {
        "azurerm_subnet_network_security_group_association",
        "azurerm_network_interface_security_group_association",
    }

    def emit(
        self,
        resource: Dict[str, Any],
        context: EmitterContext,
    ) -> Optional[Tuple[str, str, Dict[str, Any]]]:
        """This handler doesn't emit during normal resource processing.

        Args:
            resource: Azure resource dictionary (unused)
            context: Emitter context (unused)

        Returns:
            Always None - associations are emitted during post_emit()
        """
        return None

    def post_emit(self, context: EmitterContext) -> None:
        """Emit all tracked NSG associations after main resources processed.

        This method emits:
        1. Subnet-NSG associations tracked during VNet/Subnet emission
        2. NIC-NSG associations tracked during NIC emission

        Args:
            context: Emitter context with tracked associations
        """
        # Emit subnet-NSG associations
        for (
            subnet_tf_name,
            nsg_tf_name,
            subnet_name,
            nsg_name,
        ) in context.nsg_associations:
            # Validate that both resources exist
            if not self._validate_association_resources(
                context, subnet_tf_name, nsg_tf_name, subnet_name, nsg_name, "subnet"
            ):
                continue

            # Bug #13: Skip cross-resource-group NSG associations
            # Get resource groups for both resources
            subnets = context.terraform_config.get("resource", {}).get("azurerm_subnet", {})
            nsgs = context.terraform_config.get("resource", {}).get("azurerm_network_security_group", {})

            if subnet_tf_name in subnets and nsg_tf_name in nsgs:
                subnet_rg = subnets[subnet_tf_name].get("resource_group_name")
                nsg_rg = nsgs[nsg_tf_name].get("resource_group_name")

                if subnet_rg != nsg_rg:
                    logger.warning(
                        f"Skipping cross-RG NSG association: subnet '{subnet_name}' in {subnet_rg} "
                        f"cannot associate with NSG '{nsg_name}' in {nsg_rg} (different resource groups)"
                    )
                    continue

            # Build association resource name
            assoc_name = f"{subnet_tf_name}_{nsg_tf_name}"

            # Build association config
            config = {
                "subnet_id": f"${{azurerm_subnet.{subnet_tf_name}.id}}",
                "network_security_group_id": f"${{azurerm_network_security_group.{nsg_tf_name}.id}}",
            }

            # Add to terraform config
            context.add_helper_resource(
                "azurerm_subnet_network_security_group_association",
                assoc_name,
                config,
            )

            logger.debug(f"Emitted subnet-NSG association: {subnet_name} -> {nsg_name}")

        # Emit NIC-NSG associations
        for (
            nic_tf_name,
            nsg_tf_name,
            nic_name,
            nsg_name,
        ) in context.nic_nsg_associations:
            # Validate that both resources exist
            if not self._validate_association_resources(
                context, nic_tf_name, nsg_tf_name, nic_name, nsg_name, "nic"
            ):
                continue

            # Bug #13: Skip cross-resource-group NSG associations
            # Get resource groups for both resources
            nics = context.terraform_config.get("resource", {}).get("azurerm_network_interface", {})
            nsgs = context.terraform_config.get("resource", {}).get("azurerm_network_security_group", {})

            if nic_tf_name in nics and nsg_tf_name in nsgs:
                nic_rg = nics[nic_tf_name].get("resource_group_name")
                nsg_rg = nsgs[nsg_tf_name].get("resource_group_name")

                if nic_rg != nsg_rg:
                    logger.warning(
                        f"Skipping cross-RG NSG association: NIC '{nic_name}' in {nic_rg} "
                        f"cannot associate with NSG '{nsg_name}' in {nsg_rg} (different resource groups)"
                    )
                    continue

            # Build association resource name
            assoc_name = f"{nic_tf_name}_{nsg_tf_name}"

            # Build association config
            config = {
                "network_interface_id": f"${{azurerm_network_interface.{nic_tf_name}.id}}",
                "network_security_group_id": f"${{azurerm_network_security_group.{nsg_tf_name}.id}}",
            }

            # Add to terraform config
            context.add_helper_resource(
                "azurerm_network_interface_security_group_association",
                assoc_name,
                config,
            )

            logger.debug(f"Emitted NIC-NSG association: {nic_name} -> {nsg_name}")

        logger.info(
            f"Emitted {len(context.nsg_associations)} subnet-NSG associations and "
            f"{len(context.nic_nsg_associations)} NIC-NSG associations"
        )

    def _validate_association_resources(
        self,
        context: EmitterContext,
        resource_tf_name: str,
        nsg_tf_name: str,
        resource_name: str,
        nsg_name: str,
        resource_type: str,
    ) -> bool:
        """Validate that both resources in association exist.

        Args:
            context: Emitter context
            resource_tf_name: Terraform name of subnet or NIC
            nsg_tf_name: Terraform name of NSG
            resource_name: Original Azure name of subnet or NIC
            nsg_name: Original Azure name of NSG
            resource_type: "subnet" or "nic" for logging

        Returns:
            True if both resources exist, False otherwise
        """
        # Check subnet/NIC exists
        if resource_type == "subnet":
            if (
                not context.available_subnets
                or resource_tf_name not in context.available_subnets
            ):
                logger.warning(
                    f"Skipping {resource_type}-NSG association: {resource_type} '{resource_name}' not found"
                )
                context.track_missing_reference(
                    resource_name=f"{resource_type}-nsg-association",
                    resource_type="azurerm_subnet",
                    missing_resource_name=resource_name,
                    missing_resource_id="",
                )
                return False
        else:  # nic
            if not self.validate_resource_reference(
                "azurerm_network_interface", resource_tf_name, context
            ):
                logger.warning(
                    f"Skipping {resource_type}-NSG association: {resource_type} '{resource_name}' not found"
                )
                context.track_missing_reference(
                    resource_name=f"{resource_type}-nsg-association",
                    resource_type="azurerm_network_interface",
                    missing_resource_name=resource_name,
                    missing_resource_id="",
                )
                return False

        # Check NSG exists
        if not self.validate_resource_reference(
            "azurerm_network_security_group", nsg_tf_name, context
        ):
            logger.warning(
                f"Skipping {resource_type}-NSG association: NSG '{nsg_name}' not found"
            )
            context.track_missing_reference(
                resource_name=f"{resource_type}-nsg-association",
                resource_type="azurerm_network_security_group",
                missing_resource_name=nsg_name,
                missing_resource_id="",
            )
            return False

        return True
