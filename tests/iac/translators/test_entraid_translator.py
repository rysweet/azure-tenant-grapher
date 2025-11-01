"""
Unit tests for EntraIdTranslator

Tests identity translation for cross-tenant scenarios.
This is the most critical translator for security-sensitive deployments.

Coverage:
- Tenant ID translation
- Object ID translation (users, groups, service principals)
- Role assignment translation
- Key Vault access policy translation
- Mapping file handling
- Strict mode enforcement
- Edge cases and error handling
"""

import pytest

from src.iac.translators.base_translator import TranslationContext
from src.iac.translators.entraid_translator import (
    EntraIdTranslator,
    IdentityMapping,
    IdentityMappingManifest,
    TenantMapping,
)


class TestEntraIdTranslator:
    """Test basic EntraIdTranslator functionality."""

    @pytest.fixture
    def source_tenant_id(self):
        """Source tenant ID."""
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        """Target tenant ID."""
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def identity_mapping(self):
        """Sample identity mapping."""
        return {
            "tenant_mapping": {
                "source_tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "target_tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
                "source_domain": "source.onmicrosoft.com",
                "target_domain": "target.onmicrosoft.com",
            },
            "identity_mappings": {
                "users": {
                    "11111111-1111-1111-1111-111111111111": {
                        "target_object_id": "99999999-9999-9999-9999-999999999999",
                        "source_upn": "alice@source.onmicrosoft.com",
                        "target_upn": "alice@target.onmicrosoft.com",
                        "match_confidence": "high",
                        "match_method": "upn",
                    }
                },
                "groups": {
                    "22222222-2222-2222-2222-222222222222": {
                        "target_object_id": "88888888-8888-8888-8888-888888888888",
                        "source_name": "DevOps Team",
                        "target_name": "DevOps Team",
                        "match_confidence": "high",
                        "match_method": "displayName",
                    }
                },
                "service_principals": {
                    "33333333-3333-3333-3333-333333333333": {
                        "target_object_id": "77777777-7777-7777-7777-777777777777",
                        "source_app_id": "44444444-4444-4444-4444-444444444444",
                        "target_app_id": "55555555-5555-5555-5555-555555555555",
                        "match_confidence": "high",
                        "match_method": "appId",
                    }
                },
            },
        }

    @pytest.fixture
    def translation_context(self, source_tenant_id, target_tenant_id):
        """Basic translation context without mapping."""
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
            strict_mode=False,
        )

    @pytest.fixture
    def translation_context_with_mapping(
        self, source_tenant_id, target_tenant_id, identity_mapping
    ):
        """Translation context with identity mapping."""
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
            identity_mapping=identity_mapping,
            strict_mode=False,
        )

    def test_supported_resource_types(self, translation_context):
        """Test that all expected resource types are supported."""
        translator = EntraIdTranslator(translation_context)

        expected_types = [
            "Microsoft.Authorization/roleAssignments",
            "Microsoft.KeyVault/vaults",
            "Microsoft.Graph/users",
            "Microsoft.Graph/groups",
            "Microsoft.Graph/servicePrincipals",
            "Microsoft.Graph/applications",
            "azuread_user",
            "azuread_group",
            "azuread_service_principal",
            "azuread_application",
            "azurerm_role_assignment",
            "azurerm_key_vault",
        ]

        supported = translator.supported_resource_types

        for expected_type in expected_types:
            assert expected_type in supported, f"Missing type: {expected_type}"

    def test_can_translate_role_assignment(self, translation_context):
        """Test detection of role assignment resources."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "11111111-1111-1111-1111-111111111111",
                "roleDefinitionId": "/subscriptions/sub/providers/Microsoft.Authorization/roleDefinitions/def",
            },
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_key_vault_with_access_policies(self, translation_context):
        """Test detection of Key Vault with access policies."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                        "objectId": "11111111-1111-1111-1111-111111111111",
                        "permissions": {"keys": ["get"], "secrets": ["get"]},
                    }
                ],
            },
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_key_vault_without_access_policies(
        self, translation_context
    ):
        """Test that Key Vault without access policies is not translated."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {"accessPolicies": []},
        }

        assert translator.can_translate(resource) is False

    def test_can_translate_with_tenant_id_reference(
        self, translation_context, source_tenant_id
    ):
        """Test detection of resources containing tenant ID."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "azurerm_role_assignment",
            "properties": {"some_field": f"value-with-{source_tenant_id}"},
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_unsupported_type(self, translation_context):
        """Test that unsupported resource types are not translated."""
        translator = EntraIdTranslator(translation_context)

        resource = {"type": "Microsoft.Storage/storageAccounts", "properties": {}}

        assert translator.can_translate(resource) is False

    def test_initialization_with_mapping(self, translation_context_with_mapping):
        """Test initialization with identity mapping."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        assert translator.manifest is not None
        assert len(translator.manifest.users) == 1
        assert len(translator.manifest.groups) == 1
        assert len(translator.manifest.service_principals) == 1
        assert translator.missing_mappings == []

    def test_initialization_without_mapping(self, translation_context):
        """Test initialization without identity mapping."""
        translator = EntraIdTranslator(translation_context)

        assert translator.manifest is None
        assert translator.missing_mappings == []


class TestEntraIdTranslatorRoleAssignments:
    """Test role assignment translation."""

    @pytest.fixture
    def source_tenant_id(self):
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def identity_mapping(self):
        return {
            "tenant_mapping": {
                "source_tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "target_tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            },
            "identity_mappings": {
                "users": {
                    "11111111-1111-1111-1111-111111111111": {
                        "target_object_id": "99999999-9999-9999-9999-999999999999",
                    }
                },
                "groups": {
                    "22222222-2222-2222-2222-222222222222": {
                        "target_object_id": "88888888-8888-8888-8888-888888888888",
                    }
                },
                "service_principals": {
                    "33333333-3333-3333-3333-333333333333": {
                        "target_object_id": "77777777-7777-7777-7777-777777777777",
                    }
                },
            },
        }

    @pytest.fixture
    def translation_context_with_mapping(
        self, source_tenant_id, target_tenant_id, identity_mapping
    ):
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
            identity_mapping=identity_mapping,
            strict_mode=False,
        )

    def test_translate_role_assignment_user(self, translation_context_with_mapping):
        """Test translating role assignment with user principal."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "11111111-1111-1111-1111-111111111111",
                "principalType": "User",
            },
        }

        result = translator.translate(resource)

        assert (
            result["properties"]["principalId"]
            == "99999999-9999-9999-9999-999999999999"
        )

    def test_translate_role_assignment_group(self, translation_context_with_mapping):
        """Test translating role assignment with group principal."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "22222222-2222-2222-2222-222222222222",
                "principalType": "Group",
            },
        }

        result = translator.translate(resource)

        assert (
            result["properties"]["principalId"]
            == "88888888-8888-8888-8888-888888888888"
        )

    def test_translate_role_assignment_service_principal(
        self, translation_context_with_mapping
    ):
        """Test translating role assignment with service principal."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "33333333-3333-3333-3333-333333333333",
                "principalType": "ServicePrincipal",
            },
        }

        result = translator.translate(resource)

        assert (
            result["properties"]["principalId"]
            == "77777777-7777-7777-7777-777777777777"
        )

    def test_translate_role_assignment_missing_mapping_non_strict(
        self, translation_context_with_mapping
    ):
        """Test role assignment with missing mapping in non-strict mode."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        unmapped_id = "aaaaaaaa-1111-1111-1111-111111111111"
        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": unmapped_id, "principalType": "User"},
        }

        result = translator.translate(resource)

        # Should preserve original ID in non-strict mode
        assert result["properties"]["principalId"] == unmapped_id
        assert len(translator.missing_mappings) == 1
        assert translator.missing_mappings[0]["source_id"] == unmapped_id

    def test_translate_role_assignment_missing_mapping_strict_mode(
        self, source_tenant_id, target_tenant_id, identity_mapping
    ):
        """Test role assignment with missing mapping in strict mode."""
        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
            identity_mapping=identity_mapping,
            strict_mode=True,
        )
        translator = EntraIdTranslator(context)

        unmapped_id = "aaaaaaaa-1111-1111-1111-111111111111"
        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": unmapped_id, "principalType": "User"},
        }

        with pytest.raises(ValueError) as exc_info:
            translator.translate(resource)

        assert "Missing identity mapping" in str(exc_info.value)
        assert "strict mode" in str(exc_info.value)

    def test_translate_role_assignment_invalid_principal_id_format(
        self, translation_context_with_mapping
    ):
        """Test role assignment with invalid UUID format."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "not-a-valid-uuid",
                "principalType": "User",
            },
        }

        result = translator.translate(resource)

        # Should preserve invalid ID
        assert result["properties"]["principalId"] == "not-a-valid-uuid"


