"""
Tests for Neo4j-based TenantManager
"""

import json
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.services.tenant_manager import (
    InvalidTenantConfigError,
    TenantManager,
    TenantNotFoundError,
    get_tenant_manager,
)


class TestNeo4jTenantManager:
    """Test Neo4j-based TenantManager functionality."""

    @pytest.fixture
    def mock_session_manager(self):
        """Create a mock Neo4j session manager."""
        mock = Mock()
        mock.execute_query = MagicMock()
        mock.driver = Mock()
        return mock

    @pytest.fixture
    def tenant_manager(self, mock_session_manager):
        """Create TenantManager instance with mock session."""
        # Reset singleton for testing
        TenantManager._instance = None
        return TenantManager(mock_session_manager)

    def test_register_tenant_creates_node(self, tenant_manager, mock_session_manager):
        """Test that registering a tenant creates a Neo4j node."""
        # Arrange
        tenant_id = "test-tenant-123"
        display_name = "Test Tenant"
        config = {"key": "value"}
        subscription_ids = ["sub1", "sub2"]

        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act
        tenant = tenant_manager.register_tenant(
            tenant_id=tenant_id,
            display_name=display_name,
            config=config,
            subscription_ids=subscription_ids,
        )

        # Assert
        assert tenant.tenant_id == tenant_id
        assert tenant.display_name == display_name
        assert tenant.subscription_ids == subscription_ids
        assert tenant.is_active == True

        # Verify Neo4j query was executed
        mock_session_manager.execute_query.assert_called()
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MERGE (t:TenantConfig {tenant_id: $tenant_id})" in query_call

    def test_get_current_tenant_queries_neo4j(
        self, tenant_manager, mock_session_manager
    ):
        """Test that getting current tenant queries Neo4j."""
        # Arrange
        mock_result = [
            {
                "tenant_id": "current-tenant",
                "display_name": "Current Tenant",
                "subscription_ids": '["sub1"]',
                "created_at": datetime.now(),
                "last_accessed": datetime.now(),
                "is_active": True,
                "is_current": True,
                "configuration": "{}",
            }
        ]
        mock_session_manager.execute_query.return_value = (mock_result, {}, {})

        # Act
        current = tenant_manager.get_current_tenant()

        # Assert
        assert current is not None
        assert current.tenant_id == "current-tenant"
        assert current.display_name == "Current Tenant"

        # Verify query
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MATCH (t:TenantConfig {is_current: true})" in query_call

    def test_switch_tenant_updates_current(self, tenant_manager, mock_session_manager):
        """Test that switching tenant updates is_current in Neo4j."""
        # Arrange
        new_tenant_id = "new-tenant"
        mock_result = [
            {
                "tenant_id": new_tenant_id,
                "display_name": "New Tenant",
                "subscription_ids": "[]",
                "created_at": datetime.now(),
                "last_accessed": datetime.now(),
                "is_active": True,
                "is_current": True,
                "configuration": "{}",
            }
        ]
        mock_session_manager.execute_query.return_value = (mock_result, {}, {})

        # Act
        switched = tenant_manager.switch_tenant(new_tenant_id)

        # Assert
        assert switched.tenant_id == new_tenant_id

        # Verify atomic switch query
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MATCH (current:TenantConfig {is_current: true})" in query_call
        assert "SET current.is_current = false" in query_call
        assert "MATCH (new:TenantConfig {tenant_id: $tenant_id})" in query_call
        assert "SET new.is_current = true" in query_call

    def test_list_tenants_queries_all(self, tenant_manager, mock_session_manager):
        """Test that list_tenants queries all tenant nodes."""
        # Arrange
        mock_results = [
            {
                "tenant_id": "tenant1",
                "display_name": "Tenant 1",
                "subscription_ids": "[]",
                "is_active": True,
                "configuration": "{}",
            },
            {
                "tenant_id": "tenant2",
                "display_name": "Tenant 2",
                "subscription_ids": "[]",
                "is_active": False,
                "configuration": "{}",
            },
        ]
        mock_session_manager.execute_query.return_value = (mock_results, {}, {})

        # Act
        all_tenants = tenant_manager.list_tenants(active_only=False)

        # Assert
        assert len(all_tenants) == 2
        assert all_tenants[0].tenant_id == "tenant1"
        assert all_tenants[1].tenant_id == "tenant2"

        # Verify query
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MATCH (t:TenantConfig)" in query_call

    def test_remove_tenant_deletes_node(self, tenant_manager, mock_session_manager):
        """Test that removing a tenant deletes the Neo4j node."""
        # Arrange
        tenant_id = "tenant-to-remove"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act
        tenant_manager.remove_tenant(tenant_id)

        # Assert
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MATCH (t:TenantConfig {tenant_id: $tenant_id})" in query_call
        assert "DELETE t" in query_call

    def test_singleton_pattern(self, mock_session_manager):
        """Test that TenantManager follows singleton pattern."""
        # Reset singleton
        TenantManager._instance = None

        # Create two instances
        instance1 = TenantManager(mock_session_manager)
        instance2 = TenantManager(mock_session_manager)

        # Should be the same instance
        assert instance1 is instance2

    def test_module_functions_use_default_session(self):
        """Test that module-level functions create default session manager."""
        with patch("src.services.tenant_manager.Neo4jSessionManager") as mock_sm_class:
            with patch(
                "src.services.tenant_manager.create_neo4j_config_from_env"
            ) as mock_config:
                # Reset singleton
                TenantManager._instance = None

                # Configure mocks
                mock_config.return_value.neo4j = Mock()
                mock_sm_instance = Mock()
                mock_sm_class.return_value = mock_sm_instance
                mock_sm_instance.execute_query.return_value = ([], {}, {})

                # Call module function without session manager
                manager = get_tenant_manager()

                # Should have created session manager from config
                mock_config.assert_called_once()
                mock_sm_class.assert_called_once_with(mock_config.return_value.neo4j)

    def test_tenant_not_found_error(self, tenant_manager, mock_session_manager):
        """Test that TenantNotFoundError is raised appropriately."""
        # Arrange
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act & Assert
        with pytest.raises(TenantNotFoundError) as exc_info:
            tenant_manager.switch_tenant("non-existent-tenant")

        assert "non-existent-tenant" in str(exc_info.value)

    def test_json_serialization(self, tenant_manager, mock_session_manager):
        """Test that subscription_ids and configuration are properly serialized."""
        # Arrange
        config = {"complex": {"nested": "value"}}
        subscription_ids = ["sub1", "sub2", "sub3"]

        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act
        tenant = tenant_manager.register_tenant(
            tenant_id="test",
            display_name="Test",
            config=config,
            subscription_ids=subscription_ids,
        )

        # Assert - check that JSON serialization was used in query
        query_call = mock_session_manager.execute_query.call_args
        params = query_call[1]
        assert params["subscription_ids"] == json.dumps(subscription_ids)
        assert params["configuration"] == json.dumps(config)

    def test_deactivate_tenant(self, tenant_manager, mock_session_manager):
        """Test deactivating a tenant."""
        # Arrange
        tenant_id = "test-tenant"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register tenant first
        tenant = tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Test Tenant", config={"key": "value"}
        )
        assert tenant.is_active == True

        # Act
        tenant_manager.deactivate_tenant(tenant_id)

        # Assert
        deactivated_tenant = tenant_manager.get_tenant(tenant_id)
        assert deactivated_tenant.is_active == False

        # Verify Neo4j update query was executed
        calls = mock_session_manager.execute_query.call_args_list
        last_query = calls[-1][0][0]
        assert "MERGE (t:TenantConfig {tenant_id: $tenant_id})" in last_query
        assert "SET" in last_query
        last_params = calls[-1][1]
        assert last_params["is_active"] == False

    def test_deactivate_nonexistent_tenant(self, tenant_manager):
        """Test deactivating a non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError) as exc_info:
            tenant_manager.deactivate_tenant("non-existent")
        assert "non-existent" in str(exc_info.value)

    def test_activate_tenant(self, tenant_manager, mock_session_manager):
        """Test reactivating a deactivated tenant."""
        # Arrange
        tenant_id = "test-tenant"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register and deactivate tenant
        tenant = tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Test Tenant"
        )
        tenant_manager.deactivate_tenant(tenant_id)
        assert tenant_manager.get_tenant(tenant_id).is_active == False

        # Act
        tenant_manager.activate_tenant(tenant_id)

        # Assert
        activated_tenant = tenant_manager.get_tenant(tenant_id)
        assert activated_tenant.is_active == True

        # Verify last accessed was updated
        assert activated_tenant.last_accessed > tenant.created_at

        # Verify Neo4j update query
        calls = mock_session_manager.execute_query.call_args_list
        last_query = calls[-1][0][0]
        assert "MERGE (t:TenantConfig {tenant_id: $tenant_id})" in last_query
        last_params = calls[-1][1]
        assert last_params["is_active"] == True

    def test_activate_nonexistent_tenant(self, tenant_manager):
        """Test activating a non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError) as exc_info:
            tenant_manager.activate_tenant("non-existent")
        assert "non-existent" in str(exc_info.value)

    def test_get_tenant_config(self, tenant_manager, mock_session_manager):
        """Test retrieving tenant configuration."""
        # Arrange
        tenant_id = "test-tenant"
        config = {"api_key": "secret", "region": "us-west-2", "nested": {"value": 123}}
        mock_session_manager.execute_query.return_value = ([], {}, {})

        tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Test", config=config
        )

        # Act
        retrieved_config = tenant_manager.get_tenant_config(tenant_id)

        # Assert
        assert retrieved_config == config
        assert retrieved_config is not config  # Should be a copy

        # Verify modifying returned config doesn't affect original
        retrieved_config["new_key"] = "new_value"
        assert "new_key" not in tenant_manager.get_tenant_config(tenant_id)

    def test_get_tenant_config_nonexistent(self, tenant_manager):
        """Test getting config for non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError) as exc_info:
            tenant_manager.get_tenant_config("non-existent")
        assert "non-existent" in str(exc_info.value)

    def test_update_tenant_config(self, tenant_manager, mock_session_manager):
        """Test updating tenant configuration."""
        # Arrange
        tenant_id = "test-tenant"
        initial_config = {"key1": "value1", "key2": "value2"}
        mock_session_manager.execute_query.return_value = ([], {}, {})

        tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Test", config=initial_config
        )

        # Act
        update_config = {"key2": "updated_value", "key3": "new_value"}
        tenant_manager.update_tenant_config(tenant_id, update_config)

        # Assert
        final_config = tenant_manager.get_tenant_config(tenant_id)
        assert final_config["key1"] == "value1"  # Original value preserved
        assert final_config["key2"] == "updated_value"  # Updated value
        assert final_config["key3"] == "new_value"  # New value added

        # Verify last accessed was updated
        tenant = tenant_manager.get_tenant(tenant_id)
        assert tenant.last_accessed > tenant.created_at

        # Verify Neo4j update
        calls = mock_session_manager.execute_query.call_args_list
        last_params = calls[-1][1]
        assert json.loads(last_params["configuration"]) == final_config

    def test_update_tenant_config_nonexistent(self, tenant_manager):
        """Test updating config for non-existent tenant raises error."""
        with pytest.raises(TenantNotFoundError) as exc_info:
            tenant_manager.update_tenant_config("non-existent", {"key": "value"})
        assert "non-existent" in str(exc_info.value)

    def test_export_tenants(self, tenant_manager, mock_session_manager):
        """Test exporting all tenants to dictionary."""
        # Arrange
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register multiple tenants
        tenant1 = tenant_manager.register_tenant(
            tenant_id="tenant1",
            display_name="Tenant 1",
            config={"env": "prod"},
            subscription_ids=["sub1"],
        )
        tenant2 = tenant_manager.register_tenant(
            tenant_id="tenant2",
            display_name="Tenant 2",
            config={"env": "dev"},
            subscription_ids=["sub2", "sub3"],
        )

        # Deactivate one tenant
        tenant_manager.deactivate_tenant("tenant2")

        # Switch to tenant1
        tenant_manager.switch_tenant("tenant1")

        # Mock the reload queries
        mock_session_manager.execute_query.side_effect = [
            # _load_tenants query result
            (
                [
                    {
                        "tenant_id": "tenant1",
                        "display_name": "Tenant 1",
                        "subscription_ids": json.dumps(["sub1"]),
                        "created_at": tenant1.created_at,
                        "last_accessed": tenant1.last_accessed,
                        "is_active": True,
                        "configuration": json.dumps({"env": "prod"}),
                    },
                    {
                        "tenant_id": "tenant2",
                        "display_name": "Tenant 2",
                        "subscription_ids": json.dumps(["sub2", "sub3"]),
                        "created_at": tenant2.created_at,
                        "last_accessed": tenant2.last_accessed,
                        "is_active": False,
                        "configuration": json.dumps({"env": "dev"}),
                    },
                ],
                {},
                {},
            ),
            # _load_current_tenant query result
            ([{"tenant_id": "tenant1"}], {}, {}),
        ]

        # Act
        exported = tenant_manager.export_tenants()

        # Assert
        assert "tenants" in exported
        assert "current_tenant_id" in exported
        assert "exported_at" in exported

        assert len(exported["tenants"]) == 2
        assert exported["current_tenant_id"] == "tenant1"

        # Check tenant1 data
        t1_data = exported["tenants"]["tenant1"]
        assert t1_data["tenant_id"] == "tenant1"
        assert t1_data["display_name"] == "Tenant 1"
        assert t1_data["subscription_ids"] == ["sub1"]
        assert t1_data["configuration"]["env"] == "prod"
        assert t1_data["is_active"] == True

        # Check tenant2 data
        t2_data = exported["tenants"]["tenant2"]
        assert t2_data["tenant_id"] == "tenant2"
        assert t2_data["is_active"] == False

    def test_import_tenants(self, tenant_manager, mock_session_manager):
        """Test importing tenants from dictionary."""
        # Arrange
        import_data = {
            "tenants": {
                "imported1": {
                    "tenant_id": "imported1",
                    "display_name": "Imported Tenant 1",
                    "subscription_ids": ["sub1", "sub2"],
                    "created_at": "2024-01-01T00:00:00",
                    "last_accessed": "2024-01-02T00:00:00",
                    "is_active": True,
                    "configuration": {"env": "prod", "region": "us-east-1"},
                },
                "imported2": {
                    "tenant_id": "imported2",
                    "display_name": "Imported Tenant 2",
                    "subscription_ids": [],
                    "created_at": "2024-01-01T00:00:00",
                    "last_accessed": "2024-01-01T12:00:00",
                    "is_active": False,
                    "configuration": {},
                },
            },
            "current_tenant_id": "imported1",
            "exported_at": "2024-01-03T00:00:00",
        }

        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act
        tenant_manager.import_tenants(import_data)

        # Assert
        # Verify clear query was executed
        calls = mock_session_manager.execute_query.call_args_list
        clear_query = calls[0][0][0]
        assert "MATCH (t:TenantConfig)" in clear_query
        assert "DELETE t" in clear_query

        # Verify tenants were imported
        assert tenant_manager.get_tenant_count() == 2

        imported1 = tenant_manager.get_tenant("imported1")
        assert imported1.display_name == "Imported Tenant 1"
        assert imported1.subscription_ids == ["sub1", "sub2"]
        assert imported1.is_active == True
        assert imported1.configuration["env"] == "prod"

        imported2 = tenant_manager.get_tenant("imported2")
        assert imported2.display_name == "Imported Tenant 2"
        assert imported2.is_active == False

        # Verify current tenant was set
        current = tenant_manager.get_current_tenant()
        assert current.tenant_id == "imported1"

        # Verify save queries were executed
        save_queries = [
            call
            for call in calls
            if "MERGE (t:TenantConfig {tenant_id: $tenant_id})" in call[0][0]
        ]
        assert len(save_queries) >= 2  # At least 2 tenants saved

    def test_import_tenants_invalid_data(self, tenant_manager, mock_session_manager):
        """Test importing invalid tenant data raises error."""
        # Arrange
        invalid_data = {
            "tenants": {
                "invalid": {
                    # Missing required fields
                    "display_name": "Invalid"
                }
            }
        }

        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Act & Assert
        with pytest.raises(InvalidTenantConfigError) as exc_info:
            tenant_manager.import_tenants(invalid_data)
        assert "Failed to import tenants" in str(exc_info.value)

    def test_switch_to_deactivated_tenant(self, tenant_manager, mock_session_manager):
        """Test switching to a deactivated tenant (should succeed but log warning)."""
        # Arrange
        tenant_id = "deactivated-tenant"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register and deactivate tenant
        tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Deactivated Tenant"
        )
        tenant_manager.deactivate_tenant(tenant_id)

        # Act - Should succeed (no restriction on switching to inactive tenants)
        switched = tenant_manager.switch_tenant(tenant_id)

        # Assert
        assert switched.tenant_id == tenant_id
        assert switched.is_active == False
        current = tenant_manager.get_current_tenant()
        assert current.tenant_id == tenant_id

    def test_remove_current_tenant(self, tenant_manager, mock_session_manager):
        """Test removing the current tenant clears current_tenant_id."""
        # Arrange
        tenant_id = "current-tenant"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register and switch to tenant
        tenant_manager.register_tenant(
            tenant_id=tenant_id, display_name="Current Tenant"
        )
        tenant_manager.switch_tenant(tenant_id)
        assert tenant_manager.get_current_tenant().tenant_id == tenant_id

        # Act
        tenant_manager.remove_tenant(tenant_id)

        # Assert
        assert tenant_manager.get_current_tenant() is None
        assert tenant_manager._current_tenant_id is None

        # Verify state save was called to clear current tenant
        calls = mock_session_manager.execute_query.call_args_list
        state_calls = [
            call for call in calls if "SET t.is_current = false" in call[0][0]
        ]
        assert len(state_calls) > 0

    def test_tenant_exists(self, tenant_manager, mock_session_manager):
        """Test checking if tenant exists."""
        # Arrange
        mock_session_manager.execute_query.return_value = ([], {}, {})
        tenant_manager.register_tenant(tenant_id="existing", display_name="Existing")

        # Act & Assert
        assert tenant_manager.tenant_exists("existing") == True
        assert tenant_manager.tenant_exists("non-existent") == False

    def test_get_tenant_count(self, tenant_manager, mock_session_manager):
        """Test getting tenant count with active_only filter."""
        # Arrange
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register multiple tenants
        tenant_manager.register_tenant("t1", "Tenant 1")
        tenant_manager.register_tenant("t2", "Tenant 2")
        tenant_manager.register_tenant("t3", "Tenant 3")

        # Deactivate one
        tenant_manager.deactivate_tenant("t2")

        # Act & Assert
        assert tenant_manager.get_tenant_count(active_only=False) == 3
        assert tenant_manager.get_tenant_count(active_only=True) == 2

    def test_register_tenant_with_empty_values(self, tenant_manager):
        """Test registering tenant with empty required fields raises error."""
        # Test empty tenant_id
        with pytest.raises(InvalidTenantConfigError) as exc_info:
            tenant_manager.register_tenant("", "Display Name")
        assert "Tenant ID and display name are required" in str(exc_info.value)

        # Test empty display_name
        with pytest.raises(InvalidTenantConfigError) as exc_info:
            tenant_manager.register_tenant("tenant-id", "")
        assert "Tenant ID and display name are required" in str(exc_info.value)

    def test_update_existing_tenant_via_register(
        self, tenant_manager, mock_session_manager
    ):
        """Test that registering an existing tenant updates it."""
        # Arrange
        tenant_id = "existing-tenant"
        mock_session_manager.execute_query.return_value = ([], {}, {})

        # Register initial tenant
        initial_tenant = tenant_manager.register_tenant(
            tenant_id=tenant_id,
            display_name="Initial Name",
            config={"key1": "value1"},
            subscription_ids=["sub1"],
        )

        # Act - Register again with updates
        updated_tenant = tenant_manager.register_tenant(
            tenant_id=tenant_id,
            display_name="Updated Name",
            config={"key2": "value2"},
            subscription_ids=["sub2", "sub3"],
        )

        # Assert
        assert updated_tenant.tenant_id == tenant_id
        assert updated_tenant.display_name == "Updated Name"
        assert updated_tenant.configuration == {"key1": "value1", "key2": "value2"}
        assert updated_tenant.subscription_ids == ["sub2", "sub3"]
        assert updated_tenant.last_accessed > initial_tenant.last_accessed
