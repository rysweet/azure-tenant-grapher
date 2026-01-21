"""Tests for KeyVault soft-delete conflict handler.

Following TDD approach - tests written BEFORE implementation.

Test Coverage:
- Unit tests with mocked Azure SDK (60%)
- Edge case handling (30%)
- Error scenarios (10%)

Target test ratio: 2:1 to 3:1 (tests:implementation)
"""

from unittest.mock import Mock, patch

import pytest
from azure.core.exceptions import (
    HttpResponseError,
    ServiceRequestError,
)

from src.iac.keyvault_handler import KeyVaultHandler


class TestKeyVaultHandlerNoConflicts:
    """Test scenarios where no conflicts exist."""

    def test_no_soft_deleted_vaults_returns_empty_dict(self):
        """When no soft-deleted vaults exist, return empty mapping."""
        handler = KeyVaultHandler()

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = []

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault-1", "my-vault-2"],
                subscription_id="sub-12345",
            )

            assert result == {}
            mock_client.vaults.list_deleted.assert_called_once()

    def test_soft_deleted_vaults_exist_but_no_name_conflicts(self):
        """When soft-deleted vaults exist but names don't match, return empty."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "other-vault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault-1", "my-vault-2"],
                subscription_id="sub-12345",
            )

            assert result == {}


class TestKeyVaultHandlerConflictsWithoutPurge:
    """Test conflict resolution via name generation (auto_purge=False)."""

    def test_single_conflict_generates_new_name(self):
        """Single conflict generates unique name with -v2 suffix."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "my-vault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="sub-12345",
                auto_purge=False,
            )

            assert result == {"my-vault": "my-vault-v2"}

    def test_multiple_conflicts_generate_unique_names(self):
        """Multiple conflicts each get unique names."""
        handler = KeyVaultHandler()

        deleted_vault1 = Mock()
        deleted_vault1.name = "vault-a"
        deleted_vault1.properties.location = "eastus"

        deleted_vault2 = Mock()
        deleted_vault2.name = "vault-b"
        deleted_vault2.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [
                deleted_vault1,
                deleted_vault2,
            ]

            result = handler.handle_vault_conflicts(
                vault_names=["vault-a", "vault-b", "vault-c"],
                subscription_id="sub-12345",
                auto_purge=False,
            )

            assert result == {"vault-a": "vault-a-v2", "vault-b": "vault-b-v2"}

    def test_conflict_with_existing_v2_name_generates_v3(self):
        """If -v2 already exists, generate -v3."""
        handler = KeyVaultHandler()

        deleted_vault1 = Mock()
        deleted_vault1.name = "my-vault"
        deleted_vault1.properties.location = "eastus"

        deleted_vault2 = Mock()
        deleted_vault2.name = "my-vault-v2"
        deleted_vault2.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [
                deleted_vault1,
                deleted_vault2,
            ]

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="sub-12345",
                auto_purge=False,
            )

            assert result == {"my-vault": "my-vault-v3"}


