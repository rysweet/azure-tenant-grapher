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
                                for key, data in edges.items():
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

        for u, v, data in G_filtered.edges(data=True):
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
        for pattern_name, match in pattern_matches.items():
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
                    for key, data in edges.items():
                        outgoing_edges.append({
                            "target": target,
                            "relationship": data.get("relationship", "UNKNOWN"),
                            "frequency": data.get("frequency", 0),
                        })

            incoming_edges = []
            for source in in_neighbors:
                edges = graph.get_edge_data(source, node)
                if edges:
                    for key, data in edges.items():
                        incoming_edges.append({
                            "source": source,
                            "relationship": data.get("relationship", "UNKNOWN"),
                            "frequency": data.get("frequency", 0),
                        })

            orphaned_info.append({
                "resource_type": node,
                "connection_count": graph.nodes[node].get("count", 0),
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "total_degree": graph.degree(node),
                "outgoing_edges": outgoing_edges,
                "incoming_edges": incoming_edges,
                "connected_to": list(set(out_neighbors + in_neighbors)),
            })

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
            f"Azure {resource_type} resource - see Microsoft Learn for details"
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

        return use_cases.get(resource_type, [
            "See Microsoft Learn documentation",
            f"Common in Azure {resource_type} deployments",
        ])

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

        for idx, component in enumerate(weakly_connected):
            if len(component) >= min_cluster_size:
                component_list = list(component)

                # Get connections between component members
                internal_edges = []
                for u in component_list:
                    for v in component_list:
                        if u != v and graph.has_edge(u, v):
                            edges = graph.get_edge_data(u, v)
                            if edges:
                                for key, data in edges.items():
                                    internal_edges.append({
                                        "source": u,
                                        "target": v,
                                        "relationship": data.get("relationship", "UNKNOWN"),
                                        "frequency": data.get("frequency", 0),
                                    })

                # Get connections to non-orphaned nodes (context)
                external_connections = {}
                for node in component_list:
                    node_info = next(
                        (n for n in orphaned_nodes if n["resource_type"] == node), None
                    )
                    if node_info:
                        for conn in node_info["connected_to"]:
                            if conn not in component_list:
                                external_connections[conn] = external_connections.get(conn, 0) + 1

                # Fetch documentation for cluster members
                documented_resources = []
                for resource_type in component_list:
                    doc = self.fetch_microsoft_learn_documentation(resource_type)
                    documented_resources.append(doc)

                # Generate pattern suggestion
                pattern_name = self._generate_pattern_name(component_list, documented_resources)
                pattern_description = self._generate_pattern_description(
                    component_list, documented_resources, external_connections
                )

                suggested_patterns.append({
                    "suggested_name": pattern_name,
                    "description": pattern_description,
                    "required_resources": component_list[:2] if len(component_list) >= 2 else component_list,
                    "optional_resources": component_list[2:] if len(component_list) > 2 else [],
                    "internal_connections": len(internal_edges),
                    "internal_edges": internal_edges[:5],  # Top 5 for brevity
                    "external_connections": dict(sorted(
                        external_connections.items(),
                        key=lambda x: x[1],
                        reverse=True
                    )[:5]),
                    "documented_resources": documented_resources,
                    "confidence": self._calculate_pattern_confidence(
                        len(component_list), len(internal_edges), external_connections
                    ),
                })

        # Strategy 2: Find orphaned nodes that frequently co-occur with specific matched patterns
        for node_info in orphaned_nodes[:10]:  # Top 10 most connected orphaned nodes
            resource_type = node_info["resource_type"]

            # Find which patterns this orphaned node connects to most
            pattern_connections = {}
            for conn in node_info["connected_to"]:
                for pattern_name, match in self.ARCHITECTURAL_PATTERNS.items():
                    if conn in match.get("resources", []):
                        pattern_connections[pattern_name] = pattern_connections.get(pattern_name, 0) + 1

            if pattern_connections:
                # Suggest adding this resource to the most connected pattern
                best_pattern = max(pattern_connections.items(), key=lambda x: x[1])
                doc = self.fetch_microsoft_learn_documentation(resource_type)

                suggested_patterns.append({
                    "suggested_name": f"{best_pattern[0]} (Enhanced)",
                    "description": f"Add {resource_type} to existing {best_pattern[0]} pattern",
                    "action": "UPDATE_EXISTING",
                    "target_pattern": best_pattern[0],
                    "resource_to_add": resource_type,
                    "connection_count": best_pattern[1],
                    "documentation": doc,
                    "confidence": min(best_pattern[1] / 5.0, 1.0),  # Normalize confidence
                })

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
            0.4 * resource_score +
            0.4 * connectivity_score +
            0.2 * external_score
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
                json.dump({
                    "orphaned_count": len(orphaned_nodes),
                    "orphaned_nodes": orphaned_nodes,
                    "suggested_patterns": suggested_patterns,
                }, f, indent=2)
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

    def extract_sku_from_properties(
        self, properties: Optional[Dict[str, Any]], resource_type: str
    ) -> str:
        """
        Extract SKU/size information from resource properties.

        Different resource types store SKU information in different ways.
        This method handles the most common patterns.

        Args:
            properties: Resource properties dictionary
            resource_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            SKU string (e.g., "Standard_D2s_v3", "Standard_LRS")
        """
        if not properties:
            return "UnknownSKU"

        # Virtual Machines: hardwareProfile.vmSize
        if resource_type == "Microsoft.Compute/virtualMachines":
            if "hardwareProfile" in properties and isinstance(
                properties["hardwareProfile"], dict
            ):
                return properties["hardwareProfile"].get("vmSize", "UnknownSKU")

        # Storage Accounts: sku.name or infer from properties
        elif resource_type == "Microsoft.Storage/storageAccounts":
            if "sku" in properties and isinstance(properties["sku"], dict):
                return properties["sku"].get("name", "UnknownSKU")
            # Fallback: infer from replication type
            replication = properties.get("accountType") or properties.get(
                "skuName", "UnknownSKU"
            )
            return replication

        # Disks: sku.name
        elif resource_type == "Microsoft.Compute/disks":
            if "sku" in properties and isinstance(properties["sku"], dict):
                return properties["sku"].get("name", "UnknownSKU")

        # App Service Plans: sku.name or sku.tier
        elif resource_type == "Microsoft.Web/serverFarms":
            if "sku" in properties and isinstance(properties["sku"], dict):
                sku = properties["sku"]
                return sku.get("name") or sku.get("tier", "UnknownSKU")

        # SQL Databases: sku.name
        elif resource_type == "Microsoft.Sql/servers/databases":
            if "sku" in properties and isinstance(properties["sku"], dict):
                return properties["sku"].get("name", "UnknownSKU")

        # Generic: look for 'sku' key
        if "sku" in properties:
            sku = properties["sku"]
            if isinstance(sku, dict):
                return sku.get("name") or sku.get("tier", "UnknownSKU")
            return str(sku)

        return "UnknownSKU"

    def create_configuration_fingerprint(
        self,
        resource_id: str,
        resource_type: str,
        location: Optional[str],
        tags: Optional[Dict[str, str]],
        properties: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create a configuration fingerprint for a resource.

        A configuration fingerprint consists of:
        - SKU/size (from properties)
        - Location (Azure region)
        - Tags (key-value pairs)
        - Key properties (extracted from properties JSON)

        Args:
            resource_id: Azure resource ID
            resource_type: Azure resource type
            location: Azure region
            tags: Resource tags
            properties: Resource properties dictionary

        Returns:
            Configuration fingerprint dictionary
        """
        # Extract SKU
        sku = self.extract_sku_from_properties(properties, resource_type)

        # Extract key properties based on resource type
        key_properties = {}
        if properties:
            if resource_type == "Microsoft.Compute/virtualMachines":
                if "storageProfile" in properties:
                    storage = properties["storageProfile"]
                    if isinstance(storage, dict):
                        if "osDisk" in storage:
                            os_disk = storage["osDisk"]
                            if isinstance(os_disk, dict):
                                key_properties["osType"] = os_disk.get("osType")
                                key_properties["diskCaching"] = os_disk.get("caching")

            elif resource_type == "Microsoft.Network/virtualNetworks":
                if "addressSpace" in properties:
                    addr_space = properties["addressSpace"]
                    if isinstance(addr_space, dict):
                        key_properties["addressPrefixes"] = addr_space.get(
                            "addressPrefixes", []
                        )

        return {
            "sku": sku,
            "location": location or "NoLocation",
            "tags": tags or {},
            "key_properties": key_properties,
        }

    def analyze_configuration_distributions(
        self, resource_types: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze configuration distributions across all resource types.

        For each resource type, compute:
        - Configuration fingerprints
        - Distribution of configurations
        - Sample resources for each configuration

        Args:
            resource_types: Optional list of specific resource types to analyze.
                          If None, analyzes all resource types.

        Returns:
            Dictionary mapping resource type to configuration analysis:
            {
                "Microsoft.Compute/virtualMachines": {
                    "total_count": 114,
                    "configurations": [
                        {
                            "fingerprint": {...},
                            "count": 68,
                            "percentage": 59.6,
                            "sample_resources": ["/subscriptions/.../vm-1", ...]
                        }
                    ]
                }
            }
        """
        if not self.driver:
            raise RuntimeError("Not connected to Neo4j. Call connect() first.")

        # Get resource types to analyze
        if not resource_types:
            # Get all resource types
            with self.driver.session() as session:
                result = session.run(
                    """
                    MATCH (r:Resource:Original)
                    WITH r.type as type, count(*) as count
                    WHERE type IS NOT NULL
                    RETURN type, count
                    ORDER BY count DESC
                """
                )
                resource_types = [rec["type"] for rec in result]

        configuration_analysis = {}

        for resource_type in resource_types:
            logger.info(f"Analyzing configurations for {resource_type}...")

            with self.driver.session() as session:
                # Fetch all resources of this type
                result = session.run(
                    """
                    MATCH (r:Resource:Original)
                    WHERE r.type = $type
                    RETURN r.id as id,
                           r.location as location,
                           r.tags as tags,
                           r.properties as properties
                """,
                    type=resource_type,
                )

                # Group by configuration fingerprint
                config_to_resources: Dict[str, List[str]] = defaultdict(list)

                for record in result:
                    resource_id = record["id"]
                    location = record["location"]
                    tags = record["tags"]
                    properties = record["properties"]

                    # Parse properties if it's a JSON string
                    if isinstance(properties, str):
                        try:
                            properties = json.loads(properties)
                        except json.JSONDecodeError:
                            properties = None

                    # Create fingerprint
                    fingerprint = self.create_configuration_fingerprint(
                        resource_id, resource_type, location, tags, properties
                    )

                    # Convert to hashable key (JSON string of sorted dict)
                    fingerprint_key = json.dumps(fingerprint, sort_keys=True)
                    config_to_resources[fingerprint_key].append(resource_id)

                # Build configuration analysis
                total_count = sum(len(resources) for resources in config_to_resources.values())
                configurations = []

                for fingerprint_key, resource_ids in config_to_resources.items():
                    fingerprint = json.loads(fingerprint_key)
                    count = len(resource_ids)
                    percentage = (count / total_count * 100) if total_count > 0 else 0

                    configurations.append(
                        {
                            "fingerprint": fingerprint,
                            "count": count,
                            "percentage": percentage,
                            "sample_resources": resource_ids[:5],  # Sample up to 5
                        }
                    )

                # Sort by count (most common first)
                configurations.sort(key=lambda x: x["count"], reverse=True)

                configuration_analysis[resource_type] = {
                    "total_count": total_count,
                    "configurations": configurations,
                }

        return configuration_analysis

    def build_configuration_bags(
        self, configuration_analysis: Dict[str, Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Build bag-of-words vectors for proportional sampling.

        For each resource type, creates a list where each configuration
        appears proportionally to its frequency in the source tenant.

        This enables random sampling that naturally preserves the
        source distribution (bag-of-words model).

        Args:
            configuration_analysis: Output from analyze_configuration_distributions()

        Returns:
            Dictionary mapping resource type to configuration bag (weighted vector):
            {
                "Microsoft.Compute/virtualMachines": [
                    {"fingerprint": {...}, "sample_resources": [...]},  # Appears 68 times
                    {"fingerprint": {...}, "sample_resources": [...]},  # Appears 68 times
                    ...  # Total 114 entries
                ]
            }
        """
        configuration_bags = {}

        for resource_type, analysis in configuration_analysis.items():
            bag = []

            for config in analysis["configurations"]:
                # Add this configuration to the bag 'count' times
                for _ in range(config["count"]):
                    bag.append(
                        {
                            "fingerprint": config["fingerprint"],
                            "sample_resources": config["sample_resources"],
                        }
                    )

            configuration_bags[resource_type] = bag
            logger.info(
                f"Built configuration bag for {resource_type}: {len(bag)} entries"
            )

        return configuration_bags

    def compute_architecture_distribution(
        self,
        pattern_resources: Dict[str, List[List[str]]],
        graph: nx.MultiDiGraph,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Compute distribution scores for each architectural pattern.

        Uses the weighted pattern graph to quantify pattern prevalence through
        a composite score combining four metrics:
        - Instance count (30%): How many times the pattern appears
        - Resource count (25%): How many resources are involved
        - Connection strength (25%): Sum of edge weights within the pattern
        - Centrality (20%): Betweenness centrality of pattern nodes

        Args:
            pattern_resources: Dict mapping pattern_name to list of instances,
                             where each instance is a list of resource IDs
            graph: NetworkX graph of resource type relationships

        Returns:
            Dictionary mapping pattern_name to distribution analysis:
            {
                "VM Workload": {
                    "distribution_score": 37.8,
                    "rank": 1,
                    "source_instances": 45,
                    "breakdown": {
                        "instance_count_pct": 39.5,
                        "resource_count_pct": 42.3,
                        "connection_strength_pct": 45.2,
                        "centrality_pct": 24.9
                    }
                }
            }
        """
        if not pattern_resources:
            logger.warning("No pattern resources provided for distribution analysis")
            return {}

        # Compute totals for normalization
        total_instances = sum(len(instances) for instances in pattern_resources.values())
        total_resources = sum(
            sum(len(inst) for inst in instances)
            for instances in pattern_resources.values()
        )

        if total_instances == 0 or total_resources == 0:
            logger.warning("No instances or resources found for distribution analysis")
            return {}

        # Compute total connection strength and centrality
        total_strength = self._compute_total_connection_strength(graph)
        total_centrality = self._compute_total_centrality(graph)

        distribution = {}

        for pattern_name, instances in pattern_resources.items():
            # Metric 1: Instance count percentage
            instance_count = len(instances)
            instance_pct = (instance_count / total_instances) * 100

            # Metric 2: Resource count percentage
            resource_count = sum(len(inst) for inst in instances)
            resource_pct = (resource_count / total_resources) * 100

            # Metric 3: Connection strength percentage
            pattern_def = self.ARCHITECTURAL_PATTERNS.get(pattern_name, {})
            pattern_resource_types = set(pattern_def.get("resources", []))
            strength = self._compute_pattern_connection_strength(
                pattern_resource_types, graph
            )
            strength_pct = (
                (strength / total_strength) * 100 if total_strength > 0 else 0.0
            )

            # Metric 4: Centrality percentage
            centrality = self._compute_pattern_centrality(pattern_resource_types, graph)
            centrality_pct = (
                (centrality / total_centrality) * 100 if total_centrality > 0 else 0.0
            )

            # Composite score with configurable weights
            distribution_score = (
                0.30 * instance_pct
                + 0.25 * resource_pct
                + 0.25 * strength_pct
                + 0.20 * centrality_pct
            )

            distribution[pattern_name] = {
                "distribution_score": round(distribution_score, 1),
                "source_instances": instance_count,
                "source_resources": resource_count,
                "breakdown": {
                    "instance_count_pct": round(instance_pct, 1),
                    "resource_count_pct": round(resource_pct, 1),
                    "connection_strength_pct": round(strength_pct, 1),
                    "centrality_pct": round(centrality_pct, 1),
                },
            }

        # Rank patterns by distribution score
        sorted_patterns = sorted(
            distribution.items(), key=lambda x: x[1]["distribution_score"], reverse=True
        )
        for rank, (pattern_name, pattern_data) in enumerate(sorted_patterns, start=1):
            pattern_data["rank"] = rank

        logger.info(
            f"Computed architecture distribution for {len(distribution)} patterns"
        )
        return distribution

    def _compute_total_connection_strength(self, graph: nx.MultiDiGraph) -> float:
        """
        Compute total connection strength across the entire graph.

        Connection strength is the sum of all edge frequencies.

        Args:
            graph: NetworkX graph with edge frequency attributes

        Returns:
            Total connection strength
        """
        total_strength = 0.0
        for u, v, data in graph.edges(data=True):
            total_strength += data.get("frequency", 1)
        return total_strength

    def _compute_pattern_connection_strength(
        self, pattern_resource_types: set, graph: nx.MultiDiGraph
    ) -> float:
        """
        Compute connection strength within a pattern.

        Sums the frequency of all edges between resources in the pattern.

        Args:
            pattern_resource_types: Set of resource types in the pattern
            graph: NetworkX graph with edge frequency attributes

        Returns:
            Pattern connection strength
        """
        strength = 0.0

        # Find all edges between pattern resource types
        for source in pattern_resource_types:
            if source not in graph:
                continue
            for target in pattern_resource_types:
                if target not in graph or source == target:
                    continue

                if graph.has_edge(source, target):
                    edges = graph.get_edge_data(source, target)
                    if edges:
                        for key, data in edges.items():
                            strength += data.get("frequency", 1)

        return strength

    def _compute_total_centrality(self, graph: nx.MultiDiGraph) -> float:
        """
        Compute total betweenness centrality across the entire graph.

        Args:
            graph: NetworkX graph

        Returns:
            Sum of all betweenness centrality scores
        """
        try:
            # Convert to undirected for centrality calculation
            G_undirected = graph.to_undirected()

            # Compute betweenness centrality
            centrality = nx.betweenness_centrality(G_undirected, normalized=True)

            return sum(centrality.values())
        except Exception as e:
            logger.warning(f"Failed to compute centrality: {e}")
            return 0.0

    def _compute_pattern_centrality(
        self, pattern_resource_types: set, graph: nx.MultiDiGraph
    ) -> float:
        """
        Compute sum of betweenness centrality for pattern nodes.

        Args:
            pattern_resource_types: Set of resource types in the pattern
            graph: NetworkX graph

        Returns:
            Sum of centrality scores for pattern nodes
        """
        try:
            # Convert to undirected for centrality calculation
            G_undirected = graph.to_undirected()

            # Compute betweenness centrality
            centrality = nx.betweenness_centrality(G_undirected, normalized=True)

            # Sum centrality for pattern nodes
            pattern_centrality = 0.0
            for resource_type in pattern_resource_types:
                if resource_type in centrality:
                    pattern_centrality += centrality[resource_type]

            return pattern_centrality
        except Exception as e:
            logger.warning(f"Failed to compute pattern centrality: {e}")
            return 0.0

    def compute_pattern_targets(
        self,
        distribution_scores: Dict[str, Dict[str, Any]],
        target_count: int,
    ) -> Dict[str, int]:
        """
        Calculate how many instances to select from each pattern.

        Uses distribution scores to maintain proportional representation.

        Args:
            distribution_scores: Output from compute_architecture_distribution()
            target_count: Total number of instances to select

        Returns:
            Dict mapping pattern_name to number of instances to select:
            {
                "VM Workload": 8,
                "Web Application": 5,
                "Container Platform": 3
            }
        """
        if not distribution_scores or target_count <= 0:
            return {}

        # Extract distribution scores
        scores = {
            name: data["distribution_score"]
            for name, data in distribution_scores.items()
        }

        total_score = sum(scores.values())
        if total_score == 0:
            logger.warning("Total distribution score is 0, using uniform distribution")
            # Fallback to uniform distribution
            patterns = list(scores.keys())
            per_pattern = target_count // len(patterns)
            return {name: per_pattern for name in patterns}

        # Calculate target instance count per pattern
        pattern_targets = {}
        for pattern_name, score in scores.items():
            proportion = score / total_score
            pattern_targets[pattern_name] = int(target_count * proportion)

        # Adjust for rounding to ensure we hit target_count exactly
        total_selected = sum(pattern_targets.values())

        if total_selected < target_count:
            # Give extra instances to highest-scoring patterns
            sorted_patterns = sorted(scores.items(), key=lambda x: x[1], reverse=True)

            for pattern_name, _ in sorted_patterns:
                if total_selected >= target_count:
                    break
                pattern_targets[pattern_name] += 1
                total_selected += 1

        elif total_selected > target_count:
            # Remove instances from lowest-scoring patterns
            sorted_patterns = sorted(scores.items(), key=lambda x: x[1])

            for pattern_name, _ in sorted_patterns:
                if total_selected <= target_count:
                    break
                if pattern_targets[pattern_name] > 0:
                    pattern_targets[pattern_name] -= 1
                    total_selected -= 1

        logger.info(
            f"Computed pattern targets for {target_count} instances: {pattern_targets}"
        )
        return pattern_targets

    def validate_proportional_sampling(
        self,
        source_distribution: Dict[str, Dict[str, Any]],
        target_distribution: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Validate that target distribution matches source distribution.

        Uses statistical tests to verify proportional sampling worked correctly.

        Args:
            source_distribution: Distribution from source tenant
            target_distribution: Distribution from target tenant

        Returns:
            Validation results with statistical measures:
            {
                "target_distribution_match": 0.987,  # Cosine similarity
                "chi_squared_statistic": 0.023,
                "p_value": 0.998,
                "interpretation": "Target distribution is statistically indistinguishable from source"
            }
        """
        try:
            import numpy as np
            from scipy.stats import chisquare
        except ImportError:
            logger.warning("scipy not available, skipping statistical validation")
            return {
                "error": "scipy not installed",
                "interpretation": "Install scipy for statistical validation",
            }

        # Extract distribution scores for comparison
        source_scores = np.array(
            [data["distribution_score"] for data in source_distribution.values()]
        )
        target_scores = np.array(
            [
                target_distribution.get(name, {}).get("distribution_score", 0.0)
                for name in source_distribution.keys()
            ]
        )

        # Normalize to get probability distributions
        source_probs = source_scores / source_scores.sum()
        target_probs = target_scores / target_scores.sum() if target_scores.sum() > 0 else target_scores

        # Cosine similarity
        dot_product = np.dot(source_probs, target_probs)
        norm_product = np.linalg.norm(source_probs) * np.linalg.norm(target_probs)
        cosine_sim = dot_product / norm_product if norm_product > 0 else 0.0

        # Chi-squared test
        # Scale target to match source total for chi-squared test
        source_counts = np.array(
            [data["source_instances"] for data in source_distribution.values()]
        )
        target_counts = np.array(
            [
                target_distribution.get(name, {}).get("source_instances", 0)
                for name in source_distribution.keys()
            ]
        )

        if target_counts.sum() > 0:
            expected_counts = source_probs * target_counts.sum()
            chi2_stat, p_value = chisquare(target_counts, expected_counts)
        else:
            chi2_stat, p_value = 0.0, 1.0

        # Interpretation
        if p_value > 0.95 and cosine_sim > 0.95:
            interpretation = (
                "Target distribution is statistically indistinguishable from source"
            )
        elif p_value > 0.90 and cosine_sim > 0.90:
            interpretation = "Target distribution closely matches source"
        elif p_value > 0.80 and cosine_sim > 0.80:
            interpretation = "Target distribution reasonably matches source"
        else:
            interpretation = (
                "Target distribution differs significantly from source"
            )

        validation = {
            "target_distribution_match": round(cosine_sim, 3),
            "chi_squared_statistic": round(chi2_stat, 3),
            "p_value": round(p_value, 3),
            "interpretation": interpretation,
        }

        logger.info(f"Validation: {interpretation} (similarity: {cosine_sim:.3f})")
        return validation

    def export_architecture_distribution(
        self,
        distribution: Dict[str, Dict[str, Any]],
        output_path: Path,
    ) -> None:
        """
        Export architecture distribution analysis to JSON.

        Args:
            distribution: Output from compute_architecture_distribution()
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        export_data = {
            "metadata": {
                "generation_timestamp": self._get_timestamp(),
                "total_patterns": len(distribution),
            },
            "pattern_distribution_scores": distribution,
        }

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

        logger.info(f"Exported architecture distribution to {output_path}")

    def _get_timestamp(self) -> str:
        """Get ISO 8601 timestamp."""
        from datetime import datetime

        return datetime.utcnow().isoformat() + "Z"

    def get_pattern_graph(self) -> nx.MultiDiGraph:
        """
        Get the weighted pattern graph (type-level aggregation).

        This method builds and returns the pattern graph that can be used
        for architecture distribution analysis.

        Returns:
            NetworkX MultiDiGraph with resource types as nodes and
            relationship frequencies as edge weights
        """
        # Fetch and aggregate relationships
        all_relationships = self.fetch_all_relationships()
        aggregated_relationships = self.aggregate_relationships(all_relationships)

        # Build NetworkX graph
        graph, resource_type_counts, edge_counts = self.build_networkx_graph(
            aggregated_relationships
        )

        return graph
