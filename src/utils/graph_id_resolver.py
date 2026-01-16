"""Utilities for resolving graph database IDs to actual resource names."""

import logging
import re
from typing import List, Optional, Tuple

from neo4j import AsyncDriver

logger = logging.getLogger(__name__)


def is_graph_database_id(value: str) -> bool:
    """Check if a value appears to be a graph database ID rather than a resource name.

    Graph database IDs typically have formats like:
    - "4:5da3178c-575f-4e20-aa0b-6bd8e843b6d0:630" (Neo4j internal ID)
    - "n10" (simple node ID)
    - Numbers like "123"

    Args:
        value: The value to check

    Returns:
        True if this appears to be a graph ID, False otherwise
    """
    # Check for Neo4j internal ID format (number:uuid:number)
    if re.match(r"^\d+:[a-f0-9-]+:\d+$", value):
        return True

    # Check for simple node ID format (n followed by digits)
    if re.match(r"^n\d+$", value):
        return True

    # Check if it's just a number (could be a node ID)
    if value.isdigit():
        return True

    # Check for colon-separated format that doesn't look like Azure resource
    if ":" in value and not value.startswith("/"):
        return True

    return False


async def resolve_graph_ids_to_names(
    driver: Optional[AsyncDriver], values: List[str], node_type: str = "ResourceGroup"
) -> Tuple[List[str], List[str]]:
    """Resolve graph database IDs to actual resource names.

    Args:
        driver: Neo4j driver instance
        values: List of values that might be graph IDs or actual names
        node_type: The type of node to query (default: ResourceGroup)

    Returns:
        Tuple of (resolved_names, unresolved_ids)
        - resolved_names: List of actual resource names
        - unresolved_ids: List of IDs that couldn't be resolved
    """
    if not driver:
        logger.warning("No Neo4j driver available for ID resolution")
        return [], values

    resolved_names = []
    unresolved_ids = []

    for value in values:
        if is_graph_database_id(value):
            # Try to resolve the graph ID to an actual name
            try:
                async with driver.session() as session:
                    # Try different query approaches based on ID format
                    queries = []

                    # For Neo4j internal IDs
                    if ":" in value:
                        # Extract the UUID part if present
                        parts = value.split(":")
                        if len(parts) >= 2:
                            uuid_part = parts[1]
                            queries.append(
                                f"MATCH (n:{node_type}) WHERE n.id CONTAINS $id_part RETURN n.name AS name",
                                {"id_part": uuid_part},  # type: ignore[misc]
                            )

                    # For numeric IDs
                    if value.isdigit():
                        queries.append(
                            f"MATCH (n:{node_type}) WHERE ID(n) = $id RETURN n.name AS name",
                            {"id": int(value)},  # type: ignore[misc]
                        )

                    # Try to match by the full ID string
                    queries.append(
                        f"MATCH (n:{node_type}) WHERE n.id = $id OR n.graph_id = $id RETURN n.name AS name",
                        {"id": value},  # type: ignore[misc]
                    )

                    # Try each query until we find a match
                    name_found = None
                    for query, params in queries:
                        result = await session.run(query, params)
                        record = await result.single()
                        if record and record.get("name"):
                            name_found = record["name"]
                            break

                    if name_found:
                        resolved_names.append(name_found)
                        logger.info(
                            f"Resolved graph ID '{value}' to name '{name_found}'"
                        )
                    else:
                        unresolved_ids.append(value)
                        logger.warning(
                            f"Could not resolve graph ID '{value}' to a name"
                        )

            except Exception as e:
                logger.error(f"Error resolving graph ID '{value}': {e}")
                unresolved_ids.append(value)
        else:
            # It's already a name, not a graph ID
            resolved_names.append(value)

    return resolved_names, unresolved_ids


def split_and_detect_ids(value: str) -> Tuple[List[str], List[str]]:
    """Split a comma-separated string and detect which values are graph IDs.

    Args:
        value: Comma-separated string of values

    Returns:
        Tuple of (regular_values, graph_ids)
    """
    if not value:
        return [], []

    values = [v.strip() for v in value.split(",") if v.strip()]
    regular_values = []
    graph_ids = []

    for v in values:
        if is_graph_database_id(v):
            graph_ids.append(v)
        else:
            regular_values.append(v)

    return regular_values, graph_ids
