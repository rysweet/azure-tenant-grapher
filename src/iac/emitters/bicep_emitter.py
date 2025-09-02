"""Bicep emitter for Infrastructure-as-Code generation.

This module provides Azure Bicep template generation from
tenant graph data, supporting resource group homing and module pattern.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..traverser import TenantGraph
from . import register_emitter
from .base import IaCEmitter


class BicepEmitter(IaCEmitter):
    """Emitter for generating Azure Bicep templates."""

    def emit(
        self,
        graph: TenantGraph,
        out_dir: Path,
        rg_name: Optional[str] = None,
        rg_location: Optional[str] = None,
        domain_name: Optional[str] = None,
    ) -> List[Path]:
        """
        Generate Bicep templates from tenant graph, including managed identities and RBAC.
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []

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

        # Compose Bicep lines
        from typing import Callable

        def emit_all_blocks(
            resources: list[dict[str, Any]],
            emit_fn: Callable[[dict[str, Any]], list[str]],
        ) -> list[str]:
            lines = []
            for r in resources:
                lines.extend(emit_fn(r))
            return lines

        if rg_name:
            # Write main.bicep (subscription scope)
            main_bicep = self._emit_subscription_wrapper(rg_name, rg_location)
            main_path = out_dir / "main.bicep"
            with open(main_path, "w") as f:
                f.write(main_bicep)
            paths.append(main_path)

            # Write modules/rg.bicep (resource group scope)
            modules_dir = out_dir / "modules"
            modules_dir.mkdir(parents=True, exist_ok=True)
            rg_lines = [
                "targetScope = 'resourceGroup'",
                "",
                "param rgName string",
                "param rgLocation string",
                "",
            ]
            rg_lines += emit_all_blocks(
                managed_identities, self._emit_bicep_user_assigned_identity
            )
            rg_lines += emit_all_blocks(
                role_definitions, self._emit_bicep_custom_role_definition
            )
            rg_lines += emit_all_blocks(
                role_assignments, self._emit_bicep_role_assignment
            )
            for resource in regular_resources:
                rg_lines.extend(self._emit_resource_block(resource, in_module=True))
            rg_lines.append("output resourceGroupId string = resourceGroup().id")
            rg_bicep = "\n".join(rg_lines)
            rg_path = modules_dir / "rg.bicep"
            with open(rg_path, "w") as f:
                f.write(rg_bicep)
            paths.append(rg_path)
        else:
            # Flat main.bicep
            bicep_lines = ["// Generated Bicep template", ""]
            bicep_lines += emit_all_blocks(
                managed_identities, self._emit_bicep_user_assigned_identity
            )
            bicep_lines += emit_all_blocks(
                role_definitions, self._emit_bicep_custom_role_definition
            )
            bicep_lines += emit_all_blocks(
                role_assignments, self._emit_bicep_role_assignment
            )
            for resource in regular_resources:
                bicep_lines.extend(self._emit_resource_block(resource))
            output_file = out_dir / "main.bicep"
            with open(output_file, "w") as f:
                f.write("\n".join(bicep_lines))
            paths.append(output_file)

        # Generate deployment script
        deploy_script = self._generate_deployment_script(out_dir, rg_name, rg_location)
        script_path = out_dir / "deploy.sh"
        with open(script_path, "w") as f:
            f.write(deploy_script)
        paths.append(script_path)

        # Make script executable
        import stat

        script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
        # --- Emit aad_objects.json listing referenced AAD principals ---
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
        aad_data = {
            "users": aad_users,
            "groups": aad_groups,
            "service_principals": aad_sps,
        }
        aad_file = out_dir / "aad_objects.json"
        with open(aad_file, "w") as f:
            json.dump(aad_data, f, indent=2)
        paths.append(aad_file)

        return paths

    def _emit_bicep_user_assigned_identity(self, mi: dict[str, Any]) -> List[str]:
        name = mi.get("name", "identity")
        location = mi.get("location", "eastus")
        return [
            f"resource {name}_identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {{",
            f"  name: '{name}'",
            f"  location: '{location}'",
            "  properties: {}",
            "}\n",
        ]

    def _emit_bicep_role_assignment(self, ra: dict[str, Any]) -> List[str]:
        name = ra.get("name", ra.get("id", "roleAssignment"))
        props = ra.get("properties", ra)
        return [
            f"resource {name}_ra 'Microsoft.Authorization/roleAssignments@2022-04-01' = {{",
            f"  name: '{name}'",
            "  properties: {",
            f"    roleDefinitionId: '{props.get('roleDefinitionId', '')}',",
            f"    principalId: '{props.get('principalId', '')}',",
            f"    principalType: '{props.get('principalType', '')}',",
            f"    scope: '{props.get('scope', '')}',",
            "  }",
            "}\n",
        ]

    def _emit_bicep_custom_role_definition(self, rd: dict[str, Any]) -> List[str]:
        name = rd.get("name", rd.get("id", "roleDefinition"))
        props = rd.get("properties", rd)
        permissions = props.get("permissions", [])
        assignable_scopes = props.get("assignableScopes", [])
        permissions_str = (
            "[\n"
            + "\n".join(
                [
                    f"    {{ actions: {json.dumps(p.get('actions', []))}, notActions: {json.dumps(p.get('notActions', []))} }}"
                    for p in permissions
                ]
            )
            + "\n  ]"
            if permissions
            else "[]"
        )
        assignable_scopes_str = json.dumps(assignable_scopes)
        return [
            f"resource {name}_rd 'Microsoft.Authorization/roleDefinitions@2022-04-01' = {{",
            f"  name: '{name}'",
            "  properties: {",
            f"    roleName: '{props.get('roleName', '')}',",
            f"    description: '{props.get('description', '')}',",
            f"    permissions: {permissions_str},",
            f"    assignableScopes: {assignable_scopes_str},",
            "    roleType: 'Custom',",
            "  }",
            "}\n",
        ]

    # Patch _emit_resource_block to add identity blocks
    # Removed duplicate _emit_resource_block to resolve redeclaration error

    async def emit_template(
        self, tenant_graph: TenantGraph, output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate IaC template from tenant graph (legacy method)."""
        # For now, use the main emit method and return metadata
        out_dir = Path(output_path) if output_path else Path("./bicep-output")
        paths = self.emit(tenant_graph, out_dir)
        return {
            "format": "bicep",
            "files": [str(p) for p in paths],
            "resource_count": len(tenant_graph.resources),
        }

    def _emit_subscription_wrapper(
        self, rg_name: str, rg_location: Optional[str]
    ) -> str:
        """Emit main.bicep for subscription scope, creating RG and deploying module."""
        lines = [
            "targetScope = 'subscription'",
            "",
            f"param rgName string = '{rg_name}'",
            f"param rgLocation string = '{rg_location or 'eastus'}'",
            "",
            "module rgDeploy 'modules/rg.bicep' = {",
            "  name: 'subsetModule'",
            "  scope: resourceGroup(rgName)",
            "  params: {",
            "    rgName: rgName,",
            "    rgLocation: rgLocation",
            "  }",
            "}",
            "",
            "output resourceGroupId string = rgDeploy.outputs.resourceGroupId",
        ]
        return "\n".join(lines)

    def _emit_resource_group_module(self, graph: TenantGraph) -> str:
        """Emit modules/rg.bicep for resource group scope."""
        lines = [
            "targetScope = 'resourceGroup'",
            "",
            "param rgName string",
            "param rgLocation string",
            "",
        ]
        for resource in graph.resources:
            lines.extend(self._emit_resource_block(resource, in_module=True))
        lines.append("output resourceGroupId string = resourceGroup().id")
        return "\n".join(lines)

    def _emit_resource_block(
        self, resource: dict[str, Any], in_module: bool = False
    ) -> List[str]:
        """Emit a single Bicep resource block."""
        az_type = resource.get("type", "")
        name = resource.get("name", "unnamed")
        location = resource.get("location", "eastus")
        lines = [
            f"resource {name}_res '{az_type}@2023-01-01' = {{",
            f"  name: '{name}'",
            "  location: rgLocation" if in_module else f"  location: '{location}'",
        ]
        if "tags" in resource and isinstance(resource["tags"], dict):
            tags = resource["tags"]
            tag_str = ", ".join(f"{k}: '{v}'" for k, v in tags.items())
            lines.append(f"  tags: {{ {tag_str} }}")
        # Identity block handling
        identity = resource.get("identity")
        if identity and isinstance(identity, dict):
            lines.append("  identity: {")
            if identity.get("type"):
                lines.append(f"    type: '{identity['type']}'")
            if identity.get("userAssignedIdentities"):
                lines.append("    userAssignedIdentities: {")
                for k in identity["userAssignedIdentities"]:
                    lines.append(f"      '{k}': {{}}")
                lines.append("    }")
            lines.append("  }")
        if resource.get("systemAssignedIdentity", False):
            lines.append("  identity: { type: 'SystemAssigned' }")
        lines.append("  properties: {}")
        lines.append("}\n")
        return lines

    def get_supported_resource_types(self) -> List[str]:
        return [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Storage/storageAccounts",
            "Microsoft.Network/virtualNetworks",
            "Microsoft.Web/sites",
            "Microsoft.Sql/servers",
            "Microsoft.KeyVault/vaults",
        ]

    def _generate_deployment_script(
        self, out_dir: Path, rg_name: Optional[str], rg_location: Optional[str]
    ) -> str:
        """Generate a deployment script for the Bicep templates."""
        if rg_name and rg_location:
            # Module pattern deployment
            lines = [
                "#!/bin/bash",
                "# Azure Bicep Deployment Script",
                "# Generated by Azure Tenant Grapher",
                "",
                "set -e  # Exit on any error",
                "",
                "echo '🚀 Starting Azure Bicep deployment...'",
                "",
                "# Check if Azure CLI is installed",
                "if ! command -v az &> /dev/null; then",
                "    echo '❌ Azure CLI is not installed. Please install it first.'",
                "    echo 'Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli'",
                "    exit 1",
                "fi",
                "",
                "# Check if user is logged in",
                "if ! az account show &> /dev/null; then",
                "    echo '❌ Please log in to Azure CLI first:'",
                "    echo 'az login'",
                "    exit 1",
                "fi",
                "",
                "# Variables",
                f"RESOURCE_GROUP='{rg_name}'",
                f"LOCATION='{rg_location}'",
                "DEPLOYMENT_NAME='tenant-grapher-deployment'",
                "",
                "echo '📋 Deployment Details:'",
                'echo "  Resource Group: $RESOURCE_GROUP"',
                'echo "  Location: $LOCATION"',
                'echo "  Deployment Name: $DEPLOYMENT_NAME"',
                "echo",
                "",
                "# Create resource group if it doesn't exist",
                "echo '🏗️ Creating resource group if needed...'",
                'az group create --name "$RESOURCE_GROUP" --location "$LOCATION"',
                "",
                "# Deploy the main template",
                "echo '🚀 Deploying Bicep template...'",
                "az deployment group create \\",
                '    --resource-group "$RESOURCE_GROUP" \\',
                "    --template-file main.bicep \\",
                '    --name "$DEPLOYMENT_NAME" \\',
                '    --parameters rgName="$RESOURCE_GROUP" rgLocation="$LOCATION"',
                "",
                "echo '✅ Deployment completed successfully!'",
                "echo '📊 You can check the deployment status in the Azure portal.'",
                "",
                "# Optional: Show deployment outputs",
                "echo '📋 Deployment outputs:'",
                "az deployment group show \\",
                '    --resource-group "$RESOURCE_GROUP" \\',
                '    --name "$DEPLOYMENT_NAME" \\',
                "    --query properties.outputs",
            ]
        else:
            # Flat deployment
            lines = [
                "#!/bin/bash",
                "# Azure Bicep Deployment Script",
                "# Generated by Azure Tenant Grapher",
                "",
                "set -e  # Exit on any error",
                "",
                "echo '🚀 Starting Azure Bicep deployment...'",
                "",
                "# Check if Azure CLI is installed",
                "if ! command -v az &> /dev/null; then",
                "    echo '❌ Azure CLI is not installed. Please install it first.'",
                "    echo 'Visit: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli'",
                "    exit 1",
                "fi",
                "",
                "# Check if user is logged in",
                "if ! az account show &> /dev/null; then",
                "    echo '❌ Please log in to Azure CLI first:'",
                "    echo 'az login'",
                "    exit 1",
                "fi",
                "",
                "# Prompt for resource group and location",
                "read -p 'Enter resource group name: ' RESOURCE_GROUP",
                "read -p 'Enter location (e.g., eastus): ' LOCATION",
                "",
                "DEPLOYMENT_NAME='tenant-grapher-deployment'",
                "",
                "echo '📋 Deployment Details:'",
                'echo "  Resource Group: $RESOURCE_GROUP"',
                'echo "  Location: $LOCATION"',
                'echo "  Deployment Name: $DEPLOYMENT_NAME"',
                "echo",
                "",
                "# Create resource group if it doesn't exist",
                "echo '🏗️ Creating resource group if needed...'",
                'az group create --name "$RESOURCE_GROUP" --location "$LOCATION"',
                "",
                "# Deploy the main template",
                "echo '🚀 Deploying Bicep template...'",
                "az deployment group create \\",
                '    --resource-group "$RESOURCE_GROUP" \\',
                "    --template-file main.bicep \\",
                '    --name "$DEPLOYMENT_NAME"',
                "",
                "echo '✅ Deployment completed successfully!'",
                "echo '📊 You can check the deployment status in the Azure portal.'",
            ]

        return "\n".join(lines)

    def validate_template(self, template_data: Dict[str, Any]) -> bool:
        """Validate the Bicep template structure."""
        # Basic validation for Bicep templates
        required_fields = ["targetScope", "metadata", "resources"]
        
        for field in required_fields:
            if field not in template_data:
                self.logger.error(f"Missing required field in Bicep template: {field}")
                return False
        
        # Validate resources structure
        if not isinstance(template_data.get("resources"), list):
            self.logger.error("Resources must be a list in Bicep template")
            return False
        
        # Validate each resource has required fields
        for idx, resource in enumerate(template_data.get("resources", [])):
            if not isinstance(resource, dict):
                self.logger.error(f"Resource {idx} is not a dictionary")
                return False
            
            if "type" not in resource or "name" not in resource:
                self.logger.error(f"Resource {idx} missing required 'type' or 'name' field")
                return False
        
        return True


register_emitter("bicep", BicepEmitter)
