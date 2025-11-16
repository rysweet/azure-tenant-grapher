"""
Comprehensive test suite for automatic identity mapping feature (Issue #410).

This test suite follows TDD principles and will fail until the AutoIdentityMapper
class is implemented. Tests cover:

1. User matching by email (high confidence)
2. User matching by UPN (high confidence)
3. Service Principal matching by appId (very high confidence)
4. Display name matching (lower confidence)
5. Manual mapping override behavior
6. No match scenario (warn but continue)
7. Partial match scenario (some matched, some not)
8. CLI integration and triggering
9. Bug fix: identity mapping file loading

Testing Pyramid:
- 60% Unit tests (mocked dependencies)
- 30% Integration tests (multiple components)
- 10% E2E tests (CLI to mapping generation)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Test fixtures and data


@pytest.fixture
def source_tenant_id() -> str:
    """Source tenant ID for testing."""
    return "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


@pytest.fixture
def target_tenant_id() -> str:
    """Target tenant ID for testing."""
    return "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def source_users() -> List[Dict[str, Any]]:
    """Mock users from source tenant (via AADGraphService)."""
    return [
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000001",
            "displayName": "Alice Smith",
            "userPrincipalName": "alice@source.onmicrosoft.com",
            "mail": "alice.smith@company.com",
        },
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000002",
            "displayName": "Bob Jones",
            "userPrincipalName": "bob@source.onmicrosoft.com",
            "mail": "bob.jones@company.com",
        },
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000003",
            "displayName": "Charlie Brown",
            "userPrincipalName": "charlie@source.onmicrosoft.com",
            "mail": None,  # No email
        },
        {
            "id": "aaaaaaaa-0000-0000-0000-000000000004",
            "displayName": "David Wilson",
            "userPrincipalName": "david@source.onmicrosoft.com",
            "mail": "david.wilson@company.com",
        },
    ]


@pytest.fixture
def target_users() -> List[Dict[str, Any]]:
    """Mock users from target tenant (via AADGraphService)."""
    return [
        {
            "id": "11111111-0000-0000-0000-000000000001",
            "displayName": "Alice Smith",
            "userPrincipalName": "alice@target.onmicrosoft.com",
            "mail": "alice.smith@company.com",  # Email matches
        },
        {
            "id": "11111111-0000-0000-0000-000000000002",
            "displayName": "Bob Jones",
            "userPrincipalName": "bob@target.onmicrosoft.com",
            "mail": "bob.jones@company.com",  # Email matches
        },
        {
            "id": "11111111-0000-0000-0000-000000000003",
            "displayName": "Charlie Brown",  # Display name match only
            "userPrincipalName": "charlie@target.onmicrosoft.com",
            "mail": None,
        },
        # user-4 NOT present in target tenant (no match scenario)
    ]


@pytest.fixture
def source_service_principals() -> List[Dict[str, Any]]:
    """Mock service principals from source tenant."""
    return [
        {
            "id": "aaaaaaaa-1111-1111-1111-111111111111",
            "displayName": "MyApp Service Principal",
            "appId": "bbbbbbbb-1111-1111-1111-111111111111",  # appId is stable across tenants
            "servicePrincipalType": "Application",
        },
        {
            "id": "aaaaaaaa-2222-2222-2222-222222222222",
            "displayName": "BackupService",
            "appId": "bbbbbbbb-2222-2222-2222-222222222222",
            "servicePrincipalType": "Application",
        },
        {
            "id": "aaaaaaaa-3333-3333-3333-333333333333",
            "displayName": "OrphanedSP",
            "appId": "bbbbbbbb-3333-3333-3333-333333333333",
            "servicePrincipalType": "Application",
        },
    ]


@pytest.fixture
def target_service_principals() -> List[Dict[str, Any]]:
    """Mock service principals from target tenant."""
    return [
        {
            "id": "11111111-1111-1111-1111-111111111111",
            "displayName": "MyApp Service Principal",
            "appId": "bbbbbbbb-1111-1111-1111-111111111111",  # Same appId = match!
            "servicePrincipalType": "Application",
        },
        {
            "id": "11111111-2222-2222-2222-222222222222",
            "displayName": "BackupService",
            "appId": "bbbbbbbb-2222-2222-2222-222222222222",  # Same appId = match!
            "servicePrincipalType": "Application",
        },
        # sp-3 NOT present in target (no match)
    ]


@pytest.fixture
def manual_mapping_override() -> Dict[str, Any]:
    """Manual mapping that should override automatic matching."""
    return {
        "tenant_mapping": {
            "source_tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "target_tenant_id": "11111111-2222-3333-4444-555555555555",
        },
        "identity_mappings": {
            "users": {
                "aaaaaaaa-0000-0000-0000-000000000001": {
                    "target_object_id": "manual-override-user-id",
                    "source_upn": "alice@source.onmicrosoft.com",
                    "target_upn": "alice.override@target.onmicrosoft.com",
                    "match_confidence": "manual",
                    "match_method": "manual",
                    "notes": "Manual override for testing",
                }
            },
        },
    }


@pytest.fixture
def mock_neo4j_driver() -> MagicMock:
    """Mock Neo4j driver for querying identity information."""
    driver = MagicMock()
    session = MagicMock()
    result = MagicMock()

    # Mock role assignments that reference identities
    mock_records = [
        {
            "resource": {
                "id": "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.Authorization/roleAssignments/role-1",
                "type": "Microsoft.Authorization/roleAssignments",
                "properties": {
                    "principalId": "aaaaaaaa-0000-0000-0000-000000000001",
                    "principalType": "User",
                    "roleDefinitionId": "/subscriptions/sub-1/providers/Microsoft.Authorization/roleDefinitions/reader",
                },
            }
        }
    ]

    result.__iter__.return_value = iter(mock_records)
    result.data.return_value = mock_records
    session.run.return_value = result
    driver.session.return_value.__enter__.return_value = session

    return driver


# ============================================================================
# UNIT TESTS (60%)
# ============================================================================


@pytest.mark.asyncio
async def test_match_user_by_email(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
) -> None:
    """
    Test user matching by email address (high confidence match).

    Scenario:
        - Alice Smith exists in both tenants
        - Email matches: alice.smith@company.com
        - Should create mapping with high confidence
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    # Mock AADGraphService calls
    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        # Configure which service is returned based on tenant_id
        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            # Check if tenant_id in kwargs matches
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        # Create mapping
        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Verify Alice was matched by email
        assert "users" in mapping
        assert "aaaaaaaa-0000-0000-0000-000000000001" in mapping["users"]

        alice_mapping = mapping["users"]["aaaaaaaa-0000-0000-0000-000000000001"]
        assert alice_mapping["target_object_id"] == "11111111-0000-0000-0000-000000000001"
        assert alice_mapping["match_method"] == "email"
        assert alice_mapping["match_confidence"] in ["high", "very_high"]
        assert alice_mapping["source_upn"] == "alice@source.onmicrosoft.com"
        assert alice_mapping["target_upn"] == "alice@target.onmicrosoft.com"


