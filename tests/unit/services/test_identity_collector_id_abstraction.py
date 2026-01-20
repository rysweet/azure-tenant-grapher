"""Tests for ID abstraction in identity_collector.py

This test file verifies that principalId values are properly abstracted
before being stored in IdentityReference objects, preventing source tenant
ID leakage into the Neo4j graph.

Issue #475 - ID Leakage Audit
"""

import pytest

from src.services.identity_collector import IdentityCollector


class TestIdentityCollectorIdAbstraction:
    """Test ID abstraction in identity collector."""

    def test_system_assigned_identity_principal_id_abstracted(self):
        """Verify system-assigned identity principal IDs are abstracted."""
        # Arrange
        collector = IdentityCollector()
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm001"
        identity = {
            "type": "SystemAssigned",
            "principalId": "9a2b3c4d-1234-5678-90ab-cdef12345678",  # Source tenant GUID
            "tenantId": "source-tenant-id",
        }

        # Act
        identities = collector._extract_managed_identities_from_resource(
            {"id": resource_id, "identity": identity}
        )

        # Assert
        assert len(identities) == 1
        principal_id = identities[0].id

        # CRITICAL: Principal ID must NOT be a GUID
        assert not self._is_guid(principal_id), (
            f"Principal ID leaked as GUID: {principal_id}"
        )

        # CRITICAL: Must be abstracted (human-readable)
        assert principal_id.startswith("principal-"), (
            f"Principal ID not abstracted: {principal_id}"
        )

    def test_user_assigned_identity_principal_id_abstracted(self):
        """Verify user-assigned identity principal IDs are abstracted."""
        # Arrange
        collector = IdentityCollector()
        resource_id = "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm001"
        identity = {
            "type": "UserAssigned",
            "userAssignedIdentities": {
                "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.ManagedIdentity/userAssignedIdentities/id1": {
                    "principalId": "8b3c4d5e-2345-6789-01bc-def123456789",
                    "clientId": "7c4d5e6f-3456-7890-12cd-ef1234567890",
                }
            },
        }

        # Act
        identities = collector._extract_managed_identities_from_resource(
            {"id": resource_id, "identity": identity}
        )

        # Assert
        # Should have 2 identities: resource ID + principal ID
        assert len(identities) >= 1

        # Check all identities for GUID leakage
        for ident in identities:
            if self._is_guid(ident.id):
                pytest.fail(f"GUID leaked in identity: {ident.id}")

    def test_role_assignment_principal_id_abstracted(self):
        """Verify role assignment principal IDs are abstracted."""
        # Arrange
        collector = IdentityCollector()
        role_assignment = {
            "id": "/subscriptions/sub1/providers/Microsoft.Authorization/roleAssignments/ra1",
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "6d5e7f8g-4567-8901-23de-f12345678901",
                "roleDefinitionId": "/subscriptions/sub1/providers/Microsoft.Authorization/roleDefinitions/rd1",
                "scope": "/subscriptions/sub1",
            },
        }

        # Act
        identities = collector._extract_identity_from_role_assignment(role_assignment)

        # Assert
        assert len(identities) == 1
        principal_id = identities[0].id

        # CRITICAL: No GUID leakage
        assert not self._is_guid(principal_id), (
            f"Role assignment principal ID leaked: {principal_id}"
        )

    @staticmethod
    def _is_guid(value: str) -> bool:
        """Check if value is a GUID."""
        import re

        guid_pattern = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
        return bool(re.match(guid_pattern, value, re.IGNORECASE))