class TestKeyVaultHandlerConflictsWithPurge:
    """Test conflict resolution via purge (auto_purge=True)."""

    def test_single_conflict_purged_returns_empty_dict(self):
        """When vault purged successfully, original name available - empty dict."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "my-vault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            mock_poller = Mock()
            mock_poller.result.return_value = None  # Purge succeeded
            mock_client.vaults.begin_purge_deleted_vault.return_value = mock_poller

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="sub-12345",
                auto_purge=True,
            )

            assert result == {}
            mock_client.vaults.begin_purge_deleted_vault.assert_called_once_with(
                vault_name="my-vault", location="eastus"
            )
            mock_poller.result.assert_called_once_with(timeout=60)

    def test_multiple_conflicts_all_purged(self):
        """Multiple conflicts all purged, empty dict returned."""
        handler = KeyVaultHandler()

        deleted_vault1 = Mock()
        deleted_vault1.name = "vault-a"
        deleted_vault1.properties.location = "eastus"

        deleted_vault2 = Mock()
        deleted_vault2.name = "vault-b"
        deleted_vault2.properties.location = "westus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [
                deleted_vault1,
                deleted_vault2,
            ]

            mock_poller = Mock()
            mock_poller.result.return_value = None
            mock_client.vaults.begin_purge_deleted_vault.return_value = mock_poller

            result = handler.handle_vault_conflicts(
                vault_names=["vault-a", "vault-b"],
                subscription_id="sub-12345",
                auto_purge=True,
            )

            assert result == {}
            assert mock_client.vaults.begin_purge_deleted_vault.call_count == 2


class TestKeyVaultHandlerLocationFiltering:
    """Test location-based filtering of soft-deleted vaults."""

    def test_location_filter_excludes_other_locations(self):
        """When location specified, only vaults in that location considered."""
        handler = KeyVaultHandler()

        vault_eastus = Mock()
        vault_eastus.name = "my-vault"
        vault_eastus.properties.location = "eastus"

        vault_westus = Mock()
        vault_westus.name = "my-vault"  # Same name, different location
        vault_westus.properties.location = "westus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [
                vault_eastus,
                vault_westus,
            ]

            # Check for vault in eastus - only eastus vault should conflict
            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="sub-12345",
                location="eastus",
                auto_purge=False,
            )

            assert result == {"my-vault": "my-vault-v2"}

    def test_location_filter_no_conflicts_in_target_location(self):
        """Location filter prevents conflicts from other regions."""
        handler = KeyVaultHandler()

        vault_westus = Mock()
        vault_westus.name = "my-vault"
        vault_westus.properties.location = "westus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [vault_westus]

            # Check in eastus - westus vault not a conflict
            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="sub-12345",
                location="eastus",
                auto_purge=False,
            )

            assert result == {}


class TestKeyVaultHandlerErrorHandling:
    """Test error handling for invalid inputs and Azure failures."""

    def test_empty_vault_names_raises_value_error(self):
        """Empty vault_names list raises ValueError."""
        handler = KeyVaultHandler()

        with pytest.raises(ValueError, match="vault_names cannot be empty"):
            handler.handle_vault_conflicts(
                vault_names=[],
                subscription_id="sub-12345",
            )

    def test_none_vault_names_raises_value_error(self):
        """None vault_names raises ValueError."""
        handler = KeyVaultHandler()

        with pytest.raises(ValueError, match="vault_names cannot be None"):
            handler.handle_vault_conflicts(
                vault_names=None,  # type: ignore
                subscription_id="sub-12345",
            )

    def test_purge_timeout_raises_timeout_error(self):
        """Purge operation timeout raises TimeoutError with vault name."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "my-vault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            mock_poller = Mock()
            mock_poller.result.side_effect = TimeoutError("Purge exceeded 60s")
            mock_client.vaults.begin_purge_deleted_vault.return_value = mock_poller

            with pytest.raises(
                TimeoutError, match="Purge operation timed out.*my-vault"
            ):
                handler.handle_vault_conflicts(
                    vault_names=["my-vault"],
                    subscription_id="sub-12345",
                    auto_purge=True,
                )

    def test_purge_permission_error_raises_permission_error(self):
        """Insufficient purge permissions raises PermissionError."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "my-vault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            http_error = HttpResponseError(
                message="Forbidden: Insufficient permissions"
            )
            http_error.status_code = 403
            mock_client.vaults.begin_purge_deleted_vault.side_effect = http_error

            with pytest.raises(PermissionError, match="Insufficient permissions"):
                handler.handle_vault_conflicts(
                    vault_names=["my-vault"],
                    subscription_id="sub-12345",
                    auto_purge=True,
                )

    def test_azure_service_error_logged_and_raised(self):
        """Azure service errors are logged with context and re-raised."""
        handler = KeyVaultHandler()

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.side_effect = ServiceRequestError(
                "Network failure"
            )

            with pytest.raises(ServiceRequestError, match="Network failure"):
                handler.handle_vault_conflicts(
                    vault_names=["my-vault"],
                    subscription_id="sub-12345",
                )


class TestKeyVaultHandlerEdgeCases:
    """Test edge cases and unusual scenarios."""

    def test_vault_name_with_special_characters(self):
        """Vault names with hyphens/numbers handled correctly."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "my-vault-123"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            result = handler.handle_vault_conflicts(
                vault_names=["my-vault-123"],
                subscription_id="sub-12345",
                auto_purge=False,
            )

            assert result == {"my-vault-123": "my-vault-123-v2"}

    def test_case_sensitive_name_matching(self):
        """Vault names are case-sensitive (Azure behavior)."""
        handler = KeyVaultHandler()

        deleted_vault = Mock()
        deleted_vault.name = "MyVault"
        deleted_vault.properties.location = "eastus"

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = [deleted_vault]

            # Check with lowercase - no conflict (case-sensitive)
            result = handler.handle_vault_conflicts(
                vault_names=["myvault"],
                subscription_id="sub-12345",
                auto_purge=False,
            )

            assert result == {}

    def test_subscription_id_format_not_validated(self):
        """Subscription ID format not validated (Azure SDK handles it)."""
        handler = KeyVaultHandler()

        with patch(
            "src.iac.keyvault_handler.KeyVaultManagementClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.vaults.list_deleted.return_value = []

            # Should not raise - Azure SDK will validate
            result = handler.handle_vault_conflicts(
                vault_names=["my-vault"],
                subscription_id="invalid-sub-id",
            )

            assert result == {}

    def test_default_azure_credential_used(self):
        """Verify DefaultAzureCredential is used for authentication."""
        handler = KeyVaultHandler()

        with patch(
            "src.iac.keyvault_handler.DefaultAzureCredential"
        ) as mock_cred_class:
            with patch(
                "src.iac.keyvault_handler.KeyVaultManagementClient"
            ) as mock_client_class:
                mock_client = mock_client_class.return_value
                mock_client.vaults.list_deleted.return_value = []

                handler.handle_vault_conflicts(
                    vault_names=["my-vault"],
                    subscription_id="sub-12345",
                )

                mock_cred_class.assert_called_once()
                mock_client_class.assert_called_once()
