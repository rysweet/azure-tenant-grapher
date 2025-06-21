import os
from typing import Any

import pytest
from neo4j import GraphDatabase

from src.resource_processor import DatabaseOperations


@pytest.fixture(scope="module")
def neo4j_test_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "azure-grapher-2024")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()


@pytest.fixture
def session_manager(neo4j_test_driver: "GraphDatabase.driver") -> Any:
    class DummySessionManager:
        def session(self):
            return neo4j_test_driver.session()

    return DummySessionManager()


def test_resource_group_creation_no_cypher_error(session_manager: Any):
    db_ops = DatabaseOperations(session_manager)
    resource = {
        "id": "test-rg-id",
        "name": "test-rg",
        "type": "ResourceGroup",
        "location": "eastus",
        "resource_group": "test-rg",
        "subscription_id": "test-sub-id",
    }
    # Cleanup before test
    with session_manager.session() as session:
        session.run(
            "MATCH (r:Resource {name: $name, subscription_id: $sub_id, type: 'ResourceGroup'}) DETACH DELETE r",
            name="test-rg",
            sub_id="test-sub-id",
        )

    # Should not raise CypherSyntaxError
    result = db_ops.upsert_resource(resource)
    assert result is True

    # Verify node exists in Neo4j
    with session_manager.session() as session:
        res = session.run(
            "MATCH (r:Resource {name: $name, subscription_id: $sub_id, type: 'ResourceGroup'}) RETURN r",
            name="test-rg",
            sub_id="test-sub-id",
        )
        record = res.single()
        if record is None:
            # Print all Resource nodes with type ResourceGroup for debugging
            all_rgs = list(
                session.run(
                    "MATCH (r:Resource {type: 'ResourceGroup'}) RETURN r.name, r.subscription_id"
                )
            )
            print("All Resource nodes with type ResourceGroup in DB:", all_rgs)
        assert record is not None
        node = record["r"]
        assert node["name"] == "test-rg"
        assert node["llm_description"] == "" or node["llm_description"] is not None

    # Cleanup after test
    with session_manager.session() as session:
        session.run(
            "MATCH (r:Resource {name: $name, subscription_id: $sub_id, type: 'ResourceGroup'}) DETACH DELETE r",
            name="test-rg",
            sub_id="test-sub-id",
        )
