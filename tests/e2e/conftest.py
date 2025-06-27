import pytest
import os
import time
import traceback
import uuid
from src.config_manager import create_neo4j_config_from_env

from testcontainers.neo4j import Neo4jContainer

@pytest.fixture(scope="session")
def unique_container_name():
    """Generate a unique container name for each test session."""
    return f"test-neo4j-{uuid.uuid4().hex[:8]}"

@pytest.fixture(scope="session", autouse=True)
def neo4j_test_container(unique_container_name):
    """Start a Neo4j Docker container for the test session and set env vars."""
    with Neo4jContainer("neo4j:5.18").with_name(unique_container_name) as neo4j:
        bolt_url = neo4j.get_connection_url()
        user = "neo4j"
        # Try all likely password attributes in order
        password = (
            getattr(neo4j, "password", None)
            or getattr(neo4j, "NEO4J_PASSWORD", None)
            or getattr(neo4j, "admin_password", None)
            or "test"
        )
        os.environ["NEO4J_URI"] = bolt_url
        os.environ["NEO4J_USER"] = user
        os.environ["NEO4J_PASSWORD"] = password
        os.environ["NEO4J_CONTAINER_NAME"] = unique_container_name
        print(f"[TEST] Started Neo4j test container at {bolt_url} (user: {user}, password: {password}, container: {unique_container_name})")
        yield

@pytest.fixture(scope="session", autouse=True)
def ensure_neo4j(neo4j_test_container):
    import sys
    print(f"[TEST] Python: {sys.executable}")
    print(f"[TEST] Python version: {sys.version}")
    print(f"[TEST] CWD: {os.getcwd()}")
    print("[TEST] Environment variables (NEO4J_*):")
    for k, v in os.environ.items():
        if k.startswith("NEO4J_"):
            print(f"    {k}={v}")
    config = create_neo4j_config_from_env()
    uri = config.neo4j.uri
    user = config.neo4j.user
    password = config.neo4j.password
    print(f"[TEST] NEO4J_URI: {os.environ.get('NEO4J_URI')}")
    print(f"[TEST] Neo4j URI: {uri}, user: {user}")
    last_error = None
    for attempt in range(20):
        try:
            from neo4j import GraphDatabase
            driver = GraphDatabase.driver(uri, auth=(user, password))
            with driver.session() as session:
                session.run("RETURN 1")
            print("[TEST] Connected to Neo4j at", uri)
            return
        except Exception as e:
            last_error = e
            print(f"[TEST] Attempt {attempt+1}/20: Could not connect to Neo4j: {e}")
            print("[TEST] Full exception info:")
            traceback.print_exc()
            time.sleep(3)
    pytest.skip(f"Could not connect to Neo4j at {uri} after 20 attempts. Last error: {last_error}")

@pytest.fixture(scope="session", autouse=True)
def load_sample_graph(ensure_neo4j):
    """Load sample nodes and relationships into the test Neo4j instance."""
    from neo4j import GraphDatabase
    uri = os.environ["NEO4J_URI"]
    user = os.environ["NEO4J_USER"]
    password = os.environ["NEO4J_PASSWORD"]
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("""
            CREATE (a:TestNode {name: 'A'})-[:CONNECTED_TO]->(b:TestNode {name: 'B'})
        """)
    print("[TEST] Sample graph loaded into Neo4j")