@pytest.mark.asyncio
async def test_match_user_by_upn(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
) -> None:
    """
    Test user matching by UPN username part (high confidence match).

    Scenario:
        - Bob Jones exists in both tenants
        - UPN username matches: bob (from bob@source vs bob@target)
        - Should create mapping with high confidence
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Verify Bob was matched by UPN
        assert "aaaaaaaa-0000-0000-0000-000000000002" in mapping["users"]

        bob_mapping = mapping["users"]["aaaaaaaa-0000-0000-0000-000000000002"]
        assert bob_mapping["target_object_id"] == "11111111-0000-0000-0000-000000000002"
        assert bob_mapping["match_method"] in ["email", "upn"]  # Email takes precedence
        assert bob_mapping["match_confidence"] in ["high", "very_high"]


@pytest.mark.asyncio
async def test_match_sp_by_app_id(
    source_tenant_id: str,
    target_tenant_id: str,
    source_service_principals: List[Dict[str, Any]],
    target_service_principals: List[Dict[str, Any]],
) -> None:
    """
    Test service principal matching by appId (very high confidence match).

    Scenario:
        - MyApp Service Principal exists in both tenants
        - appId matches: app-id-12345
        - appId is globally unique and stable across tenants
        - Should create mapping with very high confidence
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_service_principals.return_value = (
            source_service_principals
        )
        mock_target_service.get_service_principals.return_value = (
            target_service_principals
        )

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Verify MyApp SP was matched by appId
        assert "service_principals" in mapping
        assert "aaaaaaaa-1111-1111-1111-111111111111" in mapping["service_principals"]

        sp_mapping = mapping["service_principals"]["aaaaaaaa-1111-1111-1111-111111111111"]
        assert sp_mapping["target_object_id"] == "11111111-1111-1111-1111-111111111111"
        assert sp_mapping["match_method"] == "appId"
        assert sp_mapping["match_confidence"] == "very_high"
        assert sp_mapping["source_app_id"] == "bbbbbbbb-1111-1111-1111-111111111111"
        assert sp_mapping["target_app_id"] == "bbbbbbbb-1111-1111-1111-111111111111"


