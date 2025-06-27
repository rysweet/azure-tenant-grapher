import os
import subprocess
import tempfile
import pytest
from neo4j import GraphDatabase

@pytest.mark.e2e
def test_neo4j_backup_and_restore():
    # Setup connection info from env
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7688")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "azure-grapher-2024")
    container_name = os.environ.get("NEO4J_CONTAINER_NAME", "azure-tenant-grapher-neo4j")

    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        # Count nodes before backup
        before_count = session.run("MATCH (n) RETURN count(n)").single()[0]

    # Create a backup
    with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as tmp:
        backup_path = tmp.name
    try:
        env = os.environ.copy()
        env["NEO4J_URI"] = uri
        env["NEO4J_USER"] = user
        env["NEO4J_PASSWORD"] = password
        env["NEO4J_CONTAINER_NAME"] = container_name

        subprocess.check_call([
            "python", "scripts/cli.py", "backup-db", backup_path, "--container-name", container_name
        ], env=env)

        # Delete all nodes
        with driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
            after_delete_count = session.run("MATCH (n) RETURN count(n)").single()[0]
        assert after_delete_count == 0

        # Restore from backup
        subprocess.check_call([
            "python", "scripts/cli.py", "restore-db", backup_path, "--container-name", container_name
        ], env=env)

        # Count nodes after restore
        with driver.session() as session:
            after_restore_count = session.run("MATCH (n) RETURN count(n)").single()[0]

        assert after_restore_count == before_count
    finally:
        os.remove(backup_path)