"""Unit tests for conflict detection module.

These tests use mocked Azure SDK clients to verify conflict detection
logic without making actual API calls.
"""

from unittest.mock import Mock

import pytest
from azure.core.exceptions import AzureError, ResourceNotFoundError

from src.iac.conflict_detector import (
    ConflictDetector,
    ConflictReport,
    ConflictType,
    ResourceConflict,
)


@pytest.fixture
def mock_resource_client():
    """Mock ResourceManagementClient."""
    client = Mock()
    client.resources.list.return_value = []
    return client


@pytest.fixture
def mock_keyvault_client():
    """Mock KeyVaultManagementClient."""
    client = Mock()
    client.vaults.list_deleted.return_value = []
    return client


@pytest.fixture
def mock_lock_client():
    """Mock ManagementLockClient."""
    client = Mock()
    client.management_locks.list_at_resource_group_level.return_value = []
    return client


@pytest.fixture
def mock_clients(mock_resource_client, mock_keyvault_client, mock_lock_client):
    """All mock clients."""
    return (mock_resource_client, mock_keyvault_client, mock_lock_client)


@pytest.fixture
def mock_credential():
    """Mock Azure credential."""
    return Mock()


class TestConflictDetector:
    """Test ConflictDetector initialization and basic functionality."""

    def test_initialization(self, mock_credential):
        """Test detector initialization."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        assert detector.subscription_id == "test-sub-id"
        assert detector.credential == mock_credential
        assert detector.timeout == 300

    def test_lazy_client_initialization(self, mock_credential):
        """Test that clients are lazily initialized."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        assert detector._resource_client is None
        assert detector._keyvault_client is None
        assert detector._lock_client is None

        # Access properties to trigger lazy initialization
        _ = detector.resource_client
        _ = detector.keyvault_client
        _ = detector.lock_client

        # Should now be initialized
        assert detector._resource_client is not None
        assert detector._keyvault_client is not None
        assert detector._lock_client is not None