@pytest.mark.asyncio
async def test_match_by_display_name_lower_confidence(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
) -> None:
    """
    Test user matching by display name only (lower confidence match).

    Scenario:
        - Charlie Brown has no email
        - Can only match by display name
        - Should create mapping with medium/low confidence
        - Should warn user to verify
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Verify Charlie was matched by display name
        assert "aaaaaaaa-0000-0000-0000-000000000003" in mapping["users"]

        charlie_mapping = mapping["users"]["aaaaaaaa-0000-0000-0000-000000000003"]
        assert charlie_mapping["target_object_id"] == "11111111-0000-0000-0000-000000000003"
        assert charlie_mapping["match_method"] == "displayName"
        assert charlie_mapping["match_confidence"] in ["medium", "low"]
        assert "verify" in charlie_mapping.get("notes", "").lower()


@pytest.mark.asyncio
async def test_no_match_warns_but_continues(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """
    Test that when no match is found, the system warns but continues.

    Scenario:
        - David Wilson exists in source but NOT in target
        - No match found
        - Should log warning
        - Should create placeholder mapping or skip
        - Should NOT raise exception
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        # Should not raise exception
        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Should have completed successfully
        assert mapping is not None

        # David should either:
        # 1. Not be in mapping at all, OR
        # 2. Have placeholder "MANUAL_INPUT_REQUIRED"
        if "user-4-source-id" in mapping["users"]:
            david_mapping = mapping["users"]["user-4-source-id"]
            assert (
                david_mapping["target_object_id"] == "MANUAL_INPUT_REQUIRED"
                or david_mapping["match_confidence"] == "none"
            )

        # Should have logged warning
        assert any(
            "no match" in record.message.lower()
            or "not found" in record.message.lower()
            for record in caplog.records
        )


