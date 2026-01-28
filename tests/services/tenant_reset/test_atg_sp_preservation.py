"""
Tests for ATG Service Principal Preservation (Issue #627).

CRITICAL: These tests verify that the ATG Service Principal is NEVER deleted
under ANY circumstances, as its deletion would permanently lock out the system.

Test Coverage:
- Multi-source ATG SP identification
- ATG SP preservation across all scopes (tenant, subscription, RG, resource)
- Configuration tampering detection
- Pre-flight validation
- Post-deletion verification
- ATG-managed resource protection
- Role assignment preservation

Target: 100% coverage for ATG SP preservation logic
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import List, Dict
import os
from pathlib import Path

# Imports will fail until implementation exists
from src.services.tenant_reset_service import TenantResetService
from src.services.reset_confirmation import ResetScope, SecurityError


class TestATGSPIdentification:
    """Test multi-source ATG Service Principal identification."""

    @pytest.fixture
    def mock_credential(self):
        """Mock Azure credential."""
        return Mock()

    @pytest.fixture
    def mock_tenant_id(self):
        """Mock tenant ID."""
        return "12345678-1234-1234-1234-123456789abc"

    @pytest.fixture
    def mock_atg_sp_id(self):
        """Mock ATG Service Principal object ID."""
        return "87654321-4321-4321-4321-210987654321"

    @pytest.fixture
    def service(self, mock_credential, mock_tenant_id):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=mock_credential,
            tenant_id=mock_tenant_id
        )

    @pytest.mark.asyncio
    async def test_identify_atg_sp_from_environment(self, service, mock_atg_sp_id):
        """Test ATG SP identification from environment variables."""
        with patch.dict(os.environ, {"AZURE_CLIENT_ID": mock_atg_sp_id}):
            atg_sp_id = await service.identify_atg_service_principal()
            assert atg_sp_id == mock_atg_sp_id

    @pytest.mark.asyncio
    async def test_identify_atg_sp_multi_source_agreement(
        self, service, mock_atg_sp_id
    ):
        """Test multi-source verification when all sources agree."""
        with patch.dict(os.environ, {"AZURE_CLIENT_ID": mock_atg_sp_id}):
            with patch("subprocess.check_output", return_value=mock_atg_sp_id.encode()):
                with patch.object(
                    service, "_query_neo4j_for_atg_sp", return_value=mock_atg_sp_id
                ):
                    atg_sp_id = await service.identify_atg_service_principal()
                    assert atg_sp_id == mock_atg_sp_id

    @pytest.mark.asyncio
    async def test_identify_atg_sp_multi_source_disagreement(self, service):
        """
        CRITICAL: Test that SP identification fails if sources disagree.

        This prevents configuration tampering attacks.
        """
        env_sp_id = "11111111-1111-1111-1111-111111111111"
        cli_sp_id = "22222222-2222-2222-2222-222222222222"

        with patch.dict(os.environ, {"AZURE_CLIENT_ID": env_sp_id}):
            with patch("subprocess.check_output", return_value=cli_sp_id.encode()):
                with pytest.raises(SecurityError) as exc:
                    await service.identify_atg_service_principal()

                assert "mismatch" in str(exc.value).lower()
                assert env_sp_id in str(exc.value)
                assert cli_sp_id in str(exc.value)

    @pytest.mark.asyncio
    async def test_identify_atg_sp_missing_environment_variable(self, service):
        """Test that missing AZURE_CLIENT_ID raises ValueError."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc:
                await service.identify_atg_service_principal()

            assert "AZURE_CLIENT_ID" in str(exc.value)


