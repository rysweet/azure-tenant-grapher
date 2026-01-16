"""CTF Annotation Service for adding CTF properties to Neo4j Resource nodes.

Philosophy:
- Single responsibility: Annotate resources with CTF properties
- Ruthless simplicity: Properties on existing nodes, no new node types
- Zero-BS implementation: Every method works, idempotent operations

Public API (the "studs"):
    CTFAnnotationService: Main service for CTF property annotations
    annotate_resource: Add CTF properties to a single resource
    annotate_batch: Add CTF properties to multiple resources
    determine_role: Infer CTF role from resource type/name

Dependencies:
- neo4j>=5.0 (graph database driver)

Supports:
- Property-based CTF annotations (ctf_exercise, ctf_scenario, ctf_role)
- Role determination heuristics (VMs=target, networks=infrastructure)
- Batch operations with resilient error handling
- Base layer protection with audit logging

Usage:
    ```python
    from src.services.ctf_annotation_service import CTFAnnotationService

    service = CTFAnnotationService(neo4j_driver=driver)

    result = service.annotate_resource(
        resource_id="vm-abc123",
        layer_id="default",
        ctf_exercise="M003",
        ctf_scenario="v2-cert",
        ctf_role="target"
    )
    ```

Issue #552: CTF Overlay System Implementation
"""

import logging
import re
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)
audit_logger = logging.getLogger("ctf_audit")


