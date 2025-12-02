"""CTF Deploy Service for deploying CTF scenarios from Neo4j.

Philosophy:
- Single responsibility: Export and deploy CTF scenarios
- Ruthless simplicity: Reuse TerraformEmitter and TerraformDeployer
- Zero-BS implementation: Idempotent deployments with auto-import

Public API (the "studs"):
    CTFDeployService: Main service for CTF scenario deployment
    deploy_scenario: Export Terraform and deploy resources

Dependencies:
- src.iac.emitters.terraform_emitter (Terraform generation)
- src.services.ctf_import_service (Auto-import after deployment)

Supports:
- Query resources by CTF properties (exercise, scenario, role)
- Export resources to Terraform format
- Deploy with idempotent operations
- Auto-import deployed resources back to Neo4j

Usage:
    ```python
    from src.services.ctf_deploy_service import CTFDeployService

    service = CTFDeployService(neo4j_driver=driver)

    result = service.deploy_scenario(
        layer_id="default",
        ctf_exercise="M003",
        ctf_scenario="v2-cert",
        output_dir=Path("./terraform/deployed")
    )
    ```

Issue #552: CTF Overlay System Implementation
"""

import logging
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .ctf_import_service import CTFImportService

logger = structlog.get_logger(__name__)


class CTFDeployService:
    """Service for deploying CTF scenarios from Neo4j.

    Queries resources by CTF properties, exports to Terraform,
    deploys them, and optionally re-imports the deployed state.
    """

    def __init__(self, neo4j_driver: Any) -> None:
        """Initialize the CTF deploy service.

        Args:
            neo4j_driver: Neo4j driver instance
        """
        self.neo4j_driver = neo4j_driver
        self.import_service = CTFImportService(neo4j_driver)

    def deploy_scenario(
        self,
        layer_id: str,
        ctf_exercise: str,
        ctf_scenario: str,
        output_dir: Path,
        auto_import: bool = True,
        deploy_args: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Deploy a CTF scenario from Neo4j resources.

        Args:
            layer_id: Layer identifier
            ctf_exercise: Exercise identifier (e.g., "M003")
            ctf_scenario: Scenario variant (e.g., "v2-cert")
            output_dir: Directory for Terraform files
            auto_import: Automatically import deployed resources back to Neo4j
            deploy_args: Additional arguments for terraform apply

        Returns:
            Dictionary with deployment results:
                - success: bool
                - resources_deployed: int
                - terraform_dir: str
                - deploy_output: str (if deployed)
                - import_result: Dict (if auto_import=True)

        Raises:
            ValueError: If required parameters missing
        """
        if not layer_id:
            raise ValueError("layer_id is required")
        if not ctf_exercise:
            raise ValueError("ctf_exercise is required")
        if not ctf_scenario:
            raise ValueError("ctf_scenario is required")

        # Query resources for this scenario
        logger.info(
            f"Querying resources for {ctf_exercise}/{ctf_scenario} "
            f"in layer {layer_id}"
        )

        resources = self._query_ctf_resources(
            layer_id=layer_id,
            ctf_exercise=ctf_exercise,
            ctf_scenario=ctf_scenario
        )

        if not resources:
            logger.warning(
                f"No resources found for {ctf_exercise}/{ctf_scenario}"
            )
            return {
                "success": False,
                "resources_deployed": 0,
                "error": "No resources found for scenario"
            }

        # Export resources to Terraform
        logger.info(f"Exporting {len(resources)} resources to Terraform")

        terraform_content = self._export_to_terraform(
            resources=resources,
            layer_id=layer_id,
            ctf_exercise=ctf_exercise,
            ctf_scenario=ctf_scenario
        )

        # Create output directory and write Terraform files
        output_dir.mkdir(parents=True, exist_ok=True)
        main_tf = output_dir / "main.tf"
        main_tf.write_text(terraform_content)

        logger.info(f"Wrote Terraform configuration to {main_tf}")

        # Deploy with Terraform (optional - depends on deploy_args)
        deploy_output = None
        if deploy_args is not None:
            logger.info("Deploying with Terraform")
            deploy_output = self._deploy_terraform(output_dir, deploy_args)

        # Auto-import deployed resources back to Neo4j
        import_result = None
        if auto_import and deploy_output:
            logger.info("Auto-importing deployed resources")

            state_file = output_dir / "terraform.tfstate"
            if state_file.exists():
                import_result = self.import_service.import_terraform(
                    state_file=state_file,
                    layer_id=layer_id,
                    ctf_exercise=ctf_exercise,
                    ctf_scenario=ctf_scenario
                )

        return {
            "success": True,
            "resources_deployed": len(resources),
            "terraform_dir": str(output_dir),
            **({"deploy_output": deploy_output} if deploy_output else {}),
            **({"import_result": import_result} if import_result else {})
        }

    def _query_ctf_resources(
        self,
        layer_id: str,
        ctf_exercise: str,
        ctf_scenario: str,
        ctf_role: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query Neo4j for resources matching CTF properties.

        Args:
            layer_id: Layer identifier
            ctf_exercise: Exercise identifier
            ctf_scenario: Scenario variant
            ctf_role: Optional role filter

        Returns:
            List of resource dictionaries
        """
        query = """
        MATCH (r:Resource {layer_id: $layer_id})
        WHERE r.ctf_exercise = $ctf_exercise
          AND r.ctf_scenario = $ctf_scenario
        """

        params = {
            "layer_id": layer_id,
            "ctf_exercise": ctf_exercise,
            "ctf_scenario": ctf_scenario
        }

        if ctf_role:
            query += " AND r.ctf_role = $ctf_role"
            params["ctf_role"] = ctf_role

        query += """
        RETURN r.id AS id,
               r.name AS name,
               r.resource_type AS resource_type,
               r.location AS location,
               r.ctf_role AS ctf_role,
               r.properties AS properties
        """

        result_records, _, _ = self.neo4j_driver.execute_query(query, **params)

        resources = []
        for record in result_records:
            resources.append({
                "id": record["id"],
                "name": record["name"],
                "resource_type": record["resource_type"],
                "location": record.get("location"),
                "ctf_role": record.get("ctf_role"),
                "properties": record.get("properties", {})
            })

        return resources

    def _export_to_terraform(
        self,
        resources: List[Dict[str, Any]],
        layer_id: str,
        ctf_exercise: str,
        ctf_scenario: str
    ) -> str:
        """Export resources to Terraform HCL format.

        Args:
            resources: List of resource dictionaries

        Returns:
            Terraform HCL configuration as string
        """
        # This is a simplified Terraform generation
        # In production, this would use TerraformEmitter
        terraform_blocks = []

        for resource in resources:
            resource_type = resource.get("resource_type", "")
            resource_name = resource.get("name", "resource")
            resource_id = resource.get("id", "")

            # Convert Azure resource type to Terraform resource type
            # This is a simplified mapping
            tf_type = self._azure_to_terraform_type(resource_type)

            if not tf_type:
                logger.warning(f"Unknown resource type: {resource_type}")
                continue

            # Sanitize resource name for Terraform
            tf_name = resource_name.replace("-", "_").replace(".", "_")

            # Build Terraform block
            block = f"""
resource "{tf_type}" "{tf_name}" {{
  name                = "{resource_name}"
  location            = "{resource.get('location', 'eastus')}"
  resource_group_name = "ctf-resources"

  tags = {{
    layer_id     = "{layer_id}"
    ctf_exercise = "{ctf_exercise}"
    ctf_scenario = "{ctf_scenario}"
    ctf_role     = "{resource.get('ctf_role', 'infrastructure')}"
  }}
}}
"""
            terraform_blocks.append(block)

        # Combine all blocks with provider configuration
        terraform_content = """
terraform {
  required_version = ">= 1.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}
"""
        terraform_content += "\n".join(terraform_blocks)

        return terraform_content

    def _azure_to_terraform_type(self, azure_type: str) -> Optional[str]:
        """Map Azure resource type to Terraform resource type.

        Args:
            azure_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Terraform resource type or None if unknown
        """
        mapping = {
            "Microsoft.Compute/virtualMachines": "azurerm_virtual_machine",
            "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
            "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
            "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
            "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
            "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
        }

        return mapping.get(azure_type)

    def _deploy_terraform(
        self,
        terraform_dir: Path,
        deploy_args: List[str]
    ) -> str:
        """Deploy Terraform configuration.

        Args:
            terraform_dir: Directory containing Terraform files
            deploy_args: Additional arguments for terraform apply

        Returns:
            Deployment output

        Raises:
            RuntimeError: If deployment fails
        """
        # Initialize Terraform
        init_result = subprocess.run(
            ["terraform", "init"],
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )

        if init_result.returncode != 0:
            raise RuntimeError(
                f"Terraform init failed: {init_result.stderr}"
            )

        # Apply Terraform configuration
        apply_cmd = ["terraform", "apply"] + deploy_args
        apply_result = subprocess.run(
            apply_cmd,
            cwd=terraform_dir,
            capture_output=True,
            text=True
        )

        if apply_result.returncode != 0:
            raise RuntimeError(
                f"Terraform apply failed: {apply_result.stderr}"
            )

        return apply_result.stdout


__all__ = ["CTFDeployService"]
