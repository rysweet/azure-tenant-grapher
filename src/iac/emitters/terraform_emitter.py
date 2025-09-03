"""Terraform emitter for Infrastructure-as-Code generation.

This module provides Terraform-specific template generation from
tenant graph data.
"""

import json
import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ..traverser import TenantGraph
from . import register_emitter
from .base import IaCEmitter

logger = logging.getLogger(__name__)


class TerraformEmitter(IaCEmitter):
    """Emitter for generating Terraform templates."""

    # Azure resource type to Terraform resource type mapping
    AZURE_TO_TERRAFORM_MAPPING: ClassVar[Dict[str, str]] = {
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
        "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
        "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Web/sites": "azurerm_app_service",
        "Microsoft.Sql/servers": "azurerm_mssql_server",
        "Microsoft.KeyVault/vaults": "azurerm_key_vault",
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
    }

    def emit(
        self, graph: TenantGraph, out_dir: Path, domain_name: Optional[str] = None
    ) -> List[Path]:
        """Generate Terraform template from tenant graph."""
        # If a domain name is specified, set it for all user account entities
        if domain_name:
            for resource in graph.resources:
                if resource.get("type", "").lower() in (
                    "user",
                    "aaduser",
                    "microsoft.aad/user",
                ):
                    base_name = resource.get("name", "user")
                    base_name = base_name.split("@")[0]
                    resource["userPrincipalName"] = f"{base_name}@{domain_name}"
                    resource["email"] = f"{base_name}@{domain_name}"

        logger.info(f"Generating Terraform templates to {out_dir}")

        # Ensure output directory exists
        out_dir.mkdir(parents=True, exist_ok=True)

        # Build Terraform JSON structure
        terraform_config = {
            "terraform": {
                "required_providers": {
                    "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"}
                }
            },
            "provider": {
                "azurerm": {
                    "features": {},
                    "resource_provider_registrations": "none"
                }
            },
            "resource": {},
        }

        # Process resources
        for resource in graph.resources:
            terraform_resource = self._convert_resource(resource)
            if terraform_resource:
                resource_type, resource_name, resource_config = terraform_resource

                if resource_type not in terraform_config["resource"]:
                    terraform_config["resource"][resource_type] = {}

                terraform_config["resource"][resource_type][resource_name] = (
                    resource_config
                )

        # Write main.tf.json
        output_file = out_dir / "main.tf.json"
        with open(output_file, "w") as f:
            json.dump(terraform_config, f, indent=2)

        logger.info(
            f"Generated Terraform template with {len(graph.resources)} resources"
        )
        return [output_file]

    async def emit_template(
        self, tenant_graph: TenantGraph, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate Terraform template from tenant graph (legacy method).

        Args:
            tenant_graph: Input tenant graph data
            output_path: Optional output file path

        Returns:
            Dictionary containing generated Terraform template data
        """
        # Use the new emit method for actual implementation
        if output_path:
            out_dir = Path(output_path)
        else:
            out_dir = Path("./terraform_output")

        written_files = self.emit(tenant_graph, out_dir)

        return {
            "files_written": [str(f) for f in written_files],
            "resource_count": len(tenant_graph.resources),
        }

    def _convert_resource(
        self, resource: Dict[str, Any]
    ) -> Optional[tuple[str, str, Dict[str, Any]]]:
        """Convert Azure resource to Terraform resource.

        Args:
            resource: Azure resource data

        Returns:
            Tuple of (terraform_type, resource_name, resource_config) or None
        """
        azure_type = resource.get("type", "")
        resource_name = resource.get("name", "unknown")

        # Get Terraform resource type
        terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(
            azure_type, "azurerm_generic_resource"
        )

        # Sanitize resource name for Terraform
        safe_name = self._sanitize_terraform_name(resource_name)

        # Build basic resource configuration
        # Ensure location is never null - default to eastus if missing
        location = resource.get("location")
        if not location or location.lower() == "none" or location.lower() == "null":
            location = "eastus"
        
        resource_config = {
            "name": resource_name,
            "location": location,
            "resource_group_name": resource.get("resourceGroup", "default-rg"),
        }

        # Add tags if present
        if "tags" in resource:
            resource_config["tags"] = resource["tags"]

        # Add type-specific properties to ensure all required fields are present
        if azure_type == "Microsoft.Storage/storageAccounts":
            resource_config.update(
                {
                    "account_tier": resource.get("account_tier", "Standard"),
                    "account_replication_type": resource.get("account_replication_type", "LRS")
                }
            )
        elif azure_type == "Microsoft.Network/virtualNetworks":
            resource_config["address_space"] = resource.get("address_space", ["10.0.0.0/16"])
        elif azure_type == "Microsoft.Compute/virtualMachines":
            # Ensure required VM properties
            resource_config.update(
                {
                    "size": resource.get("size", "Standard_B2s"),
                    "admin_username": resource.get("admin_username", "azureuser"),
                    "os_disk": {
                        "caching": "ReadWrite",
                        "storage_account_type": "Standard_LRS"
                    },
                    "source_image_reference": {
                        "publisher": "Canonical",
                        "offer": "0001-com-ubuntu-server-jammy",
                        "sku": "22_04-lts",
                        "version": "latest"
                    }
                }
            )
        elif azure_type == "Microsoft.Network/publicIPAddresses":
            resource_config["allocation_method"] = resource.get("allocation_method", "Static")
        elif azure_type == "Microsoft.Network/networkSecurityGroups":
            # NSGs don't need additional required properties beyond name, location, and resource_group
            pass
        elif azure_type == "Microsoft.Web/sites":
            resource_config.update(
                {
                    "app_service_plan_id": resource.get("app_service_plan_id", "/subscriptions/xxx/resourceGroups/default-rg/providers/Microsoft.Web/serverfarms/default-plan")
                }
            )
        elif azure_type == "Microsoft.Sql/servers":
            resource_config.update(
                {
                    "version": resource.get("version", "12.0"),
                    "administrator_login": resource.get("administrator_login", "sqladmin"),
                    "administrator_login_password": resource.get("administrator_login_password", "P@ssw0rd123!")
                }
            )
        elif azure_type == "Microsoft.KeyVault/vaults":
            resource_config.update(
                {
                    "tenant_id": resource.get("tenant_id", "00000000-0000-0000-0000-000000000000"),
                    "sku_name": resource.get("sku_name", "standard")
                }
            )

        return terraform_type, safe_name, resource_config

    def _sanitize_terraform_name(self, name: str) -> str:
        """Sanitize resource name for Terraform compatibility.

        Args:
            name: Original resource name

        Returns:
            Sanitized name safe for Terraform
        """
        # Replace invalid characters with underscores
        import re

        sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", name)

        # Ensure it starts with a letter or underscore
        if sanitized and sanitized[0].isdigit():
            sanitized = f"resource_{sanitized}"

        return sanitized or "unnamed_resource"

    def get_supported_resource_types(self) -> List[str]:
        """Get list of Azure resource types supported by Terraform provider.

        Returns:
            List of supported Azure resource type strings
        """
        return list(self.AZURE_TO_TERRAFORM_MAPPING.keys())

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate generated Terraform template for correctness.

        Args:
            template_data: Generated Terraform template data

        Returns:
            True if template is valid, False otherwise
        """
        required_keys = ["terraform", "provider", "resource"]

        for key in required_keys:
            if key not in template_data:
                logger.error(f"Missing required key in Terraform template: {key}")
                return False

        # Basic validation passed
        return True


# Auto-register this emitter
register_emitter("terraform", TerraformEmitter)
