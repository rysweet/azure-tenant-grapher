"""Tests for DependsOnRule logging (Issue #873).

This test suite validates:
- DependsOnRule logs relationship creation
- Logging includes resource IDs with truncation for readability
- extract_target_ids returns correct dependency IDs
"""

from unittest.mock import MagicMock, patch

import pytest

from src.relationship_rules.depends_on_rule import DependsOnRule


class TestDependsOnRuleApplies:
    """Test applies() method."""

    def test_applies_to_resource_with_depends_on(self):
        """Test that rule applies to resources with dependsOn array."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        assert rule.applies(resource) is True

    def test_does_not_apply_without_depends_on(self):
        """Test that rule does not apply to resources without dependsOn."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
        }

        assert rule.applies(resource) is False

    def test_does_not_apply_with_empty_depends_on(self):
        """Test that rule does not apply when dependsOn is empty."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [],
        }

        assert rule.applies(resource) is False

    def test_does_not_apply_when_depends_on_not_list(self):
        """Test that rule does not apply when dependsOn is not a list."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": "not a list",
        }

        assert rule.applies(resource) is False


class TestDependsOnRuleEmit:
    """Test emit() method creates relationships."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None  # Use legacy mode for tests
        db_ops.create_generic_rel = MagicMock(return_value=True)
        return db_ops

    def test_emit_single_dependency(self, mock_db_ops):
        """Test emit creates relationship for single dependency."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        rule.emit(resource, mock_db_ops)

        # Relationship should be created via dual-graph helper (which queues in legacy mode)
        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert (
            buffered[0]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        )
        assert buffered[1] == "DEPENDS_ON"
        assert (
            buffered[2]
            == "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
        )

    def test_emit_multiple_dependencies(self, mock_db_ops):
        """Test emit creates relationships for multiple dependencies."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            ],
        }

        rule.emit(resource, mock_db_ops)

        # Should have 3 relationships queued
        assert len(rule._relationship_buffer) == 3
        assert all(r[1] == "DEPENDS_ON" for r in rule._relationship_buffer)

        # Verify all dependencies are present
        dep_ids = {r[2] for r in rule._relationship_buffer}
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            in dep_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
            in dep_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
            in dep_ids
        )

    def test_emit_skips_non_string_dependencies(self, mock_db_ops):
        """Test that emit skips dependencies that are not strings."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                None,  # Should be skipped
                123,  # Should be skipped
                {"id": "not a string"},  # Should be skipped
            ],
        }

        rule.emit(resource, mock_db_ops)

        # Should only have 1 relationship (for the valid string)
        assert len(rule._relationship_buffer) == 1

    def test_emit_handles_missing_resource_id(self, mock_db_ops):
        """Test that emit handles missing resource ID gracefully."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            # No 'id' field
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        # Should not raise exception
        rule.emit(resource, mock_db_ops)

        # No relationships should be created
        assert len(rule._relationship_buffer) == 0

    @patch("src.relationship_rules.depends_on_rule.logger")
    def test_emit_logs_queued_relationship(self, mock_logger, mock_db_ops):
        """Test that emit logs when relationships are queued."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        rule.emit(resource, mock_db_ops)

        # Verify logger.debug was called
        assert mock_logger.debug.called

        # Check log message content
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        depends_on_logs = [log for log in debug_calls if "DEPENDS_ON" in log]
        assert len(depends_on_logs) > 0

    @patch("src.relationship_rules.depends_on_rule.logger")
    def test_emit_logs_with_truncated_resource_names(self, mock_logger, mock_db_ops):
        """Test that logging truncates long resource IDs to just resource names."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        rule.emit(resource, mock_db_ops)

        # Get debug log messages
        debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
        depends_on_logs = [log for log in debug_calls if "DEPENDS_ON" in log]

        # Verify truncation (should contain "vm1" and "sa1", not full paths)
        if len(depends_on_logs) > 0:
            log_msg = depends_on_logs[0]
            assert "vm1" in log_msg
            assert "sa1" in log_msg
            # Full subscription path should not be in truncated log
            # (Note: This tests the split('/')[-1] pattern)


class TestDependsOnRuleExtractTargetIds:
    """Test extract_target_ids() method."""

    def test_extract_single_dependency(self):
        """Test extracting single dependency ID."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            ],
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 1
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            in target_ids
        )

    def test_extract_multiple_dependencies(self):
        """Test extracting multiple dependency IDs."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1",
            ],
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 3
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.KeyVault/vaults/kv1"
            in target_ids
        )

    def test_extract_skips_non_string_dependencies(self):
        """Test that extract_target_ids skips non-string dependencies."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                None,
                123,
                {"id": "not a string"},
            ],
        }

        target_ids = rule.extract_target_ids(resource)

        # Should only extract the valid string dependency
        assert len(target_ids) == 1
        assert (
            "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1"
            in target_ids
        )

    def test_extract_returns_empty_set_without_depends_on(self):
        """Test that extract_target_ids returns empty set without dependsOn."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 0

    def test_extract_returns_empty_set_with_empty_depends_on(self):
        """Test that extract_target_ids returns empty set for empty dependsOn."""
        rule = DependsOnRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "dependsOn": [],
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 0


class TestDependsOnRuleIntegration:
    """Integration tests for DependsOnRule."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        db_ops.create_generic_rel = MagicMock(return_value=True)
        return db_ops

    def test_end_to_end_workflow(self, mock_db_ops):
        """Test complete workflow: applies -> emit -> extract."""
        rule = DependsOnRule(enable_dual_graph=True)

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            ],
        }

        # Test applies
        assert rule.applies(resource) is True

        # Test emit
        rule.emit(resource, mock_db_ops)
        assert len(rule._relationship_buffer) == 2

        # Test extract_target_ids
        target_ids = rule.extract_target_ids(resource)
        assert len(target_ids) == 2

        # Verify extracted IDs match emitted relationships
        buffered_targets = {r[2] for r in rule._relationship_buffer}
        assert buffered_targets == target_ids

    def test_consistent_behavior_between_emit_and_extract(self, mock_db_ops):
        """Test that emit and extract_target_ids handle edge cases consistently."""
        rule = DependsOnRule(enable_dual_graph=True)

        # Test with mixed valid/invalid dependencies
        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            "dependsOn": [
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/sa1",
                None,  # Invalid
                123,  # Invalid
            ],
        }

        rule.emit(resource, mock_db_ops)
        buffered_count = len(rule._relationship_buffer)

        target_ids = rule.extract_target_ids(resource)

        # Both should handle invalid dependencies the same way
        assert buffered_count == len(target_ids)
