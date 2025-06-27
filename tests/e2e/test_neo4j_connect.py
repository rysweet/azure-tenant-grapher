import pytest
import os
from src.config_manager import create_neo4j_config_from_env

def test_neo4j_connect_config():
    # Use the same config loading as the rest of the project
    config = create_neo4j_config_from_env()
    uri = config.neo4j.uri
    user = config.neo4j.user
    password = config.neo4j.password
    print(f"[TEST] Python: {__import__('sys').executable}")
    print(f"[TEST] NEO4J_URI: {os.environ.get('NEO4J_URI')}")
    print(f"[TEST] Neo4j URI: {uri}, user: {user}")
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(uri, auth=(user, password))
        with driver.session() as session:
            result = session.run("RETURN 1 as test")
            value = result.single()["test"]
            print("[TEST] Neo4j connection test value:", value)
            assert value == 1
    except Exception as e:
        print("[TEST] Neo4j connection failed:", e)
        assert False, f"Neo4j connection failed: {e}"