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
        "Microsoft.Network/subnets": "azurerm_subnet",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Web/sites": "azurerm_app_service",
        "Microsoft.Sql/servers": "azurerm_mssql_server",
        "Microsoft.KeyVault/vaults": "azurerm_key_vault",
        "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
        # Azure AD / Entra ID / Microsoft Graph resource mappings
        "Microsoft.AAD/User": "azuread_user",
        "Microsoft.AAD/Group": "azuread_group",
        "Microsoft.AAD/ServicePrincipal": "azuread_service_principal",
        "Microsoft.Graph/users": "azuread_user",
        "Microsoft.Graph/groups": "azuread_group",
        "Microsoft.Graph/servicePrincipals": "azuread_service_principal",
        "Microsoft.ManagedIdentity/managedIdentities": "azurerm_user_assigned_identity",
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
            resource.get("type", "").startswith("Microsoft.AAD/")
            or resource.get("type", "").startswith("Microsoft.Graph/")
            or resource.get("type", "").lower()
            in ("user", "aaduser", "group", "aadgroup", "serviceprincipal")
            for resource in graph.resources
        )

        # Build Terraform JSON structure
        terraform_config: Dict[str, Any] = {
            "terraform": {
                "required_providers": {
                    "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"},
                    "random": {"source": "hashicorp/random", "version": ">=3.1"},
                    "tls": {"source": "hashicorp/tls", "version": ">=4.0"},
                }
            },
            "provider": {
                "azurerm": {"features": {}, "resource_provider_registrations": "none"}
            },
            "resource": {},
        }

        # Add Azure AD provider if needed
        if has_azuread_resources:
            # Add azuread to required providers
            terraform_config["terraform"]["required_providers"]["azuread"] = {
                "source": "hashicorp/azuread",
                "version": ">=2.0",
            }
            # Convert provider to list format for multiple providers
            terraform_config["provider"] = [
                {"azurerm": {"features": {}}},
                {"azuread": {}},
            ]

        # Process resources
        for resource in graph.resources:
            terraform_resource = self._convert_resource(resource, terraform_config)
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

    def _parse_tags(self, tags: Any, resource_name: str) -> Optional[Dict[str, str]]:
        """Parse and validate resource tags from Neo4j (JSON string or dict)."""
        if not tags:
            return None

        if isinstance(tags, str):
            try:
                parsed = json.loads(tags)
                return parsed if isinstance(parsed, dict) and parsed else None
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Invalid tags JSON for '{resource_name}': {str(tags)[:100]} ({e})"
                )
                return None

        if isinstance(tags, dict):
            return tags if tags else None

        logger.warning(f"Unexpected tags type for '{resource_name}': {type(tags)}")
        return None

    def _convert_resource(
        self, resource: Dict[str, Any], terraform_config: Dict[str, Any]
    ) -> Optional[tuple[str, str, Dict[str, Any]]]:
        """Convert Azure resource to Terraform resource.

        Args:
            resource: Azure resource data
            terraform_config: The main Terraform configuration dict to add helper resources to

        Returns:
            Tuple of (terraform_type, resource_name, resource_config) or None
        """
        azure_type = resource.get("type", "")
        resource_name = resource.get("name", "unknown")

        # Handle simple type names for Azure AD resources
        if azure_type.lower() in ("user", "aaduser"):
            azure_type = "Microsoft.Graph/users"
        elif azure_type.lower() in ("group", "aadgroup", "identitygroup"):
            azure_type = "Microsoft.Graph/groups"
        elif azure_type.lower() == "serviceprincipal":
            azure_type = "Microsoft.Graph/servicePrincipals"
        elif azure_type.lower() == "managedidentity":
            azure_type = "Microsoft.ManagedIdentity/managedIdentities"

        # Get Terraform resource type
        terraform_type = self.AZURE_TO_TERRAFORM_MAPPING.get(azure_type)

        if not terraform_type:
            logger.warning(
                f"Skipping unsupported Azure resource type '{azure_type}' "
                f"for resource '{resource_name}'. Add mapping to AZURE_TO_TERRAFORM_MAPPING."
            )
            return None

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
            parsed_tags = self._parse_tags(resource["tags"], resource_name)
            if parsed_tags:
                resource_config["tags"] = parsed_tags

        # Add type-specific properties to ensure all required fields are present
        if azure_type == "Microsoft.Storage/storageAccounts":
            resource_config.update(
                {
                    "account_tier": resource.get("account_tier", "Standard"),
                    "account_replication_type": resource.get(
                        "account_replication_type", "LRS"
                    ),
                }
            )
        elif azure_type == "Microsoft.Network/virtualNetworks":
            resource_config["address_space"] = resource.get(
                "address_space", ["10.0.0.0/16"]
            )

            # Extract and emit subnets from vnet properties
            properties_str = resource.get("properties", "{}")
            if isinstance(properties_str, str):
                try:
                    properties = json.loads(properties_str)
                except json.JSONDecodeError:
                    properties = {}
            else:
                properties = properties_str

            subnets = properties.get("subnets", [])
            for subnet in subnets:
                subnet_name = subnet.get("name")
                if not subnet_name:
                    continue  # Skip subnets without names

                subnet_props = subnet.get("properties", {})
                address_prefix = subnet_props.get("addressPrefix")
                if not address_prefix:
                    logger.warning(
                        f"Subnet '{subnet_name}' in vnet '{resource_name}' has no addressPrefix, skipping"
                    )
                    continue

                # Build subnet resource name
                subnet_safe_name = self._sanitize_terraform_name(subnet_name)

                # Build subnet resource config
                subnet_config = {
                    "name": subnet_name,
                    "resource_group_name": resource.get("resourceGroup", "default-rg"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{safe_name}.name}}",
                    "address_prefixes": [address_prefix],
                }

                # Add to terraform config
                if "azurerm_subnet" not in terraform_config["resource"]:
                    terraform_config["resource"]["azurerm_subnet"] = {}

                terraform_config["resource"]["azurerm_subnet"][subnet_safe_name] = (
                    subnet_config
                )

        elif azure_type == "Microsoft.Compute/virtualMachines":
            # Generate SSH key pair for VM authentication using Terraform's tls_private_key resource
            ssh_key_resource_name = f"{safe_name}_ssh_key"

            # Add the tls_private_key resource to terraform config
            if "resource" not in terraform_config:
                terraform_config["resource"] = {}
            if "tls_private_key" not in terraform_config["resource"]:
                terraform_config["resource"]["tls_private_key"] = {}

            terraform_config["resource"]["tls_private_key"][ssh_key_resource_name] = {
                "algorithm": "RSA",
                "rsa_bits": 4096,
            }

            # Ensure required VM properties with SSH key authentication
            resource_config.update(
                {
                    "size": resource.get("size", "Standard_B2s"),
                    "admin_username": resource.get("admin_username", "azureuser"),
                    "admin_ssh_key": {
                        "username": resource.get("admin_username", "azureuser"),
                        "public_key": f"${{tls_private_key.{ssh_key_resource_name}.public_key_openssh}}",
                    },
                    "os_disk": {
                        "caching": "ReadWrite",
                        "storage_account_type": "Standard_LRS",
                    },
                    "source_image_reference": {
                        "publisher": "Canonical",
                        "offer": "0001-com-ubuntu-server-jammy",
                        "sku": "22_04-lts",
                        "version": "latest",
                    },
                }
            )

            # Add network_interface_ids by parsing VM properties
            properties_str = resource.get("properties", "{}")
            if isinstance(properties_str, str):
                try:
                    properties = json.loads(properties_str)
                except json.JSONDecodeError:
                    properties = {}
            else:
                properties = properties_str

            network_profile = properties.get("networkProfile", {})
            nics = network_profile.get("networkInterfaces", [])

            if nics:
                nic_refs = []
                for nic in nics:
                    nic_id = nic.get("id", "")
                    if nic_id:
                        # Extract NIC name from ID
                        # Format: /subscriptions/.../networkInterfaces/{nic_name}
                        if "/networkInterfaces/" in nic_id:
                            nic_name = nic_id.split("/networkInterfaces/")[-1]
                            nic_name = self._sanitize_terraform_name(nic_name)
                            nic_refs.append(
                                f"${{azurerm_network_interface.{nic_name}.id}}"
                            )

                if nic_refs:
                    resource_config["network_interface_ids"] = nic_refs
            else:
                logger.warning(
                    f"VM '{resource_name}' has no network interfaces in properties. "
                    "Generated Terraform may be invalid."
                )
        elif azure_type == "Microsoft.Network/publicIPAddresses":
            resource_config["allocation_method"] = resource.get(
                "allocation_method", "Static"
            )
        elif azure_type == "Microsoft.Network/networkSecurityGroups":
            # NSGs don't need additional required properties beyond name, location, and resource_group
            pass
        elif azure_type == "Microsoft.Network/networkInterfaces":
            # NICs require ip_configuration blocks
            # Parse properties field to get ipConfigurations
            properties_str = resource.get("properties", "{}")
            if isinstance(properties_str, str):
                try:
                    properties = json.loads(properties_str)
                except json.JSONDecodeError:
                    properties = {}
            else:
                properties = properties_str

            ip_configurations = properties.get("ipConfigurations", [])
            if ip_configurations:
                # Use first IP configuration
                ip_config = ip_configurations[0]
                ip_props = ip_config.get("properties", {})
                subnet_info = ip_props.get("subnet", {})
                subnet_id = subnet_info.get("id", "")

                # Extract subnet name from ID
                # Format: /subscriptions/.../virtualNetworks/{vnet}/subnets/{subnet}
                subnet_name = "unknown"
                if subnet_id and "/subnets/" in subnet_id:
                    subnet_name = subnet_id.split("/subnets/")[-1]
                    subnet_name = self._sanitize_terraform_name(subnet_name)

                private_ip = ip_props.get("privateIPAddress", "")
                allocation_method = ip_props.get("privateIPAllocationMethod", "Dynamic")

                ip_config_block = {
                    "name": ip_config.get("name", "internal"),
                    "subnet_id": f"${{azurerm_subnet.{subnet_name}.id}}",
                    "private_ip_address_allocation": allocation_method,
                }

                # Add private IP if static allocation
                if allocation_method == "Static" and private_ip:
                    ip_config_block["private_ip_address"] = private_ip

                resource_config["ip_configuration"] = ip_config_block
            else:
                logger.warning(
                    f"NIC '{resource_name}' has no ip_configurations in properties. "
                    "Generated Terraform may be invalid."
                )
        elif azure_type == "Microsoft.Web/sites":
            resource_config.update(
                {
                    "app_service_plan_id": resource.get(
                        "app_service_plan_id",
                        "/subscriptions/xxx/resourceGroups/default-rg/providers/Microsoft.Web/serverfarms/default-plan",
                    )
                }
            )
        elif azure_type == "Microsoft.Sql/servers":
            # Generate a unique password for each SQL server using Terraform's random_password resource
            password_resource_name = f"{safe_name}_password"

            # Add the random_password resource to terraform config
            if "resource" not in terraform_config:
                terraform_config["resource"] = {}
            if "random_password" not in terraform_config["resource"]:
                terraform_config["resource"]["random_password"] = {}

            terraform_config["resource"]["random_password"][password_resource_name] = {
                "length": 20,
                "special": True,
                "override_special": "!@#$%&*()-_=+[]{}<>:?",
                "min_lower": 1,
                "min_upper": 1,
                "min_numeric": 1,
                "min_special": 1,
            }

            resource_config.update(
                {
                    "version": resource.get("version", "12.0"),
                    "administrator_login": resource.get(
                        "administrator_login", "sqladmin"
                    ),
                    "administrator_login_password": f"${{random_password.{password_resource_name}.result}}",
                }
            )
        elif azure_type == "Microsoft.KeyVault/vaults":
            resource_config.update(
                {
                    "tenant_id": resource.get(
                        "tenant_id", "00000000-0000-0000-0000-000000000000"
                    ),
                    "sku_name": resource.get("sku_name", "standard"),
                }
            )
        elif azure_type in ("Microsoft.AAD/User", "Microsoft.Graph/users"):
            # Azure AD User specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "user_principal_name": resource.get(
                    "userPrincipalName", f"{resource_name}@example.com"
                ),
                "mail_nickname": resource.get("mailNickname", resource_name),
            }
            if "password" in resource:
                resource_config["password"] = resource["password"]
        elif azure_type in ("Microsoft.AAD/Group", "Microsoft.Graph/groups"):
            # Azure AD Group specific properties
            resource_config = {
                "display_name": resource.get("displayName", resource_name),
                "security_enabled": resource.get("securityEnabled", True),
            }
            if "description" in resource:
                resource_config["description"] = resource["description"]
        elif azure_type in (
            "Microsoft.AAD/ServicePrincipal",
            "Microsoft.Graph/servicePrincipals",
        ):
            # Azure AD Service Principal specific properties
            resource_config = {
                "application_id": resource.get("applicationId", ""),
            }
            if "displayName" in resource:
                resource_config["display_name"] = resource["displayName"]
        elif azure_type == "Microsoft.ManagedIdentity/managedIdentities":
            # Managed Identity specific properties
            resource_config = {
                "name": resource_name,
                "location": location,
                "resource_group_name": resource.get("resourceGroup", "default-rg"),
            }

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