class TestExistingResourceDetection:
    """Test detection of existing resources."""

    @pytest.mark.asyncio
    async def test_detect_existing_resource_conflict(
        self, mock_resource_client, mock_credential
    ):
        """Test detection of existing resource with same name."""
        # Setup: Mock existing storage account
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "existingstorageacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        # Plan to deploy resource with same name
        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "existingstorageacct",
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client

        report = await detector.detect_conflicts(planned)

        # Assert: Conflict detected
        assert report.has_conflicts
        assert report.existing_resources_found == 1
        assert len(report.conflicts) == 1
        assert report.conflicts[0].conflict_type == ConflictType.EXISTING_RESOURCE
        assert report.conflicts[0].resource_name == "existingstorageacct"

    @pytest.mark.asyncio
    async def test_no_conflict_different_names(
        self, mock_resource_client, mock_credential
    ):
        """Test no conflict when names differ."""
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "existingacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "newacct",  # Different name
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client

        report = await detector.detect_conflicts(planned)

        assert not report.has_conflicts
        assert report.existing_resources_found == 0

    @pytest.mark.asyncio
    async def test_no_conflict_different_types(
        self, mock_resource_client, mock_credential
    ):
        """Test no conflict when resource types differ."""
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "testacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        planned = [
            {
                "type": "Microsoft.KeyVault/vaults",  # Different type
                "name": "testacct",
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client

        report = await detector.detect_conflicts(planned)

        assert not report.has_conflicts


class TestSoftDeletedVaultDetection:
    """Test detection of soft-deleted Key Vaults."""

    @pytest.mark.asyncio
    async def test_detect_soft_deleted_vault(
        self, mock_keyvault_client, mock_credential
    ):
        """Test detection of soft-deleted Key Vault."""
        # Setup: Mock soft-deleted vault
        mock_vault = Mock()
        mock_vault.name = "deleted-vault"
        mock_vault.properties = Mock()
        mock_vault.properties.location = "eastus"
        mock_vault.properties.deletion_date = "2025-01-01T00:00:00Z"
        mock_vault.properties.scheduled_purge_date = "2025-04-01T00:00:00Z"
        mock_keyvault_client.vaults.list_deleted.return_value = [mock_vault]

        planned = [{"type": "Microsoft.KeyVault/vaults", "name": "deleted-vault"}]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._keyvault_client = mock_keyvault_client

        report = await detector.detect_conflicts(planned)

        assert report.has_conflicts
        assert report.soft_deleted_vaults_found == 1
        assert (
            report.conflicts[0].conflict_type == ConflictType.SOFT_DELETED_KEYVAULT
        )
        assert "purge" in report.conflicts[0].remediation_actions[0].lower()

    @pytest.mark.asyncio
    async def test_no_soft_deleted_conflict(
        self, mock_keyvault_client, mock_credential
    ):
        """Test no conflict when vault not soft-deleted."""
        mock_keyvault_client.vaults.list_deleted.return_value = []

        planned = [{"type": "Microsoft.KeyVault/vaults", "name": "new-vault"}]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._keyvault_client = mock_keyvault_client

        report = await detector.detect_conflicts(planned)

        assert not report.has_conflicts

    @pytest.mark.asyncio
    async def test_multiple_soft_deleted_vaults(
        self, mock_keyvault_client, mock_credential
    ):
        """Test detection of multiple soft-deleted vaults."""
        # Setup: Mock multiple soft-deleted vaults
        mock_vault1 = Mock()
        mock_vault1.name = "vault-1"
        mock_vault1.properties = Mock()
        mock_vault1.properties.location = "eastus"
        mock_vault1.properties.deletion_date = "2025-01-01T00:00:00Z"
        mock_vault1.properties.scheduled_purge_date = "2025-04-01T00:00:00Z"

        mock_vault2 = Mock()
        mock_vault2.name = "vault-2"
        mock_vault2.properties = Mock()
        mock_vault2.properties.location = "westus"
        mock_vault2.properties.deletion_date = "2025-01-15T00:00:00Z"
        mock_vault2.properties.scheduled_purge_date = "2025-04-15T00:00:00Z"

        mock_keyvault_client.vaults.list_deleted.return_value = [
            mock_vault1,
            mock_vault2,
        ]

        planned = [
            {"type": "Microsoft.KeyVault/vaults", "name": "vault-1"},
            {"type": "Microsoft.KeyVault/vaults", "name": "vault-2"},
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._keyvault_client = mock_keyvault_client

        report = await detector.detect_conflicts(planned)

        assert report.has_conflicts
        assert report.soft_deleted_vaults_found == 2
        assert len(report.conflicts) == 2


class TestLockedResourceGroupDetection:
    """Test detection of locked resource groups."""

    @pytest.mark.asyncio
    async def test_detect_locked_resource_group(
        self, mock_lock_client, mock_credential
    ):
        """Test detection of locked resource group."""
        # Setup: Mock RG lock
        mock_lock = Mock()
        mock_lock.level = "CanNotDelete"
        mock_lock.name = "DevTestLabLock"
        mock_lock_client.management_locks.list_at_resource_group_level.return_value = [
            mock_lock
        ]

        planned = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "resource_group": "locked-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(planned)

        assert report.has_conflicts
        assert report.locked_rgs_found == 1
        assert (
            report.conflicts[0].conflict_type == ConflictType.LOCKED_RESOURCE_GROUP
        )
        assert report.conflicts[0].lock_type == "CanNotDelete"

    @pytest.mark.asyncio
    async def test_no_lock_on_new_rg(self, mock_lock_client, mock_credential):
        """Test no conflict when RG doesn't exist yet."""
        # RG doesn't exist - should not raise error
        mock_lock_client.management_locks.list_at_resource_group_level.side_effect = (
            ResourceNotFoundError()
        )

        planned = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "resource_group": "new-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(planned)

        # Should not treat as conflict
        assert not report.has_conflicts

    @pytest.mark.asyncio
    async def test_multiple_locks_on_rg(self, mock_lock_client, mock_credential):
        """Test detection of multiple locks on same RG."""
        # Setup: Mock multiple locks
        mock_lock1 = Mock()
        mock_lock1.level = "CanNotDelete"
        mock_lock1.name = "Lock1"

        mock_lock2 = Mock()
        mock_lock2.level = "ReadOnly"
        mock_lock2.name = "Lock2"

        mock_lock_client.management_locks.list_at_resource_group_level.return_value = [
            mock_lock1,
            mock_lock2,
        ]

        planned = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "resource_group": "locked-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(planned)

        assert report.has_conflicts
        assert report.locked_rgs_found == 1
        # Should contain both lock types
        assert "CanNotDelete" in report.conflicts[0].lock_type
        assert "ReadOnly" in report.conflicts[0].lock_type


class TestMultipleConflictTypes:
    """Test detecting multiple types of conflicts simultaneously."""

    @pytest.mark.asyncio
    async def test_multiple_conflict_types(self, mock_clients, mock_credential):
        """Test detecting multiple types of conflicts simultaneously."""
        mock_resource_client, mock_keyvault_client, mock_lock_client = mock_clients

        # Setup: Existing resource
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "existingacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        # Setup: Soft-deleted vault
        mock_vault = Mock()
        mock_vault.name = "deleted-vault"
        mock_vault.properties = Mock()
        mock_vault.properties.location = "eastus"
        mock_vault.properties.deletion_date = "2025-01-01T00:00:00Z"
        mock_vault.properties.scheduled_purge_date = "2025-04-01T00:00:00Z"
        mock_keyvault_client.vaults.list_deleted.return_value = [mock_vault]

        # Setup: Locked RG
        mock_lock = Mock()
        mock_lock.level = "CanNotDelete"
        mock_lock_client.management_locks.list_at_resource_group_level.return_value = [
            mock_lock
        ]

        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "existingacct",
                "resource_group": "locked-rg",
            },
            {
                "type": "Microsoft.KeyVault/vaults",
                "name": "deleted-vault",
                "resource_group": "locked-rg",
            },
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client
        detector._keyvault_client = mock_keyvault_client
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(planned)

        # Assert: All three conflict types detected
        assert report.has_conflicts
        assert report.existing_resources_found == 1
        assert report.soft_deleted_vaults_found == 1
        assert report.locked_rgs_found == 1
        assert len(report.conflicts) == 3

        summary = report.conflict_summary
        assert summary[ConflictType.EXISTING_RESOURCE] == 1
        assert summary[ConflictType.SOFT_DELETED_KEYVAULT] == 1
        assert summary[ConflictType.LOCKED_RESOURCE_GROUP] == 1


class TestErrorHandling:
    """Test error handling and resilience."""

    @pytest.mark.asyncio
    async def test_api_error_adds_warning(self, mock_resource_client, mock_credential):
        """Test that API errors are caught and added as warnings."""
        mock_resource_client.resources.list.side_effect = AzureError("API rate limit")

        planned = [{"type": "Microsoft.Storage/storageAccounts", "name": "test"}]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client

        report = await detector.detect_conflicts(planned)

        # Should not crash, but add warning
        assert len(report.warnings) > 0
        assert (
            "API rate limit" in report.warnings[0]
            or "Failed to check" in report.warnings[0]
        )

    @pytest.mark.asyncio
    async def test_keyvault_api_error_adds_warning(
        self, mock_keyvault_client, mock_credential
    ):
        """Test that Key Vault API errors are caught and added as warnings."""
        mock_keyvault_client.vaults.list_deleted.side_effect = AzureError(
            "Permission denied"
        )

        planned = [{"type": "Microsoft.KeyVault/vaults", "name": "test-vault"}]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._keyvault_client = mock_keyvault_client

        report = await detector.detect_conflicts(planned)

        # Should not crash, but add warning
        assert len(report.warnings) > 0
        assert any("Failed to check soft-deleted vaults" in w for w in report.warnings)

    @pytest.mark.asyncio
    async def test_lock_api_error_graceful_handling(
        self, mock_lock_client, mock_credential
    ):
        """Test that lock API errors are caught gracefully without crashing."""
        # When list() is called, it will raise during iteration
        mock_lock_client.management_locks.list_at_resource_group_level.side_effect = (
            AzureError("Permission denied")
        )

        planned = [
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._lock_client = mock_lock_client

        # Should not crash - per-RG errors are logged but don't add warnings
        report = await detector.detect_conflicts(planned)

        # Should complete without crashing
        assert report is not None
        # Per-RG errors don't add warnings (by design - only catastrophic failures do)
        # This allows the check to continue for other RGs

    @pytest.mark.asyncio
    async def test_partial_failure_continues(self, mock_clients, mock_credential):
        """Test that partial failures don't block other checks."""
        mock_resource_client, mock_keyvault_client, mock_lock_client = mock_clients

        # Setup: Existing resource check succeeds
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "existingacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        # Setup: Vault check fails
        mock_keyvault_client.vaults.list_deleted.side_effect = AzureError(
            "API error"
        )

        # Setup: Lock check succeeds
        mock_lock_client.management_locks.list_at_resource_group_level.return_value = (
            []
        )

        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "existingacct",
                "resource_group": "test-rg",
            },
            {"type": "Microsoft.KeyVault/vaults", "name": "test-vault"},
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client
        detector._keyvault_client = mock_keyvault_client
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(planned)

        # Should have detected existing resource despite vault check failure
        assert report.existing_resources_found == 1
        assert len(report.warnings) > 0


class TestResourceExtraction:
    """Test resource group and vault extraction methods."""

    def test_extract_resource_groups_from_property(self, mock_credential):
        """Test extracting RG names from resource_group property."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)

        resources = [
            {"name": "vm1", "resource_group": "rg-1"},
            {"name": "vm2", "resource_group": "rg-2"},
            {"name": "vm3", "resource_group": "rg-1"},  # Duplicate
        ]

        rgs = detector._extract_resource_groups(resources)

        assert len(rgs) == 2
        assert "rg-1" in rgs
        assert "rg-2" in rgs

    def test_extract_resource_groups_from_id(self, mock_credential):
        """Test extracting RG names from resource IDs."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)

        resources = [
            {
                "name": "vm1",
                "id": "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Compute/virtualMachines/vm1",
            },
            {
                "name": "vm2",
                "id": "/subscriptions/sub-1/resourceGroups/rg-2/providers/Microsoft.Compute/virtualMachines/vm2",
            },
        ]

        rgs = detector._extract_resource_groups(resources)

        assert len(rgs) == 2
        assert "rg-1" in rgs
        assert "rg-2" in rgs

    def test_extract_key_vaults(self, mock_credential):
        """Test extracting Key Vault names."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)

        resources = [
            {"name": "vault1", "type": "Microsoft.KeyVault/vaults"},
            {"name": "vault2", "type": "Microsoft.KeyVault/vaults"},
            {"name": "vm1", "type": "Microsoft.Compute/virtualMachines"},
        ]

        vaults = detector._extract_key_vaults(resources)

        assert len(vaults) == 2
        assert "vault1" in vaults
        assert "vault2" in vaults


class TestConflictReport:
    """Test ConflictReport functionality."""

    def test_conflict_report_no_conflicts(self):
        """Test report when no conflicts found."""
        report = ConflictReport(subscription_id="test-sub")
        report.total_resources_checked = 10

        assert not report.has_conflicts
        formatted = report.format_report()

        assert "test-sub" in formatted
        assert "No conflicts detected" in formatted
        assert "should succeed" in formatted.lower()

    def test_conflict_report_with_conflicts(self):
        """Test report with conflicts."""
        report = ConflictReport(subscription_id="test-sub")

        report.conflicts.append(
            ResourceConflict(
                conflict_type=ConflictType.EXISTING_RESOURCE,
                resource_name="myacct",
                resource_type="Microsoft.Storage/storageAccounts",
                resource_group="test-rg",
                remediation_actions=["Delete resource", "Use --name-suffix"],
            )
        )

        report.conflicts.append(
            ResourceConflict(
                conflict_type=ConflictType.SOFT_DELETED_KEYVAULT,
                resource_name="myvault",
                resource_type="Microsoft.KeyVault/vaults",
                scheduled_purge_date="2025-04-01",
                remediation_actions=["Purge vault", "Use --auto-purge"],
            )
        )

        report.existing_resources_found = 1
        report.soft_deleted_vaults_found = 1
        report.total_resources_checked = 2

        formatted = report.format_report()

        # Assert report contains key information
        assert "test-sub" in formatted
        assert "EXISTING RESOURCE" in formatted
        assert "SOFT DELETED KEYVAULT" in formatted
        assert "myacct" in formatted
        assert "myvault" in formatted
        assert "Delete resource" in formatted
        assert "Purge vault" in formatted

    def test_conflict_summary(self):
        """Test conflict summary generation."""
        report = ConflictReport(subscription_id="test-sub")

        report.conflicts.append(
            ResourceConflict(
                conflict_type=ConflictType.EXISTING_RESOURCE,
                resource_name="res1",
                resource_type="Microsoft.Storage/storageAccounts",
            )
        )

        report.conflicts.append(
            ResourceConflict(
                conflict_type=ConflictType.EXISTING_RESOURCE,
                resource_name="res2",
                resource_type="Microsoft.Storage/storageAccounts",
            )
        )

        report.conflicts.append(
            ResourceConflict(
                conflict_type=ConflictType.SOFT_DELETED_KEYVAULT,
                resource_name="vault1",
                resource_type="Microsoft.KeyVault/vaults",
            )
        )

        summary = report.conflict_summary

        assert summary[ConflictType.EXISTING_RESOURCE] == 2
        assert summary[ConflictType.SOFT_DELETED_KEYVAULT] == 1
        assert summary[ConflictType.LOCKED_RESOURCE_GROUP] == 0

    def test_remediation_suggestions(self, mock_credential):
        """Test remediation suggestion generation."""
        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        report = ConflictReport(subscription_id="test-sub")

        # Add multiple conflicts
        for i in range(3):
            report.conflicts.append(
                ResourceConflict(
                    conflict_type=ConflictType.EXISTING_RESOURCE,
                    resource_name=f"res{i}",
                    resource_type="Microsoft.Storage/storageAccounts",
                )
            )
        report.existing_resources_found = 3

        detector._add_remediation_suggestions(report)

        # Should have cleanup script suggestion
        assert len(report.warnings) > 0
        assert any("cleanup script" in w.lower() for w in report.warnings)
        assert any("--name-suffix" in w for w in report.warnings)


class TestSelectiveChecking:
    """Test selective conflict checking flags."""

    @pytest.mark.asyncio
    async def test_check_existing_only(self, mock_clients, mock_credential):
        """Test checking only existing resources."""
        mock_resource_client, mock_keyvault_client, mock_lock_client = mock_clients

        # Setup all mock data
        mock_resource = Mock()
        mock_resource.type = "Microsoft.Storage/storageAccounts"
        mock_resource.name = "existingacct"
        mock_resource_client.resources.list.return_value = [mock_resource]

        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "existingacct",
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client
        detector._keyvault_client = mock_keyvault_client
        detector._lock_client = mock_lock_client

        # Check only existing resources
        report = await detector.detect_conflicts(
            planned, check_existing=True, check_soft_deleted=False, check_locks=False
        )

        # Vault and lock methods should not have been called
        mock_keyvault_client.vaults.list_deleted.assert_not_called()
        mock_lock_client.management_locks.list_at_resource_group_level.assert_not_called()

        # But resource check should have found conflict
        assert report.existing_resources_found == 1

    @pytest.mark.asyncio
    async def test_skip_all_checks(self, mock_clients, mock_credential):
        """Test skipping all checks."""
        mock_resource_client, mock_keyvault_client, mock_lock_client = mock_clients

        planned = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "test",
                "resource_group": "test-rg",
            }
        ]

        detector = ConflictDetector("test-sub-id", credential=mock_credential)
        detector._resource_client = mock_resource_client
        detector._keyvault_client = mock_keyvault_client
        detector._lock_client = mock_lock_client

        report = await detector.detect_conflicts(
            planned, check_existing=False, check_soft_deleted=False, check_locks=False
        )

        # No checks should have been called
        mock_resource_client.resources.list.assert_not_called()
        mock_keyvault_client.vaults.list_deleted.assert_not_called()
        mock_lock_client.management_locks.list_at_resource_group_level.assert_not_called()

        assert not report.has_conflicts
