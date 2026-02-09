"""Tests for deferred flush pattern in relationship rules (Issue #873).

This test suite validates the deferred flush pattern that prevents
relationships from being flushed before target nodes exist.

Key scenarios:
- enable_auto_flush=False prevents auto-flush (default behavior)
- enable_auto_flush=True allows auto-flush (legacy behavior)
- Relationships buffer correctly until explicit flush
- Explicit flush creates relationships when nodes exist
"""

from typing import Any, Dict
from unittest.mock import MagicMock, patch

import pytest

from src.relationship_rules.relationship_rule import RelationshipRule


class ConcreteRelationshipRule(RelationshipRule):
    """Concrete implementation for testing abstract base class."""

    def applies(self, resource: Dict[str, Any]) -> bool:
        return True

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        pass


class TestDeferredFlush:
    """Test suite for deferred flush pattern (Issue #873)."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None  # Use legacy mode for tests
        db_ops.create_generic_rel = MagicMock(return_value=True)
        return db_ops

    def test_default_enable_auto_flush_is_false(self):
        """Test that enable_auto_flush defaults to False (deferred flush mode)."""
        rule = ConcreteRelationshipRule()
        assert rule.enable_auto_flush is False

    def test_explicit_enable_auto_flush_true(self):
        """Test that enable_auto_flush can be set to True (legacy mode)."""
        rule = ConcreteRelationshipRule(enable_auto_flush=True)
        assert rule.enable_auto_flush is True

    def test_buffer_initialization_empty(self):
        """Test that relationship buffer starts empty."""
        rule = ConcreteRelationshipRule()
        assert len(rule._relationship_buffer) == 0
        assert rule._buffer_size == 100

    def test_queue_dual_graph_relationship_adds_to_buffer(self, mock_db_ops):
        """Test that queueing relationships adds them to buffer."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        src_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        tgt_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"

        rule.queue_dual_graph_relationship(src_id, "USES", tgt_id)

        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert buffered[0] == src_id
        assert buffered[1] == "USES"
        assert buffered[2] == tgt_id
        assert buffered[3] is None  # No properties

    def test_queue_dual_graph_relationship_with_properties(self, mock_db_ops):
        """Test queueing relationships with properties."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        src_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"
        tgt_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"
        props = {"ipConfiguration": "primary"}

        rule.queue_dual_graph_relationship(src_id, "CONNECTED_TO", tgt_id, props)

        assert len(rule._relationship_buffer) == 1
        buffered = rule._relationship_buffer[0]
        assert buffered[3] == props

    def test_auto_flush_disabled_by_default(self, mock_db_ops):
        """Test that auto-flush does NOT trigger when enable_auto_flush=False (default)."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)
        assert rule.enable_auto_flush is False

        # Queue relationships up to threshold
        for i in range(rule._buffer_size):
            rule.queue_dual_graph_relationship(
                f"/resource/{i}", "USES", f"/resource/{i+1000}"
            )

        # Call auto_flush_if_needed
        rule.auto_flush_if_needed(mock_db_ops)

        # Buffer should NOT be cleared (deferred flush)
        assert len(rule._relationship_buffer) == rule._buffer_size

    def test_auto_flush_enabled_when_explicitly_set(self, mock_db_ops):
        """Test that auto-flush DOES trigger when enable_auto_flush=True."""
        rule = ConcreteRelationshipRule(
            enable_dual_graph=True, enable_auto_flush=True
        )
        assert rule.enable_auto_flush is True

        # Queue relationships up to threshold
        for i in range(rule._buffer_size):
            rule.queue_dual_graph_relationship(
                f"/resource/{i}", "USES", f"/resource/{i+1000}"
            )

        # Call auto_flush_if_needed
        rule.auto_flush_if_needed(mock_db_ops)

        # Buffer SHOULD be cleared (auto-flush happened)
        assert len(rule._relationship_buffer) == 0

    def test_explicit_flush_clears_buffer(self, mock_db_ops):
        """Test that explicit flush_relationship_buffer() clears the buffer."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        # Queue several relationships
        for i in range(10):
            rule.queue_dual_graph_relationship(
                f"/resource/{i}", "USES", f"/resource/{i+1000}"
            )

        assert len(rule._relationship_buffer) == 10

        # Explicit flush
        created = rule.flush_relationship_buffer(mock_db_ops)

        # Buffer should be cleared
        assert len(rule._relationship_buffer) == 0
        assert created == 10  # All relationships created in legacy mode

    def test_flush_empty_buffer_returns_zero(self, mock_db_ops):
        """Test that flushing empty buffer returns 0."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        created = rule.flush_relationship_buffer(mock_db_ops)

        assert created == 0
        assert len(rule._relationship_buffer) == 0

    def test_create_dual_graph_relationship_queues_by_default(self, mock_db_ops):
        """Test that create_dual_graph_relationship queues (doesn't create immediately) when enable_auto_flush=False."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)
        assert rule.enable_auto_flush is False

        src_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        tgt_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkInterfaces/nic1"

        result = rule.create_dual_graph_relationship(
            mock_db_ops, src_id, "USES", tgt_id
        )

        # Should return True (queued successfully)
        assert result is True

        # Should be in buffer
        assert len(rule._relationship_buffer) == 1

        # Should NOT have called legacy create yet
        mock_db_ops.create_generic_rel.assert_not_called()

    def test_immediate_flush_bypasses_buffer(self, mock_db_ops):
        """Test that immediate_flush=True bypasses buffer and creates immediately."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        src_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1"
        tgt_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1"

        result = rule.create_dual_graph_relationship(
            mock_db_ops, src_id, "CONTAINS", tgt_id, immediate_flush=True
        )

        # Should return True (created immediately in legacy mode)
        assert result is True

        # Should NOT be in buffer
        assert len(rule._relationship_buffer) == 0

        # Should have called legacy create
        mock_db_ops.create_generic_rel.assert_called_once()

    def test_multiple_relationships_queued_correctly(self, mock_db_ops):
        """Test that multiple relationships are queued in order."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        relationships = [
            ("/vm/1", "USES", "/nic/1"),
            ("/nic/1", "CONNECTED_TO", "/subnet/1"),
            ("/subnet/1", "SECURED_BY", "/nsg/1"),
        ]

        for src, rel_type, tgt in relationships:
            rule.queue_dual_graph_relationship(src, rel_type, tgt)

        assert len(rule._relationship_buffer) == 3

        # Verify order preserved
        for i, (src, rel_type, tgt) in enumerate(relationships):
            buffered = rule._relationship_buffer[i]
            assert buffered[0] == src
            assert buffered[1] == rel_type
            assert buffered[2] == tgt

    @patch("src.relationship_rules.relationship_rule.logger")
    def test_flush_logs_buffer_size(self, mock_logger, mock_db_ops):
        """Test that flush operation logs statistics."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        # Queue relationships
        for i in range(5):
            rule.queue_dual_graph_relationship(
                f"/resource/{i}", "USES", f"/resource/{i+1000}"
            )

        # Flush
        rule.flush_relationship_buffer(mock_db_ops)

        # Verify buffer was cleared
        assert len(rule._relationship_buffer) == 0


