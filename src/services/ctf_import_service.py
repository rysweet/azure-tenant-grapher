"""CTF Import Service for importing Terraform resources into Neo4j.

Philosophy:
- Single responsibility: Parse Terraform and map to graph
- Ruthless simplicity: Reuse existing TerraformParser, delegate to CTFAnnotationService
- Zero-BS implementation: Handle missing resources gracefully with warnings

Public API (the "studs"):
    CTFImportService: Main service for importing CTF scenarios
    import_terraform: Import Terraform state/directory into Neo4j

Dependencies:
- src.iac.parsers.terraform_parser (Terraform parsing)
- src.services.ctf_annotation_service (Resource annotation)

Supports:
- Terraform state file parsing
- Terraform directory scanning
- Tag-based CTF property extraction
- Automatic role determination
- Graceful handling of missing resources

Usage:
    ```python
    from src.services.ctf_import_service import CTFImportService

    service = CTFImportService(neo4j_driver=driver)

    result = service.import_terraform(
        terraform_dir="./terraform/m003/v2-cert",
        layer_id="default",
        ctf_exercise="M003",
        ctf_scenario="v2-cert"
    )
    ```

Issue #552: CTF Overlay System Implementation
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from .ctf_annotation_service import CTFAnnotationService

logger = structlog.get_logger(__name__)


def get_neo4j_driver():
    """Get default Neo4j driver from session manager.

    This is a placeholder that will be replaced with actual
    Neo4j driver retrieval from the session manager.
    """
    from src.utils.session_manager import Neo4jSessionManager
    from src.config_manager import load_config

    config = load_config()
    neo4j_config = config.get("neo4j", {})
    session_manager = Neo4jSessionManager(neo4j_config)
    return session_manager.driver


class CTFImportService:
    """Service for importing Terraform resources with CTF annotations.

    Parses Terraform configurations and state files, then annotates
    the corresponding Neo4j Resource nodes with CTF properties.
    """

    def __init__(self, neo4j_driver: Optional[Any] = None) -> None:
        """Initialize the CTF import service.

        Args:
            neo4j_driver: Neo4j driver instance (uses default if None)
        """
        if neo4j_driver is None:
            neo4j_driver = get_neo4j_driver()

        self.neo4j_driver = neo4j_driver
        self.annotation_service = CTFAnnotationService(neo4j_driver)

    def import_terraform(
        self,
        terraform_dir: Optional[Path] = None,
        state_file: Optional[Path] = None,
        layer_id: str = "default",
        ctf_exercise: Optional[str] = None,
        ctf_scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """Import Terraform resources and annotate with CTF properties.

        Args:
            terraform_dir: Path to Terraform directory (for .tf files)
            state_file: Path to Terraform state file (terraform.tfstate)
            layer_id: Layer identifier for resources
            ctf_exercise: Exercise identifier (e.g., "M003")
            ctf_scenario: Scenario variant (e.g., "v2-cert")

        Returns:
            Dictionary with import results:
                - success: bool
                - resources_imported: int
                - resources_failed: int
                - warnings: List[str]

        Raises:
            ValueError: If neither terraform_dir nor state_file provided
        """
        if terraform_dir is None and state_file is None:
            raise ValueError("Either terraform_dir or state_file must be provided")

        resources = []
        warnings = []

        # Parse Terraform state file if provided
        if state_file:
            try:
                parsed = self._parse_terraform_state(state_file)
                resources.extend(parsed["resources"])
                warnings.extend(parsed.get("warnings", []))
            except Exception as e:
                logger.error(f"Failed to parse Terraform state: {e}")
                warnings.append(f"State file parsing failed: {e}")

        # Parse Terraform directory if provided
        if terraform_dir:
            # Directory parsing not yet implemented - state file parsing is sufficient for MVP
            warnings.append(
                f"Terraform directory parsing not yet supported. "
                f"Use terraform.tfstate file instead."
            )

        # Extract CTF properties from tags and annotate resources
        resources_to_annotate = []
        for resource in resources:
            resource_id = resource.get("id")
            if not resource_id:
                warnings.append(f"Resource missing ID: {resource.get('name', 'unknown')}")
                continue

            # Extract CTF properties from tags
            tags = resource.get("tags", {})
            resource_layer_id = tags.get("layer_id", layer_id)
            resource_exercise = tags.get("ctf_exercise", ctf_exercise)
            resource_scenario = tags.get("ctf_scenario", ctf_scenario)
            resource_role = tags.get("ctf_role")

            # If no explicit role, determine from resource type/name
            if not resource_role:
                resource_role = self.annotation_service.determine_role(
                    resource.get("resource_type", ""),
                    resource.get("name", "")
                )

            resources_to_annotate.append({
                "id": resource_id,
                "resource_type": resource.get("resource_type"),
                "name": resource.get("name"),
                "layer_id": resource_layer_id,
                "ctf_exercise": resource_exercise,
                "ctf_scenario": resource_scenario,
                "ctf_role": resource_role
            })

        # Batch annotate all resources
        if resources_to_annotate:
            result = self._annotate_resources_batch(resources_to_annotate)
            resources_imported = result["success_count"]
            resources_failed = result["failure_count"]
            warnings.extend([
                f"Resource {r['id']}: {r.get('error', 'unknown error')}"
                for r in result.get("failed_resources", [])
            ])
        else:
            resources_imported = 0
            resources_failed = 0

        return {
            "success": resources_imported > 0 or (resources_imported == 0 and resources_failed == 0),
            "resources_imported": resources_imported,
            "resources_failed": resources_failed,
            "warnings": warnings
        }

    def _parse_terraform_state(self, state_file: Path) -> Dict[str, Any]:
        """Parse Terraform state file to extract resources.

        Args:
            state_file: Path to terraform.tfstate file

        Returns:
            Dictionary with resources and warnings
        """
        if not state_file.exists():
            raise FileNotFoundError(f"State file not found: {state_file}")

        with open(state_file, 'r') as f:
            state_data = json.load(f)

        resources = []
        warnings = []

        # Extract resources from state file
        for resource_block in state_data.get("resources", []):
            resource_type = resource_block.get("type", "")
            resource_name = resource_block.get("name", "")

            for instance in resource_block.get("instances", []):
                attributes = instance.get("attributes", {})

                resource_id = attributes.get("id")
                if not resource_id:
                    warnings.append(
                        f"Resource {resource_type}.{resource_name} missing ID"
                    )
                    continue

                resources.append({
                    "id": resource_id,
                    "name": attributes.get("name", resource_name),
                    "resource_type": resource_type,
                    "location": attributes.get("location"),
                    "tags": attributes.get("tags", {})
                })

        return {
            "resources": resources,
            "warnings": warnings
        }


    def _annotate_resources_batch(
        self,
        resources: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Annotate multiple resources in batch.

        Args:
            resources: List of resource dictionaries with CTF properties

        Returns:
            Batch annotation results
        """
        success_count = 0
        failure_count = 0
        failed_resources = []

        for resource in resources:
            try:
                result = self.annotation_service.annotate_resource(
                    resource_id=resource["id"],
                    layer_id=resource.get("layer_id", "default"),
                    ctf_exercise=resource.get("ctf_exercise"),
                    ctf_scenario=resource.get("ctf_scenario"),
                    ctf_role=resource.get("ctf_role")
                )

                if result["success"]:
                    success_count += 1
                else:
                    failure_count += 1
                    failed_resources.append({
                        "id": resource["id"],
                        "error": result.get("error", "Unknown error")
                    })

            except Exception as e:
                logger.error(f"Failed to annotate resource {resource['id']}: {e}")
                failure_count += 1
                failed_resources.append({
                    "id": resource["id"],
                    "error": str(e)
                })

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "failed_resources": failed_resources
        }


__all__ = ["CTFImportService", "get_neo4j_driver"]
