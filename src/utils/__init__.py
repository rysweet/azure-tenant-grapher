"""
Utility modules for Azure Tenant Grapher.

This package contains utility classes and functions that provide common
functionality across the application.
"""

from .neo4j_credentials import (
    Neo4jCredentialsError,
    get_neo4j_graph,
    load_neo4j_credentials,
)
from .session_manager import Neo4jSessionManager, create_session_manager, neo4j_session

__all__ = [
    "Neo4jCredentialsError",
    "Neo4jSessionManager",
    "create_session_manager",
    "get_neo4j_graph",
    "load_neo4j_credentials",
    "neo4j_session",
]


def extract_subscription_id_from_resource_id(resource_id: str) -> str:
    """
    Extracts the subscription ID from a full Azure resource ID.
    Example: /subscriptions/1234/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1
    Returns: 1234
    """
    import re

    match = re.search(r"/subscriptions/([^/]+)", resource_id)
    if match:
        return match.group(1)
    return ""
