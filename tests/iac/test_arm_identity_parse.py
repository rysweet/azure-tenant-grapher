import re

from src.resource_processor import extract_identity_fields


def is_guid(val):
    return bool(
        re.match(
            r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
            val,
        )
    )


def test_identity_block_extracted():
    resource = {
        "name": "vm1",
        "identity": {
            "type": "SystemAssigned",
            "principalId": "11111111-2222-3333-4444-555555555555",
        },
    }
    extract_identity_fields(resource)
    assert "identity" in resource
    assert resource["identity"]["type"] == "SystemAssigned"


def test_principal_id_valid_guid():
    resource = {"name": "sp1", "principalId": "12345678-1234-1234-1234-123456789abc"}
    extract_identity_fields(resource)
    assert "principal_id" in resource
    assert is_guid(resource["principal_id"])


def test_both_identity_and_principal_id():
    resource = {
        "name": "webapp1",
        "identity": {"type": "UserAssigned"},
        "principalId": "abcdefab-1234-5678-9abc-def012345678",
    }
    extract_identity_fields(resource)
    assert "identity" in resource
    assert "principal_id" in resource
    assert is_guid(resource["principal_id"])


def test_invalid_principal_id_not_extracted():
    resource = {"name": "badsp", "principalId": "not-a-guid"}
    extract_identity_fields(resource)
    assert "principal_id" not in resource


def test_neither_identity_nor_principal_id():
    resource = {"name": "storage1"}
    extract_identity_fields(resource)
    assert "identity" not in resource
    assert "principal_id" not in resource
