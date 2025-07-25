import os

from src.container_manager import Neo4jContainerManager

_manager = Neo4jContainerManager()


def ensure_neo4j_running() -> None:
    """
    Idempotently ensure a Neo4j instance is running and reachable.
    Safe to call multiple times or concurrently.
    Raises RuntimeError if the database cannot be reached after the
    container manager's retry logic.
    """
    _manager.setup_neo4j()
    port_str = os.environ.get("NEO4J_PORT")
    if not port_str:
        raise RuntimeError(
            "NEO4J_PORT must be set in the environment (see .env.example)"
        )
    # _manager.setup_neo4j() is responsible for ensuring Neo4j is available on the correct port.
    # If Neo4j is not available, this should raise an error with a clear message.
