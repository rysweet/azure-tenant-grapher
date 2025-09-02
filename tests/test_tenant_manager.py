"""
Tests for Neo4j-based TenantManager
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import json

from src.services.tenant_manager import (
    TenantManager,
    Tenant,
    TenantNotFoundError,
    InvalidTenantConfigError,
    TenantSwitchError,
    get_tenant_manager,
    register_tenant,
    switch_tenant,
    get_current_tenant
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
            subscription_ids=subscription_ids
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

    def test_get_current_tenant_queries_neo4j(self, tenant_manager, mock_session_manager):
        """Test that getting current tenant queries Neo4j."""
        # Arrange
        mock_result = [{
            'tenant_id': 'current-tenant',
            'display_name': 'Current Tenant',
            'subscription_ids': '["sub1"]',
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'is_active': True,
            'is_current': True,
            'configuration': '{}'
        }]
        mock_session_manager.execute_query.return_value = (mock_result, {}, {})
        
        # Act
        current = tenant_manager.get_current_tenant()
        
        # Assert
        assert current is not None
        assert current.tenant_id == 'current-tenant'
        assert current.display_name == 'Current Tenant'
        
        # Verify query
        query_call = mock_session_manager.execute_query.call_args[0][0]
        assert "MATCH (t:TenantConfig {is_current: true})" in query_call

    def test_switch_tenant_updates_current(self, tenant_manager, mock_session_manager):
        """Test that switching tenant updates is_current in Neo4j."""
        # Arrange
        new_tenant_id = "new-tenant"
        mock_result = [{
            'tenant_id': new_tenant_id,
            'display_name': 'New Tenant',
            'subscription_ids': '[]',
            'created_at': datetime.now(),
            'last_accessed': datetime.now(),
            'is_active': True,
            'is_current': True,
            'configuration': '{}'
        }]
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
                'tenant_id': 'tenant1',
                'display_name': 'Tenant 1',
                'subscription_ids': '[]',
                'is_active': True,
                'configuration': '{}'
            },
            {
                'tenant_id': 'tenant2',
                'display_name': 'Tenant 2',
                'subscription_ids': '[]',
                'is_active': False,
                'configuration': '{}'
            }
        ]
        mock_session_manager.execute_query.return_value = (mock_results, {}, {})
        
        # Act
        all_tenants = tenant_manager.list_tenants(active_only=False)
        
        # Assert
        assert len(all_tenants) == 2
        assert all_tenants[0].tenant_id == 'tenant1'
        assert all_tenants[1].tenant_id == 'tenant2'
        
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
        with patch('src.services.tenant_manager.Neo4jSessionManager') as mock_sm_class:
            with patch('src.services.tenant_manager.create_neo4j_config_from_env') as mock_config:
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
            subscription_ids=subscription_ids
        )
        
        # Assert - check that JSON serialization was used in query
        query_call = mock_session_manager.execute_query.call_args
        params = query_call[1]
        assert params['subscription_ids'] == json.dumps(subscription_ids)
        assert params['configuration'] == json.dumps(config)