class TestEntraIdTranslatorKeyVault:
    """Test Key Vault access policy translation."""

    @pytest.fixture
    def source_tenant_id(self):
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def identity_mapping(self):
        return {
            "tenant_mapping": {
                "source_tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                "target_tenant_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
            },
            "identity_mappings": {
                "users": {
                    "11111111-1111-1111-1111-111111111111": {
                        "target_object_id": "99999999-9999-9999-9999-999999999999",
                    }
                },
                "service_principals": {
                    "22222222-2222-2222-2222-222222222222": {
                        "target_object_id": "88888888-8888-8888-8888-888888888888",
                    }
                },
            },
        }

    @pytest.fixture
    def translation_context_with_mapping(
        self, source_tenant_id, target_tenant_id, identity_mapping
    ):
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
            identity_mapping=identity_mapping,
            strict_mode=False,
        )

    def test_translate_keyvault_access_policy_single(
        self, translation_context_with_mapping, source_tenant_id, target_tenant_id
    ):
        """Test translating single Key Vault access policy."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": source_tenant_id,
                        "objectId": "11111111-1111-1111-1111-111111111111",
                        "permissions": {
                            "keys": ["get", "list"],
                            "secrets": ["get"],
                            "certificates": [],
                        },
                    }
                ],
            },
        }

        result = translator.translate(resource)

        policy = result["properties"]["accessPolicies"][0]
        assert policy["tenantId"] == target_tenant_id
        assert policy["objectId"] == "99999999-9999-9999-9999-999999999999"
        assert policy["permissions"]["keys"] == ["get", "list"]
        assert policy["permissions"]["secrets"] == ["get"]

    def test_translate_keyvault_access_policies_multiple(
        self, translation_context_with_mapping, source_tenant_id, target_tenant_id
    ):
        """Test translating multiple Key Vault access policies."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": source_tenant_id,
                        "objectId": "11111111-1111-1111-1111-111111111111",
                        "permissions": {"keys": ["get"]},
                    },
                    {
                        "tenantId": source_tenant_id,
                        "objectId": "22222222-2222-2222-2222-222222222222",
                        "permissions": {"secrets": ["get", "set"]},
                    },
                ],
            },
        }

        result = translator.translate(resource)

        policies = result["properties"]["accessPolicies"]
        assert len(policies) == 2

        assert policies[0]["tenantId"] == target_tenant_id
        assert policies[0]["objectId"] == "99999999-9999-9999-9999-999999999999"

        assert policies[1]["tenantId"] == target_tenant_id
        assert policies[1]["objectId"] == "88888888-8888-8888-8888-888888888888"

    def test_translate_keyvault_access_policy_missing_object_id(
        self, translation_context_with_mapping, source_tenant_id, target_tenant_id
    ):
        """Test Key Vault access policy with missing object ID mapping."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        unmapped_id = "aaaaaaaa-1111-1111-1111-111111111111"
        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": source_tenant_id,
                        "objectId": unmapped_id,
                        "permissions": {"keys": ["get"]},
                    }
                ],
            },
        }

        result = translator.translate(resource)

        policy = result["properties"]["accessPolicies"][0]
        assert policy["tenantId"] == target_tenant_id
        assert policy["objectId"] == unmapped_id  # Preserved
        assert len(translator.missing_mappings) == 1

    def test_translate_keyvault_preserve_all_permissions(
        self, translation_context_with_mapping, source_tenant_id
    ):
        """Test that all permission arrays are preserved during translation."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": source_tenant_id,
                        "objectId": "11111111-1111-1111-1111-111111111111",
                        "permissions": {
                            "keys": ["get", "list", "create", "delete"],
                            "secrets": ["get", "set", "delete"],
                            "certificates": ["get", "list", "import"],
                            "storage": ["get", "set"],
                        },
                    }
                ],
            },
        }

        result = translator.translate(resource)

        permissions = result["properties"]["accessPolicies"][0]["permissions"]
        assert permissions["keys"] == ["get", "list", "create", "delete"]
        assert permissions["secrets"] == ["get", "set", "delete"]
        assert permissions["certificates"] == ["get", "list", "import"]
        assert permissions["storage"] == ["get", "set"]

    def test_translate_keyvault_access_policy_invalid_object_id(
        self, translation_context_with_mapping, source_tenant_id
    ):
        """Test Key Vault access policy with invalid object ID format."""
        translator = EntraIdTranslator(translation_context_with_mapping)

        resource = {
            "type": "Microsoft.KeyVault/vaults",
            "properties": {
                "accessPolicies": [
                    {
                        "tenantId": source_tenant_id,
                        "objectId": "not-a-valid-uuid",
                        "permissions": {"keys": ["get"]},
                    }
                ],
            },
        }

        result = translator.translate(resource)

        # Should preserve invalid ID and continue
        policy = result["properties"]["accessPolicies"][0]
        assert policy["objectId"] == "not-a-valid-uuid"


