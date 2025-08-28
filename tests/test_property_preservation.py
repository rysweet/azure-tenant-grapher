"""Test that properties are preserved when re-running builds."""

import json
from unittest.mock import Mock

import pytest

from src.resource_processor import DatabaseOperations, serialize_value


class TestPropertyPreservation:
    """Test suite for verifying properties are preserved during updates."""

    def test_empty_properties_not_included_in_update(self):
        """Test that empty properties dict is removed from update data."""
        # Mock session
        mock_session = Mock()
        mock_session.run.return_value = Mock(single=lambda: None)
        
        # Mock session manager
        mock_session_manager = Mock()
        mock_session_manager.session.return_value.__enter__ = lambda self: mock_session
        mock_session_manager.session.return_value.__exit__ = lambda self, *args: None
        
        db_ops = DatabaseOperations(mock_session_manager)
        
        # Resource with empty properties
        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",  # Required field
            "properties": {},  # Empty properties should be excluded
            "subscription_id": "sub1",
            "resource_group": "rg1"
        }
        
        # Call upsert
        db_ops.upsert_resource(resource, "completed")
        
        # Verify the query was called
        assert mock_session.run.called
        
        # Get the actual props passed to the query
        call_args = mock_session.run.call_args
        props = call_args[1]["props"]
        
        # Verify properties field was removed to preserve existing data
        assert "properties" not in props, "Empty properties should be removed from update"
    
    def test_non_empty_properties_are_updated(self):
        """Test that non-empty properties are included in the update."""
        # Mock session
        mock_session = Mock()
        mock_session.run.return_value = Mock(single=lambda: None)
        
        # Mock session manager
        mock_session_manager = Mock()
        mock_session_manager.session.return_value.__enter__ = lambda self: mock_session
        mock_session_manager.session.return_value.__exit__ = lambda self, *args: None
        
        db_ops = DatabaseOperations(mock_session_manager)
        
        # Resource with actual properties
        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",  # Required field
            "properties": {
                "vmSize": "Standard_D4s_v3",
                "provisioningState": "Succeeded"
            },
            "subscription_id": "sub1",
            "resource_group": "rg1"
        }
        
        # Call upsert
        db_ops.upsert_resource(resource, "completed")
        
        # Get the actual props passed to the query
        call_args = mock_session.run.call_args
        props = call_args[1]["props"]
        
        # Verify properties field was included and serialized
        assert "properties" in props, "Non-empty properties should be included"
        # Properties should be serialized as JSON string
        assert isinstance(props["properties"], str)
        parsed_props = json.loads(props["properties"])
        assert parsed_props["vmSize"] == "Standard_D4s_v3"
    
    def test_null_properties_preserved(self):
        """Test that None/null properties are handled correctly."""
        # Mock session
        mock_session = Mock()
        mock_session.run.return_value = Mock(single=lambda: None)
        
        # Mock session manager
        mock_session_manager = Mock()
        mock_session_manager.session.return_value.__enter__ = lambda self: mock_session
        mock_session_manager.session.return_value.__exit__ = lambda self, *args: None
        
        db_ops = DatabaseOperations(mock_session_manager)
        
        # Resource with None properties
        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
            "name": "sa1",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",  # Required field
            "properties": None,  # None should be handled
            "subscription_id": "sub1",
            "resource_group": "rg1"
        }
        
        # Call upsert
        db_ops.upsert_resource(resource, "completed")
        
        # Get the actual props passed to the query
        call_args = mock_session.run.call_args
        props = call_args[1]["props"]
        
        # None properties should be serialized as null
        assert "properties" in props
        assert props["properties"] is None


