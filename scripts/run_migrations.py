from src.migration_runner import run_pending_migrations
from src.utils.neo4j_startup import ensure_neo4j_running

if __name__ == "__main__":
    ensure_neo4j_running()
    run_pending_migrations()
