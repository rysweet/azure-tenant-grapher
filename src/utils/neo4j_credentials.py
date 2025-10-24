"""
Neo4j credential management utilities.

This module provides secure credential loading for Neo4j database connections.
All credentials must be provided via environment variables.
"""

import os

from py2neo import Graph


class Neo4jCredentialsError(Exception):
    """Raised when Neo4j credentials are missing or invalid."""

    pass


def load_neo4j_credentials() -> tuple[str, str, str]:
    """
    Load Neo4j credentials from environment variables.

    Returns:
        tuple: (uri, username, password)

    Raises:
        Neo4jCredentialsError: If required credentials are missing

    Environment Variables:
        NEO4J_PASSWORD (required): Neo4j database password
        NEO4J_PORT (required): Neo4j bolt port number
        NEO4J_URI (optional): Complete Neo4j connection URI
            Defaults to bolt://localhost:{NEO4J_PORT}
        NEO4J_USERNAME (optional): Neo4j username (defaults to 'neo4j')

    Example:
        >>> uri, username, password = load_neo4j_credentials()
        >>> graph = Graph(uri, auth=(username, password))
    """
    # Required: Password
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise Neo4jCredentialsError(
            "NEO4J_PASSWORD environment variable is required. "
            "Set it in your .env file or environment."
        )

    # Optional: Username (defaults to neo4j)
    username = os.environ.get("NEO4J_USERNAME", "neo4j")

    # URI construction: use NEO4J_URI if set, otherwise construct from NEO4J_PORT
    uri = os.environ.get("NEO4J_URI")
    if not uri:
        port = os.environ.get("NEO4J_PORT")
        if not port:
            raise Neo4jCredentialsError(
                "Either NEO4J_URI or NEO4J_PORT environment variable is required. "
                "Set NEO4J_PORT in your .env file (e.g., NEO4J_PORT=7687)."
            )
        try:
            port_int = int(port)
            if port_int <= 0 or port_int > 65535:
                raise ValueError("Port must be between 1 and 65535")
        except ValueError as e:
            raise Neo4jCredentialsError(
                f"NEO4J_PORT must be a valid port number: {e}"
            ) from e

        uri = f"bolt://localhost:{port}"

    return uri, username, password


def get_neo4j_graph() -> Graph:
    """
    Create a py2neo Graph instance using credentials from environment variables.

    Returns:
        Graph: Connected py2neo Graph instance

    Raises:
        Neo4jCredentialsError: If credentials are missing or invalid

    Example:
        >>> graph = get_neo4j_graph()
        >>> result = graph.run("MATCH (n) RETURN count(n)").data()
    """
    uri, username, password = load_neo4j_credentials()
    return Graph(uri, auth=(username, password))
