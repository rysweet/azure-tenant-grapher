"""
Unit tests for PR #902 Bug #3: Neo4j Label Fix.

This module provides focused unit tests for the Neo4j query label change
from :AzureResource to :Resource:Original in resource_fidelity_calculator.py.

Testing pyramid distribution: 60% unit tests
"""

from unittest.mock import MagicMock, Mock

import pytest

from src.validation.resource_fidelity_calculator import (
    RedactionLevel,
    ResourceFidelityCalculator,
)


class TestNeo4jQueryLabelFix:
    """Test the Neo4j query label fix in resource fidelity calculator."""

    def test_fetch_resources_uses_resource_original_label(self):
        """Verify _fetch_resources_from_neo4j uses :Resource:Original label."""
        # Create mock session manager
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)

        # Mock empty result
        mock_session.run.return_value = []

        # Create calculator
        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="test-source-sub",
            target_subscription_id="test-target-sub",
        )

        # Execute the query
        resources = calculator._fetch_resources_from_neo4j("test-subscription-id")

        # Verify query was called
        assert mock_session.run.called, "Neo4j query should be executed"

        # Get the query string
        query_string = mock_session.run.call_args[0][0]

        # Verify correct label is used
        assert ":Resource:Original" in query_string, \
            "Query must use :Resource:Original label (Bug #3 fix)"

        # Verify old label is NOT used
        assert ":AzureResource" not in query_string, \
            "Query must not use deprecated :AzureResource label"

    def test_query_structure_after_label_fix(self):
        """Verify complete query structure with corrected label."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="test-source",
            target_subscription_id="test-target",
        )

        # Execute query
        calculator._fetch_resources_from_neo4j("subscription-123")

        query_string = mock_session.run.call_args[0][0]

        # Verify query structure elements
        assert "MATCH" in query_string, "Query should have MATCH clause"
        assert "(r:Resource:Original)" in query_string, \
            "Query should match nodes with both :Resource and :Original labels"
        assert "r.subscription_id" in query_string, \
            "Query should filter by subscription_id"
        assert "RETURN" in query_string, "Query should have RETURN clause"

    def test_query_parameters_with_subscription_id(self):
        """Verify query parameters include subscription_id correctly."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        test_subscription = "9b00bc5e-9abc-45de-9958-02a9d9277b16"
        calculator._fetch_resources_from_neo4j(test_subscription)

        # Verify query parameters
        query_params = mock_session.run.call_args[0][1]
        assert "subscription_id" in query_params, \
            "Query parameters must include subscription_id"
        assert query_params["subscription_id"] == test_subscription, \
            "subscription_id parameter must match input"

    def test_query_with_resource_type_filter_uses_correct_label(self):
        """Verify query with resource_type filter still uses correct label."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        # Execute query with resource type filter
        calculator._fetch_resources_from_neo4j(
            "subscription-123",
            resource_type="Microsoft.Storage/storageAccounts"
        )

        query_string = mock_session.run.call_args[0][0]

        # Verify correct label even with filter
        assert ":Resource:Original" in query_string, \
            "Filtered query must use :Resource:Original label"
        assert ":AzureResource" not in query_string, \
            "Filtered query must not use :AzureResource label"

        # Verify filter is applied
        assert "r.type" in query_string, \
            "Query should filter by resource type"

        # Verify parameters include resource_type
        query_params = mock_session.run.call_args[0][1]
        assert "resource_type" in query_params
        assert query_params["resource_type"] == "Microsoft.Storage/storageAccounts"

    def test_query_returns_expected_fields(self):
        """Verify query returns all expected resource fields."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        calculator._fetch_resources_from_neo4j("sub-123")

        query_string = mock_session.run.call_args[0][0]

        # Verify RETURN clause includes expected fields
        assert "r.id" in query_string, "Query should return resource id"
        assert "r.name" in query_string, "Query should return resource name"
        assert "r.type" in query_string, "Query should return resource type"
        assert "r.properties" in query_string, "Query should return resource properties"

    def test_empty_result_handling_with_correct_label(self):
        """Verify empty query results are handled correctly with new label."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)

        # Return empty result
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        # Should not crash with empty results
        resources = calculator._fetch_resources_from_neo4j("sub-123")

        # Should return empty list
        assert resources == [], "Empty query result should return empty list"

    def test_multiple_resources_returned_with_correct_label(self):
        """Verify multiple resources are correctly parsed from query results."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)

        # Mock multiple resource records
        mock_record1 = {
            "id": "/subscriptions/sub/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {"sku": {"name": "Standard_LRS"}},
        }
        mock_record2 = {
            "id": "/subscriptions/sub/resourceGroups/rg2/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "properties": {"hardwareProfile": {"vmSize": "Standard_B2s"}},
        }

        # Create mock records that support dict-like access
        record1 = Mock()
        record1.__getitem__ = lambda self, key: mock_record1.get(key)
        record2 = Mock()
        record2.__getitem__ = lambda self, key: mock_record2.get(key)

        mock_session.run.return_value = [record1, record2]

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        resources = calculator._fetch_resources_from_neo4j("sub-123")

        # Verify both resources are returned
        assert len(resources) == 2, "Should return all resource records"

        # Verify query used correct label
        query_string = mock_session.run.call_args[0][0]
        assert ":Resource:Original" in query_string