class TestATGSPPreservationTenantScope:
    """Test ATG SP preservation for tenant-level resets."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance with mocked credential."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.fixture
    def mock_atg_sp_id(self):
        """Mock ATG Service Principal ID."""
        return "87654321-4321-4321-4321-210987654321"

    @pytest.mark.asyncio
    async def test_atg_sp_excluded_from_tenant_deletion(
        self, service, mock_atg_sp_id
    ):
        """
        CRITICAL: Verify ATG SP is never included in tenant deletion scope.
        """
        all_service_principals = [
            {"id": "sp-1", "appId": "app-1", "displayName": "SP 1"},
            {"id": mock_atg_sp_id, "appId": "atg-app", "displayName": "ATG SP"},
            {"id": "sp-3", "appId": "app-3", "displayName": "SP 3"},
        ]

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            with patch.object(
                service,
                "_list_all_service_principals",
                return_value=all_service_principals,
            ):
                scope_data = await service.calculate_scope_tenant(
                    tenant_id="12345678-1234-1234-1234-123456789abc"
                )

                # ATG SP should be in preserved list
                assert mock_atg_sp_id in scope_data["to_preserve"]

                # ATG SP should NOT be in deletion list
                assert mock_atg_sp_id not in scope_data["to_delete"]

                # Other SPs should be in deletion list
                assert "sp-1" in scope_data["to_delete"]
                assert "sp-3" in scope_data["to_delete"]

    @pytest.mark.asyncio
    async def test_atg_sp_role_assignments_preserved(self, service, mock_atg_sp_id):
        """
        CRITICAL: Verify ATG SP role assignments are preserved.

        If role assignments are deleted, ATG loses access mid-operation.
        """
        all_role_assignments = [
            {"id": "role-1", "principalId": "sp-1", "roleDefinitionId": "role-def-1"},
            {
                "id": "role-atg",
                "principalId": mock_atg_sp_id,
                "roleDefinitionId": "contributor",
            },
            {"id": "role-3", "principalId": "sp-3", "roleDefinitionId": "role-def-3"},
        ]

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            with patch.object(
                service,
                "_list_all_role_assignments",
                return_value=all_role_assignments,
            ):
                scope_data = await service.calculate_scope_tenant(
                    tenant_id="12345678-1234-1234-1234-123456789abc"
                )

                # ATG SP role assignments should be preserved
                assert "role-atg" in scope_data["to_preserve"]

                # ATG SP role assignments should NOT be deleted
                assert "role-atg" not in scope_data["to_delete"]

                # Other role assignments should be deleted
                assert "role-1" in scope_data["to_delete"]
                assert "role-3" in scope_data["to_delete"]


class TestATGSPPreservationSubscriptionScope:
    """Test ATG SP preservation for subscription-level resets."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_atg_sp_excluded_from_subscription_deletion(self, service):
        """Verify ATG SP is excluded from subscription-level deletion."""
        mock_atg_sp_id = "87654321-4321-4321-4321-210987654321"
        subscription_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            scope_data = await service.calculate_scope_subscription([subscription_id])

            assert mock_atg_sp_id in scope_data["to_preserve"]
            assert mock_atg_sp_id not in scope_data["to_delete"]


class TestATGSPPreservationResourceGroupScope:
    """Test ATG SP preservation for resource group-level resets."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_atg_sp_excluded_from_rg_deletion(self, service):
        """Verify ATG SP is excluded from resource group deletion."""
        mock_atg_sp_id = "87654321-4321-4321-4321-210987654321"
        subscription_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        resource_group = "test-rg"

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            scope_data = await service.calculate_scope_resource_group(
                resource_group_names=[resource_group], subscription_id=subscription_id
            )

            assert mock_atg_sp_id in scope_data["to_preserve"]
            assert mock_atg_sp_id not in scope_data["to_delete"]


class TestATGSPPreservationResourceScope:
    """Test ATG SP preservation for single resource deletion."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_direct_atg_sp_deletion_blocked(self, service):
        """
        CRITICAL: Test that directly targeting ATG SP for deletion is blocked.
        """
        mock_atg_sp_id = "87654321-4321-4321-4321-210987654321"

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            with pytest.raises(SecurityError) as exc:
                await service.calculate_scope_resource(resource_id=mock_atg_sp_id)

            assert "ATG Service Principal cannot be deleted" in str(exc.value)


class TestConfigurationIntegrity:
    """Test configuration tampering detection."""

    @pytest.fixture
    def config_file(self, tmp_path):
        """Create temporary config file."""
        config = tmp_path / ".env"
        config.write_text("AZURE_CLIENT_ID=87654321-4321-4321-4321-210987654321\n")
        return config

    def test_config_integrity_initial_signature_creation(self, config_file):
        """Test initial signature file creation."""
        from src.services.tenant_reset_service import validate_config_integrity

        # First call should create signature
        assert validate_config_integrity(config_file) is True

        # Signature file should exist
        signature_file = config_file.parent / f"{config_file.name}.sig"
        assert signature_file.exists()

    def test_config_integrity_validation_success(self, config_file):
        """Test that unmodified config passes validation."""
        from src.services.tenant_reset_service import validate_config_integrity

        # Create initial signature
        validate_config_integrity(config_file)

        # Should pass validation on second call
        assert validate_config_integrity(config_file) is True

    def test_config_integrity_tampering_detection(self, config_file):
        """
        CRITICAL: Test that configuration tampering is detected.

        Prevents attacks where attacker modifies .env to change ATG SP ID.
        """
        from src.services.tenant_reset_service import validate_config_integrity

        # Create initial signature
        validate_config_integrity(config_file)

        # Tamper with config
        config_file.write_text(
            "AZURE_CLIENT_ID=malicious-id-11111111-1111-1111-1111-111111111111\n"
        )

        # Should raise SecurityError
        with pytest.raises(SecurityError) as exc:
            validate_config_integrity(config_file)

        assert "modified" in str(exc.value).lower()


