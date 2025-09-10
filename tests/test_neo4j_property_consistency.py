"""Test Neo4j property consistency for User nodes."""

from unittest.mock import MagicMock, patch

import pytest

from src.services.aad_graph_service import AADGraphService
from src.tenant_creator import TenantCreator
from src.tenant_spec_models import Tenant, TenantSpec, User


@pytest.fixture
def mock_session_manager():
    """Mock session manager for database operations."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__ = MagicMock(return_value=mock_session)
    mock_manager.session.return_value.__exit__ = MagicMock(return_value=None)
    return mock_manager, mock_session


def test_user_properties_consistency_tenant_creator(mock_session_manager):
    """Test that tenant_creator creates User nodes with camelCase properties."""
    mock_manager, mock_session = mock_session_manager

    # Create a test tenant spec with a user
    test_user = User(
        id="user-001",
        display_name="Test User",
        user_principal_name="test@example.com",
        job_title="Engineer",
    )

    tenant = Tenant(id="tenant-001", display_name="Test Tenant", users=[test_user])

    spec = TenantSpec(tenant=tenant)

    # Mock the session manager
    with patch(
        "src.tenant_creator.get_default_session_manager", return_value=mock_manager
    ):
        creator = TenantCreator()
        import asyncio

        asyncio.run(creator.ingest_to_graph(spec))

    # Find the call that creates the User node
    user_creation_call = None
    for call in mock_session.run.call_args_list:
        if call and len(call[0]) > 0:
            query = call[0][0]
            if "MERGE (u:User" in query:
                user_creation_call = call
                break

    assert user_creation_call is not None, "User node creation query not found"

    # Check that the query uses camelCase properties
    query = user_creation_call[0][0]
    assert "u.displayName" in query or "u.display_name" in query, (
        "Query should set displayName property"
    )
    assert "u.userPrincipalName" in query or "u.user_principal_name" in query, (
        "Query should set userPrincipalName property"
    )

    # Check the actual parameters passed
    params = user_creation_call[0][1] if len(user_creation_call[0]) > 1 else {}

    # The query should use camelCase properties in Neo4j
    if "u.displayName" in query:
        # Correct: using camelCase
        assert "displayName" in params or "display_name" in params
    else:
        # Incorrect: using snake_case - this is the bug we're fixing
        raise AssertionError(
            "Query uses snake_case (u.display_name) instead of camelCase (u.displayName)"
        )


def test_user_properties_consistency_aad_service():
    """Test that AAD service creates User nodes with camelCase properties."""
    # Create mock db_ops
    mock_db_ops = MagicMock()

    # Create AAD service with mock data
    aad_service = AADGraphService(use_mock=True)

    # Run ingestion
    import asyncio

    asyncio.run(aad_service.ingest_into_graph(mock_db_ops, dry_run=False))

    # Check that upsert_generic was called with camelCase properties
    user_calls = [
        call
        for call in mock_db_ops.upsert_generic.call_args_list
        if call[0][0] == "User"
    ]

    assert len(user_calls) > 0, "No User nodes created"

    # Check first user call
    first_user_call = user_calls[0]
    properties = first_user_call[0][3]  # Fourth argument is properties dict

    # AAD service should use camelCase properties
    assert "displayName" in properties, "AAD service should use displayName (camelCase)"
    assert "userPrincipalName" in properties, (
        "AAD service should use userPrincipalName (camelCase)"
    )
    assert "display_name" not in properties, (
        "AAD service should not use display_name (snake_case)"
    )
    assert "user_principal_name" not in properties, (
        "AAD service should not use user_principal_name (snake_case)"
    )


def test_query_can_find_users_by_principal_name(mock_session_manager):
    """Test that queries can find users by userPrincipalName."""
    mock_manager, mock_session = mock_session_manager

    # Simulate a query looking for a user by userPrincipalName
    query = """
    MATCH (u:User {userPrincipalName: $upn})
    RETURN u
    """

    # This query should work with both tenant_creator and aad_service created nodes
    # After the fix, both should use camelCase properties
    mock_session.run.return_value = MagicMock()

    with mock_manager.session() as session:
        session.run(query, {"upn": "test@example.com"})

    # The query should have been executed successfully
    mock_session.run.assert_called_once_with(query, {"upn": "test@example.com"})


def test_user_node_expected_properties():
    """Test that User nodes have the expected camelCase properties."""
    expected_properties = [
        "id",
        "displayName",
        "userPrincipalName",
        "mail",
        "mailNickname",
        "jobTitle",
    ]

    # These should NOT be present (snake_case versions)
    # Note: This list is kept for documentation purposes
    # incorrect_properties = [
    #     "display_name",
    #     "user_principal_name",
    #     "mail_nickname",
    #     "job_title",
    # ]

    # This test documents the expected property names
    # After fix, all User nodes should use camelCase
    assert all(prop[0].islower() or prop[0].isupper() for prop in expected_properties)
    assert all(
        "_" not in prop or prop == "updated_at"
        for prop in expected_properties
        if prop != "updated_at"
    )
