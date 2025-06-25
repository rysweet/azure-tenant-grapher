import os

import pytest
from neo4j import GraphDatabase

from src.resource_processor import DatabaseOperations


@pytest.fixture(scope="module")
def neo4j_test_driver():
    uri = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise RuntimeError(
            "NEO4J_PASSWORD environment variable must be set for integration tests (do not hardcode secrets)."
        )
    driver = GraphDatabase.driver(uri, auth=(user, password))
    yield driver
    driver.close()


@pytest.fixture
def session_manager(neo4j_test_driver):
    class DummySessionManager:
        def session(self):
            return neo4j_test_driver.session()

    return DummySessionManager()


def test_resource_group_creation_no_cypher_error(session_manager):
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


def test_subscription_and_resource_group_schema(session_manager):
    db_ops = DatabaseOperations(session_manager)
    resource = {
        "id": "/subscriptions/test-sub-id/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1",
        "name": "vm1",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "test-rg",
        "subscription_id": "test-sub-id",
    }
    subscription_id = "test-sub-id"
    subscription_name = "Test Subscription"
    rg_id = f"/subscriptions/{subscription_id}/resourceGroups/test-rg"

    # Cleanup before test
    with session_manager.session() as session:
        session.run("MATCH (r:Resource {id: $id}) DETACH DELETE r", id=resource["id"])
        session.run("MATCH (rg:ResourceGroup {id: $id}) DETACH DELETE rg", id=rg_id)
        session.run(
            "MATCH (s:Subscription {id: $id}) DETACH DELETE s", id=subscription_id
        )

    # Upsert Subscription node
    db_ops.upsert_subscription(subscription_id, subscription_name)
    # Upsert ResourceGroup node
    db_ops.upsert_resource_group(rg_id, "test-rg", subscription_id)
    # Upsert Resource node
    db_ops.upsert_resource(resource)
    # Create relationships
    db_ops.create_subscription_relationship(subscription_id, resource["id"])
    db_ops.create_resource_group_relationships(resource)

    # Assert Subscription node
    with session_manager.session() as session:
        sub = session.run(
            "MATCH (s:Subscription {id: $id}) RETURN s", id=subscription_id
        ).single()
        assert sub is not None
        sub_node = sub["s"]
        assert sub_node["id"] == subscription_id

    # Assert ResourceGroup node
    with session_manager.session() as session:
        rg = session.run(
            "MATCH (rg:ResourceGroup {id: $id}) RETURN rg", id=rg_id
        ).single()
        assert rg is not None
        rg_node = rg["rg"]
        assert rg_node["id"] == rg_id
        assert rg_node["name"] == "test-rg"
        assert rg_node["subscription_id"] == subscription_id

    # Assert Resource node
    with session_manager.session() as session:
        res = session.run(
            "MATCH (r:Resource {id: $id}) RETURN r", id=resource["id"]
        ).single()
        assert res is not None
        res_node = res["r"]
        for prop in [
            "id",
            "name",
            "type",
            "location",
            "resource_group",
            "subscription_id",
        ]:
            assert prop in res_node

    # Assert relationships
    with session_manager.session() as session:
        rel1 = session.run(
            "MATCH (s:Subscription {id: $sid})-[:CONTAINS]->(rg:ResourceGroup {id: $rgid}) RETURN s, rg",
            sid=subscription_id,
            rgid=rg_id,
        ).single()
        assert rel1 is not None

        rel2 = session.run(
            "MATCH (s:Subscription {id: $sid})-[:CONTAINS]->(r:Resource {id: $rid}) RETURN s, r",
            sid=subscription_id,
            rid=resource["id"],
        ).single()
        assert rel2 is not None

        rel3 = session.run(
            "MATCH (rg:ResourceGroup {id: $rgid})-[:CONTAINS]->(r:Resource {id: $rid}) RETURN rg, r",
            rgid=rg_id,
            rid=resource["id"],
        ).single()
        assert rel3 is not None

    # Cleanup after test
    with session_manager.session() as session:
        session.run("MATCH (r:Resource {id: $id}) DETACH DELETE r", id=resource["id"])
        session.run("MATCH (rg:ResourceGroup {id: $id}) DETACH DELETE rg", id=rg_id)
        session.run(
            "MATCH (s:Subscription {id: $id}) DETACH DELETE s", id=subscription_id
        )