@pytest.mark.asyncio
async def test_manual_override_takes_precedence(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    manual_mapping_override: Dict[str, Any],
    tmp_path: Path,
) -> None:
    """
    Test that manual mapping file overrides automatic matching.

    Scenario:
        - Alice would normally match automatically to user-1-target-id
        - Manual mapping says Alice -> manual-override-user-id
        - Manual mapping should win
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    # Write manual mapping to file
    manual_mapping_file = tmp_path / "manual_mappings.json"
    with open(manual_mapping_file, "w") as f:
        json.dump(manual_mapping_override, f, indent=2)

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        # Create mapping with manual override
        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            manual_mapping_file=manual_mapping_file,
        )

        # Verify manual mapping took precedence
        assert "aaaaaaaa-0000-0000-0000-000000000001" in mapping["users"]

        alice_mapping = mapping["users"]["aaaaaaaa-0000-0000-0000-000000000001"]
        assert alice_mapping["target_object_id"] == "manual-override-user-id"
        assert alice_mapping["match_method"] == "manual"
        assert alice_mapping["match_confidence"] == "manual"
        assert "manual override" in alice_mapping.get("notes", "").lower()


@pytest.mark.asyncio
async def test_partial_mapping_some_matched_some_not(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    source_service_principals: List[Dict[str, Any]],
    target_service_principals: List[Dict[str, Any]],
) -> None:
    """
    Test partial matching where some identities match and some don't.

    Scenario:
        - 3 out of 4 users should match
        - 2 out of 3 service principals should match
        - Should generate complete mapping with placeholders for missing
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users
        mock_source_service.get_service_principals.return_value = (
            source_service_principals
        )
        mock_target_service.get_service_principals.return_value = (
            target_service_principals
        )

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Count matches
        user_matches = sum(
            1
            for user_map in mapping["users"].values()
            if user_map["target_object_id"] != "MANUAL_INPUT_REQUIRED"
            and user_map.get("match_confidence") != "none"
        )

        sp_matches = sum(
            1
            for sp_map in mapping["service_principals"].values()
            if sp_map["target_object_id"] != "MANUAL_INPUT_REQUIRED"
            and sp_map.get("match_confidence") != "none"
        )

        # Should have matched 3/4 users (Alice, Bob, Charlie)
        assert user_matches >= 3

        # Should have matched 2/3 service principals
        assert sp_matches >= 2


# ============================================================================
# INTEGRATION TESTS (30%)
# ============================================================================


@pytest.mark.asyncio
async def test_mapping_integration_with_neo4j(
    source_tenant_id: str,
    target_tenant_id: str,
    mock_neo4j_driver: MagicMock,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
) -> None:
    """
    Integration test: AutoIdentityMapper queries Neo4j for role assignments.

    Scenario:
        - Neo4j contains role assignments referencing users
        - AutoIdentityMapper should discover which users need mapping
        - Should only map users that are actually referenced
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        # Create mapping with Neo4j context
        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            neo4j_driver=mock_neo4j_driver,
        )

        # Should have discovered user-1 from role assignment
        assert "users" in mapping
        assert "aaaaaaaa-0000-0000-0000-000000000001" in mapping["users"]


@pytest.mark.asyncio
async def test_mapping_file_generation_format(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    tmp_path: Path,
) -> None:
    """
    Integration test: Generated mapping file has correct format.

    Scenario:
        - Generate mapping and save to file
        - Verify file format matches EntraIdTranslator expectations
        - Verify file can be loaded by EntraIdTranslator
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Save to file
        output_file = tmp_path / "generated_mapping.json"
        mapper.save_mapping(mapping, output_file)

        # Verify file exists and is valid JSON
        assert output_file.exists()
        with open(output_file) as f:
            loaded_mapping = json.load(f)

        # Verify format matches EntraIdTranslator expectations
        assert "tenant_mapping" in loaded_mapping
        assert "identity_mappings" in loaded_mapping
        assert "source_tenant_id" in loaded_mapping["tenant_mapping"]
        assert "target_tenant_id" in loaded_mapping["tenant_mapping"]

        # Verify can be loaded by EntraIdTranslator
        from src.iac.translators.base_translator import TranslationContext
        from src.iac.translators.entraid_translator import EntraIdTranslator

        context = TranslationContext(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            identity_mapping=loaded_mapping,
        )

        translator = EntraIdTranslator(context)
        assert translator.manifest is not None
        assert len(translator.manifest.users) > 0