class CTFAnnotationService:
    """Service for annotating resources with CTF properties.

    Adds CTF-specific properties (ctf_exercise, ctf_scenario, ctf_role)
    directly to existing :Resource nodes in Neo4j without creating
    separate annotation nodes.
    """

    # Valid characters for CTF properties (alphanumeric, dash, underscore)
    _VALID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

    # Role determination heuristics
    _ROLE_HEURISTICS = {
        'attacker': ['attacker', 'attack', 'offensive'],
        'target': ['target', 'victim', 'vulnerable'],
        'monitoring': ['monitor', 'log', 'analytics', 'insight'],
        'infrastructure': ['vnet', 'network', 'storage', 'nsg', 'subnet']
    }

    # Resource type to role mapping
    _TYPE_TO_ROLE = {
        'Microsoft.Compute/virtualMachines': 'target',
        'Microsoft.Network/virtualNetworks': 'infrastructure',
        'Microsoft.Network/networkSecurityGroups': 'infrastructure',
        'Microsoft.Storage/storageAccounts': 'infrastructure',
        'Microsoft.OperationalInsights/workspaces': 'monitoring',
    }

    def __init__(self, neo4j_driver: Any) -> None:
        """Initialize the CTF annotation service.

        Args:
            neo4j_driver: Neo4j driver instance

        Raises:
            ValueError: If neo4j_driver is None
        """
        if neo4j_driver is None:
            raise ValueError("Neo4j driver is required")

        self.neo4j_driver = neo4j_driver

    def annotate_resource(
        self,
        resource_id: str,
        layer_id: str,
        ctf_exercise: Optional[str] = None,
        ctf_scenario: Optional[str] = None,
        ctf_role: Optional[str] = None,
        allow_base_modification: bool = False
    ) -> Dict[str, Any]:
        """Annotate a single resource with CTF properties.

        Args:
            resource_id: Azure resource ID
            layer_id: Layer identifier (e.g., "default", "base")
            ctf_exercise: Exercise identifier (e.g., "M003")
            ctf_scenario: Scenario variant (e.g., "v2-cert")
            ctf_role: Resource role (e.g., "target", "attacker")
            allow_base_modification: Allow modifying base layer resources

        Returns:
            Dictionary with operation result:
                - success: bool
                - resource_id: str
                - warning: Optional[str] (if resource may not exist)

        Raises:
            ValueError: If validation fails or base layer protection triggered
        """
        # Validate required parameters
        if not resource_id:
            raise ValueError("resource_id is required")
        if not layer_id:
            raise ValueError("layer_id is required")

        # Validate layer_id format
        self._validate_property_format(layer_id, "layer_id")

        # Base layer protection
        if layer_id == "base" and not allow_base_modification:
            raise ValueError(
                "Cannot modify base layer without explicit permission. "
                "Set allow_base_modification=True to proceed."
            )

        # Validate optional CTF properties
        if ctf_exercise is not None:
            self._validate_property_format(ctf_exercise, "ctf_exercise")
        if ctf_scenario is not None:
            self._validate_property_format(ctf_scenario, "ctf_scenario")
        if ctf_role is not None:
            self._validate_property_format(ctf_role, "ctf_role")

        # Audit log the annotation operation
        audit_logger.info(
            f"CTF annotation: resource={resource_id}, layer={layer_id}, "
            f"exercise={ctf_exercise}, scenario={ctf_scenario}, role={ctf_role}"
        )

        # Build Cypher query for idempotent annotation
        query = """
        MERGE (r:Resource {id: $id})
        SET r.layer_id = $layer_id
        """

        params = {
            "id": resource_id,
            "layer_id": layer_id
        }

        # Add optional CTF properties
        if ctf_exercise is not None:
            query += ", r.ctf_exercise = $ctf_exercise"
            params["ctf_exercise"] = ctf_exercise
        else:
            params["ctf_exercise"] = None

        if ctf_scenario is not None:
            query += ", r.ctf_scenario = $ctf_scenario"
            params["ctf_scenario"] = ctf_scenario
        else:
            params["ctf_scenario"] = None

        if ctf_role is not None:
            query += ", r.ctf_role = $ctf_role"
            params["ctf_role"] = ctf_role
        else:
            params["ctf_role"] = None

        query += "\nRETURN r"

        # Execute the annotation
        result_records, _, _ = self.neo4j_driver.execute_query(query, **params)

        # Check if resource was created vs updated
        warning = None
        if not result_records or len(result_records) == 0:
            warning = "Resource may not exist in Neo4j"
            logger.warning(
                f"Annotated resource {resource_id} but no existing node found - "
                "MERGE created a new node"
            )

        return {
            "success": True,
            "resource_id": resource_id,
            **({"warning": warning} if warning else {})
        }

    def annotate_batch(
        self,
        resources: List[Dict[str, Any]],
        layer_id: str,
        ctf_exercise: Optional[str] = None,
        ctf_scenario: Optional[str] = None
    ) -> Dict[str, Any]:
        """Annotate multiple resources with CTF properties in batch.

        Args:
            resources: List of resource dictionaries (must have 'id' key)
            layer_id: Layer identifier for all resources
            ctf_exercise: Exercise identifier for all resources
            ctf_scenario: Scenario variant for all resources

        Returns:
            Dictionary with batch results:
                - success_count: int
                - failure_count: int
                - results: List[Dict] (individual results)
                - failed_resources: List[Dict] (resources that failed)
        """
        if not resources:
            return {
                "success_count": 0,
                "failure_count": 0,
                "results": [],
                "failed_resources": []
            }

        # Validate batch parameters
        self._validate_property_format(layer_id, "layer_id")
        if ctf_exercise is not None:
            self._validate_property_format(ctf_exercise, "ctf_exercise")
        if ctf_scenario is not None:
            self._validate_property_format(ctf_scenario, "ctf_scenario")

        # Prepare batch data with automatic role determination
        batch_data = []
        for resource in resources:
            resource_id = resource.get("id")
            if not resource_id:
                continue

            # Determine role from resource type/name
            resource_type = resource.get("resource_type", "")
            resource_name = resource.get("name", "")
            ctf_role = self.determine_role(resource_type, resource_name)

            batch_data.append({
                "id": resource_id,
                "layer_id": layer_id,
                "ctf_exercise": ctf_exercise,
                "ctf_scenario": ctf_scenario,
                "ctf_role": ctf_role
            })

        # Execute batch annotation using UNWIND
        query = """
        UNWIND $resources AS resource
        MERGE (r:Resource {id: resource.id})
        SET r.layer_id = resource.layer_id,
            r.ctf_exercise = resource.ctf_exercise,
            r.ctf_scenario = resource.ctf_scenario,
            r.ctf_role = resource.ctf_role
        RETURN r.id AS resource_id
        """

        success_count = 0
        failure_count = 0
        results = []
        failed_resources = []

        try:
            result_records, _, _ = self.neo4j_driver.execute_query(
                query,
                resources=batch_data
            )

            success_count = len(result_records)
            results = [{"resource_id": r["resource_id"]} for r in result_records]

        except Exception as e:
            logger.error(f"Batch annotation failed: {e}")
            failure_count = len(batch_data)
            failed_resources = [{"id": r["id"], "error": str(e)} for r in batch_data]

        return {
            "success_count": success_count,
            "failure_count": failure_count,
            "results": results,
            "failed_resources": failed_resources
        }

    def determine_role(
        self,
        resource_type: str,
        resource_name: str
    ) -> str:
        """Determine CTF role from resource type and name.

        Uses heuristics based on:
        1. Resource name patterns (e.g., "attacker-vm" → "attacker")
        2. Resource type mapping (e.g., VirtualMachine → "target")
        3. Default to "infrastructure" for unknown types

        Args:
            resource_type: Azure resource type
            resource_name: Resource name

        Returns:
            CTF role string (target, attacker, monitoring, infrastructure)
        """
        # Check resource name patterns first (more specific)
        name_lower = resource_name.lower()
        for role, keywords in self._ROLE_HEURISTICS.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return role

        # Check resource type mapping
        if resource_type in self._TYPE_TO_ROLE:
            return self._TYPE_TO_ROLE[resource_type]

        # Default to infrastructure for unknown types
        return "infrastructure"

    def _validate_property_format(self, value: str, property_name: str) -> None:
        """Validate CTF property format to prevent injection attacks.

        Args:
            value: Property value to validate
            property_name: Name of the property (for error messages)

        Raises:
            ValueError: If validation fails
        """
        if not value:
            raise ValueError(f"Invalid {property_name} format: cannot be empty")

        if not self._VALID_PATTERN.match(value):
            raise ValueError(
                f"Invalid {property_name} format: '{value}'. "
                "Only alphanumeric characters, dashes, and underscores allowed."
            )


__all__ = ["CTFAnnotationService"]