class TestLabelMigrationCompatibility:
    """Test that the label fix maintains compatibility with existing data."""

    def test_calculator_works_with_multiple_labels(self):
        """Verify calculator works when Neo4j nodes have multiple labels."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)

        # Mock resource with multiple labels
        mock_record = {
            "id": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "properties": {"location": "eastus"},
        }
        record = Mock()
        record.__getitem__ = lambda self, key: mock_record.get(key)
        mock_session.run.return_value = [record]

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        # Should work without issues
        resources = calculator._fetch_resources_from_neo4j("sub-123")
        assert len(resources) == 1

    def test_query_label_syntax_is_valid_cypher(self):
        """Verify the label syntax :Resource:Original is valid Cypher."""
        mock_session_manager = Mock()
        mock_session = MagicMock()
        mock_session_manager.session.return_value.__enter__ = Mock(return_value=mock_session)
        mock_session_manager.session.return_value.__exit__ = Mock(return_value=False)
        mock_session.run.return_value = []

        calculator = ResourceFidelityCalculator(
            session_manager=mock_session_manager,
            source_subscription_id="source",
            target_subscription_id="target",
        )

        # Execute query
        calculator._fetch_resources_from_neo4j("sub-123")

        # Get query string
        query_string = mock_session.run.call_args[0][0]

        # Verify Cypher syntax for multiple labels is correct
        # Format: (variable:Label1:Label2)
        assert "(r:Resource:Original)" in query_string, \
            "Query should use correct Cypher syntax for multiple labels"


class TestRegressionPreventionLabelFix:
    """Regression tests to ensure label fix persists."""

    def test_no_hardcoded_azure_resource_label(self):
        """Ensure :AzureResource label is not hardcoded anywhere in calculator."""
        from src.validation import resource_fidelity_calculator
        import inspect

        source_code = inspect.getsource(resource_fidelity_calculator)

        # Check for old label
        assert ":AzureResource" not in source_code, \
            "Source code should not contain deprecated :AzureResource label"

    def test_resource_original_label_present(self):
        """Ensure :Resource:Original label is present in calculator."""
        from src.validation import resource_fidelity_calculator
        import inspect

        source_code = inspect.getsource(resource_fidelity_calculator)

        # Check for new label
        assert ":Resource:Original" in source_code, \
            "Source code should contain :Resource:Original label"

    def test_label_consistency_across_queries(self):
        """Verify label is consistent across all query methods."""
        from src.validation.resource_fidelity_calculator import ResourceFidelityCalculator
        import inspect

        # Get all methods that might construct queries
        methods = inspect.getmembers(ResourceFidelityCalculator, predicate=inspect.isfunction)

        # Check _fetch_resources_from_neo4j specifically
        for method_name, method in methods:
            if "fetch" in method_name.lower() or "query" in method_name.lower():
                source = inspect.getsource(method)
                if "MATCH" in source:  # This method constructs a Cypher query
                    assert ":Resource:Original" in source or ":AzureResource" not in source, \
                        f"Method {method_name} should use correct label"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
