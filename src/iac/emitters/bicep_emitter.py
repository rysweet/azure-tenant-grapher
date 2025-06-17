"""Bicep emitter for Infrastructure-as-Code generation.

This module provides Azure Bicep template generation from
tenant graph data, supporting resource group homing and module pattern.
"""

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
        out_dir,
        rg_name: Optional[str] = None,
        rg_location: Optional[str] = None,
    ) -> List[Path]:
        """
        Generate Bicep templates from tenant graph, using module pattern if RG is specified.

        Args:
            graph: Input tenant graph data
            out_dir: Output directory path
            rg_name: Name of the resource group to home resources in (optional)
            rg_location: Location for the resource group (optional)

        Returns:
            List of written file paths
        """
        out_dir = Path(out_dir)  # Convert string to Path if needed
        out_dir.mkdir(parents=True, exist_ok=True)
        paths = []

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
            rg_bicep = self._emit_resource_group_module(graph)
            rg_path = modules_dir / "rg.bicep"
            with open(rg_path, "w") as f:
                f.write(rg_bicep)
            paths.append(rg_path)
        else:
            # Fallback: flat main.bicep
            bicep_lines = ["// Generated Bicep template", ""]
            for resource in graph.resources:
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

        return paths

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
        self, resource: dict, in_module: bool = False
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
        raise NotImplementedError("Bicep template validation not yet implemented")


register_emitter("bicep", BicepEmitter)
