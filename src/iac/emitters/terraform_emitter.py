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
        # Azure AD / Entra ID resource mappings
        "Microsoft.AAD/User": "azuread_user",
        "Microsoft.AAD/Group": "azuread_group",
        "Microsoft.AAD/ServicePrincipal": "azuread_service_principal",
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

        # Check if we have any Azure AD resources
        has_azuread_resources = any(
            resource.get("type", "").startswith("Microsoft.AAD/") or
            resource.get("type", "").lower() in ("user", "aaduser", "group", "aadgroup", "serviceprincipal")
            for resource in graph.resources
        )

        # Build Terraform JSON structure
        terraform_config = {
            "terraform": {
                "required_providers": {
                    "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"}
                }
            },
            "provider": {"azurerm": {"features": {}}},
            "resource": {},
        }
        
        # Add Azure AD provider if needed
        if has_azuread_resources:
            # Add azuread to required providers
            terraform_config["terraform"]["required_providers"]["azuread"] = {
                "source": "hashicorp/azuread",
                "version": ">=2.0"
            }
            # Convert provider to list format for multiple providers
            terraform_config["provider"] = [
                {"azurerm": {"features": {}}},
                {"azuread": {}}
            ]

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
        
        # Handle simple type names for Azure AD resources
        if azure_type.lower() in ("user", "aaduser"):
            azure_type = "Microsoft.AAD/User"
        elif azure_type.lower() in ("group", "aadgroup"):
            azure_type = "Microsoft.AAD/Group"
        elif azure_type.lower() == "serviceprincipal":
            azure_type = "Microsoft.AAD/ServicePrincipal"

        # Get Terraform resource type
        terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(
            azure_type, "azurerm_generic_resource"
        )

        # Sanitize resource name for Terraform
        safe_name = self._sanitize_terraform_name(resource_name)

        # Build basic resource configuration
        resource_config = {
            "name": resource_name,
            "location": resource.get("location", "East US"),
            "resource_group_name": resource.get("resourceGroup", "default-rg"),
        }

        # Add tags if present
        if "tags" in resource:
            resource_config["tags"] = resource["tags"]

        # Add type-specific properties
        if azure_type == "Microsoft.Storage/storageAccounts":
            resource_config.update(
                {"account_tier": "Standard", "account_replication_type": "LRS"}
            )
        elif azure_type == "Microsoft.Network/virtualNetworks":
            resource_config["address_space"] = ["10.0.0.0/16"]
        elif azure_type == "Microsoft.AAD/User":
            # Azure AD User specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "user_principal_name": resource.get("userPrincipalName", f"{resource_name}@example.com"),
                "mail_nickname": resource.get("mailNickname", resource_name),
            }
            if "password" in resource:
                resource_config["password"] = resource["password"]
        elif azure_type == "Microsoft.AAD/Group":
            # Azure AD Group specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "security_enabled": resource.get("securityEnabled", True),
            }
            if "description" in resource:
                resource_config["description"] = resource["description"]
        elif azure_type == "Microsoft.AAD/ServicePrincipal":
            # Azure AD Service Principal specific properties
            resource_config = {
                "application_id": resource.get("applicationId", ""),
            }
            if "displayName" in resource:
                resource_config["display_name"] = resource["displayName"]

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
