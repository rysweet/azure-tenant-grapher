"""
DFD (Data Flow Diagram) builder strategy for Threat Modeling Agent.
"""

from typing import Any, Dict, List, Tuple, Union

from .models import DFDEdge, DFDNode


class DFDBuilderStrategy:
    """
    Strategy class for building Data Flow Diagrams (DFDs) from tenant specifications and graph data.

    The `run()` method processes the provided tenant specification and graph data to produce:
      - A list of DFDNode objects representing the nodes in the DFD.
      - A list of DFDEdge objects representing the edges (data flows) in the DFD.
      - A Mermaid diagram string representing the DFD.

    This class is intended for use within the Threat Modeling Agent and does not perform any CLI or print operations.
    """

    @staticmethod
    def run(
        tenant_spec: Union[Dict[str, Any], str],
        graph_data: Dict[str, Any],
    ) -> Tuple[List[DFDNode], List[DFDEdge], str]:
        """
        Build a DFD artifact (nodes, edges, and Mermaid diagram) from tenant spec and graph data.

        Args:
            tenant_spec: The loaded tenant specification (dict or Markdown string).
            graph_data: The loaded graph data (expected as dict with 'nodes' and 'edges').

        Returns:
            Tuple containing:
                - List of DFDNode objects.
                - List of DFDEdge objects.
                - Mermaid diagram string.
        """
        # Parse nodes and edges from graph_data
        nodes_raw = graph_data.get("nodes", [])
        edges_raw = graph_data.get("edges", [])
        print(str(f"[DFDBuilderStrategy] nodes_raw: {nodes_raw}"))
        print(str(f"[DFDBuilderStrategy] edges_raw: {edges_raw}"))

        # Classify nodes
        def classify_node(node: Dict[str, Any]) -> str:
            t = (node.get("type") or "").lower()
            label = (node.get("label") or node.get("id") or "").lower()
            if (
                "database" in t
                or "db" in t
                or "sql" in t
                or "storage" in t
                or "vault" in t
            ):
                return "datastore"
            elif (
                "user" in t
                or "external" in t
                or "aad" in t
                or "identity" in t
                or "client" in t
                or "interactor" in t
            ):
                return "external"
            elif (
                "process" in t
                or "app" in t
                or "service" in t
                or "function" in t
                or "api" in t
            ):
                return "process"
            # Fallback: try label
            if (
                "database" in label
                or "db" in label
                or "sql" in label
                or "storage" in label
                or "vault" in label
            ):
                return "datastore"
            elif (
                "user" in label
                or "external" in label
                or "aad" in label
                or "identity" in label
                or "client" in label
                or "interactor" in label
            ):
                return "external"
            elif (
                "process" in label
                or "app" in label
                or "service" in label
                or "function" in label
                or "api" in label
            ):
                return "process"
            return "process"  # Default to process

        dfd_nodes: List[DFDNode] = []
        dfd_edges: List[DFDEdge] = []
        mermaid_lines = ["flowchart TD"]
        node_ids = set()

        # Build DFDNode objects and Mermaid node lines
        for node in nodes_raw:
            node_id = node.get("id", "unknown")
            label = node.get("label", node_id)
            node_type = classify_node(node)
            node_ids.add(node_id)
            dfd_nodes.append(DFDNode(id=node_id, label=label, type=node_type))
            if node_type == "datastore":
                mermaid_lines.append(f'    {node_id}[(("{label}"))]')
            elif node_type == "external":
                mermaid_lines.append(f"    {node_id}(({label}))")
            else:  # process
                mermaid_lines.append(f'    {node_id}["{label}"]')

        # Build DFDEdge objects and Mermaid edge lines
        for edge in edges_raw:
            src = edge.get("source", "unknown")
            dst = edge.get("target", "unknown")
            label = edge.get("label", "")
            if src not in node_ids or dst not in node_ids:
                continue  # Skip edges referencing unknown nodes
            dfd_edges.append(DFDEdge(source=src, target=dst, label=label))
            if label:
                mermaid_lines.append(f"    {src} -->|{label}| {dst}")
            else:
                mermaid_lines.append(f"    {src} --> {dst}")

        if not nodes_raw:
            mermaid_lines.append('    A["No nodes found"]')

        mermaid_diagram = "\n".join(mermaid_lines)
        return dfd_nodes, dfd_edges, mermaid_diagram
