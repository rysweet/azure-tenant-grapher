"""
Tests for Dual-Graph Implementation - Resource Processor (Issue #420)

These tests verify the actual implementation of dual-node creation.
"""

import os
from typing import Any, Dict
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def sample_azure_resource() -> Dict[str, Any]:
    """Provide a sample Azure resource for testing."""
    return {
        "id": "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm-001",
        "name": "test-vm-001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "test-rg",
        "subscription_id": "abc123",
        "tenant_id": "tenant-123",
        "scan_id": "scan-001",
        "properties": {
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
            "storageProfile": {"imageReference": {"publisher": "Canonical"}},
        },
        "tags": {"environment": "production", "owner": "team-platform"},
    }


@pytest.fixture
def mock_session_manager():
    """Provide a mock session manager."""
    session_manager = MagicMock()
    session = MagicMock()
    tx = MagicMock()

    # Mock session context manager
    session_manager.session.return_value.__enter__.return_value = session
    session_manager.session.return_value.__exit__.return_value = False

    # Mock transaction context manager
    session.begin_transaction.return_value.__enter__.return_value = tx
    session.begin_transaction.return_value.__exit__.return_value = False

    # Mock query results
    tx.run.return_value = MagicMock()
    session.run.return_value = MagicMock()

    # Mock single() for seed queries
    mock_record = {"seed": "test-seed-" + "0" * 54}  # 64 char seed
    session.run.return_value.single.return_value = mock_record

    return session_manager


class TestDualGraphImplementation:
    """Test suite for dual-graph implementation."""

    def test_feature_flag_disabled_creates_single_node(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that when feature flag is disabled, only single node is created."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations with dual-graph disabled
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=False,
        )

        # Process resource
        result = db_ops.upsert_resource(sample_azure_resource)

        # Should succeed
        assert result is True

        # Verify it called the single resource method (not dual)
        # We can check that it didn't try to create abstracted IDs
        assert db_ops._id_abstraction_service is None

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_feature_flag_enabled_initializes_services(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that when feature flag is enabled, dual-graph services are initialized."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations with dual-graph enabled
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=True,
        )

        # Should have initialized services
        assert db_ops._tenant_seed_manager is not None
        assert db_ops._id_abstraction_service is not None

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_dual_graph_creates_two_nodes(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that dual-graph mode creates both Original and Abstracted nodes."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations with dual-graph enabled
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=True,
        )

        # Process resource
        result = db_ops.upsert_resource(sample_azure_resource)

        # Should succeed
        assert result is True

        # Get the transaction object
        session = mock_session_manager.session.return_value.__enter__.return_value
        tx = session.begin_transaction.return_value.__enter__.return_value

        # Verify transaction was used
        session.begin_transaction.assert_called()

        # Verify tx.run was called at least 3 times (Original, Abstracted, Relationship)
        assert tx.run.call_count >= 3

        # Check that Original node was created
        calls = [str(call) for call in tx.run.call_args_list]
        original_calls = [c for c in calls if ":Original" in c]
        assert len(original_calls) >= 1, "Should create Original node"

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_abstracted_id_generation(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that abstracted IDs are generated correctly."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations with dual-graph enabled
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=True,
        )

        # Get ID abstraction service
        abstraction_service = db_ops._id_abstraction_service
        assert abstraction_service is not None

        # Generate abstracted ID
        original_id = sample_azure_resource["id"]
        abstracted_id = abstraction_service.abstract_resource_id(original_id)

        # Should have type prefix
        assert abstracted_id.startswith("vm-"), (
            f"Expected vm- prefix, got {abstracted_id}"
        )

        # Should be different from original
        assert abstracted_id != original_id

        # Should be deterministic (same input = same output)
        abstracted_id2 = abstraction_service.abstract_resource_id(original_id)
        assert abstracted_id == abstracted_id2

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_tenant_seed_is_persistent(self, mock_session_manager):
        """Test that tenant seed is retrieved from database if it exists."""
        from src.services.tenant_seed_manager import TenantSeedManager

        # Create manager
        seed_manager = TenantSeedManager(mock_session_manager)

        # Get or create seed
        seed1 = seed_manager.get_or_create_seed("tenant-123")

        # Should return the mocked seed
        assert seed1 is not None
        assert len(seed1) == 64  # Mocked seed is 64 chars

        # Verify it queried the database
        session = mock_session_manager.session.return_value.__enter__.return_value
        session.run.assert_called()

    def test_database_operations_requires_tenant_id_for_dual_graph(
        self, mock_session_manager
    ):
        """Test that dual-graph mode requires tenant_id."""
        from src.resource_processor import DatabaseOperations

        # Try to create with dual-graph but no tenant_id - should not crash
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id=None,  # No tenant ID
            enable_dual_graph=True,
        )

        # Should not have initialized services (no tenant_id)
        assert db_ops._id_abstraction_service is None

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_resource_processor_accepts_tenant_id(self, mock_session_manager):
        """Test that ResourceProcessor accepts tenant_id parameter."""
        from src.resource_processor import ResourceProcessor

        # Create processor with tenant_id
        processor = ResourceProcessor(
            session_manager=mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=True,
        )

        # Should have initialized
        assert processor.tenant_id == "tenant-123"
        assert processor.enable_dual_graph is True

    def test_id_abstraction_service_generates_type_prefixes(self):
        """Test that ID abstraction service generates correct type prefixes."""
        from src.services.id_abstraction_service import IDAbstractionService

        service = IDAbstractionService("test-seed")

        # Test various resource types
        test_cases = [
            ("Microsoft.Compute/virtualMachines", "vm-"),
            ("Microsoft.Storage/storageAccounts", "storage-"),
            ("Microsoft.Network/virtualNetworks", "vnet-"),
            ("Microsoft.Network/networkSecurityGroups", "nsg-"),
            ("Microsoft.KeyVault/vaults", "kv-"),
        ]

        for resource_type, expected_prefix in test_cases:
            test_id = (
                f"/subscriptions/sub1/resourceGroups/rg1/providers/{resource_type}/test"
            )
            abstracted = service.abstract_resource_id(test_id)
            assert abstracted.startswith(expected_prefix), (
                f"Expected {expected_prefix} for {resource_type}, got {abstracted}"
            )

    def test_feature_flag_environment_variable(self):
        """Test that ENABLE_DUAL_GRAPH environment variable is read correctly."""
        # Test default (should be false)
        with patch.dict(os.environ, {}, clear=True):
            # Reimport to get fresh value
            import importlib

            import src.resource_processor

            importlib.reload(src.resource_processor)
            assert src.resource_processor.ENABLE_DUAL_GRAPH is False

        # Test explicit true
        with patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"}):
            importlib.reload(src.resource_processor)
            assert src.resource_processor.ENABLE_DUAL_GRAPH is True

        # Test explicit false
        with patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "false"}):
            importlib.reload(src.resource_processor)
            assert src.resource_processor.ENABLE_DUAL_GRAPH is False

    @patch.dict(os.environ, {"ENABLE_DUAL_GRAPH": "true"})
    def test_create_resource_processor_factory_function(self, mock_session_manager):
        """Test that create_resource_processor factory function works with dual-graph."""
        from src.resource_processor import create_resource_processor

        # Create processor using factory
        processor = create_resource_processor(
            session_manager=mock_session_manager,
            tenant_id="tenant-123",
            enable_dual_graph=True,
        )

        # Should have created processor
        assert processor is not None
        assert processor.tenant_id == "tenant-123"
        assert processor.enable_dual_graph is True
