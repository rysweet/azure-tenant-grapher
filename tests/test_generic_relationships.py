"""Tests for generic relationship functionality."""

import pytest

from src.tenant_spec_models import Relationship, Tenant, TenantSpec


def test_relationship_with_original_type():
    """Test that Relationship model handles original_type field."""
    rel_data = {
        "sourceId": "source-1",
        "targetId": "target-1",
        "relationshipType": "GENERIC_RELATIONSHIP",
        "originalType": "custom_relationship_type",
        "narrativeContext": "The system connects to external APIs",
    }

    rel = Relationship(**rel_data)

    assert rel.source_id == "source-1"
    assert rel.target_id == "target-1"
    assert rel.type == "GENERIC_RELATIONSHIP"
    assert rel.original_type == "custom_relationship_type"
    assert rel.narrative_context == "The system connects to external APIs"


def test_relationship_normalization_with_unknown_type():
    """Test that unknown relationship types are normalized correctly."""
    # Test original LLM output format
    rel_data = {
        "source_id": "source-1",
        "target_id": "target-1",
        "type": "custom_api_integration",
    }

    rel = Relationship(**rel_data)

    assert rel.source_id == "source-1"
    assert rel.target_id == "target-1"
    assert rel.type == "custom_api_integration"


@pytest.mark.asyncio
async def test_tenant_creation_with_generic_relationship(neo4j_container):
    """Test that unknown relationship types become GENERIC_RELATIONSHIP in Neo4j."""
    import os

    from src.tenant_creator import TenantCreator, get_default_session_manager

    # Set Neo4j env vars
    neo4j_uri, neo4j_user, neo4j_password = neo4j_container
    os.environ["NEO4J_URI"] = neo4j_uri
    os.environ["NEO4J_USER"] = neo4j_user
    os.environ["NEO4J_PASSWORD"] = neo4j_password

    # Create a spec with an unknown relationship type
    tenant_data = {
        "tenant": {
            "tenantId": "test-tenant-001",
            "displayName": "Test Tenant",
            "subscriptions": [
                {"subscriptionId": "sub-001", "subscriptionName": "Test Sub"}
            ],
            "relationships": [
                {
                    "sourceId": "test-tenant-001",
                    "targetId": "sub-001",
                    "relationshipType": "unknown_custom_type",
                    "narrativeContext": "This is a custom relationship from the narrative",
                }
            ],
        }
    }

    spec = TenantSpec(**tenant_data)
    creator = TenantCreator()

    # This should create a GENERIC_RELATIONSHIP
    await creator.ingest_to_graph(spec, is_llm_generated=True)

    # Verify the relationship was created with correct properties
    session_manager = get_default_session_manager()
    session_manager.connect()

    with session_manager.session() as session:
        result = session.run("""
            MATCH (a)-[r:GENERIC_RELATIONSHIP]->(b)
            RETURN r.original_type as original_type, r.narrative_context as context
        """)
        record = result.single()

        assert record is not None
        assert record["original_type"] == "unknown_custom_type"
        assert record["context"] == "This is a custom relationship from the narrative"

    session_manager.disconnect()


def test_tenant_with_narrative_context():
    """Test that Tenant model handles narrative_context field."""
    tenant_data = {
        "tenantId": "tenant-001",
        "displayName": "Test Tenant",
        "narrativeContext": "This tenant represents a financial services company",
    }

    tenant = Tenant(**tenant_data)

    assert tenant.id == "tenant-001"
    assert tenant.display_name == "Test Tenant"
    assert (
        tenant.narrative_context
        == "This tenant represents a financial services company"
    )
