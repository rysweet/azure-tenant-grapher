"""Test subscription ID abstraction in dual-graph role assignments (Bug #59)."""
import json
from unittest.mock import MagicMock, Mock

import pytest

from src.resource_processor import ResourceProcessor
from src.services.id_abstraction_service import IDAbstractionService


class TestSubscriptionIDAbstraction:
    """Test that subscription IDs are abstracted in role assignment properties."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock Neo4j session manager."""
        session_manager = Mock()
        session_manager.session = MagicMock()

        # Mock the transaction context manager
        tx_mock = MagicMock()
        tx_mock.__enter__ = Mock(return_value=tx_mock)
        tx_mock.__exit__ = Mock(return_value=False)
        tx_mock.run = Mock()

        session_manager.session.return_value.__enter__ = Mock(
            return_value=Mock(begin_transaction=Mock(return_value=tx_mock))
        )
        session_manager.session.return_value.__exit__ = Mock(return_value=False)

        return session_manager

    @pytest.fixture
    def id_abstraction_service(self):
        """Create ID abstraction service."""
        return IDAbstractionService(tenant_id="test-tenant-id")

    @pytest.fixture
    def resource_processor(self, mock_session_manager, id_abstraction_service):
        """Create resource processor with ID abstraction."""
        return ResourceProcessor(
            session_manager=mock_session_manager,
            llm_generator=None,
            resource_limit=None,
            max_retries=1,
            tenant_id="test-tenant-id",
        )

    def test_role_assignment_subscription_abstraction(
        self, resource_processor, mock_session_manager
    ):
        """Test that role assignment properties have subscription IDs abstracted."""
        # Create role assignment with source subscription ID
        source_subscription_id = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
        role_assignment = {
            "id": f"/subscriptions/{source_subscription_id}/resourceGroups/test-rg/providers/Microsoft.Authorization/roleAssignments/test-role",
            "type": "Microsoft.Authorization/roleAssignments",
            "name": "test-role",
            "properties": json.dumps({
                "scope": f"/subscriptions/{source_subscription_id}/resourceGroups/test-rg",
                "roleDefinitionId": f"/subscriptions/{source_subscription_id}/providers/Microsoft.Authorization/roleDefinitions/test-role-def",
                "principalId": "12345678-1234-1234-1234-123456789012"
            })
        }

        # Process the resource (this creates both Original and Abstracted nodes)
        resource_processor.create_or_update_resource(role_assignment, "completed")

        # Get all the calls to tx.run (Neo4j queries)
        tx_mock = mock_session_manager.session.return_value.__enter__.return_value.begin_transaction.return_value
        all_calls = tx_mock.run.call_args_list

        # Find the call that creates the abstracted node
        # It should be the MERGE query for ":Resource {id: $abstracted_id}"
        abstracted_node_call = None
        for call in all_calls:
            query = call[0][0]  # First positional arg is the query string
            if "MERGE (r:Resource {id: $abstracted_id})" in query:
                abstracted_node_call = call
                break

        assert abstracted_node_call is not None, "Abstracted node creation query not found"

        # Get the props parameter passed to the query
        props = abstracted_node_call[1]["props"]  # Keyword argument

        # Verify the properties field is a JSON string (as it comes from the graph)
        assert "properties" in props, "properties field missing from abstracted node"
        properties_field = props["properties"]

        # Parse the properties JSON
        if isinstance(properties_field, str):
            props_dict = json.loads(properties_field)
        else:
            props_dict = properties_field

        # Verify subscription IDs are abstracted to placeholder
        assert "scope" in props_dict, "scope field missing"
        assert "roleDefinitionId" in props_dict, "roleDefinitionId field missing"

        # Check that source subscription ID is replaced with ABSTRACT_SUBSCRIPTION
        assert "ABSTRACT_SUBSCRIPTION" in props_dict["scope"], \
            f"scope should contain ABSTRACT_SUBSCRIPTION, got: {props_dict['scope']}"
        assert source_subscription_id not in props_dict["scope"], \
            f"scope should not contain source subscription ID {source_subscription_id}"

        assert "ABSTRACT_SUBSCRIPTION" in props_dict["roleDefinitionId"], \
            f"roleDefinitionId should contain ABSTRACT_SUBSCRIPTION, got: {props_dict['roleDefinitionId']}"
        assert source_subscription_id not in props_dict["roleDefinitionId"], \
            f"roleDefinitionId should not contain source subscription ID {source_subscription_id}"

    def test_role_assignment_principalId_also_abstracted(
        self, resource_processor, mock_session_manager
    ):
        """Test that principalId is also abstracted (Bug #52 - already implemented)."""
        source_principal_id = "12345678-1234-1234-1234-123456789012"
        role_assignment = {
            "id": "/subscriptions/test-sub/providers/Microsoft.Authorization/roleAssignments/test-role",
            "type": "Microsoft.Authorization/roleAssignments",
            "name": "test-role",
            "properties": json.dumps({
                "scope": "/subscriptions/test-sub",
                "roleDefinitionId": "/subscriptions/test-sub/providers/Microsoft.Authorization/roleDefinitions/role",
                "principalId": source_principal_id
            })
        }

        resource_processor.create_or_update_resource(role_assignment, "completed")

        tx_mock = mock_session_manager.session.return_value.__enter__.return_value.begin_transaction.return_value
        all_calls = tx_mock.run.call_args_list

        abstracted_node_call = None
        for call in all_calls:
            query = call[0][0]
            if "MERGE (r:Resource {id: $abstracted_id})" in query:
                abstracted_node_call = call
                break

        props = abstracted_node_call[1]["props"]
        properties_field = props["properties"]

        if isinstance(properties_field, str):
            props_dict = json.loads(properties_field)
        else:
            props_dict = properties_field

        # Verify principalId is abstracted (should NOT be the source ID)
        assert "principalId" in props_dict
        assert props_dict["principalId"] != source_principal_id, \
            "principalId should be abstracted, not source principal ID"
