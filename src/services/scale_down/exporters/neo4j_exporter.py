"""
Neo4j Exporter for Azure Tenant Graph Sampling

This module exports sampled graphs to Cypher statements for Neo4j import.
Includes comprehensive security features to prevent Cypher injection.

Security Features:
- String escaping for all values
- Identifier validation and escaping
- Property name validation
- Safe handling of complex types (lists, dicts)
"""

import json
import logging
import re
from datetime import UTC, datetime
from typing import Any, Dict, Set

import networkx as nx

from src.services.scale_down.exporters.base_exporter import BaseExporter

logger = logging.getLogger(__name__)


def _escape_cypher_string(value: str) -> str:
    """
    Escape special characters for Cypher string literals.

    Args:
        value: String value to escape

    Returns:
        Safely escaped string for Cypher
    """
    # Escape backslashes first
    value = value.replace("\\", "\\\\")
    # Escape double quotes
    value = value.replace('"', '\\"')
    # Escape newlines
    value = value.replace("\n", "\\n")
    value = value.replace("\r", "\\r")
    value = value.replace("\t", "\\t")
    return value


def _escape_cypher_identifier(name: str) -> str:
    """
    Escape identifiers (property names, relationship types) for Cypher.

    Args:
        name: Identifier to escape

    Returns:
        Safely escaped identifier for Cypher
    """
    # If identifier contains only alphanumeric and underscore, no escaping needed
    if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name):
        return name

    # Otherwise, use backticks and escape any backticks in the name
    escaped = name.replace("`", "``")
    return f"`{escaped}`"


def _is_safe_cypher_identifier(name: str) -> bool:
    """Check if identifier is safe without escaping."""
    return bool(re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", name)) and len(name) <= 100


class Neo4jExporter(BaseExporter):
    """
    Export sampled graph to Neo4j Cypher statements.

    Creates properly escaped Cypher statements for importing into a new database.
    Includes comprehensive security features to prevent Cypher injection.

    Note: This creates Cypher statements in a file.
    Actual database creation would require separate Neo4j instance.
    """

    def __init__(self) -> None:
        """Initialize the Neo4j exporter."""
        self.logger = logging.getLogger(__name__)

    async def export(
        self,
        node_ids: Set[str],
        node_properties: Dict[str, Dict[str, Any]],
        sampled_graph: nx.DiGraph[str],
        output_path: str,
    ) -> None:
        """
        Export sample to Neo4j Cypher statements.

        Creates properly escaped Cypher statements for importing into a new database.

        Args:
            node_ids: Set of node IDs to export
            node_properties: Properties for all nodes
            sampled_graph: NetworkX graph of sample
            output_path: Output file path

        Raises:
            ValueError: If export fails
            Exception: If unexpected error occurs

        Example:
            >>> exporter = Neo4jExporter()
            >>> await exporter.export(
            ...     sampled_ids,
            ...     node_props,
            ...     G_sampled,
            ...     "/tmp/sample.cypher"
            ... )
        """
        self.logger.info(str(f"Exporting sample to Neo4j Cypher at {output_path}"))

        cypher_statements = []

        # Add header with metadata
        cypher_statements.append("// Neo4j Import Cypher Statements")
        cypher_statements.append(f"// Generated: {datetime.now(UTC).isoformat()}")
        cypher_statements.append(f"// Nodes: {len(node_ids)}")
        cypher_statements.append(f"// Relationships: {sampled_graph.number_of_edges()}")
        cypher_statements.append("// WARNING: Review this file before executing")
        cypher_statements.append("")

        # Create nodes with proper escaping
        cypher_statements.append("// Create nodes")

        for node_id in sorted(node_ids):  # Sort for deterministic output
            if node_id not in node_properties:
                continue

            props = node_properties[node_id]

            # Build property map with proper escaping
            prop_strings = []
            for key, value in props.items():
                # Validate and escape property name
                if not _is_safe_cypher_identifier(key):
                    self.logger.warning(
                        str(f"Skipping property with unsafe name: {key}")
                    )
                    continue

                safe_key = _escape_cypher_identifier(key)

                # Handle different value types
                if value is None:
                    # Skip null values
                    continue
                elif isinstance(value, str):
                    # Escape string values
                    safe_value = _escape_cypher_string(value)
                    prop_strings.append(f'{safe_key}: "{safe_value}"')
                elif isinstance(value, bool):
                    # Use lowercase boolean literals
                    prop_strings.append(f"{safe_key}: {str(value).lower()}")
                elif isinstance(value, (int, float)):
                    # Numbers are safe
                    prop_strings.append(f"{safe_key}: {json.dumps(value)}")
                elif isinstance(value, (list, dict)):
                    # Use JSON representation for complex types
                    json_value = json.dumps(value)
                    safe_value = _escape_cypher_string(json_value)
                    prop_strings.append(f'{safe_key}: "{safe_value}"')
                else:
                    # Skip unsupported types
                    self.logger.warning(
                        f"Skipping property {key} with unsupported type {type(value)}"
                    )
                    continue

            props_str = ", ".join(prop_strings) if prop_strings else ""

            # Get resource type for label
            resource_type = props.get("type", "Resource")

            # Extract last part of resource type for label
            # e.g., "Microsoft.Compute/virtualMachines" -> "virtualMachines"
            if "/" in resource_type:
                label_name = resource_type.split("/")[-1]
            else:
                label_name = "Resource"

            # Validate and escape label
            safe_label = _escape_cypher_identifier(label_name)

            # Generate CREATE statement
            cypher_statements.append(
                f"CREATE (:{safe_label}:Resource {{{props_str}}});"
            )

        cypher_statements.append("")

        # Create relationships with proper escaping
        cypher_statements.append("// Create relationships")

        for source, target, data in sampled_graph.edges(data=True):
            # Escape node IDs
            safe_source = _escape_cypher_string(source)
            safe_target = _escape_cypher_string(target)

            # Get and validate relationship type
            rel_type = data.get("relationship_type", "RELATED_TO")
            if not _is_safe_cypher_identifier(rel_type):
                self.logger.warning(
                    f"Skipping relationship with unsafe type: {rel_type}"
                )
                continue

            safe_rel_type = _escape_cypher_identifier(rel_type)

            # Generate MATCH + CREATE statement
            cypher_statements.append(
                f'MATCH (a:Resource {{id: "{safe_source}"}}), '
                f'(b:Resource {{id: "{safe_target}"}}) '
                f"CREATE (a)-[:{safe_rel_type}]->(b);"
            )

        # Write to file
        with open(output_path, "w") as f:
            f.write("\n".join(cypher_statements))

        self.logger.info(str(f"Neo4j Cypher export completed: {output_path}"))