class TestBufferSizeProtection:
    """Test buffer size protection (Issue #873 - robustness fix)."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        db_ops.create_generic_rel = MagicMock(return_value=True)
        return db_ops

    def test_buffer_size_within_limits(self, mock_db_ops):
        """Test that normal buffer sizes work correctly."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        # Queue up to buffer size (100)
        for i in range(rule._buffer_size):
            rule.queue_dual_graph_relationship(
                f"/resource/{i}", "USES", f"/resource/{i+1000}"
            )

        assert len(rule._relationship_buffer) == rule._buffer_size

        # Flush should work
        created = rule.flush_relationship_buffer(mock_db_ops)
        assert created == rule._buffer_size
        assert len(rule._relationship_buffer) == 0

    @patch("src.relationship_rules.relationship_rule.logger")
    def test_buffer_exceeds_max_size_forcibly_cleared(self, mock_logger, mock_db_ops):
        """Test that buffer exceeding max size (10x batch size) is forcibly cleared."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        # Simulate buffer growth beyond max (1000 = 10x batch size of 100)
        max_buffer_size = rule._buffer_size * 10
        for i in range(max_buffer_size + 100):
            rule._relationship_buffer.append(
                (f"/resource/{i}", "USES", f"/resource/{i+1000}", None)
            )

        assert len(rule._relationship_buffer) > max_buffer_size

        # Flush should detect oversized buffer
        created = rule.flush_relationship_buffer(mock_db_ops)

        # Buffer should be forcibly cleared
        assert len(rule._relationship_buffer) == 0
        # No relationships created (buffer was forcibly cleared)
        assert created == 0

        # Should have logged error
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        assert "exceeded max size" in error_call


class TestSecurityValidation:
    """Test security validation of relationship types (Issue #873 - H1 security fix)."""

    @pytest.fixture
    def mock_db_ops(self):
        """Provide mock database operations."""
        db_ops = MagicMock()
        db_ops.session_manager = None
        return db_ops

    def test_valid_relationship_types_accepted(self, mock_db_ops):
        """Test that valid relationship types are accepted."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        valid_types = [
            "CONTAINS",
            "USES_SUBNET",
            "SECURED_BY",
            "CONNECTED_TO",
            "DEPENDS_ON",
            "USES",
        ]

        for rel_type in valid_types:
            rule.queue_dual_graph_relationship(
                "/resource/src", rel_type, "/resource/tgt"
            )

        # All should be queued
        assert len(rule._relationship_buffer) == len(valid_types)

    @patch("src.relationship_rules.relationship_rule.logger")
    def test_invalid_relationship_type_skipped_during_flush(
        self, mock_logger, mock_db_ops
    ):
        """Test that invalid relationship types are skipped during flush."""
        rule = ConcreteRelationshipRule(enable_dual_graph=True)

        # Manually inject invalid relationship type into buffer
        rule._relationship_buffer.append(
            ("/resource/src", "INVALID_TYPE", "/resource/tgt", None)
        )

        # Flush should skip invalid type
        created = rule.flush_relationship_buffer(mock_db_ops)

        # No relationships created (invalid type skipped)
        assert created == 0

        # Should have logged error about invalid type
        mock_logger.error.assert_called()
        error_call = mock_logger.error.call_args[0][0]
        assert "INVALID_TYPE" in error_call

    def test_valid_relationship_types_whitelist_complete(self):
        """Test that VALID_RELATIONSHIP_TYPES whitelist is comprehensive."""
        rule = ConcreteRelationshipRule()

        expected_types = {
            "CONTAINS",
            "USES_SUBNET",
            "SECURED_BY",
            "CONNECTED_TO",
            "DEPENDS_ON",
            "USES_IDENTITY",
            "RESOLVES_TO",
            "CONNECTED_TO_PE",
            "MONITORS",
            "LOGS_TO",
            "USES_NETWORK",
            "TAGGED_WITH",
            "LOCATED_IN",
            "CREATED_BY",
            "SENDS_DIAG_TO",
            "ASSIGNED_TO",
            "HAS_ROLE",
            "INHERITS_TAG",
            "STORES_SECRET",
            "USES",
        }

        assert rule.VALID_RELATIONSHIP_TYPES == expected_types