class TestEntraIdTranslatorMappingHandling:
    """Test identity mapping file handling."""

    @pytest.fixture
    def source_tenant_id(self):
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    def test_load_manifest_from_dict_complete(self):
        """Test loading complete identity mapping."""
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
                "source_domain": "source.onmicrosoft.com",
                "target_domain": "target.onmicrosoft.com",
            },
            "identity_mappings": {
                "users": {
                    "user-1": {
                        "target_object_id": "user-2",
                        "source_upn": "alice@source.onmicrosoft.com",
                        "target_upn": "alice@target.onmicrosoft.com",
                    }
                },
                "groups": {"group-1": {"target_object_id": "group-2"}},
                "service_principals": {"sp-1": {"target_object_id": "sp-2"}},
            },
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
        )

        translator = EntraIdTranslator(context)

        assert translator.manifest is not None
        assert translator.manifest.tenant_mapping.source_tenant_id == "source-tenant"
        assert translator.manifest.tenant_mapping.target_tenant_id == "target-tenant"
        assert len(translator.manifest.users) == 1
        assert len(translator.manifest.groups) == 1
        assert len(translator.manifest.service_principals) == 1

    def test_load_manifest_missing_tenant_mapping(self):
        """Test loading mapping without tenant_mapping section."""
        mapping = {"identity_mappings": {}}

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            identity_mapping=mapping,
        )

        with pytest.raises(ValueError) as exc_info:
            EntraIdTranslator(context)

        assert "missing 'tenant_mapping'" in str(exc_info.value)

    def test_load_manifest_missing_tenant_ids(self):
        """Test loading mapping with incomplete tenant info."""
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "",  # Empty
                "target_tenant_id": "target-tenant",
            },
            "identity_mappings": {},
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            identity_mapping=mapping,
        )

        with pytest.raises(ValueError) as exc_info:
            EntraIdTranslator(context)

        assert "source_tenant_id and target_tenant_id are required" in str(
            exc_info.value
        )

    def test_load_manifest_empty_identity_mappings(self):
        """Test loading mapping with no identity mappings."""
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
            },
            "identity_mappings": {},
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
        )

        translator = EntraIdTranslator(context)

        assert translator.manifest is not None
        assert len(translator.manifest.users) == 0
        assert len(translator.manifest.groups) == 0
        assert len(translator.manifest.service_principals) == 0

    def test_manual_input_required_mapping_non_strict(self):
        """Test MANUAL_INPUT_REQUIRED in non-strict mode."""
        user_id = "cccccccc-1111-1111-1111-111111111111"
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
            },
            "identity_mappings": {
                "users": {
                    user_id: {
                        "target_object_id": "MANUAL_INPUT_REQUIRED",
                    }
                }
            },
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
            strict_mode=False,
        )

        translator = EntraIdTranslator(context)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": user_id, "principalType": "User"},
        }

        result = translator.translate(resource)

        # Should preserve original ID
        assert result["properties"]["principalId"] == user_id
        assert len(translator.missing_mappings) == 1
        assert translator.missing_mappings[0]["context"] == "Manual input required"

    def test_manual_input_required_mapping_strict_mode(self):
        """Test MANUAL_INPUT_REQUIRED in strict mode."""
        user_id = "cccccccc-1111-1111-1111-111111111111"
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
            },
            "identity_mappings": {
                "users": {
                    user_id: {
                        "target_object_id": "MANUAL_INPUT_REQUIRED",
                    }
                }
            },
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
            strict_mode=True,
        )

        translator = EntraIdTranslator(context)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": user_id, "principalType": "User"},
        }

        with pytest.raises(ValueError) as exc_info:
            translator.translate(resource)

        assert "Manual mapping required" in str(exc_info.value)
        assert "strict mode" in str(exc_info.value)


