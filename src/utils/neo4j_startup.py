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