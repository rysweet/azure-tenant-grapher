"""
Tests for Bug #52: Principal ID Abstraction at Graph Layer

Tests that role assignments in the graph have abstracted principal IDs
instead of source tenant GUIDs.
"""

import json
from unittest.mock import MagicMock

import pytest

from src.resource_processor import DatabaseOperations
from src.services.id_abstraction_service import IDAbstractionService


@pytest.fixture
def mock_session_manager():
    """Create a mock session manager."""
    manager = MagicMock()
    session = MagicMock()
    tx = MagicMock()

    # Setup context managers
    manager.session.return_value.__enter__.return_value = session
    session.begin_transaction.return_value.__enter__.return_value = tx

    return manager


@pytest.fixture
def id_abstraction_service():
    """Create a real ID abstraction service with a test seed."""
    return IDAbstractionService(tenant_seed="test-seed-123", hash_length=16)


def test_abstract_principal_id(id_abstraction_service):
    """Test that abstract_principal_id generates deterministic hashed IDs."""
    principal_id = "12345678-1234-1234-1234-123456789012"

    # Test basic abstraction
    abstracted = id_abstraction_service.abstract_principal_id(principal_id)

    # Should have principal- prefix
    assert abstracted.startswith("principal-")

    # Should be deterministic (same input = same output)
    abstracted2 = id_abstraction_service.abstract_principal_id(principal_id)
    assert abstracted == abstracted2

    # Different inputs should produce different outputs
    different_principal_id = "87654321-4321-4321-4321-210987654321"
    abstracted3 = id_abstraction_service.abstract_principal_id(different_principal_id)
    assert abstracted != abstracted3


def test_abstract_principal_id_empty_raises_error(id_abstraction_service):
    """Test that empty principal ID raises ValueError."""
    with pytest.raises(ValueError, match="principal_id cannot be empty"):
        id_abstraction_service.abstract_principal_id("")


def test_role_assignment_properties_dict(mock_session_manager, id_abstraction_service):
    """Test principal ID abstraction for role assignment with properties as dict."""
    db_ops = DatabaseOperations(
        session_manager=mock_session_manager, tenant_id="test-tenant-123"
    )
    db_ops._id_abstraction_service = id_abstraction_service

    # Create a mock transaction
    tx = MagicMock()

    # Role assignment resource with properties as dict
    original_principal_id = "12345678-1234-1234-1234-123456789012"
    properties = {
        "id": "/subscriptions/sub123/providers/Microsoft.Authorization/roleAssignments/ra123",
        "name": "test-role-assignment",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "roleDefinitionId": "/subscriptions/sub123/providers/Microsoft.Authorization/roleDefinitions/role123",
            "principalId": original_principal_id,
            "principalType": "ServicePrincipal",
            "scope": "/subscriptions/sub123",
        },
    }

    # Call the method
    db_ops._create_abstracted_node(
        tx=tx,
        abstracted_id="roleassignment-abc123",
        original_id=properties["id"],
        properties=properties,
    )

    # Verify the transaction was called
    assert tx.run.called

    # Get the props argument passed to the query
    call_args = tx.run.call_args
    props = call_args.kwargs.get("props")

    # Verify that principalId was abstracted
    assert "properties" in props
    props_dict = props["properties"]

    # Should be a dict
    assert isinstance(props_dict, dict)

    # principalId should be abstracted
    assert "principalId" in props_dict
    abstracted_principal = props_dict["principalId"]
    assert abstracted_principal.startswith("principal-")
    assert abstracted_principal != original_principal_id

    # Verify it matches the expected abstraction
    expected_abstraction = id_abstraction_service.abstract_principal_id(
        original_principal_id
    )
    assert abstracted_principal == expected_abstraction


