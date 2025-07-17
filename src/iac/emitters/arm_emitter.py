# type: ignore
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false, reportUnknownMemberType=false
# type: ignore
# type: ignore
# pyright: reportMissingParameterType=false, reportMissingTypeArgument=false, reportAttributeAccessIssue=false, reportCallIssue=false, reportIndexIssue=false, reportUnknownMemberType=false
"""ARM template emitter for Infrastructure-as-Code generation.

This module provides Azure Resource Manager template generation from
tenant graph data.

TODO: Implement complete ARM template generation logic.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional

from ..traverser import TenantGraph
from . import register_emitter
from .base import IaCEmitter


class ArmEmitter(IaCEmitter):
    """Emitter for generating Azure Resource Manager templates.

    TODO: Implement complete ARM template resource mapping and generation.
    """

    def emit(
        self, graph: TenantGraph, out_dir: Path, domain_name: Optional[str] = None
    ) -> List[Path]:
        """Generate ARM templates from tenant graph, including managed identities and RBAC."""
        import json
        from typing import cast

        out_dir.mkdir(parents=True, exist_ok=True)

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
            "parameters": {},
            "variables": {},
            "resources": [],
            "outputs": {},
        }
        resources_list = cast(list[dict[str, Any]], arm_template["resources"])

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

        # --- Collect special resources ---
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

        # --- Emit managed identities ---
        for mi in managed_identities:
            resources_list.append(self._emit_user_assigned_identity(mi))

        # --- Emit custom role definitions ---
        for rd in role_definitions:
            if rd.get("properties", {}).get("roleType", "").lower() == "custom":
                resources_list.append(self._emit_custom_role_definition(rd))

        # --- Emit role assignments ---
        for ra in role_assignments:
            resources_list.append(self._emit_role_assignment(ra))

        # --- Emit regular resources, wiring up identity blocks ---
        for resource in regular_resources:
            az_type = resource.get("type", "")
            mapping = ARM_TYPE_MAPPING.get(az_type)
            if not mapping:
                continue

            arm_resource = {
                "type": mapping["type"],
                "apiVersion": mapping["apiVersion"],
                "name": resource.get("name", "unnamed"),
                "location": resource.get("location", "eastus"),
                "properties": resource.get("properties", {}),
            }

            # Add required fields for specific types
            if az_type == "Microsoft.Storage/storageAccounts":
                arm_resource["sku"] = {"name": "Standard_LRS"}
                arm_resource["kind"] = "StorageV2"
            if "tags" in resource:
                arm_resource["tags"] = resource["tags"]

            # --- System-assigned or user-assigned identity block ---
            identity = resource.get("identity")
            if identity and isinstance(identity, dict):
                arm_resource["identity"] = identity

            # If resource references a user-assigned identity by id, add identity block
            if "userAssignedIdentities" in resource:
                # ARM expects: {"type": "UserAssigned", "userAssignedIdentities": {id: {}}}
                if "identity" not in arm_resource:
                    arm_resource["identity"] = {}
                arm_resource["identity"]["type"] = "UserAssigned"  # type: ignore
                arm_resource["identity"]["userAssignedIdentities"] = resource[
                    "userAssignedIdentities"
                ]  # type: ignore

            # If resource is marked with systemAssignedIdentity: true, add block
            if resource.get("systemAssignedIdentity", False):
                if "identity" not in arm_resource:
                    arm_resource["identity"] = {}
                arm_resource["identity"]["type"] = "SystemAssigned"  # type: ignore

            resources_list.append(arm_resource)

        output_file = out_dir / "azuredeploy.json"
        with open(output_file, "w") as f:
            json.dump(arm_template, f, indent=2)

        # --- Build AAD objects list ---
        aad_users: list[dict[str, str]] = []
        aad_groups: list[dict[str, str]] = []
        aad_sps: list[dict[str, str]] = []
        for ra in role_assignments:
            props = ra.get("properties", ra)
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

        files: list[Path] = [output_file]
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

    def _emit_role_assignment(self, ra: dict[str, Any]) -> dict[str, Any]:
        # ARM resource for role assignment
        props = ra.get("properties", ra)
        return {
            "type": "Microsoft.Authorization/roleAssignments",
            "apiVersion": "2022-04-01",
            "name": ra.get("name", ra.get("id", "roleAssignment")),
            "properties": {
                "roleDefinitionId": props.get("roleDefinitionId"),
                "principalId": props.get("principalId"),
                "principalType": props.get("principalType"),
                "scope": props.get("scope"),
            },
        }

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

        TODO: Implement ARM template generation logic.
        """
        # TODO: Convert tenant graph resources to ARM template resources
        # TODO: Generate ARM template schema and metadata
        # TODO: Handle resource dependencies and deployment order
        # TODO: Generate parameters and variables
        # TODO: Generate outputs section
        # TODO: Write template files (azuredeploy.json, azuredeploy.parameters.json)
        raise NotImplementedError("ARM template generation not yet implemented")

    def get_supported_resource_types(self) -> List[str]:
        """Get list of Azure resource types supported by ARM templates.

        Returns:
            List of supported Azure resource type strings

        TODO: Implement comprehensive Azure resource type mapping for ARM.
        """
        # TODO: Return complete list of Azure resource types supported by ARM
        return [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Web/sites",
            "Microsoft.Sql/servers",
            "Microsoft.KeyVault/vaults",
        ]

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate generated ARM template for correctness.

        Args:
            template_data: Generated ARM template data

        Returns:
            True if template is valid, False otherwise

        TODO: Implement ARM template-specific validation.
        """
        # TODO: Validate ARM template JSON schema
        # TODO: Check resource API versions
        # TODO: Validate resource dependencies
        # TODO: Check parameter and variable references
        raise NotImplementedError("ARM template validation not yet implemented")


# Auto-register this emitter
register_emitter("arm", ArmEmitter)
