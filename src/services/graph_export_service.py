"""Graph Export Service for visualization-friendly formats.

Philosophy:
- Single responsibility: Data transformation only (no business logic)
- Ruthless simplicity: 3 export formats, NetworkX intermediary
- Zero-BS implementation: Every method works, validates output

Public API (the "studs"):
    GraphExportService: Main export service class
    export_abstraction: Export to GraphML/JSON/DOT

Dependencies:
- networkx>=3.0 (graph data structure)
- pydot>=3.0.0 (DOT format writer)
- src.utils.session_manager.Neo4jSessionManager (Neo4j connection)

Supports:
- GraphML: For Gephi, Cytoscape, yEd
- JSON: For D3.js, custom visualization tools
- DOT: For Graphviz rendering

Usage:
    ```python
    from src.services.graph_export_service import GraphExportService
    from src.utils.session_manager import Neo4jSessionManager

    session_manager = Neo4jSessionManager(neo4j_config)
    service = GraphExportService(session_manager)

    result = service.export_abstraction(
        tenant_id="abc-123",
        output_path=Path("graph.graphml"),
        format="graphml"
    )
    ```

Issue #508: MCP Server and Visualization Export Integration
"""

import json
from pathlib import Path
from typing import Any, Dict

import networkx as nx
import structlog

from src.utils.session_manager import Neo4jSessionManager

logger = structlog.get_logger(__name__)


class GraphExportService:
    """Service for exporting graph abstractions to various formats.

    Exports graph abstractions to visualization-friendly formats:
    - GraphML (Gephi, Cytoscape)
    - JSON (D3.js, custom tools)
    - DOT (Graphviz)
    """

    def __init__(self, session_manager: Neo4jSessionManager) -> None:
        """Initialize export service.

        Args:
            session_manager: Neo4j session manager
        """
        self.session_manager = session_manager

    def export_abstraction(
        self,
        tenant_id: str,
        output_path: Path,
        format: str = "graphml",
        include_relationships: bool = True,
    ) -> Dict[str, Any]:
        """Export graph abstraction to file.

        Args:
            tenant_id: Tenant to export
            output_path: Output file path
            format: Export format (graphml, json, dot)
            include_relationships: Include edges between resources

        Returns:
            Dictionary with export metadata:
                - success: bool
                - format: str
                - output_path: str
                - node_count: int
                - edge_count: int

        Raises:
            ValueError: If format is unsupported or tenant not found
        """
        format = format.lower()
        if format not in ("graphml", "json", "dot"):
            raise ValueError(f"Unsupported format: {format}. Use graphml, json, or dot")

        # Build NetworkX graph from Neo4j
        graph = self._build_networkx_graph(tenant_id, include_relationships)

        if graph.number_of_nodes() == 0:
            raise ValueError(f"No abstraction found for tenant {tenant_id}")

        # Export to format
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "graphml":
            nx.write_graphml(graph, str(output_path))
        elif format == "json":
            self._export_to_json(graph, output_path)
        elif format == "dot":
            nx.drawing.nx_pydot.write_dot(graph, str(output_path))

        logger.info(
            f"Exported {graph.number_of_nodes()} nodes to {format}",
            tenant_id=tenant_id,
            format=format,
            output_path=str(output_path),
        )

        return {
            "success": True,
            "format": format,
            "output_path": str(output_path),
            "node_count": graph.number_of_nodes(),
            "edge_count": graph.number_of_edges(),
        }

    def _build_networkx_graph(
        self, tenant_id: str, include_relationships: bool
    ) -> nx.DiGraph:
        """Build NetworkX graph from Neo4j abstraction.

        Args:
            tenant_id: Tenant to export
            include_relationships: Include edges between resources

        Returns:
            NetworkX directed graph
        """
        graph = nx.DiGraph()

        with self.session_manager.session() as session:
            # Add nodes (sampled resources)
            node_result = session.run(
                """
                MATCH (sample:Resource)-[:SAMPLE_OF]->(source:Resource)
                WHERE source.tenant_id = $tenant_id
                RETURN source.id as id,
                       source.name as name,
                       source.type as type,
                       source.location as location,
                       source.tenant_id as tenant_id
                """,
                tenant_id=tenant_id,
            )

            for record in node_result:
                # Use 'label' instead of 'name' to avoid pydot conflict
                # (pydot.Node uses 'name' as constructor parameter)
                graph.add_node(
                    record["id"],
                    label=record["name"] or "",
                    type=record["type"] or "",
                    location=record["location"] or "",
                    tenant_id=record["tenant_id"] or "",
                )

            # Add edges (relationships between sampled resources)
            if include_relationships:
                edge_result = session.run(
                    """
                    MATCH (sample1:Resource)-[:SAMPLE_OF]->(source1:Resource)
                    MATCH (sample2:Resource)-[:SAMPLE_OF]->(source2:Resource)
                    MATCH (source1)-[r]->(source2)
                    WHERE source1.tenant_id = $tenant_id
                      AND source2.tenant_id = $tenant_id
                    RETURN source1.id as source_id,
                           source2.id as target_id,
                           type(r) as rel_type
                    """,
                    tenant_id=tenant_id,
                )

                for record in edge_result:
                    graph.add_edge(
                        record["source_id"],
                        record["target_id"],
                        relationship=record["rel_type"],
                    )

        return graph

    def _export_to_json(self, graph: nx.DiGraph, output_path: Path) -> None:
        """Export graph to D3.js-compatible JSON format.

        Format:
        {
            "nodes": [{"id": "...", "name": "...", "type": "..."}],
            "links": [{"source": "...", "target": "...", "relationship": "..."}]
        }

        Args:
            graph: NetworkX graph to export
            output_path: Output file path
        """
        nodes = [{"id": node_id, **graph.nodes[node_id]} for node_id in graph.nodes()]

        links = [
            {"source": source, "target": target, **graph.edges[source, target]}
            for source, target in graph.edges()
        ]

        output = {
            "nodes": nodes,
            "links": links,
            "metadata": {
                "node_count": len(nodes),
                "edge_count": len(links),
            },
        }

        output_path.write_text(json.dumps(output, indent=2))


__all__ = ["GraphExportService"]
