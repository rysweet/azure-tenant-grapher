"""
Azure Threat Analysis Runner module.
Replaces TMT with custom threat analysis using Neo4j graph data and STRIDE methodology.
"""

import logging
from typing import Any, Dict, List, Optional

from .threat_enumerator import enumerate_threats


class AzureThreatAnalysisRunner:
    """
    Custom threat analysis runner for Azure resources.
    Replaces Microsoft Threat Modeling Tool (TMT) with STRIDE-based analysis.
    """

    def __init__(self, neo4j_session_manager: Optional[Any] = None):
        """
        Initialize the threat analysis runner.

        Args:
            neo4j_session_manager: Optional Neo4j session manager to query graph data
        """
        self.session_manager = neo4j_session_manager
        self.logger = logging.getLogger("AzureThreatAnalysisRunner")

    def analyze_from_graph(
        self, logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze threats by querying Azure resources from Neo4j graph database.

        Args:
            logger: Optional logger for error reporting

        Returns:
            List of threat dictionaries
        """
        if logger is None:
            logger = self.logger

        if not self.session_manager:
            logger.warning(
                "No Neo4j session manager provided, cannot analyze from graph"
            )
            return []

        try:
            # Query all Azure resources from the graph
            query = """
            MATCH (r:Resource)
            RETURN r.id as id, r.name as name, r.type as type, r.location as location,
                   r.resourceGroup as resourceGroup, r.subscriptionId as subscriptionId,
                   r.properties as properties, r.tags as tags
            """

            resources = []
            with self.session_manager.get_session() as session:
                result = session.run(query)
                for record in result:
                    resource = {
                        "id": record.get("id"),
                        "name": record.get("name"),
                        "type": record.get("type"),
                        "location": record.get("location"),
                        "resourceGroup": record.get("resourceGroup"),
                        "subscriptionId": record.get("subscriptionId"),
                        "properties": record.get("properties", {}),
                        "tags": record.get("tags", {}),
                    }
                    resources.append(resource)

            logger.info(f"Retrieved {len(resources)} resources from Neo4j graph")

            # Enumerate threats for the retrieved resources
            threats = enumerate_threats(resources, logger)
            logger.info(f"Generated {len(threats)} threats from graph analysis")

            return threats

        except Exception as e:
            logger.error(f"Failed to analyze threats from graph: {e}")
            return []

    def analyze_from_resources(
        self, resources: List[Dict[str, Any]], logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze threats for a specific list of Azure resources.

        Args:
            resources: List of Azure resource dictionaries
            logger: Optional logger for error reporting

        Returns:
            List of threat dictionaries
        """
        if logger is None:
            logger = self.logger

        try:
            logger.info(f"Analyzing threats for {len(resources)} provided resources")
            threats = enumerate_threats(resources, logger)
            logger.info(f"Generated {len(threats)} threats from resource analysis")
            return threats

        except Exception as e:
            logger.error(f"Failed to analyze threats from resources: {e}")
            return []

    def analyze_from_dfd_specification(
        self, dfd_spec: str, logger: Optional[logging.Logger] = None
    ) -> List[Dict[str, Any]]:
        """
        Analyze threats from a Data Flow Diagram specification.
        This method parses DFD components and generates threats for each component.

        Args:
            dfd_spec: DFD specification as a string (Mermaid, PlantUML, or JSON format)
            logger: Optional logger for error reporting

        Returns:
            List of threat dictionaries
        """
        if logger is None:
            logger = self.logger

        try:
            # Parse DFD components from specification
            components = self._parse_dfd_components(dfd_spec, logger)

            # Convert DFD components to Azure resource-like objects for threat analysis
            resources = []
            for component in components:
                resource = self._convert_dfd_component_to_resource(component)
                if resource:
                    resources.append(resource)

            logger.info(f"Extracted {len(resources)} components from DFD specification")

            # Enumerate threats for the components
            threats = enumerate_threats(resources, logger)
            logger.info(f"Generated {len(threats)} threats from DFD analysis")

            return threats

        except Exception as e:
            logger.error(f"Failed to analyze threats from DFD specification: {e}")
            return []

    def _parse_dfd_components(
        self, dfd_spec: str, logger: logging.Logger
    ) -> List[Dict[str, Any]]:
        """
        Parse DFD components from specification.
        Supports basic Mermaid flowchart syntax and JSON format.
        """
        components = []

        try:
            # Try to parse as JSON first
            import json

            try:
                dfd_data = json.loads(dfd_spec)
                if isinstance(dfd_data, dict) and "nodes" in dfd_data:
                    for node in dfd_data.get("nodes", []):
                        components.append(
                            {
                                "id": node.get("id", ""),
                                "label": node.get("label", ""),
                                "type": node.get("type", "process"),
                                "description": node.get("description", ""),
                            }
                        )
                return components
            except json.JSONDecodeError:
                pass

            # Parse Mermaid flowchart syntax
            lines = dfd_spec.strip().split("\n")
            for line in lines:
                line = line.strip()
                if not line or line.startswith("flowchart") or line.startswith("graph"):
                    continue

                # Basic parsing for node definitions like: A[Web App] --> B[Database]
                if "-->" in line:
                    parts = line.split("-->")
                    for part in parts:
                        part = part.strip()
                        if "[" in part and "]" in part:
                            node_id = part.split("[")[0].strip()
                            node_label = part.split("[")[1].split("]")[0].strip()
                            components.append(
                                {
                                    "id": node_id,
                                    "label": node_label,
                                    "type": self._infer_component_type(node_label),
                                    "description": f"DFD component: {node_label}",
                                }
                            )
                elif "[" in line and "]" in line:
                    # Simple node definition like: A[Web Application]
                    node_id = line.split("[")[0].strip()
                    node_label = line.split("[")[1].split("]")[0].strip()
                    components.append(
                        {
                            "id": node_id,
                            "label": node_label,
                            "type": self._infer_component_type(node_label),
                            "description": f"DFD component: {node_label}",
                        }
                    )

        except Exception as e:
            logger.warning(f"Failed to parse DFD components: {e}")

        return components

    def _infer_component_type(self, label: str) -> str:
        """
        Infer Azure resource type from DFD component label.
        """
        label_lower = label.lower()

        if any(
            keyword in label_lower
            for keyword in ["web app", "webapp", "api", "app service"]
        ):
            return "Microsoft.Web/sites"
        elif any(keyword in label_lower for keyword in ["database", "sql", "db"]):
            return "Microsoft.Sql/servers"
        elif any(keyword in label_lower for keyword in ["storage", "blob", "file"]):
            return "Microsoft.Storage/storageAccounts"
        elif any(
            keyword in label_lower for keyword in ["vm", "virtual machine", "server"]
        ):
            return "Microsoft.Compute/virtualMachines"
        elif any(keyword in label_lower for keyword in ["network", "vnet", "subnet"]):
            return "Microsoft.Network/virtualNetworks"
        elif any(
            keyword in label_lower for keyword in ["key vault", "keyvault", "secrets"]
        ):
            return "Microsoft.KeyVault/vaults"
        else:
            return "Microsoft.Resources/resourceGroups"  # Default fallback

    def _convert_dfd_component_to_resource(
        self, component: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Convert a DFD component to an Azure resource-like dictionary for threat analysis.
        """
        return {
            "id": f"/dfd/components/{component.get('id', 'unknown')}",
            "name": component.get("label", "Unknown Component"),
            "type": component.get("type", "Microsoft.Resources/resourceGroups"),
            "location": "dfd-analysis",
            "resourceGroup": "dfd-analysis",
            "subscriptionId": "dfd-analysis",
            "properties": {
                "description": component.get("description", ""),
                "dfd_component": True,
            },
            "tags": {"source": "dfd-analysis"},
        }


def run_tmt(
    dfd_artifact: str, logger: Optional[logging.Logger] = None
) -> List[Dict[str, Any]]:
    """
    Legacy function for compatibility with existing code.
    Now uses custom Azure threat analysis instead of Microsoft TMT.

    Args:
        dfd_artifact: Path to DFD file or DFD specification string
        logger: Optional logger for error reporting

    Returns:
        List of threat dictionaries
    """
    if logger is None:
        logger = logging.getLogger("TMTRunner")

    logger.info("Using custom Azure threat analysis instead of Microsoft TMT")

    runner = AzureThreatAnalysisRunner()

    try:
        # If dfd_artifact is a file path, read the contents
        if dfd_artifact and (
            dfd_artifact.endswith(".tm7")
            or dfd_artifact.endswith(".json")
            or dfd_artifact.endswith(".md")
        ):
            try:
                with open(dfd_artifact, encoding="utf-8") as f:
                    dfd_content = f.read()
                return runner.analyze_from_dfd_specification(dfd_content, logger)
            except FileNotFoundError:
                logger.warning(
                    f"DFD file not found: {dfd_artifact}, treating as specification string"
                )
                return runner.analyze_from_dfd_specification(dfd_artifact, logger)
        else:
            # Treat as DFD specification string
            return runner.analyze_from_dfd_specification(dfd_artifact, logger)

    except Exception as e:
        logger.error(f"Custom threat analysis failed: {e}")
        return []
