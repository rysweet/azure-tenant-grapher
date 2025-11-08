"""
Tests for Dual-Graph Implementation - Resource Processor (Issue #420)

These tests verify the implementation of dual-node creation.
Dual-graph is always enabled (no feature flags).
"""

from typing import Any, Dict
from unittest.mock import MagicMock

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

    def test_dual_graph_initializes_services(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that dual-graph services are always initialized."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations with tenant_id
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
        )

        # Should have initialized services
        assert db_ops._tenant_seed_manager is not None
        assert db_ops._id_abstraction_service is not None

    def test_dual_graph_creates_two_nodes(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that dual-graph creates both Original and Abstracted nodes."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
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

    def test_abstracted_id_generation(
        self, mock_session_manager, sample_azure_resource
    ):
        """Test that abstracted IDs are generated correctly."""
        from src.resource_processor import DatabaseOperations

        # Create DatabaseOperations
        db_ops = DatabaseOperations(
            mock_session_manager,
            tenant_id="tenant-123",
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

    def test_resource_processor_accepts_tenant_id(self, mock_session_manager):
        """Test that ResourceProcessor accepts tenant_id parameter."""
        from src.resource_processor import ResourceProcessor

        # Create processor with tenant_id
        processor = ResourceProcessor(
            session_manager=mock_session_manager,
            tenant_id="tenant-123",
        )

        # Should have initialized
        assert processor.tenant_id == "tenant-123"

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

    def test_create_resource_processor_factory_function(self, mock_session_manager):
        """Test that create_resource_processor factory function works."""
        from src.resource_processor import create_resource_processor

        # Create processor using factory
        processor = create_resource_processor(
            session_manager=mock_session_manager,
            tenant_id="tenant-123",
        )

        # Should have created processor
        assert processor is not None
        assert processor.tenant_id == "tenant-123"
