# type: ignore
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false, reportUnknownMemberType=false
# type: ignore
# type: ignore
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false, reportUnknownMemberType=false
"""ARM template emitter for Infrastructure-as-Code generation.

This module provides Azure Resource Manager template generation from
tenant graph data.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..traverser import TenantGraph
from . import register_emitter
from .base import IaCEmitter

logger = logging.getLogger(__name__)


class ArmEmitter(IaCEmitter):
    """Emitter for generating Azure Resource Manager templates."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        target_subscription_id: Optional[str] = None,
        target_tenant_id: Optional[str] = None,
        identity_mapping: Optional[Dict[str, Any]] = None,
    ):
        """Initialize ArmEmitter with optional cross-tenant translation.

        Bug #69 fix: Add cross-tenant translation support for ARM templates.

        Args:
            config: Optional emitter-specific configuration
            target_subscription_id: Target subscription ID for cross-tenant translation
            target_tenant_id: Target tenant ID for cross-tenant translation
            identity_mapping: Identity mapping dictionary for Entra ID translation
        """
        super().__init__(config)
        self.target_subscription_id = target_subscription_id
        self.target_tenant_id = target_tenant_id
        self.identity_mapping = identity_mapping

    def emit(
        self, graph: TenantGraph, out_dir: Path, domain_name: Optional[str] = None
    ) -> List[Path]:
        """Generate ARM templates from tenant graph, including managed identities and RBAC."""
        import json

        out_dir.mkdir(parents=True, exist_ok=True)

        # Generate the main ARM template using the refactored method
        arm_template = self._generate_template_data(graph, domain_name)

        # Write the main ARM template
        output_file = out_dir / "azuredeploy.json"
        with open(output_file, "w") as f:
            json.dump(arm_template, f, indent=2)

        # Generate AAD objects file for role assignments
        files: list[Path] = [output_file]

        # Collect AAD objects from role assignments
        aad_users: list[dict[str, str]] = []
        aad_groups: list[dict[str, str]] = []
        aad_sps: list[dict[str, str]] = []

        for resource in graph.resources:
            if resource.get("type", "").endswith("roleAssignments"):
                props = resource.get("properties", resource)
                pid = props.get("principalId")
                ptype = (props.get("principalType") or "").lower()
                if pid:
                    entry = {"id": pid}
                    if ptype == "user":
                        aad_users.append(entry)
                    elif ptype == "group":
                        aad_groups.append(entry)
                    elif ptype == "serviceprincipal":
                        aad_sps.append(entry)

        # Write AAD objects file if there are any AAD principals
        if aad_users or aad_groups or aad_sps:
            aad_data = {
                "users": aad_users,
                "groups": aad_groups,
                "service_principals": aad_sps,
            }
            aad_file = out_dir / "aad_objects.json"
            with open(aad_file, "w") as f:
                json.dump(aad_data, f, indent=2)
            files.append(aad_file)

        return files

    def _emit_user_assigned_identity(self, mi: dict[str, Any]) -> dict[str, Any]:
        # Minimal ARM resource for user-assigned managed identity
        return {
            "type": "Microsoft.ManagedIdentity/userAssignedIdentities",
            "apiVersion": "2023-01-31",
            "name": mi.get("name", "identity"),
            "location": mi.get("location", "eastus"),
            "properties": {},
        }

    def _emit_role_assignment(self, ra: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Emit ARM resource for role assignment with cross-tenant translation.

        Bug #69 fix: Translate scope, roleDefinitionId, and principalId for
        cross-tenant deployments. Returns None if translation fails.
        """
        props = ra.get("properties", ra)
        resource_name = ra.get("name", ra.get("id", "roleAssignment"))

        # Get scope and translate subscription ID for cross-tenant deployments
        scope = props.get("scope", "")
        if self.target_subscription_id and scope:
            scope = re.sub(
                r"/subscriptions/([a-f0-9-]+|ABSTRACT_SUBSCRIPTION)(/|$)",
                f"/subscriptions/{self.target_subscription_id}\\2",
                scope,
                flags=re.IGNORECASE,
            )

        # Translate roleDefinitionId subscription
        role_def_id = props.get("roleDefinitionId", "")
        if self.target_subscription_id and role_def_id:
            role_def_id = re.sub(
                r"/subscriptions/([a-f0-9-]+|ABSTRACT_SUBSCRIPTION)/",
                f"/subscriptions/{self.target_subscription_id}/",
                role_def_id,
                flags=re.IGNORECASE,
            )

        # Translate principal_id using identity mapping
        principal_id = props.get("principalId", "")
        principal_type = props.get("principalType", "Unknown")

        # Skip role assignments in cross-tenant mode without identity mapping
        if self.target_tenant_id and not self.identity_mapping:
            logger.warning(
                f"Skipping ARM role assignment '{resource_name}' in cross-tenant mode: "
                f"No identity mapping provided."
            )
            return None

        # Translate principalId if identity mapping provided
        if self.identity_mapping and principal_id:
            translated = self._translate_principal_id(principal_id, principal_type)
            if translated:
                logger.info(f"ARM: Translated principal {principal_id} -> {translated}")
                principal_id = translated
            else:
                logger.warning(
                    f"Skipping ARM role assignment '{resource_name}': "
                    f"Principal ID '{principal_id}' not found in identity mapping"
                )
                return None

        return {
            "type": "Microsoft.Authorization/roleAssignments",
            "apiVersion": "2022-04-01",
            "name": resource_name,
            "properties": {
                "roleDefinitionId": role_def_id,
                "principalId": principal_id,
                "principalType": principal_type,
                "scope": scope,
            },
        }

    def _translate_principal_id(
        self, principal_id: str, principal_type: str
    ) -> Optional[str]:
        """Translate a principal ID using the identity mapping.

        Args:
            principal_id: Source tenant principal ID
            principal_type: Type of principal (User, Group, ServicePrincipal)

        Returns:
            Translated principal ID or None if not found
        """
        if not self.identity_mapping:
            return None

        identity_mappings = self.identity_mapping.get("identity_mappings", {})
        type_lower = principal_type.lower() if principal_type else "unknown"

        type_mapping = {
            "user": "users",
            "group": "groups",
            "serviceprincipal": "service_principals",
        }

        mapping_key = type_mapping.get(type_lower)
        if mapping_key and mapping_key in identity_mappings:
            type_mappings = identity_mappings.get(mapping_key, {})
            if principal_id in type_mappings:
                target_id = type_mappings[principal_id].get("target_object_id")
                if target_id and target_id != "MANUAL_INPUT_REQUIRED":
                    return target_id

        # Try all types as fallback
        for id_type in ["users", "groups", "service_principals"]:
            type_mappings = identity_mappings.get(id_type, {})
            if principal_id in type_mappings:
                target_id = type_mappings[principal_id].get("target_object_id")
                if target_id and target_id != "MANUAL_INPUT_REQUIRED":
                    return target_id

        return None

    def _emit_custom_role_definition(self, rd: dict[str, Any]) -> dict[str, Any]:
        # ARM resource for custom role definition
        props = rd.get("properties", rd)
        return {
            "type": "Microsoft.Authorization/roleDefinitions",
            "apiVersion": "2022-04-01",
            "name": rd.get("name", rd.get("id", "roleDefinition")),
            "properties": {
                "roleName": props.get("roleName"),
                "description": props.get("description"),
                "permissions": props.get("permissions", []),
                "assignableScopes": props.get("assignableScopes", []),
                "roleType": "Custom",
            },
        }

    async def emit_template(
        self, tenant_graph: TenantGraph, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate ARM template from tenant graph.

        Args:
            tenant_graph: Input tenant graph data
            output_path: Optional output file path

        Returns:
            Dictionary containing generated ARM template data
        """
        # Use the main emit method for actual implementation
        if output_path:
            out_dir = Path(output_path)
        else:
            out_dir = Path("./arm_output")

        written_files = self.emit(tenant_graph, out_dir)

        return {
            "format": "arm",
            "files_written": [str(f) for f in written_files],
            "resource_count": len(tenant_graph.resources),
        }

    def get_supported_resource_types(self) -> List[str]:
        """Get list of Azure resource types supported by ARM templates.

        Returns:
            List of supported Azure resource type strings
        """
        return [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Network/networkSecurityGroups",
            "Microsoft.Network/publicIPAddresses",
            "Microsoft.Network/networkInterfaces",
            "Microsoft.Web/sites",
            "Microsoft.Sql/servers",
            "Microsoft.KeyVault/vaults",
            "Microsoft.ManagedIdentity/userAssignedIdentities",
            "Microsoft.Authorization/roleAssignments",
            "Microsoft.Authorization/roleDefinitions",
            "Microsoft.Resources/resourceGroups",
        ]

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate generated ARM template for correctness.

        Args:
            template_data: Generated ARM template data

        Returns:
            True if template is valid, False otherwise
        """
        # Validate required ARM template schema elements
        required_keys = [
            "$schema",
            "contentVersion",
            "parameters",
            "variables",
            "resources",
            "outputs",
        ]

        for key in required_keys:
            if key not in template_data:
                return False

        # Validate schema URL
        if not template_data["$schema"].startswith(
            "https://schema.management.azure.com"
        ):
            return False

        # Validate contentVersion format
        if not template_data["contentVersion"]:
            return False

        # Validate resources is a list
        if not isinstance(template_data["resources"], list):
            return False

        # Validate each resource has required properties
        for resource in template_data["resources"]:
            if not isinstance(resource, dict):
                return False
            if (
                "type" not in resource
                or "name" not in resource
                or "apiVersion" not in resource
            ):
                return False

        return True

    def emit_to_file(
        self, graph: TenantGraph, file_path: Path, domain_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate ARM template and write to a specific file.

        Args:
            graph: Input tenant graph data
            file_path: Path to the output ARM template file
            domain_name: Optional domain name for user accounts

        Returns:
            Dictionary containing the ARM template data
        """
        template_data = self._generate_template_data(graph, domain_name)

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write the ARM template to the specified file
        import json

        with open(file_path, "w") as f:
            json.dump(template_data, f, indent=2)

        return template_data

    def emit_to_string(
        self, graph: TenantGraph, domain_name: Optional[str] = None
    ) -> str:
        """Generate ARM template as a JSON string.

        Args:
            graph: Input tenant graph data
            domain_name: Optional domain name for user accounts

        Returns:
            ARM template as a JSON string
        """
        template_data = self._generate_template_data(graph, domain_name)

        import json

        return json.dumps(template_data, indent=2)

    def _generate_template_data(
        self, graph: TenantGraph, domain_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate ARM template data structure from tenant graph.

        Args:
            graph: Input tenant graph data
            domain_name: Optional domain name for user accounts

        Returns:
            Dictionary containing ARM template data
        """
        from typing import cast

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

        arm_template: dict[str, Any] = {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "parameters": {
                "location": {
                    "type": "string",
                    "defaultValue": "[resourceGroup().location]",
                    "metadata": {"description": "Location for all resources"},
                }
            },
            "variables": {},
            "resources": [],
            "outputs": {},
        }
        resources_list = cast(list[dict[str, Any]], arm_template["resources"])

        # ARM resource type mapping with comprehensive API versions
        ARM_TYPE_MAPPING = {
            "Microsoft.Compute/virtualMachines": {
                "type": "Microsoft.Compute/virtualMachines",
                "apiVersion": "2023-03-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Storage/storageAccounts": {
                "type": "Microsoft.Storage/storageAccounts",
                "apiVersion": "2023-01-01",
                "required": ["name", "location", "sku", "kind", "properties"],
            },
            "Microsoft.Network/virtualNetworks": {
                "type": "Microsoft.Network/virtualNetworks",
                "apiVersion": "2023-04-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Network/networkSecurityGroups": {
                "type": "Microsoft.Network/networkSecurityGroups",
                "apiVersion": "2023-04-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Network/publicIPAddresses": {
                "type": "Microsoft.Network/publicIPAddresses",
                "apiVersion": "2023-04-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Network/networkInterfaces": {
                "type": "Microsoft.Network/networkInterfaces",
                "apiVersion": "2023-04-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Web/sites": {
                "type": "Microsoft.Web/sites",
                "apiVersion": "2023-01-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.Sql/servers": {
                "type": "Microsoft.Sql/servers",
                "apiVersion": "2022-11-01",
                "required": ["name", "location", "properties"],
            },
            "Microsoft.KeyVault/vaults": {
                "type": "Microsoft.KeyVault/vaults",
                "apiVersion": "2023-02-01",
                "required": ["name", "location", "properties"],
            },
        }

        # Collect special resources
        managed_identities = []
        role_assignments = []
        role_definitions = []
        regular_resources = []

        for resource in graph.resources:
            rtype = resource.get("type", "")
            if rtype == "Microsoft.ManagedIdentity/userAssignedIdentities":
                managed_identities.append(resource)
            elif rtype.endswith("roleAssignments"):
                role_assignments.append(resource)
            elif rtype.endswith("roleDefinitions"):
                role_definitions.append(resource)
            else:
                regular_resources.append(resource)

        # Emit managed identities
        for mi in managed_identities:
            resources_list.append(self._emit_user_assigned_identity(mi))

        # Emit custom role definitions
        for rd in role_definitions:
            if rd.get("properties", {}).get("roleType", "").lower() == "custom":
                resources_list.append(self._emit_custom_role_definition(rd))

        # Emit role assignments (filter out None returns from failed translations)
        for ra in role_assignments:
            arm_ra = self._emit_role_assignment(ra)
            if arm_ra:  # Bug #69: Skip role assignments that failed translation
                resources_list.append(arm_ra)

        # Emit regular resources with improved conversion logic
        for resource in regular_resources:
            az_type = resource.get("type", "")
            mapping = ARM_TYPE_MAPPING.get(az_type)
            if not mapping:
                continue

            arm_resource = self._convert_resource_to_arm(resource, mapping)
            if arm_resource:
                resources_list.append(arm_resource)

        # Add outputs section with resource information
        arm_template["outputs"]["deployedResources"] = {
            "type": "array",
            "value": "[variables('resourceNames')]",
        }

        # Add variables for resource tracking
        arm_template["variables"]["resourceNames"] = [
            resource.get("name", "unnamed") for resource in graph.resources
        ]

        return arm_template

    def _convert_resource_to_arm(
        self, resource: Dict[str, Any], mapping: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Convert a tenant graph resource to ARM template resource format.

        Args:
            resource: Source resource from tenant graph
            mapping: ARM type mapping information

        Returns:
            ARM template resource definition or None if conversion fails
        """
        arm_resource = {
            "type": mapping["type"],
            "apiVersion": mapping["apiVersion"],
            "name": resource.get("name", "unnamed"),
            "location": "[parameters('location')]",
            "properties": resource.get("properties", {}),
        }

        # Add resource-specific required properties
        az_type = resource.get("type", "")

        if az_type == "Microsoft.Storage/storageAccounts":
            arm_resource["sku"] = resource.get("sku", {"name": "Standard_LRS"})
            arm_resource["kind"] = resource.get("kind", "StorageV2")
        elif az_type == "Microsoft.Network/virtualNetworks":
            if "properties" not in arm_resource or not arm_resource["properties"]:
                arm_resource["properties"] = {
                    "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}
                }
        elif az_type == "Microsoft.Network/publicIPAddresses":
            if "properties" not in arm_resource or not arm_resource["properties"]:
                arm_resource["properties"] = {"publicIPAllocationMethod": "Dynamic"}

        # Add tags if present
        if "tags" in resource:
            arm_resource["tags"] = resource["tags"]

        # Handle identity blocks
        identity = resource.get("identity")
        if identity and isinstance(identity, dict):
            arm_resource["identity"] = identity

        # Handle user-assigned identities
        if "userAssignedIdentities" in resource:
            if "identity" not in arm_resource:
                arm_resource["identity"] = {}
            arm_resource["identity"]["type"] = "UserAssigned"
            arm_resource["identity"]["userAssignedIdentities"] = resource[
                "userAssignedIdentities"
            ]

        # Handle system-assigned identity
        if resource.get("systemAssignedIdentity", False):
            if "identity" not in arm_resource:
                arm_resource["identity"] = {}
            arm_resource["identity"]["type"] = "SystemAssigned"

        # Add resource dependencies if specified
        depends_on = resource.get("dependsOn", [])
        if depends_on:
            arm_resource["dependsOn"] = depends_on

        return arm_resource


# Auto-register this emitter
register_emitter("arm", ArmEmitter)
