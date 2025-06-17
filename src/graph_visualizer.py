"""
3D Graph Visualization Module

This module provides functionality to generate interactive 3D visualizations
of the Azure resource graph using the 3d-force-graph library.
"""

import json
import os
import webbrowser
from datetime import datetime
from typing import Any, Dict, Optional

import colorlog
from neo4j import Driver, GraphDatabase

from .visualization.html_template_builder import HtmlTemplateBuilder


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle DateTime objects."""

    def default(self, obj: Any) -> Any:  # type: ignore[override]
        if isinstance(obj, datetime):
            return obj.isoformat()
        # Handle Neo4j DateTime objects
        if hasattr(obj, "iso_format"):
            return obj.iso_format()
        # Handle other Neo4j temporal types
        if hasattr(obj, "__str__") and str(type(obj)).startswith("<class 'neo4j.time"):  # type: ignore[misc]
            return str(obj)
        return super().default(obj)


logger = colorlog.getLogger(__name__)


class GraphVisualizer:
    """Generate interactive 3D visualizations of the Neo4j graph."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str) -> None:
        """
        Initialize the Graph Visualizer.

        Args:
            neo4j_uri: Neo4j database URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.driver: Optional[Driver] = None

    def connect(self) -> None:
        """Establish connection to Neo4j database."""
        try:
            self.driver = GraphDatabase.driver(
                self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password)
            )

            # Test the connection
            with self.driver.session() as session:
                session.run("RETURN 1")

            logger.info(f"Connected to Neo4j at {self.neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self) -> None:
        """Close Neo4j database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def _add_hierarchical_edges(
        self, nodes: list[dict[str, Any]], links: list[dict[str, Any]]
    ) -> None:
        """
        Add Resource→Subscription and Subscription→Tenant edges if not already present.
        """
        # Build lookup maps
        subscription_id_map = {}
        tenant_id_map = {}
        node_id_map = {}

        for node in nodes:
            node_id_map[node["id"]] = node
            if "Subscription" in node.get("labels", []):
                # Accept both 'id' and 'properties' for subscription id
                subscription_id_map[node["properties"].get("id")] = node["id"]
            if "Tenant" in node.get("labels", []):
                tenant_id_map[node["properties"].get("id")] = node["id"]

        # Build a set of (source, target, type) for existing links to avoid duplicates
        existing_edges = {
            (link["source"], link["target"], link["type"]) for link in links
        }

        # Resource → Subscription
        for node in nodes:
            if "Resource" in node.get("labels", []):
                sub_id = node["properties"].get("subscriptionId")
                if sub_id and sub_id in subscription_id_map:
                    sub_node_id = subscription_id_map[sub_id]
                    edge_key = (node["id"], sub_node_id, "CONTAINS")
                    if edge_key not in existing_edges:
                        links.append(
                            {
                                "source": node["id"],
                                "target": sub_node_id,
                                "type": "CONTAINS",
                                "properties": {},
                                "color": self._get_relationship_color("CONTAINS"),
                                "width": self._get_relationship_width("CONTAINS"),
                            }
                        )
                        existing_edges.add(edge_key)

        # Subscription → Tenant
        for node in nodes:
            if "Subscription" in node.get("labels", []):
                tenant_id = node["properties"].get("tenantId")
                if tenant_id and tenant_id in tenant_id_map:
                    tenant_node_id = tenant_id_map[tenant_id]
                    edge_key = (node["id"], tenant_node_id, "CONTAINS")
                    if edge_key not in existing_edges:
                        links.append(
                            {
                                "source": node["id"],
                                "target": tenant_node_id,
                                "type": "CONTAINS",
                                "properties": {},
                                "color": self._get_relationship_color("CONTAINS"),
                                "width": self._get_relationship_width("CONTAINS"),
                            }
                        )
                        existing_edges.add(edge_key)

    def extract_graph_data(self, link_to_hierarchy: bool = False) -> Dict[str, Any]:
        """
        Extract all nodes and relationships from Neo4j for visualization.

        Args:
            link_to_hierarchy: If True, add Resource→Subscription and Subscription→Tenant edges

        Returns:
            Dictionary containing nodes and links for the 3D graph
        """
        logger.info("Extracting graph data from Neo4j...")
        logger.info(f"Neo4j URI: {self.neo4j_uri}")
        logger.info(f"Neo4j User: {self.neo4j_user}")
        logger.info(f"Neo4j Driver: {self.driver}")
        logger.info("Connecting to database: neo4j")

        if not self.driver:
            self.connect()

        # At this point driver should be available
        if not self.driver:
            raise RuntimeError("Failed to establish database connection")

        nodes: list[Any] = []
        links: list[Any] = []
        node_types: set[Any] = set()
        relationship_types: set[Any] = set()

        with self.driver.session(database="neo4j") as session:
            # Extract all nodes with their properties
            node_query = """
            MATCH (n)
            RETURN n, labels(n) as node_labels
            """

            result = session.run(node_query)
            node_map = {}

            node_count = 0
            for record in result:
                node = record["n"]
                labels = record["node_labels"]

                # Use node's internal id as unique identifier
                node_id = (
                    node.element_id if hasattr(node, "element_id") else str(node.id)
                )

                # Extract node properties first
                properties = dict(node)

                # Determine node type - use Azure resource type for Resources, otherwise use label
                primary_label = labels[0] if labels else "Unknown"
                if primary_label == "Resource" and properties.get("type"):
                    # Use the Azure resource type (e.g., Microsoft.Compute/virtualMachines)
                    node_type = properties["type"]
                else:
                    # Use the Neo4j label for non-resource nodes
                    node_type = primary_label

                node_types.add(node_type)

                # Create node data structure
                node_data = {
                    "id": node_id,
                    "name": properties.get(
                        "name",
                        properties.get("display_name", f"{node_type}_{node_id}"),
                    ),
                    "type": node_type,
                    "labels": labels,
                    "properties": properties,
                    "group": self._get_node_group(node_type),
                    "color": self._get_node_color(node_type),
                    "size": self._get_node_size(node_type, properties),
                }

                nodes.append(node_data)
                node_map[node_id] = node_data
                node_count += 1

            logger.info(f"Extracted {node_count} nodes (raw count)")

            # Extract all relationships
            relationship_query = """
            MATCH (a)-[r]->(b)
            RETURN a, r, b, type(r) as rel_type
            """

            result = session.run(relationship_query)

            rel_count = 0
            for record in result:
                source_node = record["a"]
                target_node = record["b"]
                relationship = record["r"]
                rel_type = record["rel_type"]

                source_id = (
                    source_node.element_id
                    if hasattr(source_node, "element_id")
                    else str(source_node.id)
                )
                target_id = (
                    target_node.element_id
                    if hasattr(target_node, "element_id")
                    else str(target_node.id)
                )

                relationship_types.add(rel_type)

                # Create link data structure
                link_data = {
                    "source": source_id,
                    "target": target_id,
                    "type": rel_type,
                    "properties": dict(relationship) if relationship else {},
                    "color": self._get_relationship_color(rel_type),
                    "width": self._get_relationship_width(rel_type),
                }

                links.append(link_data)
                rel_count += 1

            logger.info(f"Extracted {rel_count} relationships (raw count)")

        # Add hierarchical edges if requested
        if link_to_hierarchy:
            self._add_hierarchical_edges(nodes, links)

        # Update relationship_types if new CONTAINS edges were added
        rel_types_set = set(relationship_types)
        if link_to_hierarchy:
            rel_types_set.add("CONTAINS")

        return {
            "nodes": nodes,
            "links": links,
            "node_types": sorted(node_types),
            "relationship_types": sorted(rel_types_set),
        }

    def _get_node_group(self, node_type: str) -> int:
        """Get node group for clustering visualization."""
        group_mapping = {
            # High-level organizational nodes
            "Subscription": 1,
            "ResourceGroup": 2,
            # Compute services
            "Microsoft.Compute/virtualMachines": 10,
            "Microsoft.ContainerService/managedClusters": 11,
            # Networking services
            "Microsoft.Network/virtualNetworks": 20,
            "Microsoft.Network/networkInterfaces": 21,
            "Microsoft.Network/networkSecurityGroups": 22,
            "Microsoft.Network/publicIPAddresses": 23,
            "Microsoft.Network/loadBalancers": 24,
            # Storage services
            "Microsoft.Storage/storageAccounts": 30,
            # Database services
            "Microsoft.Sql/servers": 40,
            "Microsoft.DBforPostgreSQL/servers": 41,
            "Microsoft.DBforMySQL/servers": 42,
            "Microsoft.DocumentDB/databaseAccounts": 43,
            # Web services
            "Microsoft.Web/sites": 50,
            # Security services
            "Microsoft.KeyVault/vaults": 60,
            "Microsoft.Security/assessments": 61,
            "Microsoft.Security/securityContacts": 62,
            "Microsoft.Authorization/roleAssignments": 63,
            "Microsoft.ManagedIdentity/userAssignedIdentities": 64,
            # Monitoring services
            "Microsoft.OperationalInsights/workspaces": 70,
            "Microsoft.Insights/components": 71,
        }

        # If exact match not found, group by service provider
        if node_type not in group_mapping:
            if node_type.startswith("Microsoft.Compute"):
                return 10
            elif node_type.startswith("Microsoft.Network"):
                return 20
            elif node_type.startswith("Microsoft.Storage"):
                return 30
            elif node_type.startswith("Microsoft.Sql") or node_type.startswith(
                "Microsoft.DB"
            ):
                return 40
            elif node_type.startswith("Microsoft.Web"):
                return 50
            elif (
                node_type.startswith("Microsoft.KeyVault")
                or node_type.startswith("Microsoft.Security")
                or node_type.startswith("Microsoft.Authorization")
            ):
                return 60
            elif node_type.startswith("Microsoft.Insights") or node_type.startswith(
                "Microsoft.OperationalInsights"
            ):
                return 70
            elif node_type.startswith("Microsoft.ContainerService"):
                return 11

        return group_mapping.get(node_type, 99)

    def _get_node_color(self, node_type: str) -> str:
        """Get node color based on type."""
        color_mapping = {
            # Non-resource node types
            "Subscription": "#ff6b6b",  # Red
            "ResourceGroup": "#45b7d1",  # Blue
            # Azure resource types
            "Microsoft.Compute/virtualMachines": "#6c5ce7",  # Purple
            "Microsoft.Network/networkInterfaces": "#a55eea",  # Light Purple
            "Microsoft.Network/virtualNetworks": "#26de81",  # Green
            "Microsoft.Network/networkSecurityGroups": "#00d2d3",  # Cyan
            "Microsoft.Network/publicIPAddresses": "#81ecec",  # Light Cyan
            "Microsoft.Network/loadBalancers": "#00b894",  # Dark Green
            "Microsoft.Storage/storageAccounts": "#f9ca24",  # Yellow
            "Microsoft.KeyVault/vaults": "#fd79a8",  # Pink
            "Microsoft.Sql/servers": "#fdcb6e",  # Orange
            "Microsoft.Web/sites": "#e17055",  # Dark Orange
            "Microsoft.ContainerService/managedClusters": "#0984e3",  # Blue
            "Microsoft.DBforPostgreSQL/servers": "#a29bfe",  # Light Purple
            "Microsoft.DBforMySQL/servers": "#74b9ff",  # Light Blue
            "Microsoft.DocumentDB/databaseAccounts": "#e84393",  # Pink
            "Microsoft.OperationalInsights/workspaces": "#636e72",  # Gray
            "Microsoft.Insights/components": "#2d3436",  # Dark Gray
            "Microsoft.Authorization/roleAssignments": "#fab1a0",  # Light Orange
            "Microsoft.ManagedIdentity/userAssignedIdentities": "#00cec9",  # Teal
            "Microsoft.Security/assessments": "#fd79a8",  # Pink
            "Microsoft.Security/securityContacts": "#e84393",  # Pink
        }

        # If exact match not found, try to match by service provider
        if node_type not in color_mapping:
            if node_type.startswith("Microsoft.Compute"):
                return "#6c5ce7"  # Purple for compute
            elif node_type.startswith("Microsoft.Network"):
                return "#26de81"  # Green for networking
            elif node_type.startswith("Microsoft.Storage"):
                return "#f9ca24"  # Yellow for storage
            elif node_type.startswith("Microsoft.Web"):
                return "#e17055"  # Orange for web
            elif node_type.startswith("Microsoft.Sql") or node_type.startswith(
                "Microsoft.DB"
            ):
                return "#fdcb6e"  # Orange for databases
            elif node_type.startswith("Microsoft.KeyVault"):
                return "#fd79a8"  # Pink for security
            elif node_type.startswith("Microsoft.ContainerService"):
                return "#0984e3"  # Blue for containers
            elif node_type.startswith("Microsoft.Security"):
                return "#e84393"  # Pink for security
            elif node_type.startswith("Microsoft.Authorization"):
                return "#fab1a0"  # Light orange for identity

        return color_mapping.get(node_type, "#74b9ff")  # Default blue

    def _get_node_size(self, node_type: str, properties: Dict[str, Any]) -> int:
        """Get node size based on type and properties."""
        base_sizes = {
            "Subscription": 15,
            "Resource": 8,
            "ResourceGroup": 12,
            "StorageAccount": 10,
            "VirtualMachine": 12,
            "NetworkInterface": 6,
            "VirtualNetwork": 10,
            "KeyVault": 8,
            "SqlServer": 10,
            "WebSite": 8,
        }
        return base_sizes.get(node_type, 8)

    def _get_relationship_color(self, rel_type: str) -> str:
        """Get relationship color based on type."""
        color_mapping = {
            "CONTAINS": "#74b9ff",
            "BELONGS_TO": "#a29bfe",
            "CONNECTED_TO": "#fd79a8",
            "DEPENDS_ON": "#fdcb6e",
            "MANAGES": "#e17055",
        }
        return color_mapping.get(rel_type, "#ddd")

    def _get_relationship_width(self, rel_type: str) -> int:
        """Get relationship width based on type."""
        width_mapping = {
            "CONTAINS": 3,
            "BELONGS_TO": 2,
            "CONNECTED_TO": 2,
            "DEPENDS_ON": 1,
            "MANAGES": 2,
        }
        return width_mapping.get(rel_type, 1)

    def generate_html_visualization(
        self,
        output_path: Optional[str] = None,
        specification_path: Optional[str] = None,
        link_to_hierarchy: bool = True,
    ) -> str:
        """
        Generate HTML file with interactive 3D visualization.

        Args:
            output_path: Path where to save the HTML file
            specification_path: Path to the tenant specification markdown file
            link_to_hierarchy: If True, add Resource→Subscription and Subscription→Tenant edges

        Returns:
            Path to the generated HTML file
        """
        logger.info("Generating 3D visualization HTML...")

        # Extract graph data
        graph_data = self.extract_graph_data(link_to_hierarchy=link_to_hierarchy)

        # Generate output path if not provided
        if not output_path:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"azure_graph_visualization_{timestamp}.html"

        # Generate HTML content
        html_content = self._generate_html_template(graph_data, specification_path)

        # Write HTML file
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        logger.info(f"3D visualization saved to: {output_path}")
        return output_path

    def _generate_specification_link(self, specification_path: Optional[str]) -> str:
        """Generate HTML for the tenant specification link - ENHANCED."""
        import glob

        # If not provided or doesn't exist, look for latest in current directory
        if not specification_path or not os.path.exists(specification_path):
            current_dir = os.getcwd()
            spec_files = sorted(
                glob.glob(os.path.join(current_dir, "*_tenant_spec.md")), reverse=True
            )
            if spec_files:
                specification_path = spec_files[0]
            else:
                return ""

        spec_filename = os.path.basename(specification_path)
        return f"""
        <div class="filter-section">
            <h4>Documentation</h4>
            <a href="{spec_filename}" target="_blank" class="spec-link">
                📄 View Tenant Specification
            </a>
        </div>
        """

    def _generate_html_template(
        self, graph_data: Dict[str, Any], specification_path: Optional[str] = None
    ) -> str:
        """
        Generate the complete HTML template using the new component-based builder.

        This method now uses the modular HtmlTemplateBuilder instead of the previous
        680-line monolithic implementation. Maintains backward compatibility.
        """
        try:
            # Create the template builder
            template_builder = HtmlTemplateBuilder()

            # Generate the HTML template using the new component-based approach
            html_content = template_builder.build_template(
                graph_data=graph_data,
                specification_path=specification_path,
                title="Azure Tenant Graph - 3D Visualization",
            )

            return html_content

        except Exception as e:
            logger.error(f"Failed to generate HTML template using new builder: {e}")
            # If the new builder fails, we could fall back to a minimal template
            # For now, just re-raise the exception with more context
            raise RuntimeError(f"HTML template generation failed: {e!s}") from e

    # Cluster labeling: Each resource group is treated as a cluster. Labels are rendered at the centroid of each cluster and follow camera movement.
    # If resource_group is null, fallback to subscription or resource type. See _generate_html_template for implementation.

    def open_visualization(self, html_path: str) -> None:
        """Open the visualization in the default web browser."""
        try:
            webbrowser.open(f"file://{os.path.abspath(html_path)}")
            logger.info(f"Opened visualization in browser: {html_path}")
        except Exception as e:
            logger.error(f"Failed to open visualization in browser: {e}")
