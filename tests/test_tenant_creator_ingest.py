import os

import pytest

from src.tenant_creator import TenantCreator


@pytest.mark.asyncio
async def test_tenant_ingest_to_graph(neo4j_container):
    # Arrange: set Neo4j env vars for session manager
    neo4j_uri, neo4j_user, neo4j_password = neo4j_container
    os.environ["NEO4J_URI"] = neo4j_uri
    os.environ["NEO4J_USER"] = neo4j_user
    os.environ["NEO4J_PASSWORD"] = neo4j_password

    # Load sample markdown
    with open("tests/fixtures/sample-tenant.md") as f:
        markdown = f.read()

    creator = TenantCreator()
    spec = await creator.create_from_markdown(markdown)
    # For tests, explicitly use strict validation (not LLM-generated)
    await creator.ingest_to_graph(spec, is_llm_generated=False)

    # Assert: check that the Tenant node exists
    from src.tenant_creator import get_default_session_manager

    session_manager = get_default_session_manager()
    session_manager.connect()
    with session_manager.session() as session:
        result = session.run(
            "MATCH (t:Tenant {id: $id}) RETURN count(t) as count", {"id": "tenant-001"}
        )
        record = result.single()
        assert record is not None, "No result returned from Neo4j"
        count = record["count"]
        assert count == 1, "Tenant node was not created in Neo4j"
    session_manager.disconnect()
