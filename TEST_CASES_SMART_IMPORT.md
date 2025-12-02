# Test Cases for Smart Import Fixes

**Purpose**: Prevent regression of Bugs #113, #115, #116
**Target**: `src/iac/resource_comparator.py` and related components

---

## Test Suite Structure

```
tests/iac/
├── test_resource_comparator_scan_source_node.py  # NEW: Test SCAN_SOURCE_NODE handling
├── test_resource_comparator_heuristic_cleanup.py # NEW: Test heuristic ID cleanup
├── test_resource_comparator_validation.py         # NEW: Test validation warnings
└── test_resource_comparator.py                    # EXISTING: Update with new tests
```

---

## Test File 1: test_resource_comparator_scan_source_node.py

**Purpose**: Test that SCAN_SOURCE_NODE relationships are correctly queried and handled.

```python
"""
Tests for SCAN_SOURCE_NODE relationship handling in ResourceComparator.

These tests verify the fix for Bugs #113, #115, #116 where missing
SCAN_SOURCE_NODE relationships caused false positives/negatives.
"""

import pytest
from unittest.mock import MagicMock, Mock
from typing import Dict, Any

from src.iac.resource_comparator import (
    ResourceComparator,
    ResourceState,
)
from src.iac.target_scanner import TargetResource, TargetScanResult


@pytest.fixture
def mock_session_manager():
    """Create a mock Neo4jSessionManager."""
    mock_manager = MagicMock()
    mock_session = MagicMock()
    mock_manager.session.return_value.__enter__.return_value = mock_session
    mock_manager.session.return_value.__exit__ = Mock(return_value=False)
    return mock_manager


@pytest.fixture
def comparator(mock_session_manager):
    """Create a ResourceComparator instance."""
    return ResourceComparator(mock_session_manager)


class TestScanSourceNodeHandling:
    """Test SCAN_SOURCE_NODE relationship handling."""

    def test_scan_source_node_exists_cosmosdb(self, comparator):
        """Test that CosmosDB resource with SCAN_SOURCE_NODE is classified correctly."""
        # Setup: CosmosDB resource with transformed name
        abstracted_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/ballista_cosmosdb_a9c787_f05ca8",
            "name": "ballista_cosmosdb_a9c787_f05ca8",
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "location": "eastus",
            "tags": {},
        }

        # Mock SCAN_SOURCE_NODE query to return original ID
        original_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/ballista-cosmosdb"

        mock_result = MagicMock()
        mock_result.single.return_value = {"original_id": original_id}
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        # Target resource with original name
        target_resource = TargetResource(
            id=original_id,
            type="Microsoft.DocumentDB/databaseAccounts",
            name="ballista-cosmosdb",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Assert: Should be classified as EXACT_MATCH (or DRIFTED if name differs)
        # But definitely NOT NEW
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification != ResourceState.NEW, (
            f"CosmosDB resource incorrectly classified as NEW. "
            f"Classification: {classification.classification}, "
            f"Expected: EXACT_MATCH or DRIFTED"
        )

    def test_scan_source_node_missing_triggers_heuristic(self, comparator):
        """Test that missing SCAN_SOURCE_NODE triggers heuristic cleanup."""
        abstracted_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/test_db_abc123_def456",
            "name": "test_db_abc123_def456",
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "location": "eastus",
            "tags": {},
        }

        # Mock SCAN_SOURCE_NODE query to return None (relationship missing)
        mock_result = MagicMock()
        mock_result.single.return_value = None
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        # Target resource with cleaned name
        target_resource = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/test-db",
            type="Microsoft.DocumentDB/databaseAccounts",
            name="test-db",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Assert: Heuristic cleanup should match test_db_abc123_def456 → test-db
        assert len(result.classifications) == 1
        classification = result.classifications[0]

        # With heuristic cleanup, this should match
        assert classification.classification != ResourceState.NEW, (
            f"Heuristic cleanup failed to match resource. "
            f"Classification: {classification.classification}"
        )

    def test_scan_source_node_missing_for_runbooks(self, comparator):
        """Test runbook classification when SCAN_SOURCE_NODE is missing (Bug #115)."""
        abstracted_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Automation/automationAccounts/account1/runbooks/TestRunbook",
            "name": "TestRunbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "tags": {},
        }

        # Mock SCAN_SOURCE_NODE query to return None
        mock_result = MagicMock()
        mock_result.single.return_value = None
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        # Target resource
        target_resource = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Automation/automationAccounts/account1/runbooks/TestRunbook",
            type="Microsoft.Automation/automationAccounts/runbooks",
            name="TestRunbook",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Assert: Should match even without SCAN_SOURCE_NODE (exact name match)
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification != ResourceState.NEW

    def test_scan_source_node_missing_for_role_assignments(self, comparator):
        """Test role assignment classification when SCAN_SOURCE_NODE is missing (Bug #116)."""
        # Role assignments have GUID-based IDs
        abstracted_guid = "12345678-1234-1234-1234-123456789abc"
        target_guid = "12345678-1234-1234-1234-123456789abc"  # Same GUID

        abstracted_resource = {
            "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/{abstracted_guid}",
            "name": abstracted_guid,
            "type": "Microsoft.Authorization/roleAssignments",
            "location": None,
            "tags": {},
        }

        # Mock SCAN_SOURCE_NODE query to return None
        mock_result = MagicMock()
        mock_result.single.return_value = None
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        target_resource = TargetResource(
            id=f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/{target_guid}",
            type="Microsoft.Authorization/roleAssignments",
            name=target_guid,
            location=None,
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources([abstracted_resource], target_scan)

        # Assert: GUIDs match, should classify as EXACT_MATCH
        assert len(result.classifications) == 1
        classification = result.classifications[0]
        assert classification.classification != ResourceState.NEW


class TestHeuristicCleanup:
    """Test heuristic ID cleanup logic."""

    def test_heuristic_cleanup_removes_hex_suffix(self, comparator):
        """Test that heuristic cleanup removes hex suffix pattern."""
        abstracted_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/my_db_abc123_def456"

        cleaned_id = comparator._heuristic_clean_abstracted_id(abstracted_id)

        # Should remove _abc123_def456 suffix
        assert "abc123" not in cleaned_id
        assert "def456" not in cleaned_id
        assert "my-db" in cleaned_id.lower() or "my_db" in cleaned_id.lower()

    def test_heuristic_cleanup_replaces_underscores(self, comparator):
        """Test that heuristic cleanup replaces underscores with hyphens."""
        abstracted_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/my_database_abc123_def456"

        cleaned_id = comparator._heuristic_clean_abstracted_id(abstracted_id)

        # After removing suffix and replacing underscores
        assert "my-database" in cleaned_id

    def test_heuristic_cleanup_handles_no_pattern(self, comparator):
        """Test that heuristic cleanup returns original if no pattern matches."""
        abstracted_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/mystorage"

        cleaned_id = comparator._heuristic_clean_abstracted_id(abstracted_id)

        # No pattern to clean, should return original
        assert cleaned_id == abstracted_id

    def test_heuristic_cleanup_handles_invalid_id(self, comparator):
        """Test that heuristic cleanup handles invalid ID formats gracefully."""
        abstracted_id = "invalid-id-format"

        cleaned_id = comparator._heuristic_clean_abstracted_id(abstracted_id)

        # Should return original without crashing
        assert cleaned_id == abstracted_id


class TestValidationWarnings:
    """Test validation warnings for suspicious classification patterns."""

    def test_validation_warning_high_new_percentage(self, comparator, caplog):
        """Test that validation warning is logged when > 50% resources are NEW."""
        import logging

        caplog.set_level(logging.WARNING)

        # Create 10 abstracted resources, all will be classified as NEW
        abstracted_resources = [
            {
                "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage{i}",
                "name": f"storage{i}",
                "type": "Microsoft.Storage/storageAccounts",
                "location": "eastus",
                "tags": {},
            }
            for i in range(10)
        ]

        # Mock SCAN_SOURCE_NODE queries to return None (all missing)
        mock_result = MagicMock()
        mock_result.single.return_value = None
        comparator.session_manager.session.return_value.__enter__.return_value.run.return_value = mock_result

        # Empty target scan (all will be NEW)
        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources(abstracted_resources, target_scan)

        # Assert: Should log warning about high NEW percentage
        assert any("SUSPICIOUS CLASSIFICATION" in record.message for record in caplog.records)

    def test_validation_no_warning_normal_percentage(self, comparator, caplog):
        """Test that no warning is logged when NEW percentage is < 50%."""
        import logging

        caplog.set_level(logging.WARNING)

        # Create 2 abstracted resources
        abstracted_resource_new = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage_new",
            "name": "storage_new",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {},
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-new",
        }

        abstracted_resource_match = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage_match",
            "name": "storage_match",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "tags": {},
            "original_id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-match",
        }

        # Target scan with one matching resource
        target_resource_match = TargetResource(
            id="/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Storage/storageAccounts/storage-match",
            type="Microsoft.Storage/storageAccounts",
            name="storage-match",
            location="eastus",
            resource_group="rg1",
            subscription_id="sub1",
            properties={},
            tags={},
        )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=[target_resource_match],
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources(
            [abstracted_resource_new, abstracted_resource_match], target_scan
        )

        # Assert: 50% NEW, should not log warning
        assert not any("SUSPICIOUS CLASSIFICATION" in record.message for record in caplog.records)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios."""

    def test_bug_113_cosmosdb_false_positives(self, comparator):
        """
        Integration test for Bug #113: CosmosDB false positives.

        Scenario: 35 CosmosDB accounts in abstracted graph, all have
        SCAN_SOURCE_NODE relationships, should NOT be classified as NEW.
        """
        # Create 5 sample CosmosDB resources (representing the 35)
        abstracted_resources = []
        target_resources = []

        for i in range(5):
            abstracted_name = f"cosmosdb_{i}_abc123_def456"
            original_name = f"cosmosdb-{i}"

            abstracted_resources.append(
                {
                    "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/{abstracted_name}",
                    "name": abstracted_name,
                    "type": "Microsoft.DocumentDB/databaseAccounts",
                    "location": "eastus",
                    "tags": {},
                }
            )

            target_resources.append(
                TargetResource(
                    id=f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/{original_name}",
                    type="Microsoft.DocumentDB/databaseAccounts",
                    name=original_name,
                    location="eastus",
                    resource_group="rg1",
                    subscription_id="sub1",
                    properties={},
                    tags={},
                )
            )

        # Mock SCAN_SOURCE_NODE queries to return original IDs
        def mock_run_side_effect(*args, **kwargs):
            query_params = args[1] if len(args) > 1 else kwargs.get("parameters", {})
            abstracted_id = query_params.get("abstracted_id", "")

            # Extract index from abstracted_id
            for i in range(5):
                if f"cosmosdb_{i}" in abstracted_id:
                    original_id = f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb-{i}"
                    mock_result = MagicMock()
                    mock_result.single.return_value = {"original_id": original_id}
                    return mock_result

            # Default: no relationship found
            mock_result = MagicMock()
            mock_result.single.return_value = None
            return mock_result

        comparator.session_manager.session.return_value.__enter__.return_value.run.side_effect = mock_run_side_effect

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=target_resources,
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources(abstracted_resources, target_scan)

        # Assert: NONE should be classified as NEW (all should match)
        new_count = sum(
            1
            for c in result.classifications
            if c.classification == ResourceState.NEW
        )

        assert new_count == 0, (
            f"Bug #113 regression: {new_count}/5 CosmosDB resources classified as NEW. "
            f"All should be EXACT_MATCH or DRIFTED."
        )

    def test_bug_115_runbook_false_negative(self, comparator):
        """
        Integration test for Bug #115: Automation runbook false negative.

        Scenario: 17 runbooks in abstracted graph, only 1 gets import block.
        Should ALL get import blocks (EXACT_MATCH or DRIFTED).
        """
        # Create runbook resources
        runbook_names = [
            "AzureAutomationTutorialWithIdentity",
            "Install_Crowdstrike_Without_Promot",
            "TestRunbook",
        ]

        abstracted_resources = []
        target_resources = []

        for name in runbook_names:
            abstracted_resources.append(
                {
                    "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Automation/automationAccounts/account1/runbooks/{name}",
                    "name": name,
                    "type": "Microsoft.Automation/automationAccounts/runbooks",
                    "location": "eastus",
                    "tags": {},
                    "original_id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Automation/automationAccounts/account1/runbooks/{name}",
                }
            )

            target_resources.append(
                TargetResource(
                    id=f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Automation/automationAccounts/account1/runbooks/{name}",
                    type="Microsoft.Automation/automationAccounts/runbooks",
                    name=name,
                    location="eastus",
                    resource_group="rg1",
                    subscription_id="sub1",
                    properties={},
                    tags={},
                )
            )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=target_resources,
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources(abstracted_resources, target_scan)

        # Assert: NONE should be classified as NEW
        new_count = sum(
            1
            for c in result.classifications
            if c.classification == ResourceState.NEW
        )

        assert new_count == 0, (
            f"Bug #115 regression: {new_count}/3 runbooks classified as NEW. "
            f"All should be EXACT_MATCH or DRIFTED."
        )

    def test_bug_116_role_assignment_false_negatives(self, comparator):
        """
        Integration test for Bug #116: Role assignment false negatives.

        Scenario: 160 role assignments, all classified as NEW (0 import blocks).
        Should ALL get import blocks.
        """
        # Create 3 sample role assignments (representing the 160)
        role_guids = [
            "12345678-1234-1234-1234-123456789001",
            "12345678-1234-1234-1234-123456789002",
            "12345678-1234-1234-1234-123456789003",
        ]

        abstracted_resources = []
        target_resources = []

        for guid in role_guids:
            abstracted_resources.append(
                {
                    "id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/{guid}",
                    "name": guid,
                    "type": "Microsoft.Authorization/roleAssignments",
                    "location": None,
                    "tags": {},
                    "original_id": f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/{guid}",
                }
            )

            target_resources.append(
                TargetResource(
                    id=f"/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Authorization/roleAssignments/{guid}",
                    type="Microsoft.Authorization/roleAssignments",
                    name=guid,
                    location=None,
                    resource_group="rg1",
                    subscription_id="sub1",
                    properties={},
                    tags={},
                )
            )

        target_scan = TargetScanResult(
            tenant_id="tenant1",
            subscription_id="sub1",
            resources=target_resources,
            scan_timestamp="2025-01-01T00:00:00Z",
        )

        # Act
        result = comparator.compare_resources(abstracted_resources, target_scan)

        # Assert: NONE should be classified as NEW
        new_count = sum(
            1
            for c in result.classifications
            if c.classification == ResourceState.NEW
        )

        assert new_count == 0, (
            f"Bug #116 regression: {new_count}/3 role assignments classified as NEW. "
            f"All should be EXACT_MATCH or DRIFTED."
        )
```