@pytest.mark.asyncio
async def test_auto_mapper_called_during_iac_generation(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Integration test: AutoIdentityMapper is invoked during IaC generation.

    Scenario:
        - User runs generate-iac with --target-tenant-id
        - System should automatically invoke AutoIdentityMapper
        - Generated mapping should be passed to EntraIdTranslator
    """
    from src.iac.cli_handler import generate_iac_command_handler

    # Track if AutoIdentityMapper was called
    auto_mapper_called = {"called": False, "mapping": None}

    class MockAutoIdentityMapper:
        async def create_mapping(
            self,
            source_tenant_id: str,
            target_tenant_id: str,
            manual_mapping_file: Optional[Path] = None,
            neo4j_driver: Optional[Any] = None,
        ) -> Dict[str, Any]:
            auto_mapper_called["called"] = True
            auto_mapper_called["mapping"] = {
                "tenant_mapping": {
                    "source_tenant_id": source_tenant_id,
                    "target_tenant_id": target_tenant_id,
                },
                "identity_mappings": {
                    "users": {},
                    "groups": {},
                    "service_principals": {},
                },
            }
            return auto_mapper_called["mapping"]

        def save_mapping(self, mapping: Dict[str, Any], output_file: Path) -> None:
            pass

    # Mock AutoIdentityMapper
    monkeypatch.setattr(
        "src.iac.cli_handler.AutoIdentityMapper",
        MockAutoIdentityMapper,
    )

    # Mock other dependencies
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config",
        lambda: mock_driver,
    )

    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)
    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser",
        lambda driver, rules: mock_traverser,
    )

    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]
    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter",
        lambda fmt: lambda **kwargs: mock_emitter,
    )

    mock_engine = MagicMock()
    mock_engine.generate_iac.return_value = [Path("/tmp/test.tf")]
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine",
        lambda *args, **kwargs: mock_engine,
    )

    # Run generate-iac with target tenant
    result = await generate_iac_command_handler(
        tenant_id=source_tenant_id,
        source_tenant_id=source_tenant_id,
        target_tenant_id=target_tenant_id,
        format_type="terraform",
        dry_run=True,
        skip_validation=True,
    )

    # Should have succeeded
    assert result == 0

    # Should have called AutoIdentityMapper
    assert auto_mapper_called["called"], "AutoIdentityMapper should have been invoked"
    assert auto_mapper_called["mapping"] is not None


# ============================================================================
# CLI INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_cli_triggers_auto_mapping(
    source_tenant_id: str,
    target_tenant_id: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test that CLI properly triggers auto-mapping when --target-tenant-id is provided.

    Scenario:
        - User provides --target-tenant-id
        - CLI should detect cross-tenant scenario
        - CLI should invoke AutoIdentityMapper automatically
    """
    from src.iac.cli_handler import generate_iac_command_handler

    auto_mapper_invoked = {"invoked": False}

    class MockAutoIdentityMapper:
        async def create_mapping(
            self,
            source_tenant_id: str,
            target_tenant_id: str,
            manual_mapping_file: Optional[Path] = None,
            neo4j_driver: Optional[Any] = None,
        ) -> Dict[str, Any]:
            auto_mapper_invoked["invoked"] = True
            return {
                "tenant_mapping": {
                    "source_tenant_id": source_tenant_id,
                    "target_tenant_id": target_tenant_id,
                },
                "identity_mappings": {
                    "users": {},
                    "groups": {},
                    "service_principals": {},
                },
            }

        def save_mapping(self, mapping: Dict[str, Any], output_file: Path) -> None:
            pass

    monkeypatch.setattr(
        "src.iac.cli_handler.AutoIdentityMapper",
        MockAutoIdentityMapper,
    )

    # Mock dependencies
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config",
        lambda: mock_driver,
    )

    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)
    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser",
        lambda driver, rules: mock_traverser,
    )

    mock_emitter = MagicMock()
    mock_emitter.emit.return_value = [Path("/tmp/test.tf")]
    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter",
        lambda fmt: lambda **kwargs: mock_emitter,
    )

    mock_engine = MagicMock()
    mock_engine.generate_iac.return_value = [Path("/tmp/test.tf")]
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine",
        lambda *args, **kwargs: mock_engine,
    )

    # Invoke CLI handler with target tenant
    await generate_iac_command_handler(
        tenant_id=source_tenant_id,
        source_tenant_id=source_tenant_id,
        target_tenant_id=target_tenant_id,
        format_type="terraform",
        dry_run=True,
    )

    # Verify auto-mapper was invoked
    assert auto_mapper_invoked["invoked"], (
        "AutoIdentityMapper should be triggered by CLI"
    )


