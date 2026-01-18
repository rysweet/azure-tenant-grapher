"""Tests for identity block mapping in resource handlers.

Tests that ResourceHandler.map_identity_block() correctly maps Azure resource
identity configurations to Terraform identity blocks for all three types:
- SystemAssigned
- UserAssigned
- SystemAssigned, UserAssigned (combined)
"""

from src.iac.emitters.terraform.base_handler import ResourceHandler


class TestIdentityBlockMapping:
    """Test cases for map_identity_block() method."""

    def test_system_assigned_identity(self) -> None:
        """Test mapping of SystemAssigned identity type."""
        resource = {
            "id": "resource-001",
            "name": "test-resource",
            "identity": {
                "type": "SystemAssigned",
                "principalId": "11111111-1111-1111-1111-111111111111",
                "tenantId": "22222222-2222-2222-2222-222222222222",
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is not None, "Identity block should not be None"
        assert identity_block["type"] == "SystemAssigned"
        assert "identity_ids" not in identity_block, (
            "SystemAssigned should not have identity_ids"
        )

    def test_user_assigned_identity_single(self) -> None:
        """Test mapping of UserAssigned identity with single identity."""
        resource = {
            "id": "resource-002",
            "name": "test-resource",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {
                        "principalId": "33333333-3333-3333-3333-333333333333",
                        "clientId": "44444444-4444-4444-4444-444444444444",
                    }
                },
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is not None, "Identity block should not be None"
        assert identity_block["type"] == "UserAssigned"
        assert "identity_ids" in identity_block, "UserAssigned should have identity_ids"
        assert len(identity_block["identity_ids"]) == 1
        assert (
            "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"
            in identity_block["identity_ids"]
        )

    def test_user_assigned_identity_multiple(self) -> None:
        """Test mapping of UserAssigned identity with multiple identities."""
        resource = {
            "id": "resource-003",
            "name": "test-resource",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {
                        "principalId": "11111111-1111-1111-1111-111111111111",
                        "clientId": "22222222-2222-2222-2222-222222222222",
                    },
                    "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2": {
                        "principalId": "33333333-3333-3333-3333-333333333333",
                        "clientId": "44444444-4444-4444-4444-444444444444",
                    },
                },
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is not None
        assert identity_block["type"] == "UserAssigned"
        assert len(identity_block["identity_ids"]) == 2
        assert all(
            id_path in identity_block["identity_ids"]
            for id_path in [
                "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1",
                "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2",
            ]
        )

    def test_combined_identity_system_and_user(self) -> None:
        """Test mapping of combined SystemAssigned, UserAssigned identity."""
        resource = {
            "id": "resource-004",
            "name": "test-resource",
            "identity": {
                "type": "SystemAssigned, UserAssigned",
                "principalId": "55555555-5555-5555-5555-555555555555",
                "tenantId": "66666666-6666-6666-6666-666666666666",
                "userAssignedIdentities": {
                    "/subscriptions/sub-id/resourceGroups/rg/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {
                        "principalId": "77777777-7777-7777-7777-777777777777",
                        "clientId": "88888888-8888-8888-8888-888888888888",
                    }
                },
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is not None
        assert identity_block["type"] == "SystemAssigned, UserAssigned"
        assert "identity_ids" in identity_block, (
            "Combined identity should have identity_ids"
        )
        assert len(identity_block["identity_ids"]) == 1

    def test_no_identity_returns_none(self) -> None:
        """Test that resources without identity return None."""
        resource = {
            "id": "resource-005",
            "name": "test-resource",
            # No identity field
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is None, "Resource without identity should return None"

    def test_identity_in_properties(self) -> None:
        """Test identity extraction from properties field."""
        resource = {
            "id": "resource-006",
            "name": "test-resource",
            "properties": {
                "identity": {
                    "type": "SystemAssigned",
                    "principalId": "99999999-9999-9999-9999-999999999999",
                    "tenantId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                }
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is not None
        assert identity_block["type"] == "SystemAssigned"

    def test_empty_user_assigned_identities(self) -> None:
        """Test UserAssigned identity with empty userAssignedIdentities dict."""
        resource = {
            "id": "resource-007",
            "name": "test-resource",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {},  # Empty dict
            },
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        # Should still return identity block but with empty identity_ids
        assert identity_block is not None
        assert identity_block["type"] == "UserAssigned"
        assert identity_block["identity_ids"] == []

    def test_malformed_identity_returns_none(self) -> None:
        """Test that malformed identity configuration returns None gracefully."""
        resource = {
            "id": "resource-008",
            "name": "test-resource",
            "identity": "invalid-string",  # Should be dict, not string
        }

        identity_block = ResourceHandler.map_identity_block(resource)

        assert identity_block is None, "Malformed identity should return None"