class TestPreFlightValidation:
    """Test pre-flight ATG SP validation before deletion."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_preflight_atg_sp_exists(self, service):
        """Test pre-flight validation confirms ATG SP exists."""
        mock_atg_sp_id = "87654321-4321-4321-4321-210987654321"

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            with patch.object(
                service,
                "_get_service_principal",
                return_value={
                    "id": mock_atg_sp_id,
                    "appId": "atg-app-id",
                    "displayName": "ATG SP",
                },
            ):
                fingerprint = await service.validate_atg_sp_before_deletion(
                    tenant_id="12345678-1234-1234-1234-123456789abc"
                )

                assert fingerprint["id"] == mock_atg_sp_id
                assert fingerprint["app_id"] == "atg-app-id"
                assert "roles" in fingerprint

    @pytest.mark.asyncio
    async def test_preflight_atg_sp_missing_fails(self, service):
        """
        CRITICAL: Test that deletion aborts if ATG SP doesn't exist.
        """
        mock_atg_sp_id = "87654321-4321-4321-4321-210987654321"

        with patch.object(
            service, "identify_atg_service_principal", return_value=mock_atg_sp_id
        ):
            with patch.object(service, "_get_service_principal", return_value=None):
                with pytest.raises(SecurityError) as exc:
                    await service.validate_atg_sp_before_deletion(
                        tenant_id="12345678-1234-1234-1234-123456789abc"
                    )

                assert "not found" in str(exc.value).lower()


class TestPostDeletionVerification:
    """Test post-deletion ATG SP verification."""

    @pytest.fixture
    def service(self):
        """Create TenantResetService instance."""
        return TenantResetService(
            credential=Mock(),
            tenant_id="12345678-1234-1234-1234-123456789abc"
        )

    @pytest.mark.asyncio
    async def test_post_deletion_atg_sp_still_exists(self, service):
        """Test post-deletion verification confirms ATG SP still exists."""
        fingerprint = {
            "id": "87654321-4321-4321-4321-210987654321",
            "app_id": "atg-app-id",
            "display_name": "ATG SP",
            "roles": ["Contributor", "User Access Administrator"],
        }

        with patch.object(
            service,
            "_get_service_principal",
            return_value={
                "id": fingerprint["id"],
                "appId": fingerprint["app_id"],
                "displayName": fingerprint["display_name"],
            },
        ):
            with patch.object(
                service, "_get_sp_roles", return_value=fingerprint["roles"]
            ):
                # Should not raise
                await service.verify_atg_sp_after_deletion(
                    fingerprint=fingerprint,
                    tenant_id="12345678-1234-1234-1234-123456789abc",
                )

    @pytest.mark.asyncio
    async def test_post_deletion_atg_sp_deleted_triggers_alarm(self, service):
        """
        CRITICAL: Test that ATG SP deletion triggers emergency procedures.
        """
        fingerprint = {
            "id": "87654321-4321-4321-4321-210987654321",
            "app_id": "atg-app-id",
            "display_name": "ATG SP",
            "roles": ["Contributor"],
        }

        with patch.object(service, "_get_service_principal", return_value=None):
            with patch.object(
                service, "emergency_restore_procedure", new_callable=AsyncMock
            ) as mock_emergency:
                with pytest.raises(SecurityError) as exc:
                    await service.verify_atg_sp_after_deletion(
                        fingerprint=fingerprint,
                        tenant_id="12345678-1234-1234-1234-123456789abc",
                    )

                assert "CRITICAL" in str(exc.value)
                assert "deleted" in str(exc.value).lower()

                # Emergency restore should be called
                mock_emergency.assert_called_once()


# Marker for security-critical tests
pytestmark = pytest.mark.security
