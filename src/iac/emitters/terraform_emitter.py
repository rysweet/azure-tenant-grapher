"""Terraform emitter for Infrastructure-as-Code generation.

This module provides Terraform-specific template generation from
tenant graph data.
"""

import json
import logging
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from ..dependency_analyzer import DependencyAnalyzer
from ..traverser import TenantGraph
from . import register_emitter
from .base import IaCEmitter
from .private_endpoint_emitter import (
    emit_private_dns_zone,
    emit_private_dns_zone_vnet_link,
    emit_private_endpoint,
)

logger = logging.getLogger(__name__)


class TerraformEmitter(IaCEmitter):
    """Emitter for generating Terraform templates."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the TerraformEmitter.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)
        # Track NSG associations to emit as separate resources
        # Format: [(subnet_tf_name, nsg_tf_name, subnet_name, nsg_name)]
        self._nsg_associations: List[tuple[str, str, str, str]] = []
        # Track all resource names that will be emitted (for reference validation)
        self._available_resources: Dict[str, set] = {}
        # Track missing resource references for reporting
        self._missing_references: List[Dict[str, str]] = []

    # Azure resource type to Terraform resource type mapping
    AZURE_TO_TERRAFORM_MAPPING: ClassVar[Dict[str, str]] = {
        "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
        "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
        "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
        "Microsoft.Network/subnets": "azurerm_subnet",
        "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
        "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
        "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        "Microsoft.Network/bastionHosts": "azurerm_bastion_host",
        "Microsoft.Network/privateEndpoints": "azurerm_private_endpoint",
        "Microsoft.Network/privateDnsZones": "azurerm_private_dns_zone",
        "Microsoft.Network/privateDnsZones/virtualNetworkLinks": "azurerm_private_dns_zone_virtual_network_link",
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

    def _extract_resource_groups(self, resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract unique resource groups from all resources.

        Returns list of RG resource dictionaries with properties:
        - id: RG azure resource ID
        - name: RG name
        - location: Azure region
        - type: "Microsoft.Resources/resourceGroups"
        """
        rg_map = {}
        for resource in resources:
            # Try both field names (resource_group and resourceGroup)
            rg_name = resource.get("resource_group") or resource.get("resourceGroup")
            if rg_name and rg_name not in rg_map:
                # Extract location from first resource in this RG
                location = resource.get("location", "westus2")
                subscription = resource.get("subscription_id") or resource.get("subscriptionId", "")

                rg_map[rg_name] = {
                    "id": f"/subscriptions/{subscription}/resourceGroups/{rg_name}",
                    "name": rg_name,
                    "location": location,
                    "type": "Microsoft.Resources/resourceGroups",
                    "subscriptionId": subscription,
                    "subscription_id": subscription,
                    "resourceGroup": rg_name,  # For compatibility
                    "resource_group": rg_name,  # Self-reference
                }

        return list(rg_map.values())

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

        # Clear NSG associations and tracking from previous runs
        self._nsg_associations = []
        self._available_resources = {}
        self._missing_references = []
        # Track available subnets separately (needs VNet-scoped names)
        self._available_subnets = set()

        # First pass: Build index of available resources
        logger.info("Building resource index for reference validation")
        for resource in graph.resources:
            azure_type = resource.get("type", "")
            resource_name = resource.get("name", "")

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
            if terraform_type:
                if terraform_type not in self._available_resources:
                    self._available_resources[terraform_type] = set()
                safe_name = self._sanitize_terraform_name(resource_name)
                self._available_resources[terraform_type].add(safe_name)

                # For subnets, also track VNet-scoped names
                if azure_type == "Microsoft.Network/subnets":
                    subnet_id = resource.get("id", "")
                    vnet_name = self._extract_resource_name_from_id(subnet_id, "virtualNetworks")
                    if vnet_name != "unknown" and "/subnets/" in subnet_id:
                        vnet_name_safe = self._sanitize_terraform_name(vnet_name)
                        subnet_name_safe = safe_name
                        scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"
                        self._available_subnets.add(scoped_subnet_name)

            # Also track subnets from VNet properties (inline subnets)
            if azure_type == "Microsoft.Network/virtualNetworks":
                properties = self._parse_properties(resource)
                subnets = properties.get("subnets", [])
                vnet_safe_name = self._sanitize_terraform_name(resource_name)
                for subnet in subnets:
                    subnet_name = subnet.get("name")
                    if subnet_name:
                        subnet_safe_name = self._sanitize_terraform_name(subnet_name)
                        scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"
                        self._available_subnets.add(scoped_subnet_name)

        logger.debug(f"Resource index built: {sum(len(v) for v in self._available_resources.values())} resources tracked")
        logger.debug(f"Subnet index built: {len(self._available_subnets)} subnets tracked")

        # Extract and generate resource group resources
        logger.info("Extracting resource groups from discovered resources")
        rg_resources = self._extract_resource_groups(graph.resources)
        logger.info(f"Found {len(rg_resources)} unique resource groups")

        # Add RG resources to the available resources index
        for rg_resource in rg_resources:
            rg_name_sanitized = self._sanitize_terraform_name(rg_resource["name"])
            if "azurerm_resource_group" not in self._available_resources:
                self._available_resources["azurerm_resource_group"] = set()
            self._available_resources["azurerm_resource_group"].add(rg_name_sanitized)

        # Prepend RG resources to the resource list for dependency analysis
        all_resources = rg_resources + graph.resources

        # Analyze dependencies and sort resources by tier
        logger.info("Analyzing resource dependencies and calculating tiers")
        analyzer = DependencyAnalyzer()
        resource_dependencies = analyzer.analyze(all_resources)

        # Second pass: Process resources with validation (sorted by tier)
        for resource_dep in resource_dependencies:
            resource = resource_dep.resource
            terraform_resource = self._convert_resource(resource, terraform_config)
            if terraform_resource:
                resource_type, resource_name, resource_config = terraform_resource

                # Add depends_on if resource has dependencies
                if resource_dep.depends_on:
                    resource_config["depends_on"] = sorted(list(resource_dep.depends_on))
                    logger.debug(
                        f"Added dependencies for {resource_type}.{resource_name}: "
                        f"{resource_dep.depends_on}"
                    )

                if resource_type not in terraform_config["resource"]:
                    terraform_config["resource"][resource_type] = {}

                terraform_config["resource"][resource_type][resource_name] = (
                    resource_config
                )

        # Emit NSG association resources after all resources are processed
        if self._nsg_associations:
            if "azurerm_subnet_network_security_group_association" not in terraform_config["resource"]:
                terraform_config["resource"]["azurerm_subnet_network_security_group_association"] = {}

            for subnet_tf_name, nsg_tf_name, subnet_name, nsg_name in self._nsg_associations:
                # Association resource name: subnet_name + "_nsg_association"
                assoc_name = f"{subnet_tf_name}_nsg_association"
                terraform_config["resource"]["azurerm_subnet_network_security_group_association"][assoc_name] = {
                    "subnet_id": f"${{azurerm_subnet.{subnet_tf_name}.id}}",
                    "network_security_group_id": f"${{azurerm_network_security_group.{nsg_tf_name}.id}}",
                }
                logger.debug(
                    f"Generated NSG association: {assoc_name} (Subnet: {subnet_name}, NSG: {nsg_name})"
                )

        # Write main.tf.json
        output_file = out_dir / "main.tf.json"
        with open(output_file, "w") as f:
            json.dump(terraform_config, f, indent=2)

        # Report summary of missing references
        if self._missing_references:
            # Separate by type
            nic_refs = [r for r in self._missing_references if r.get("resource_type") == "network_interface"]
            subnet_refs = [r for r in self._missing_references if r.get("resource_type") == "subnet"]

            logger.warning(
                f"\n{'=' * 80}\n"
                f"MISSING RESOURCE REFERENCES DETECTED: {len(self._missing_references)} issue(s)\n"
                f"{'=' * 80}"
            )

            if nic_refs:
                logger.warning(f"\nMissing Network Interface References ({len(nic_refs)} issues):")
                for ref in nic_refs:
                    logger.warning(
                        f"\n  VM '{ref['vm_name']}' references missing NIC:\n"
                        f"    Missing NIC: {ref['missing_resource_name']}\n"
                        f"    Azure ID: {ref['missing_resource_id']}\n"
                        f"    VM ID: {ref['vm_id']}"
                    )

            if subnet_refs:
                logger.warning(f"\nMissing Subnet References ({len(subnet_refs)} issues):")
                # Group by VNet to make it easier to understand
                subnets_by_vnet = {}
                for ref in subnet_refs:
                    vnet = ref.get("missing_vnet_name", "unknown")
                    if vnet not in subnets_by_vnet:
                        subnets_by_vnet[vnet] = []
                    subnets_by_vnet[vnet].append(ref)

                for vnet, refs in subnets_by_vnet.items():
                    logger.warning(f"\n  VNet '{vnet}' (referenced by {len(refs)} resource(s)):")
                    # Show first subnet details
                    first_ref = refs[0]
                    logger.warning(
                        f"    Missing subnet: {first_ref['missing_resource_name']}\n"
                        f"    Expected Terraform name: {first_ref['expected_terraform_name']}\n"
                        f"    Azure ID: {first_ref['missing_resource_id']}"
                    )
                    # List all resources referencing this subnet
                    logger.warning(f"    Resources referencing this subnet:")
                    for ref in refs[:10]:  # Limit to first 10
                        logger.warning(f"      - {ref['resource_name']}")
                    if len(refs) > 10:
                        logger.warning(f"      ... and {len(refs) - 10} more")

            logger.warning(
                f"\n{'=' * 80}\n"
                f"These resources exist in resource properties but were not discovered/stored in Neo4j.\n"
                f"This may indicate:\n"
                f"  1. Parent resources (VNets) in different resource groups weren't fully discovered\n"
                f"  2. Discovery service filtered these resources\n"
                f"  3. Resources were deleted after dependent resources were created\n"
                f"  4. Subnet extraction rule skipped subnets without address prefixes\n"
                f"{'=' * 80}\n"
            )

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

        # Resource groups don't have a resource_group_name field
        if azure_type == "Microsoft.Resources/resourceGroups":
            resource_config = {
                "name": resource_name,
                "location": location,
            }
        else:
            resource_config = {
                "name": resource_name,
                "location": location,
                "resource_group_name": resource.get("resource_group", "default-rg"),
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
            properties = self._parse_properties(resource)

            subnets = properties.get("subnets", [])
            for subnet in subnets:
                subnet_name = subnet.get("name")
                if not subnet_name:
                    continue  # Skip subnets without names

                subnet_props = subnet.get("properties", {})
                # Handle both addressPrefix (singular) and addressPrefixes (array)
                address_prefixes = (
                    [subnet_props.get("addressPrefix")]
                    if subnet_props.get("addressPrefix")
                    else subnet_props.get("addressPrefixes", [])
                )
                if not address_prefixes or not address_prefixes[0]:
                    logger.warning(
                        f"Subnet '{subnet_name}' in vnet '{resource_name}' has no addressPrefix or addressPrefixes, skipping"
                    )
                    continue

                # Use first address prefix for subnet config
                address_prefix = address_prefixes[0]

                # Build VNet-scoped subnet resource name
                # Pattern: {vnet_name}_{subnet_name}
                vnet_safe_name = safe_name  # Already computed: self._sanitize_terraform_name(resource_name)
                subnet_safe_name = self._sanitize_terraform_name(subnet_name)
                scoped_subnet_name = f"{vnet_safe_name}_{subnet_safe_name}"

                # Build subnet resource config (name field remains original Azure name)
                subnet_config = {
                    "name": subnet_name,  # Azure resource name (unchanged)
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_safe_name}.name}}",
                    "address_prefixes": [address_prefix],
                }

                # Check for NSG association (store for later emission as separate resource)
                nsg_info = subnet_props.get("networkSecurityGroup", {})
                if nsg_info and "id" in nsg_info:
                    nsg_name = self._extract_resource_name_from_id(
                        nsg_info["id"], "networkSecurityGroups"
                    )
                    if nsg_name != "unknown":
                        nsg_name_safe = self._sanitize_terraform_name(nsg_name)
                        # Store association for later emission
                        self._nsg_associations.append(
                            (scoped_subnet_name, nsg_name_safe, subnet_name, nsg_name)
                        )
                        logger.debug(
                            f"Tracked NSG association for inline subnet: {subnet_name} -> {nsg_name}"
                        )

                # Add to terraform config with scoped key
                if "azurerm_subnet" not in terraform_config["resource"]:
                    terraform_config["resource"]["azurerm_subnet"] = {}

                # Log if overwriting (shouldn't happen with scoped names)
                if scoped_subnet_name in terraform_config["resource"]["azurerm_subnet"]:
                    logger.warning(
                        f"Subnet resource name collision: {scoped_subnet_name} already exists. "
                        f"This indicates identical VNet and subnet names."
                    )

                terraform_config["resource"]["azurerm_subnet"][scoped_subnet_name] = (
                    subnet_config
                )

                logger.debug(
                    f"Generated subnet resource: {scoped_subnet_name} "
                    f"(VNet: {resource_name}, Subnet: {subnet_name})"
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
            properties = self._parse_properties(resource)

            network_profile = properties.get("networkProfile", {})
            nics = network_profile.get("networkInterfaces", [])

            if nics:
                nic_refs = []
                missing_nics = []
                for nic in nics:
                    nic_id = nic.get("id", "")
                    if nic_id:
                        # Extract NIC name from ID using helper
                        nic_name = self._extract_resource_name_from_id(
                            nic_id, "networkInterfaces"
                        )
                        if nic_name != "unknown":
                            nic_name_safe = self._sanitize_terraform_name(nic_name)

                            # Validate that the NIC resource exists in the graph
                            if self._validate_resource_reference(
                                "azurerm_network_interface", nic_name_safe
                            ):
                                nic_refs.append(
                                    f"${{azurerm_network_interface.{nic_name_safe}.id}}"
                                )
                            else:
                                # Track missing NIC
                                missing_nics.append({
                                    "nic_name": nic_name,
                                    "nic_id": nic_id,
                                    "nic_terraform_name": nic_name_safe,
                                })
                                self._missing_references.append({
                                    "vm_name": resource_name,
                                    "vm_id": resource.get("id", ""),
                                    "resource_type": "network_interface",
                                    "missing_resource_name": nic_name,
                                    "missing_resource_id": nic_id,
                                })

                if missing_nics:
                    logger.error(
                        f"VM '{resource_name}' references {len(missing_nics)} network interface(s) "
                        f"that don't exist in Neo4j graph: {[n['nic_name'] for n in missing_nics]}"
                    )
                    # Log detailed information about missing NICs
                    for missing_nic in missing_nics:
                        logger.error(
                            f"  Missing NIC: {missing_nic['nic_name']}\n"
                            f"    Azure ID: {missing_nic['nic_id']}\n"
                            f"    Expected Terraform name: {missing_nic['nic_terraform_name']}"
                        )
                    # Don't add invalid VM to output if all NICs are missing
                    if not nic_refs:
                        logger.error(
                            f"Skipping VM '{resource_name}' - all referenced NICs are missing from graph"
                        )
                        return None

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
        elif azure_type == "Microsoft.Network/bastionHosts":
            # Bastion Hosts require IP configuration with subnet and public IP
            properties = self._parse_properties(resource)

            ip_configurations = properties.get("ipConfigurations", [])
            if ip_configurations:
                # Use first IP configuration
                ip_config = ip_configurations[0]
                ip_config_name = ip_config.get("name", "IpConf")
                ip_props = ip_config.get("properties", {})

                # Extract subnet reference
                subnet_info = ip_props.get("subnet", {})
                subnet_id = subnet_info.get("id", "")

                # Use helper method to resolve VNet-scoped subnet reference
                subnet_reference = self._resolve_subnet_reference(
                    subnet_id, resource_name
                )

                # Extract public IP reference
                public_ip_info = ip_props.get("publicIPAddress", {})
                public_ip_id = public_ip_info.get("id", "")
                public_ip_name = self._extract_resource_name_from_id(
                    public_ip_id, "publicIPAddresses"
                )

                # Build IP configuration block
                ip_config_block = {
                    "name": ip_config_name,
                    "subnet_id": subnet_reference,  # Always set (even if placeholder)
                }

                # Add public IP reference if found
                if public_ip_name != "unknown":
                    public_ip_name = self._sanitize_terraform_name(public_ip_name)
                    ip_config_block["public_ip_address_id"] = (
                        f"${{azurerm_public_ip.{public_ip_name}.id}}"
                    )

                resource_config["ip_configuration"] = ip_config_block

                # Validate reference (warn if placeholder)
                if "unknown" in subnet_reference:
                    logger.warning(
                        f"Bastion Host '{resource_name}' has invalid subnet reference. "
                        f"Generated Terraform may be invalid."
                    )
            else:
                logger.warning(
                    f"Bastion Host '{resource_name}' has no IP configurations in properties. "
                    "Generated Terraform may be invalid."
                )

            # Add SKU if present
            sku = properties.get("sku", {})
            if sku and "name" in sku:
                resource_config["sku"] = sku["name"]

        elif azure_type == "Microsoft.Network/networkSecurityGroups":
            # NSGs don't need additional required properties beyond name, location, and resource_group
            pass
        elif azure_type == "Microsoft.Network/networkInterfaces":
            # NICs require ip_configuration blocks
            # Parse properties field to get ipConfigurations
            properties = self._parse_properties(resource)

            ip_configurations = properties.get("ipConfigurations", [])
            if ip_configurations:
                # Use first IP configuration
                ip_config = ip_configurations[0]
                ip_props = ip_config.get("properties", {})
                subnet_info = ip_props.get("subnet", {})
                subnet_id = subnet_info.get("id", "")

                # Use helper method to resolve VNet-scoped subnet reference
                subnet_reference = self._resolve_subnet_reference(
                    subnet_id, resource_name
                )

                private_ip = ip_props.get("privateIPAddress", "")
                allocation_method = ip_props.get("privateIPAllocationMethod", "Dynamic")

                ip_config_block = {
                    "name": ip_config.get("name", "internal"),
                    "subnet_id": subnet_reference,
                    "private_ip_address_allocation": allocation_method,
                }

                # Add private IP if static allocation
                if allocation_method == "Static" and private_ip:
                    ip_config_block["private_ip_address"] = private_ip

                resource_config["ip_configuration"] = ip_config_block

                # Validate reference (warn if placeholder)
                if "unknown" in subnet_reference:
                    logger.warning(
                        f"NIC '{resource_name}' has invalid subnet reference. "
                        f"Generated Terraform may be invalid."
                    )
            else:
                logger.warning(
                    f"NIC '{resource_name}' has no ip_configurations in properties. "
                    "Generated Terraform may be invalid."
                )
        elif azure_type == "Microsoft.Network/subnets":
            properties = self._parse_properties(resource)

            # Extract parent VNet name from subnet ID
            subnet_id = resource.get("id", "")
            vnet_name = self._extract_resource_name_from_id(
                subnet_id, "virtualNetworks"
            )

            # Build VNet-scoped resource name
            if vnet_name != "unknown" and "/subnets/" in subnet_id:
                vnet_name_safe = self._sanitize_terraform_name(vnet_name)
                subnet_name_safe = self._sanitize_terraform_name(resource_name)
                # Override safe_name to use scoped naming
                safe_name = f"{vnet_name_safe}_{subnet_name_safe}"

                resource_config = {
                    "name": resource_name,  # Original Azure name
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": f"${{azurerm_virtual_network.{vnet_name_safe}.name}}",
                }

                logger.debug(
                    f"Generated standalone subnet: {safe_name} "
                    f"(VNet: {vnet_name}, Subnet: {resource_name})"
                )
            else:
                logger.warning(
                    f"Standalone subnet '{resource_name}' has no parent VNet in ID: {subnet_id}. "
                    f"Using fallback naming (may cause collisions)."
                )
                # Fallback to old behavior
                safe_name = self._sanitize_terraform_name(resource_name)
                resource_config = {
                    "name": resource_name,
                    "resource_group_name": resource.get("resource_group", "default-rg"),
                    "virtual_network_name": "unknown_vnet",
                }

            # Handle address prefixes with fallback
            address_prefixes = (
                [properties.get("addressPrefix")]
                if properties.get("addressPrefix")
                else properties.get("addressPrefixes", [])
            )
            if not address_prefixes:
                logger.warning(f"Subnet '{resource_name}' has no address prefixes")
                address_prefixes = ["10.0.0.0/24"]
            resource_config["address_prefixes"] = address_prefixes

            # Check for NSG association (store for later emission as separate resource)
            nsg_info = properties.get("networkSecurityGroup", {})
            if nsg_info and "id" in nsg_info:
                nsg_name = self._extract_resource_name_from_id(
                    nsg_info["id"], "networkSecurityGroups"
                )
                if nsg_name != "unknown":
                    nsg_name_safe = self._sanitize_terraform_name(nsg_name)
                    # Store association for later emission
                    self._nsg_associations.append(
                        (safe_name, nsg_name_safe, resource_name, nsg_name)
                    )
                    logger.debug(
                        f"Tracked NSG association for standalone subnet: {resource_name} -> {nsg_name}"
                    )

            # Optional: Service Endpoints
            service_endpoints = properties.get("serviceEndpoints", [])
            if service_endpoints:
                resource_config["service_endpoints"] = [
                    ep["service"] for ep in service_endpoints if "service" in ep
                ]
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
                "resource_group_name": resource.get("resource_group", "default-rg"),
            }
        elif azure_type == "Microsoft.Network/privateEndpoints":
            # Private Endpoint specific properties
            # Ensure _available_subnets exists (for direct _convert_resource calls in tests)
            available_subnets = getattr(self, "_available_subnets", set())
            missing_references = getattr(self, "_missing_references", [])
            resource_config = emit_private_endpoint(
                resource,
                sanitize_name_fn=self._sanitize_terraform_name,
                extract_name_fn=self._extract_resource_name_from_id,
                available_subnets=available_subnets,
                missing_references=missing_references,
            )
        elif azure_type == "Microsoft.Network/privateDnsZones":
            # Private DNS Zone specific properties
            resource_config = emit_private_dns_zone(resource)
        elif azure_type == "Microsoft.Network/privateDnsZones/virtualNetworkLinks":
            # Private DNS Zone Virtual Network Link specific properties
            # Need to build set of available VNets for validation
            available_vnets = (
                self._available_resources.get("azurerm_virtual_network", set())
                if self._available_resources
                else set()
            )
            missing_references = getattr(self, "_missing_references", [])
            resource_config = emit_private_dns_zone_vnet_link(
                resource,
                sanitize_name_fn=self._sanitize_terraform_name,
                extract_name_fn=self._extract_resource_name_from_id,
                available_vnets=available_vnets,
                missing_references=missing_references,
            )
            if resource_config is None:
                # Invalid link configuration, skip it
                return None
            # Override safe_name with the link name from the config
            safe_name = resource_config.get("name", safe_name)

        return terraform_type, safe_name, resource_config

    def _parse_properties(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """Parse properties JSON from resource.

        Args:
            resource: Azure resource with properties field

        Returns:
            Parsed properties dict (empty dict if parsing fails)
        """
        properties_str = resource.get("properties", "{}")
        if isinstance(properties_str, str):
            try:
                return json.loads(properties_str)
            except json.JSONDecodeError:
                return {}
        return properties_str

    def _extract_resource_name_from_id(
        self, resource_id: str, resource_type: str
    ) -> str:
        """Extract resource name from Azure resource ID path.

        Args:
            resource_id: Full Azure resource ID
            resource_type: Azure resource type segment (e.g., "subnets", "networkInterfaces")

        Returns:
            Extracted resource name or "unknown"
        """
        path_segment = f"/{resource_type}/"
        if path_segment in resource_id:
            return resource_id.split(path_segment)[-1].split("/")[0]
        return "unknown"

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

    def _validate_resource_reference(
        self, terraform_type: str, resource_name: str
    ) -> bool:
        """Validate that a referenced resource exists in the graph.

        Args:
            terraform_type: Terraform resource type (e.g., "azurerm_network_interface")
            resource_name: Sanitized Terraform resource name

        Returns:
            True if resource exists, False otherwise
        """
        return (
            terraform_type in self._available_resources
            and resource_name in self._available_resources[terraform_type]
        )

    def _resolve_subnet_reference(self, subnet_id: str, resource_name: str) -> str:
        """Resolve subnet reference to VNet-scoped Terraform resource name.

        Extracts both VNet and subnet names from Azure resource ID and constructs
        the scoped Terraform reference: ${azurerm_subnet.{vnet}_{subnet}.id}

        Validates that the subnet exists in the graph and tracks missing references.

        Args:
            subnet_id: Azure subnet resource ID
                Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/
                        Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
            resource_name: Name of the resource referencing this subnet (for logging)

        Returns:
            Terraform reference string with VNet-scoped subnet name

        Example:
            >>> emitter._resolve_subnet_reference(
            ...     "/subscriptions/.../virtualNetworks/infra-vnet/subnets/AzureBastionSubnet",
            ...     "bastion-host-1"
            ... )
            '${azurerm_subnet.infra_vnet_AzureBastionSubnet.id}'
        """
        if not subnet_id or "/subnets/" not in subnet_id:
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet ID: {subnet_id}"
            )
            return "${azurerm_subnet.unknown_subnet.id}"

        # Extract VNet name from ID
        vnet_name = self._extract_resource_name_from_id(subnet_id, "virtualNetworks")
        if vnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' subnet ID missing VNet segment: {subnet_id}"
            )
            # Fallback: use only subnet name (old behavior for compatibility)
            subnet_name = self._extract_resource_name_from_id(subnet_id, "subnets")
            if subnet_name != "unknown":
                subnet_name_safe = self._sanitize_terraform_name(subnet_name)
                return f"${{azurerm_subnet.{subnet_name_safe}.id}}"
            return "${azurerm_subnet.unknown_subnet.id}"

        # Extract subnet name from ID
        subnet_name = self._extract_resource_name_from_id(subnet_id, "subnets")
        if subnet_name == "unknown":
            logger.warning(
                f"Resource '{resource_name}' has invalid subnet name in ID: {subnet_id}"
            )
            return "${azurerm_subnet.unknown_subnet.id}"

        # Construct VNet-scoped reference
        vnet_name_safe = self._sanitize_terraform_name(vnet_name)
        subnet_name_safe = self._sanitize_terraform_name(subnet_name)
        scoped_subnet_name = f"{vnet_name_safe}_{subnet_name_safe}"

        # Validate subnet exists in the graph
        if scoped_subnet_name not in self._available_subnets:
            logger.error(
                f"Resource '{resource_name}' references subnet that doesn't exist in graph:\n"
                f"  Subnet Terraform name: {scoped_subnet_name}\n"
                f"  Subnet Azure name: {subnet_name}\n"
                f"  VNet Azure name: {vnet_name}\n"
                f"  Azure ID: {subnet_id}"
            )
            # Track missing subnet reference
            self._missing_references.append({
                "resource_name": resource_name,
                "resource_type": "subnet",
                "missing_resource_name": subnet_name,
                "missing_resource_id": subnet_id,
                "missing_vnet_name": vnet_name,
                "expected_terraform_name": scoped_subnet_name,
            })

        logger.debug(
            f"Resolved subnet reference for '{resource_name}': "
            f"VNet='{vnet_name}', Subnet='{subnet_name}' -> {scoped_subnet_name}"
        )

        return f"${{azurerm_subnet.{scoped_subnet_name}.id}}"

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