@pytest.mark.asyncio
async def test_identity_mapping_file_actually_loaded(
    source_tenant_id: str,
    target_tenant_id: str,
    manual_mapping_override: Dict[str, Any],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Test bug fix: --identity-mapping-file actually loads the file.

    Scenario:
        - User provides --identity-mapping-file path
        - File should be loaded
        - Mapping should be passed to translator
        - CRITICAL: This was a bug where file was ignored
    """
    from src.iac.cli_handler import generate_iac_command_handler

    # Create mapping file
    mapping_file = tmp_path / "identity_mappings.json"
    with open(mapping_file, "w") as f:
        json.dump(manual_mapping_override, f, indent=2)

    # Track if mapping was passed to emitter
    emitter_kwargs = {"captured": None}

    class MockEmitter:
        def __init__(self, **kwargs: Any):
            emitter_kwargs["captured"] = kwargs

        def emit(self, *args: Any, **kwargs: Any) -> List[Path]:
            return [Path("/tmp/test.tf")]

    # Mock dependencies
    mock_driver = MagicMock()
    monkeypatch.setattr(
        "src.iac.cli_handler.get_neo4j_driver_from_config",
        lambda: mock_driver,
    )

    mock_graph = MagicMock()
    mock_graph.resources = []
    mock_traverser = MagicMock()
    mock_traverser.traverse = AsyncMock(return_value=mock_graph)
    monkeypatch.setattr(
        "src.iac.cli_handler.GraphTraverser",
        lambda driver, rules: mock_traverser,
    )

    monkeypatch.setattr(
        "src.iac.cli_handler.get_emitter",
        lambda fmt: MockEmitter,
    )

    mock_engine = MagicMock()
    mock_engine.generate_iac.return_value = [Path("/tmp/test.tf")]
    monkeypatch.setattr(
        "src.iac.cli_handler.TransformationEngine",
        lambda *args, **kwargs: mock_engine,
    )

    # Run with identity mapping file (not dry_run so emitter is actually created)
    await generate_iac_command_handler(
        tenant_id=source_tenant_id,
        source_tenant_id=source_tenant_id,
        target_tenant_id=target_tenant_id,
        identity_mapping_file=str(mapping_file),
        format_type="terraform",
        dry_run=False,
    )

    # Verify mapping file was loaded and passed to emitter
    assert emitter_kwargs["captured"] is not None
    assert "identity_mapping_file" in emitter_kwargs["captured"]

    # Verify file path is correct
    assert emitter_kwargs["captured"]["identity_mapping_file"] == str(mapping_file)


# ============================================================================
# E2E TESTS (10%)
# ============================================================================


@pytest.mark.asyncio
async def test_end_to_end_auto_mapping_workflow(
    source_tenant_id: str,
    target_tenant_id: str,
    source_users: List[Dict[str, Any]],
    target_users: List[Dict[str, Any]],
    source_service_principals: List[Dict[str, Any]],
    target_service_principals: List[Dict[str, Any]],
    tmp_path: Path,
) -> None:
    """
    End-to-end test: Complete auto-mapping workflow.

    Scenario:
        1. User has resources in source tenant
        2. User wants to deploy to target tenant
        3. System automatically creates identity mappings
        4. Mapping file is generated and saved
        5. IaC generation uses mapping file
        6. Generated Terraform has correct object IDs
    """
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    # Step 1: Create auto mapper
    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_source_service = AsyncMock()
        mock_target_service = AsyncMock()

        def get_service_for_tenant(*args: Any, **kwargs: Any) -> AsyncMock:
            if "tenant_id" in kwargs:
                if kwargs["tenant_id"] == source_tenant_id:
                    return mock_source_service
                elif kwargs["tenant_id"] == target_tenant_id:
                    return mock_target_service
            return mock_source_service

        mock_aad_service_cls.side_effect = get_service_for_tenant

        mock_source_service.get_users.return_value = source_users
        mock_target_service.get_users.return_value = target_users
        mock_source_service.get_service_principals.return_value = (
            source_service_principals
        )
        mock_target_service.get_service_principals.return_value = (
            target_service_principals
        )

        # Step 2: Generate mapping
        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Step 3: Save mapping to file
        output_file = tmp_path / "identity_mapping.json"
        mapper.save_mapping(mapping, output_file)

        # Step 4: Verify file was created
        assert output_file.exists()

        # Step 5: Load and verify mapping can be used by EntraIdTranslator
        from src.iac.translators.base_translator import TranslationContext
        from src.iac.translators.entraid_translator import EntraIdTranslator

        with open(output_file) as f:
            loaded_mapping = json.load(f)

        context = TranslationContext(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
            identity_mapping=loaded_mapping,
        )

        translator = EntraIdTranslator(context)

        # Step 6: Test translation with role assignment
        role_assignment = {
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": {
                "principalId": "aaaaaaaa-0000-0000-0000-000000000001",
                "principalType": "User",
            },
        }

        translated = translator.translate(role_assignment)

        # Verify principal ID was translated
        assert translated["properties"]["principalId"] == "11111111-0000-0000-0000-000000000001"


# ============================================================================
# ERROR HANDLING TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_invalid_tenant_id_raises_error() -> None:
    """Test that invalid tenant IDs raise appropriate errors."""
    from azure.core.exceptions import ClientAuthenticationError
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    # Invalid tenant IDs will cause authentication errors from Azure SDK
    with pytest.raises((ValueError, RuntimeError, ClientAuthenticationError, Exception)) as exc_info:
        await mapper.create_mapping(
            source_tenant_id="invalid-tenant-id",
            target_tenant_id="also-invalid",
        )

    # Verify error message mentions tenant or authentication
    error_msg = str(exc_info.value).lower()
    assert "tenant" in error_msg or "authentication" in error_msg or "authority" in error_msg


@pytest.mark.asyncio
async def test_aad_service_failure_handled_gracefully(
    source_tenant_id: str,
    target_tenant_id: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that AAD service failures are handled gracefully."""
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_service = AsyncMock()
        mock_service.get_users.side_effect = Exception("API failure")
        mock_aad_service_cls.return_value = mock_service

        # Should handle error gracefully
        with pytest.raises(Exception) as exc_info:
            await mapper.create_mapping(
                source_tenant_id=source_tenant_id,
                target_tenant_id=target_tenant_id,
            )

        # Should log appropriate error
        assert "api failure" in str(exc_info.value).lower() or any(
            "api" in record.message.lower() for record in caplog.records
        )


@pytest.mark.asyncio
async def test_empty_tenant_returns_empty_mapping(
    source_tenant_id: str,
    target_tenant_id: str,
) -> None:
    """Test that empty tenants return valid but empty mappings."""
    from src.iac.auto_identity_mapper import AutoIdentityMapper

    mapper = AutoIdentityMapper()

    with patch("src.iac.auto_identity_mapper.AADGraphService") as mock_aad_service_cls:
        mock_service = AsyncMock()
        mock_service.get_users.return_value = []
        mock_service.get_groups.return_value = []
        mock_service.get_service_principals.return_value = []
        mock_aad_service_cls.return_value = mock_service

        mapping = await mapper.create_mapping(
            source_tenant_id=source_tenant_id,
            target_tenant_id=target_tenant_id,
        )

        # Should return valid structure
        assert "tenant_mapping" in mapping
        assert "identity_mappings" in mapping
        assert len(mapping["identity_mappings"]["users"]) == 0