def test_role_assignment_properties_json_string(
    mock_session_manager, id_abstraction_service
):
    """Test principal ID abstraction for role assignment with properties as JSON string."""
    db_ops = DatabaseOperations(
        session_manager=mock_session_manager, tenant_id="test-tenant-123"
    )
    db_ops._id_abstraction_service = id_abstraction_service

    # Create a mock transaction
    tx = MagicMock()

    # Role assignment resource with properties as JSON string
    original_principal_id = "12345678-1234-1234-1234-123456789012"
    properties_dict = {
        "roleDefinitionId": "/subscriptions/sub123/providers/Microsoft.Authorization/roleDefinitions/role123",
        "principalId": original_principal_id,
        "principalType": "User",
        "scope": "/subscriptions/sub123/resourceGroups/rg123",
    }

    properties = {
        "id": "/subscriptions/sub123/providers/Microsoft.Authorization/roleAssignments/ra456",
        "name": "test-role-assignment-2",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": json.dumps(properties_dict),
    }

    # Call the method
    db_ops._create_abstracted_node(
        tx=tx,
        abstracted_id="roleassignment-def456",
        original_id=properties["id"],
        properties=properties,
    )

    # Verify the transaction was called
    assert tx.run.called

    # Get the props argument passed to the query
    call_args = tx.run.call_args
    props = call_args.kwargs.get("props")

    # Verify that principalId was abstracted
    assert "properties" in props
    props_str = props["properties"]

    # Should be a JSON string
    assert isinstance(props_str, str)

    # Parse the JSON and verify
    props_dict = json.loads(props_str)
    assert "principalId" in props_dict
    abstracted_principal = props_dict["principalId"]
    assert abstracted_principal.startswith("principal-")
    assert abstracted_principal != original_principal_id

    # Verify it matches the expected abstraction
    expected_abstraction = id_abstraction_service.abstract_principal_id(
        original_principal_id
    )
    assert abstracted_principal == expected_abstraction


def test_non_role_assignment_not_modified(mock_session_manager, id_abstraction_service):
    """Test that non-role-assignment resources are not modified."""
    db_ops = DatabaseOperations(
        session_manager=mock_session_manager, tenant_id="test-tenant-123"
    )
    db_ops._id_abstraction_service = id_abstraction_service

    # Create a mock transaction
    tx = MagicMock()

    # Non-role-assignment resource
    properties = {
        "id": "/subscriptions/sub123/resourceGroups/rg123/providers/Microsoft.Compute/virtualMachines/vm123",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "properties": {
            "vmId": "vm-guid-123",
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
        },
    }

    # Call the method
    db_ops._create_abstracted_node(
        tx=tx,
        abstracted_id="vm-abc123",
        original_id=properties["id"],
        properties=properties,
    )

    # Verify the transaction was called
    assert tx.run.called

    # Get the props argument passed to the query
    call_args = tx.run.call_args
    props = call_args.kwargs.get("props")

    # Verify that properties were not modified (except for adding abstraction metadata)
    assert "properties" in props
    props_dict = props["properties"]
    assert props_dict == properties["properties"]

    # Should not have principalId abstraction logic applied
    assert "principalId" not in props_dict


def test_role_assignment_missing_principal_id(
    mock_session_manager, id_abstraction_service
):
    """Test role assignment without principalId doesn't cause errors."""
    db_ops = DatabaseOperations(
        session_manager=mock_session_manager, tenant_id="test-tenant-123"
    )
    db_ops._id_abstraction_service = id_abstraction_service

    # Create a mock transaction
    tx = MagicMock()

    # Role assignment without principalId (shouldn't happen, but test defensively)
    properties = {
        "id": "/subscriptions/sub123/providers/Microsoft.Authorization/roleAssignments/ra789",
        "name": "test-role-assignment-3",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "roleDefinitionId": "/subscriptions/sub123/providers/Microsoft.Authorization/roleDefinitions/role123",
            "scope": "/subscriptions/sub123",
        },
    }

    # Should not raise an exception
    db_ops._create_abstracted_node(
        tx=tx,
        abstracted_id="roleassignment-ghi789",
        original_id=properties["id"],
        properties=properties,
    )

    # Verify the transaction was called
    assert tx.run.called


def test_role_assignment_empty_principal_id(
    mock_session_manager, id_abstraction_service
):
    """Test role assignment with empty principalId is handled gracefully."""
    db_ops = DatabaseOperations(
        session_manager=mock_session_manager, tenant_id="test-tenant-123"
    )
    db_ops._id_abstraction_service = id_abstraction_service

    # Create a mock transaction
    tx = MagicMock()

    # Role assignment with empty principalId
    properties = {
        "id": "/subscriptions/sub123/providers/Microsoft.Authorization/roleAssignments/ra999",
        "name": "test-role-assignment-4",
        "type": "Microsoft.Authorization/roleAssignments",
        "properties": {
            "roleDefinitionId": "/subscriptions/sub123/providers/Microsoft.Authorization/roleDefinitions/role123",
            "principalId": "",  # Empty string
            "scope": "/subscriptions/sub123",
        },
    }

    # Should not raise an exception
    db_ops._create_abstracted_node(
        tx=tx,
        abstracted_id="roleassignment-jkl999",
        original_id=properties["id"],
        properties=properties,
    )

    # Verify the transaction was called
    assert tx.run.called

    # Get the props argument passed to the query
    call_args = tx.run.call_args
    props = call_args.kwargs.get("props")

    # principalId should still be empty (not abstracted)
    assert "properties" in props
    props_dict = props["properties"]
    assert props_dict["principalId"] == ""