---

## Integration with Existing Tests

### Updates to tests/iac/test_resource_comparator.py

Add these test cases to the existing file:

```python
def test_bug_113_116_regression_suite(comparator):
    """
    Combined regression test for Bugs #113, #115, #116.

    Ensures that resources with SCAN_SOURCE_NODE relationships are
    NOT classified as NEW when they exist in target scan.
    """
    # ... implementation combines all three bug scenarios
```

---

## Running the Tests

```bash
# Run all resource comparator tests
pytest tests/iac/test_resource_comparator*.py -v

# Run only new SCAN_SOURCE_NODE tests
pytest tests/iac/test_resource_comparator_scan_source_node.py -v

# Run only heuristic cleanup tests
pytest tests/iac/test_resource_comparator_heuristic_cleanup.py::TestHeuristicCleanup -v

# Run only validation tests
pytest tests/iac/test_resource_comparator_validation.py::TestValidationWarnings -v

# Run specific bug regression test
pytest tests/iac/test_resource_comparator_scan_source_node.py::TestIntegrationScenarios::test_bug_113_cosmosdb_false_positives -v
```

---

## Expected Test Results

After implementing the fixes:

✅ **All tests should pass**

Key metrics:
- **0 resources** should be incorrectly classified as NEW when they exist in target
- **Heuristic cleanup** should match at least 80% of resources with missing SCAN_SOURCE_NODE
- **Validation warnings** should appear when > 50% resources are NEW

---

## Coverage Requirements

| Component | Target Coverage | Critical Paths |
|-----------|----------------|----------------|
| `_get_original_azure_id()` | 100% | SCAN_SOURCE_NODE query, fallback, heuristic |
| `_heuristic_clean_abstracted_id()` | 100% | Suffix removal, underscore replacement |
| `_classify_abstracted_resource()` | 95% | All classification branches |
| `_validate_classification_summary()` | 100% | Warning thresholds |

Run coverage:
```bash
pytest tests/iac/test_resource_comparator*.py --cov=src.iac.resource_comparator --cov-report=term-missing
```

---

## Continuous Integration

Add to CI pipeline:

```yaml
- name: Run Smart Import Regression Tests
  run: |
    pytest tests/iac/test_resource_comparator_scan_source_node.py -v --tb=short
    if [ $? -ne 0 ]; then
      echo "CRITICAL: Smart import regression tests failed!"
      echo "This may indicate Bugs #113, #115, #116 have regressed."
      exit 1
    fi
```

---

Arrr, these test cases be yer insurance against regression of these bugs! 🏴‍☠️