class TestEntraIdTranslatorTenantIdTranslation:
    """Test tenant ID translation across resources."""

    @pytest.fixture
    def source_tenant_id(self):
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def translation_context(self, source_tenant_id, target_tenant_id):
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
        )

    def test_translate_tenant_id_in_properties(
        self, translation_context, source_tenant_id, target_tenant_id
    ):
        """Test tenant ID replacement in properties."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "azurerm_role_assignment",
            "properties": {
                "tenant_id": source_tenant_id,
                "other_field": "value",
            },
        }

        result = translator.translate(resource)

        assert result["properties"]["tenant_id"] == target_tenant_id
        assert result["properties"]["other_field"] == "value"

    def test_translate_tenant_id_multiple_occurrences(
        self, translation_context, source_tenant_id, target_tenant_id
    ):
        """Test replacing multiple tenant ID occurrences."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "azurerm_role_assignment",
            "properties": {
                "tenant_id": source_tenant_id,
                "description": f"Resource in tenant {source_tenant_id}",
                "metadata": {"tenant": source_tenant_id},
            },
        }

        result = translator.translate(resource)

        assert result["properties"]["tenant_id"] == target_tenant_id
        assert target_tenant_id in result["properties"]["description"]
        assert result["properties"]["metadata"]["tenant"] == target_tenant_id

    def test_translate_preserves_other_guids(
        self, translation_context, source_tenant_id, target_tenant_id
    ):
        """Test that other GUIDs are not modified."""
        translator = EntraIdTranslator(translation_context)

        other_guid = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        resource = {
            "type": "azurerm_role_assignment",
            "properties": {
                "tenant_id": source_tenant_id,
                "subscription_id": other_guid,
            },
        }

        result = translator.translate(resource)

        assert result["properties"]["tenant_id"] == target_tenant_id
        assert result["properties"]["subscription_id"] == other_guid


class TestEntraIdTranslatorEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def source_tenant_id(self):
        return "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"

    @pytest.fixture
    def target_tenant_id(self):
        return "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"

    @pytest.fixture
    def translation_context(self, source_tenant_id, target_tenant_id):
        return TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
        )

    def test_translate_empty_resource(self, translation_context):
        """Test translating empty resource."""
        translator = EntraIdTranslator(translation_context)

        resource = {"type": "Microsoft.Authorization/roleAssignments", "properties": {}}

        result = translator.translate(resource)

        assert result == resource

    def test_translate_resource_with_none_values(self, translation_context):
        """Test translating resource with None values."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": None, "principalType": None},
        }

        result = translator.translate(resource)

        # Should handle None gracefully
        assert result["properties"]["principalId"] is None

    def test_translate_terraform_variable_references(self, translation_context):
        """Test that Terraform variables are not translated."""
        translator = EntraIdTranslator(translation_context)

        resource = {
            "type": "azurerm_role_assignment",
            "properties": {
                "principal_id": "${azuread_user.admin.object_id}",
                "tenant_id": "var.tenant_id",
            },
        }

        result = translator.translate(resource)

        # Terraform variables should be preserved
        assert result["properties"]["principal_id"] == "${azuread_user.admin.object_id}"
        # Note: tenant_id is still replaced via string replacement
        # This is expected behavior as tenant ID replacement is global

    def test_get_missing_mappings_report(self, translation_context):
        """Test missing mappings report generation."""
        translator = EntraIdTranslator(translation_context)

        # Translate resource with missing mapping
        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "aaaaaaaa-1111-1111-1111-111111111111",
                "principalType": "User",
            },
        }

        translator.translate(resource)

        report = translator.get_missing_mappings_report()

        assert report["total_missing"] == 1
        assert "User" in report["by_type"]
        assert len(report["details"]) == 1

    def test_identity_mapping_manifest_get_mapping_across_types(self):
        """Test IdentityMappingManifest.get_mapping() searches all types."""
        tenant_mapping = TenantMapping(
            source_tenant_id="source", target_tenant_id="target"
        )

        user_mapping = IdentityMapping(
            source_object_id="user-1", target_object_id="user-2"
        )
        group_mapping = IdentityMapping(
            source_object_id="group-1", target_object_id="group-2"
        )
        sp_mapping = IdentityMapping(
            source_object_id="sp-1", target_object_id="sp-2"
        )

        manifest = IdentityMappingManifest(
            tenant_mapping=tenant_mapping,
            users={"user-1": user_mapping},
            groups={"group-1": group_mapping},
            service_principals={"sp-1": sp_mapping},
        )

        # Test finding each type
        assert manifest.get_mapping("user-1") == user_mapping
        assert manifest.get_mapping("group-1") == group_mapping
        assert manifest.get_mapping("sp-1") == sp_mapping
        assert manifest.get_mapping("nonexistent") is None

    def test_translate_mixed_azure_and_azuread_types(
        self, source_tenant_id, target_tenant_id
    ):
        """Test handling both Azure and AzureAD resource types."""
        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            available_resources={},
        )
        translator = EntraIdTranslator(context)

        # Azure resource without principalId or tenant ID = not translatable
        azure_resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {},
        }

        # Azure resource with principalId = translatable
        azure_resource_with_principal = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {"principalId": "11111111-1111-1111-1111-111111111111"},
        }

        # azuread_user containing tenant ID = translatable
        azuread_resource = {
            "type": "azuread_user",
            "properties": {
                "description": f"User in tenant {source_tenant_id}",
            },
        }

        # azuread_user without tenant ID = not translatable
        azuread_resource_no_tenant = {"type": "azuread_user", "properties": {}}

        assert translator.can_translate(azure_resource) is False
        assert translator.can_translate(azure_resource_with_principal) is True
        assert translator.can_translate(azuread_resource) is True
        assert translator.can_translate(azuread_resource_no_tenant) is False

    def test_is_valid_uuid(self, translation_context):
        """Test UUID validation helper method."""
        translator = EntraIdTranslator(translation_context)

        # Valid UUIDs
        assert (
            translator._is_valid_uuid("11111111-1111-1111-1111-111111111111") is True
        )
        assert (
            translator._is_valid_uuid("AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA") is True
        )

        # Invalid UUIDs
        assert translator._is_valid_uuid("not-a-uuid") is False
        assert translator._is_valid_uuid("") is False
        assert translator._is_valid_uuid("11111111-1111-1111-1111") is False
        assert (
            translator._is_valid_uuid("11111111-1111-1111-1111-11111111111G") is False
        )  # Invalid char

    def test_translate_role_assignment_without_principal_type(
        self, translation_context
    ):
        """Test role assignment without principalType field."""
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
            },
            "identity_mappings": {
                "users": {
                    "11111111-1111-1111-1111-111111111111": {
                        "target_object_id": "99999999-9999-9999-9999-999999999999",
                    }
                }
            },
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
        )

        translator = EntraIdTranslator(context)

        resource = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "11111111-1111-1111-1111-111111111111",
                # No principalType - defaults to "Unknown"
            },
        }

        result = translator.translate(resource)

        # Should still translate by searching all types
        assert (
            result["properties"]["principalId"]
            == "99999999-9999-9999-9999-999999999999"
        )

    def test_upn_translation(self):
        """Test UPN domain translation."""
        mapping = {
            "tenant_mapping": {
                "source_tenant_id": "source-tenant",
                "target_tenant_id": "target-tenant",
                "source_domain": "source.onmicrosoft.com",
                "target_domain": "target.onmicrosoft.com",
            },
            "identity_mappings": {},
        }

        context = TranslationContext(
            source_subscription_id="sub-source",
            target_subscription_id="sub-target",
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            identity_mapping=mapping,
        )

        translator = EntraIdTranslator(context)

        resource = {
            "type": "azurerm_role_assignment",
            "properties": {
                "user_principal_name": "alice@source.onmicrosoft.com",
                "description": "User alice@source.onmicrosoft.com has access",
            },
        }

        result = translator.translate(resource)

        assert (
            result["properties"]["user_principal_name"]
            == "alice@target.onmicrosoft.com"
        )
        assert "alice@target.onmicrosoft.com" in result["properties"]["description"]
