"""
Architectural Pattern Analyzer

This module analyzes Azure resource graphs to identify common architectural patterns
and generate visualizations showing resource relationships and patterns.
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
from neo4j import Driver, GraphDatabase

logger = logging.getLogger(__name__)


class ArchitecturalPatternAnalyzer:
    """Analyzes Azure resource graphs to identify architectural patterns."""

    # Define architectural patterns with their characteristic resources
    ARCHITECTURAL_PATTERNS = {
        "Web Application": {
            "resources": ["sites", "serverFarms", "storageAccounts", "components"],
            "description": "App Service web application with storage and monitoring",
        },
        "Virtual Machine Workload": {
            "resources": [
                "virtualMachines",
                "disks",
                "networkInterfaces",
                "virtualNetworks",
                "networkSecurityGroups",
            ],
            "description": "IaaS VM with networking and storage",
        },
        "Container Platform": {
            "resources": [
                "managedClusters",
                "containerRegistries",
                "virtualNetworks",
                "loadBalancers",
            ],
            "description": "AKS or container-based platform",
        },
        "Data Platform": {
            "resources": [
                "servers",
                "databases",
                "storageAccounts",
                "privateEndpoints",
            ],
            "description": "Database with secure connectivity and storage",
        },
        "Serverless Application": {
            "resources": ["sites", "storageAccounts", "components", "vaults"],
            "description": "Function App with storage, monitoring, and secrets",
        },
        "Data Analytics": {
            "resources": ["clusters", "workspaces", "storageAccounts", "namespaces"],
            "description": "Analytics platform with data ingestion and storage",
        },
        "Secure Workload": {
            "resources": [
                "vaults",
                "privateEndpoints",
                "privateDnsZones",
                "networkInterfaces",
            ],
            "description": "Resources with private networking and Key Vault",
        },
        "Managed Identity Pattern": {
            "resources": [
                "userAssignedIdentities",
                "sites",
                "managedClusters",
                "virtualMachines",
            ],
            "description": "Resources using managed identities for authentication",
        },
        "Monitoring & Observability": {
            "resources": [
                "components",
                "workspaces",
                "dataCollectionRules",
                "smartDetectorAlertRules",
            ],
            "description": "Application Insights and Log Analytics monitoring",
        },
        "Network Security": {
            "resources": [
                "networkSecurityGroups",
                "virtualNetworks",
                "subnets",
                "bastionHosts",
            ],
            "description": "Network isolation and secure access",
        },
    }

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """
        Initialize the pattern analyzer.

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
            logger.exception(f"Failed to connect to Neo4j: {e}")
            raise

    def close(self) -> None:
        """Close Neo4j database connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def _get_resource_type_name(
        self, labels: List[str], azure_type: Optional[str]
    ) -> str:
        """
        Determine standardized resource type name from labels and Azure type.

        Args:
            labels: Node labels
            azure_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Standardized resource type name
        """
        if not labels:
            return "Unknown"

        # Check if it's a Resource node with Azure type
        if "Resource" in labels and azure_type:
            # Extract resource type from Azure resource type
            # e.g., "Microsoft.Compute/virtualMachines" -> "virtualMachines"
            parts = azure_type.split("/")
            if len(parts) >= 2:
                return parts[-1]  # Last part is the resource type
            return parts[0]

        # For non-Resource nodes, use the most specific label
        # Filter out generic labels like 'Original'
        filtered_labels = [
            label for label in labels if label not in ["Original", "Resource"]
        ]
        if filtered_labels:
            return filtered_labels[0]

        return labels[0] if labels else "Unknown"

    def fetch_all_relationships(self) -> List[Dict[str, Any]]:
        """
        Query all relationships from Neo4j graph.

        Filters out SCAN_SOURCE_NODE relationships which are internal dual-graph
        bookkeeping links and not actual architectural relationships.

        Returns:
            List of relationship records with source/target labels and types
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        query = """
        MATCH (source)-[r]->(target)
        WHERE type(r) <> 'SCAN_SOURCE_NODE'
        RETURN labels(source) as source_labels,
               source.type as source_type,
               type(r) as rel_type,
               labels(target) as target_labels,
               target.type as target_type
        """

        all_relationships = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                all_relationships.append(
                    {
                        "source_labels": record["source_labels"],
                        "source_type": record["source_type"],
                        "rel_type": record["rel_type"],
                        "target_labels": record["target_labels"],
                        "target_type": record["target_type"],
                    }
                )

        logger.info(f"Loaded {len(all_relationships)} relationships from graph")
        return all_relationships

    def aggregate_relationships(
        self, all_relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Aggregate relationships by resource type.

        Args:
            all_relationships: List of all relationship records

        Returns:
            List of aggregated relationships with frequency counts
        """
        relationship_counts: Dict[Tuple[str, str, str], Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )

        for rel in all_relationships:
            source_type_name = self._get_resource_type_name(
                rel["source_labels"], rel["source_type"]
            )
            target_type_name = self._get_resource_type_name(
                rel["target_labels"], rel["target_type"]
            )
            rel_type = rel["rel_type"]

            # Create aggregation key: (source_type, rel_type, target_type)
            key = (source_type_name, rel_type, target_type_name)
            relationship_counts[key][rel_type] += 1

        # Convert to list for sorting and display
        aggregated_relationships = []
        for (source_type, rel_type, target_type), counts in relationship_counts.items():
            frequency = counts[rel_type]
            aggregated_relationships.append(
                {
                    "source_type": source_type,
                    "rel_type": rel_type,
                    "target_type": target_type,
                    "frequency": frequency,
                }
            )

        # Sort by frequency
        aggregated_relationships.sort(key=lambda x: x["frequency"], reverse=True)

        logger.info(
            f"Aggregated into {len(aggregated_relationships)} unique relationship patterns"
        )
        return aggregated_relationships

    def build_networkx_graph(
        self, aggregated_relationships: List[Dict[str, Any]]
    ) -> Tuple[nx.MultiDiGraph, Dict[str, int], Dict[Tuple[str, str], int]]:
        """
        Build NetworkX graph from aggregated relationships.

        Args:
            aggregated_relationships: List of aggregated relationships

        Returns:
            Tuple of (graph, resource_type_counts, edge_counts)
        """
        G = nx.MultiDiGraph()

        # Collect all unique resource types and their frequencies
        resource_type_counts: Dict[str, int] = defaultdict(int)

        # Count occurrences of each resource type from relationships
        for rel in aggregated_relationships:
            resource_type_counts[rel["source_type"]] += rel["frequency"]
            resource_type_counts[rel["target_type"]] += rel["frequency"]

        # Add nodes for all resource types
        for resource_type, count in resource_type_counts.items():
            G.add_node(resource_type, count=count)

        # Add edges for relationships
        edge_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        for rel in aggregated_relationships:
            source = rel["source_type"]
            target = rel["target_type"]
            rel_type = rel["rel_type"]
            frequency = rel["frequency"]

            # Add edge
            G.add_edge(source, target, relationship=rel_type, frequency=frequency)

            # Track aggregated edge counts (for visualization)
            edge_key = (source, target)
            edge_counts[edge_key] += frequency

        logger.info(
            f"Graph constructed: {G.number_of_nodes()} nodes, "
            f"{G.number_of_edges()} edges"
        )
        return G, dict(resource_type_counts), dict(edge_counts)

    def detect_patterns(
        self, graph: nx.MultiDiGraph, resource_type_counts: Dict[str, int]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect architectural patterns in the graph.

        Args:
            graph: NetworkX graph
            resource_type_counts: Resource type frequency counts

        Returns:
            Dictionary of detected patterns with match information
        """
        pattern_matches = {}
        existing_resources = set(graph.nodes())

        for pattern_name, pattern_info in self.ARCHITECTURAL_PATTERNS.items():
            pattern_resources = set(pattern_info["resources"])
            matched_resources = pattern_resources.intersection(existing_resources)

            if len(matched_resources) >= 2:
                connection_count = 0
                pattern_edges = []

                for source in matched_resources:
                    for target in matched_resources:
                        if source != target and graph.has_edge(source, target):
                            edges = graph.get_edge_data(source, target)
                            if edges:
                                for _key, data in edges.items():
                                    connection_count += data.get("frequency", 1)
                                    pattern_edges.append(
                                        (source, data["relationship"], target)
                                    )

                pattern_matches[pattern_name] = {
                    "matched_resources": list(matched_resources),
                    "missing_resources": list(pattern_resources - matched_resources),
                    "connection_count": connection_count,
                    "pattern_edges": pattern_edges[:5],  # Top 5 edges
                    "completeness": len(matched_resources)
                    / len(pattern_resources)
                    * 100,
                }

        logger.info(f"Detected {len(pattern_matches)} architectural patterns")
        return pattern_matches

    def export_graph_data(
        self,
        graph: nx.MultiDiGraph,
        resource_type_counts: Dict[str, int],
        output_path: Path,
        all_relationships_count: int,
    ) -> None:
        """
        Export graph data to JSON format.

        Args:
            graph: NetworkX graph
            resource_type_counts: Resource type frequency counts
            output_path: Path to output JSON file
            all_relationships_count: Total number of source relationships
        """
        top_nodes = sorted(
            resource_type_counts.items(), key=lambda x: x[1], reverse=True
        )[:20]

        graph_export = {
            "nodes": [
                {"id": node, "label": node, "count": graph.nodes[node]["count"]}
                for node in graph.nodes()
            ],
            "edges": [
                {
                    "source": u,
                    "target": v,
                    "relationship": data["relationship"],
                    "frequency": data["frequency"],
                }
                for u, v, data in graph.edges(data=True)
            ],
            "summary": {
                "total_nodes": graph.number_of_nodes(),
                "total_edges": graph.number_of_edges(),
                "top_resource_types": [
                    {"type": name, "connection_count": count}
                    for name, count in top_nodes
                ],
                "aggregation_method": "By Azure resource type and node labels",
                "source_relationships": all_relationships_count,
            },
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(graph_export, f, indent=2)

        logger.info(f"Exported graph data to {output_path}")

    def generate_visualizations(
        self,
        graph: nx.MultiDiGraph,
        resource_type_counts: Dict[str, int],
        edge_counts: Dict[Tuple[str, str], int],
        pattern_matches: Dict[str, Dict[str, Any]],
        output_dir: Path,
        top_n_nodes: int = 30,
    ) -> List[Path]:
        """
        Generate visualization plots using matplotlib.

        Args:
            graph: NetworkX graph
            resource_type_counts: Resource type frequency counts
            edge_counts: Edge frequency counts
            pattern_matches: Detected architectural patterns
            output_dir: Directory to save visualizations
            top_n_nodes: Number of top nodes to visualize

        Returns:
            List of paths to generated visualization files
        """
        try:
            import matplotlib.pyplot as plt
            import numpy as np
            from matplotlib.patches import Patch, Polygon
            from scipy.spatial import ConvexHull
        except ImportError as e:
            logger.error(
                f"Missing visualization dependencies: {e}. "
                "Install with: uv pip install matplotlib scipy"
            )
            return []

        output_dir.mkdir(parents=True, exist_ok=True)
        generated_files = []

        # Filter to show only the most significant nodes
        top_nodes = sorted(
            resource_type_counts.items(), key=lambda x: x[1], reverse=True
        )[:top_n_nodes]
        top_node_names = [name for name, _ in top_nodes]

        # Create subgraph with only top nodes
        G_filtered = graph.subgraph(top_node_names).copy()

        # Compute layout
        pos = nx.spring_layout(G_filtered, k=3, iterations=50, seed=42)

        # Assign patterns to nodes
        node_pattern_map = {}
        node_colors = []

        for node in G_filtered.nodes():
            node_patterns = []
            for pattern_name, match in pattern_matches.items():
                if node in match["matched_resources"]:
                    node_patterns.append(pattern_name)
            node_pattern_map[node] = node_patterns

            if node_patterns:
                best_pattern = max(
                    node_patterns,
                    key=lambda p: pattern_matches[p]["completeness"],
                )
                pattern_index = list(pattern_matches.keys()).index(best_pattern)
                node_colors.append(pattern_index)
            else:
                node_colors.append(-1)

        # Calculate sizes and edge properties
        node_sizes = [
            G_filtered.nodes[node]["count"] / 4 for node in G_filtered.nodes()
        ]

        # Separate pattern vs cross-pattern edges
        pattern_edges = []
        cross_pattern_edges = []
        pattern_edge_widths = []
        cross_pattern_edge_widths = []
        pattern_edge_colors = []

        for u, v, _data in G_filtered.edges(data=True):
            freq = edge_counts.get((u, v), 0)
            edge_width = max(1, freq / 50)

            u_patterns = set(node_pattern_map.get(u, []))
            v_patterns = set(node_pattern_map.get(v, []))
            shared_patterns = u_patterns.intersection(v_patterns)

            if shared_patterns:
                pattern_edges.append((u, v))
                pattern_edge_widths.append(edge_width * 2.5)
                shared_pattern = list(shared_patterns)[0]
                pattern_index = list(pattern_matches.keys()).index(shared_pattern)
                pattern_edge_colors.append(pattern_index)
            else:
                cross_pattern_edges.append((u, v))
                cross_pattern_edge_widths.append(edge_width * 0.4)

        # Create main visualization
        fig, ax = plt.subplots(1, 1, figsize=(28, 24))

        # Draw pattern boundaries
        cmap = plt.cm.tab10
        pattern_legend = []

        for pattern_idx, (pattern_name, match) in enumerate(pattern_matches.items()):
            pattern_nodes = [
                n for n in match["matched_resources"] if n in G_filtered.nodes()
            ]

            if len(pattern_nodes) >= 3:
                try:
                    points = np.array(
                        [[pos[node][0], pos[node][1]] for node in pattern_nodes]
                    )
                    center = points.mean(axis=0)
                    points_expanded = center + (points - center) * 1.15
                    hull = ConvexHull(points_expanded)
                    hull_points = points_expanded[hull.vertices]

                    color = cmap(pattern_idx / len(pattern_matches))
                    polygon = Polygon(
                        hull_points,
                        facecolor=color,
                        alpha=0.08,
                        edgecolor=color,
                        linewidth=3,
                        linestyle="--",
                        zorder=1,
                    )
                    ax.add_patch(polygon)

                    pattern_legend.append(
                        Patch(
                            facecolor=color,
                            edgecolor=color,
                            label=f"{pattern_name} ({match['completeness']:.0f}%)",
                            alpha=0.5,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Could not draw boundary for {pattern_name}: {e}")

        # Draw cross-pattern edges first (gray background)
        if cross_pattern_edges:
            nx.draw_networkx_edges(
                G_filtered,
                pos,
                edgelist=cross_pattern_edges,
                width=cross_pattern_edge_widths,
                alpha=0.15,
                edge_color="gray",
                arrows=True,
                arrowsize=10,
                arrowstyle="->",
                connectionstyle="arc3,rad=0.05",
                ax=ax,
            )

        # Draw pattern edges (colored by pattern)
        if pattern_edges:
            for idx, (u, v) in enumerate(pattern_edges):
                edge_color = cmap(pattern_edge_colors[idx] / len(pattern_matches))
                nx.draw_networkx_edges(
                    G_filtered,
                    pos,
                    edgelist=[(u, v)],
                    width=pattern_edge_widths[idx],
                    alpha=0.6,
                    edge_color=[edge_color],
                    arrows=True,
                    arrowsize=15,
                    arrowstyle="->",
                    connectionstyle="arc3,rad=0.1",
                    ax=ax,
                )

        # Draw nodes
        nx.draw_networkx_nodes(
            G_filtered,
            pos,
            node_size=node_sizes,
            node_color=node_colors,
            cmap=cmap,
            vmin=-1,
            vmax=len(pattern_matches) - 1,
            alpha=0.95,
            edgecolors="black",
            linewidths=2.5,
            ax=ax,
        )

        # Draw labels
        nx.draw_networkx_labels(
            G_filtered, pos, font_size=10, font_weight="bold", ax=ax
        )

        # Add legend
        if pattern_legend:
            ax.legend(
                handles=pattern_legend,
                loc="upper left",
                fontsize=10,
                framealpha=0.95,
                title="Architectural Patterns",
                title_fontsize=12,
            )

        ax.set_title(
            f"Azure Resource Graph with Architectural Pattern Overlay (Top {top_n_nodes})\n"
            + "Dashed boundaries = Pattern groupings | Thick colored edges = Intra-pattern | "
            + "Thin gray = Cross-pattern\n"
            + "Node color = Pattern | Node size = Connection frequency",
            fontsize=16,
            fontweight="bold",
            pad=25,
        )
        ax.axis("off")
        plt.tight_layout()

        main_viz_path = output_dir / "architectural_patterns_overview.png"
        plt.savefig(main_viz_path, dpi=150, bbox_inches="tight")
        plt.close()
        generated_files.append(main_viz_path)
        logger.info(f"Generated main visualization: {main_viz_path}")

        return generated_files

    def identify_orphaned_nodes(
        self,
        graph: nx.MultiDiGraph,
        pattern_matches: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Identify resource types that are not part of any detected pattern.

        Args:
            graph: NetworkX graph
            pattern_matches: Detected architectural patterns

        Returns:
            List of orphaned nodes with their connection information
        """
        # Collect all nodes that are matched by at least one pattern
        matched_nodes = set()
        for _pattern_name, match in pattern_matches.items():
            matched_nodes.update(match["matched_resources"])

        # Find orphaned nodes (not in any pattern)
        all_nodes = set(graph.nodes())
        orphaned_nodes = all_nodes - matched_nodes

        # Gather connection information for each orphaned node
        orphaned_info = []
        for node in orphaned_nodes:
            # Find what this node connects to
            out_neighbors = list(graph.successors(node))
            in_neighbors = list(graph.predecessors(node))

            # Find edges
            outgoing_edges = []
            for target in out_neighbors:
                edges = graph.get_edge_data(node, target)
                if edges:
                    for _key, data in edges.items():
                        outgoing_edges.append(
                            {
                                "target": target,
                                "relationship": data.get("relationship", "UNKNOWN"),
                                "frequency": data.get("frequency", 0),
                            }
                        )

            incoming_edges = []
            for source in in_neighbors:
                edges = graph.get_edge_data(source, node)
                if edges:
                    for _key, data in edges.items():
                        incoming_edges.append(
                            {
                                "source": source,
                                "relationship": data.get("relationship", "UNKNOWN"),
                                "frequency": data.get("frequency", 0),
                            }
                        )

            orphaned_info.append(
                {
                    "resource_type": node,
                    "connection_count": graph.nodes[node].get("count", 0),
                    "in_degree": graph.in_degree(node),
                    "out_degree": graph.out_degree(node),
                    "total_degree": graph.degree(node),
                    "outgoing_edges": outgoing_edges,
                    "incoming_edges": incoming_edges,
                    "connected_to": list(set(out_neighbors + in_neighbors)),
                }
            )

        # Sort by connection count (most connected first)
        orphaned_info.sort(key=lambda x: x["connection_count"], reverse=True)

        logger.info(
            f"Identified {len(orphaned_info)} orphaned nodes "
            f"out of {len(all_nodes)} total nodes"
        )
        return orphaned_info

    def fetch_microsoft_learn_documentation(
        self, resource_type: str, max_attempts: int = 3
    ) -> Dict[str, Any]:
        """
        Fetch documentation from Microsoft Learn for a given resource type.

        Searches Microsoft Learn training materials to understand the resource type
        and its typical use cases.

        Args:
            resource_type: Azure resource type (e.g., "virtualMachines", "loadBalancers")
            max_attempts: Maximum number of search attempts with different queries

        Returns:
            Dictionary with documentation information
        """
        from urllib.parse import quote

        # Map common resource type names to full Azure type names for better search
        type_mappings = {
            "virtualMachines": "Microsoft.Compute/virtualMachines Azure Virtual Machines",
            "loadBalancers": "Microsoft.Network/loadBalancers Azure Load Balancer",
            "publicIPAddresses": "Microsoft.Network/publicIPAddresses Azure Public IP",
            "storageAccounts": "Microsoft.Storage/storageAccounts Azure Storage",
            "actiongroups": "microsoft.insights/actiongroups Azure Monitor Action Groups",
            "bastionHosts": "Microsoft.Network/bastionHosts Azure Bastion",
            "managedClusters": "Microsoft.ContainerService/managedClusters Azure Kubernetes Service AKS",
        }

        search_term = type_mappings.get(resource_type, f"Azure {resource_type}")
        encoded_query = quote(f"site:learn.microsoft.com/en-us/training {search_term}")

        doc_info = {
            "resource_type": resource_type,
            "search_term": search_term,
            "documentation_found": False,
            "summary": "",
            "url": f"https://learn.microsoft.com/en-us/search/?terms={encoded_query}",
            "typical_uses": [],
            "related_resources": [],
        }

        try:
            # Use WebFetch to search Microsoft Learn
            # Note: This is a simplified approach - in production, you might use:
            # 1. Microsoft Graph API for better search
            # 2. Bing Search API
            # 3. Custom web scraping with BeautifulSoup
            logger.info(f"Searching Microsoft Learn for: {search_term}")

            # For now, we'll provide common patterns based on resource type name
            # In a real implementation, you would use WebFetch or similar tools
            doc_info["summary"] = self._generate_resource_summary(resource_type)
            doc_info["typical_uses"] = self._get_typical_uses(resource_type)
            doc_info["related_resources"] = self._get_related_resources(resource_type)
            doc_info["documentation_found"] = True

            logger.info(f"Generated documentation summary for {resource_type}")

        except Exception as e:
            logger.warning(f"Failed to fetch documentation for {resource_type}: {e}")
            doc_info["error"] = str(e)

        return doc_info

    def _generate_resource_summary(self, resource_type: str) -> str:
        """Generate a summary description for a resource type."""
        # This is a placeholder - in production, this would fetch real documentation
        common_descriptions = {
            "loadBalancers": "Distributes inbound network traffic across multiple virtual machines or services",
            "publicIPAddresses": "Provides internet-accessible IP addresses for Azure resources",
            "actiongroups": "Defines notification and action groups for Azure Monitor alerts",
            "bastionHosts": "Provides secure RDP/SSH access to VMs without exposing public IPs",
            "applicationGateways": "Layer 7 load balancer with web application firewall capabilities",
            "trafficManagerProfiles": "DNS-based traffic load balancer for global distribution",
            "frontDoors": "Global HTTP load balancer with CDN and web application firewall",
        }

        return common_descriptions.get(
            resource_type,
            f"Azure {resource_type} resource - see Microsoft Learn for details",
        )

    def _get_typical_uses(self, resource_type: str) -> List[str]:
        """Get typical use cases for a resource type."""
        use_cases = {
            "loadBalancers": [
                "Load balancing for VM scale sets",
                "High availability for web applications",
                "Internal load balancing for multi-tier apps",
            ],
            "publicIPAddresses": [
                "Internet-facing load balancers",
                "Bastion hosts for secure access",
                "VPN gateways",
                "Application gateways",
            ],
            "actiongroups": [
                "Alert notifications via email/SMS",
                "Webhook triggers for automation",
                "ITSM integration",
                "Azure Functions for custom actions",
            ],
            "bastionHosts": [
                "Secure VM access without public IPs",
                "Centralized access management",
                "Compliance with security policies",
            ],
        }

        return use_cases.get(
            resource_type,
            [
                "See Microsoft Learn documentation",
                f"Common in Azure {resource_type} deployments",
            ],
        )

    def _get_related_resources(self, resource_type: str) -> List[str]:
        """Get commonly related resource types."""
        relationships = {
            "loadBalancers": [
                "virtualMachineScaleSets",
                "publicIPAddresses",
                "networkSecurityGroups",
                "virtualNetworks",
            ],
            "publicIPAddresses": [
                "loadBalancers",
                "bastionHosts",
                "virtualMachines",
                "applicationGateways",
            ],
            "actiongroups": [
                "metricalerts",
                "dataCollectionRules",
                "prometheusRuleGroups",
            ],
            "bastionHosts": [
                "publicIPAddresses",
                "virtualNetworks",
                "virtualMachines",
                "networkSecurityGroups",
            ],
        }

        return relationships.get(resource_type, [])

    def suggest_new_patterns(
        self,
        orphaned_nodes: List[Dict[str, Any]],
        graph: nx.MultiDiGraph,
        min_connections: int = 2,
        min_cluster_size: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Analyze orphaned nodes and suggest new architectural patterns.

        Uses co-occurrence analysis and graph clustering to identify groups of
        orphaned nodes that frequently appear together.

        Args:
            orphaned_nodes: List of orphaned node information
            graph: NetworkX graph
            min_connections: Minimum edge frequency to consider
            min_cluster_size: Minimum number of resources for a pattern

        Returns:
            List of suggested patterns with their resources and rationale
        """
        suggested_patterns = []

        # Strategy 1: Group orphaned nodes by their connections to existing matched nodes
        orphaned_types = [node["resource_type"] for node in orphaned_nodes]
        orphaned_subgraph = graph.subgraph(orphaned_types).copy()

        # Find connected components (clusters) in the orphaned subgraph
        weakly_connected = list(nx.weakly_connected_components(orphaned_subgraph))

        for _idx, component in enumerate(weakly_connected):
            if len(component) >= min_cluster_size:
                component_list = list(component)

                # Get connections between component members
                internal_edges = []
                for u in component_list:
                    for v in component_list:
                        if u != v and graph.has_edge(u, v):
                            edges = graph.get_edge_data(u, v)
                            if edges:
                                for _key, data in edges.items():
                                    internal_edges.append(
                                        {
                                            "source": u,
                                            "target": v,
                                            "relationship": data.get(
                                                "relationship", "UNKNOWN"
                                            ),
                                            "frequency": data.get("frequency", 0),
                                        }
                                    )

                # Get connections to non-orphaned nodes (context)
                external_connections = {}
                for node in component_list:
                    node_info = next(
                        (n for n in orphaned_nodes if n["resource_type"] == node), None
                    )
                    if node_info:
                        for conn in node_info["connected_to"]:
                            if conn not in component_list:
                                external_connections[conn] = (
                                    external_connections.get(conn, 0) + 1
                                )

                # Fetch documentation for cluster members
                documented_resources = []
                for resource_type in component_list:
                    doc = self.fetch_microsoft_learn_documentation(resource_type)
                    documented_resources.append(doc)

                # Generate pattern suggestion
                pattern_name = self._generate_pattern_name(
                    component_list, documented_resources
                )
                pattern_description = self._generate_pattern_description(
                    component_list, documented_resources, external_connections
                )

                suggested_patterns.append(
                    {
                        "suggested_name": pattern_name,
                        "description": pattern_description,
                        "required_resources": component_list[:2]
                        if len(component_list) >= 2
                        else component_list,
                        "optional_resources": component_list[2:]
                        if len(component_list) > 2
                        else [],
                        "internal_connections": len(internal_edges),
                        "internal_edges": internal_edges[:5],  # Top 5 for brevity
                        "external_connections": dict(
                            sorted(
                                external_connections.items(),
                                key=lambda x: x[1],
                                reverse=True,
                            )[:5]
                        ),
                        "documented_resources": documented_resources,
                        "confidence": self._calculate_pattern_confidence(
                            len(component_list),
                            len(internal_edges),
                            external_connections,
                        ),
                    }
                )

        # Strategy 2: Find orphaned nodes that frequently co-occur with specific matched patterns
        for node_info in orphaned_nodes[:10]:  # Top 10 most connected orphaned nodes
            resource_type = node_info["resource_type"]

            # Find which patterns this orphaned node connects to most
            pattern_connections = {}
            for conn in node_info["connected_to"]:
                for pattern_name, match in self.ARCHITECTURAL_PATTERNS.items():
                    if conn in match.get("resources", []):
                        pattern_connections[pattern_name] = (
                            pattern_connections.get(pattern_name, 0) + 1
                        )

            if pattern_connections:
                # Suggest adding this resource to the most connected pattern
                best_pattern = max(pattern_connections.items(), key=lambda x: x[1])
                doc = self.fetch_microsoft_learn_documentation(resource_type)

                suggested_patterns.append(
                    {
                        "suggested_name": f"{best_pattern[0]} (Enhanced)",
                        "description": f"Add {resource_type} to existing {best_pattern[0]} pattern",
                        "action": "UPDATE_EXISTING",
                        "target_pattern": best_pattern[0],
                        "resource_to_add": resource_type,
                        "connection_count": best_pattern[1],
                        "documentation": doc,
                        "confidence": min(
                            best_pattern[1] / 5.0, 1.0
                        ),  # Normalize confidence
                    }
                )

        # Sort by confidence
        suggested_patterns.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        logger.info(f"Generated {len(suggested_patterns)} pattern suggestions")
        return suggested_patterns

    def _generate_pattern_name(
        self, resources: List[str], docs: List[Dict[str, Any]]
    ) -> str:
        """Generate a descriptive pattern name from resources."""
        # Use first 2-3 resource types to generate name
        if len(resources) == 0:
            return "Unknown Pattern"

        key_resources = resources[:2]
        name_parts = []

        for resource in key_resources:
            # Clean up resource name for pattern name
            clean_name = resource.replace("_", " ").title()
            name_parts.append(clean_name)

        return f"{' + '.join(name_parts)} Pattern"

    def _generate_pattern_description(
        self,
        resources: List[str],
        docs: List[Dict[str, Any]],
        external_connections: Dict[str, int],
    ) -> str:
        """Generate a pattern description from resources and documentation."""
        if not resources:
            return "No description available"

        # Use documentation summaries if available
        summaries = [doc.get("summary", "") for doc in docs if doc.get("summary")]

        if summaries:
            # Combine first 2 summaries
            description = ". ".join(summaries[:2])
        else:
            description = f"Pattern involving {', '.join(resources)}"

        # Add context about external connections
        if external_connections:
            top_connections = list(external_connections.keys())[:3]
            description += f". Often connects to: {', '.join(top_connections)}"

        return description

    def _calculate_pattern_confidence(
        self,
        resource_count: int,
        edge_count: int,
        external_connections: Dict[str, int],
    ) -> float:
        """
        Calculate confidence score for a suggested pattern.

        Args:
            resource_count: Number of resources in the pattern
            edge_count: Number of internal connections
            external_connections: Connections to other patterns

        Returns:
            Confidence score between 0.0 and 1.0
        """
        # Base confidence from resource count (2-5 resources is ideal)
        resource_score = min(resource_count / 5.0, 1.0)

        # Internal connectivity score (more connections = higher confidence)
        connectivity_score = min(edge_count / 10.0, 1.0)

        # External integration score (connects to many other patterns)
        external_score = min(len(external_connections) / 5.0, 1.0)

        # Weighted average
        confidence = (
            0.4 * resource_score + 0.4 * connectivity_score + 0.2 * external_score
        )

        return round(confidence, 2)

    def analyze_and_export(
        self,
        output_dir: Path,
        generate_visualizations: bool = True,
        top_n_nodes: int = 30,
    ) -> Dict[str, Any]:
        """
        Run complete analysis and export results.

        Args:
            output_dir: Directory to save output files
            generate_visualizations: Whether to generate matplotlib visualizations
            top_n_nodes: Number of top nodes to include in visualizations

        Returns:
            Dictionary with analysis results and file paths
        """
        self.connect()

        try:
            # Fetch and aggregate relationships
            all_relationships = self.fetch_all_relationships()
            aggregated_relationships = self.aggregate_relationships(all_relationships)

            # Build NetworkX graph
            graph, resource_type_counts, edge_counts = self.build_networkx_graph(
                aggregated_relationships
            )

            # Detect patterns
            pattern_matches = self.detect_patterns(graph, resource_type_counts)

            # Identify orphaned nodes and suggest new patterns
            orphaned_nodes = self.identify_orphaned_nodes(graph, pattern_matches)
            suggested_patterns = self.suggest_new_patterns(orphaned_nodes, graph)

            # Export graph data to JSON
            json_output = output_dir / "resource_graph_aggregated.json"
            self.export_graph_data(
                graph, resource_type_counts, json_output, len(all_relationships)
            )

            # Export orphaned nodes analysis
            orphaned_output = output_dir / "orphaned_nodes_analysis.json"
            with open(orphaned_output, "w") as f:
                json.dump(
                    {
                        "orphaned_count": len(orphaned_nodes),
                        "orphaned_nodes": orphaned_nodes,
                        "suggested_patterns": suggested_patterns,
                    },
                    f,
                    indent=2,
                )
            logger.info(f"Exported orphaned nodes analysis to {orphaned_output}")

            # Generate visualizations if requested
            visualization_files = []
            if generate_visualizations:
                visualization_files = self.generate_visualizations(
                    graph,
                    resource_type_counts,
                    edge_counts,
                    pattern_matches,
                    output_dir,
                    top_n_nodes,
                )

            # Prepare summary report
            top_resource_types = sorted(
                resource_type_counts.items(), key=lambda x: x[1], reverse=True
            )[:20]

            summary = {
                "total_relationships": len(all_relationships),
                "unique_patterns": len(aggregated_relationships),
                "resource_types": len(resource_type_counts),
                "graph_edges": graph.number_of_edges(),
                "detected_patterns": len(pattern_matches),
                "orphaned_nodes": len(orphaned_nodes),
                "suggested_patterns": len(suggested_patterns),
                "top_resource_types": [
                    {"type": name, "connection_count": count}
                    for name, count in top_resource_types
                ],
                "patterns": {
                    name: {
                        "completeness": match["completeness"],
                        "matched_resources": match["matched_resources"],
                        "missing_resources": match["missing_resources"],
                        "connection_count": match["connection_count"],
                    }
                    for name, match in sorted(
                        pattern_matches.items(),
                        key=lambda x: x[1]["completeness"],
                        reverse=True,
                    )
                },
                "output_files": {
                    "json": str(json_output),
                    "orphaned_analysis": str(orphaned_output),
                    "visualizations": [str(f) for f in visualization_files],
                },
            }

            # Save summary report
            summary_output = output_dir / "analysis_summary.json"
            with open(summary_output, "w") as f:
                json.dump(summary, f, indent=2)

            logger.info(f"Analysis complete. Summary saved to {summary_output}")
            return summary

        finally:
            self.close()
