import inspect

from src.tenant_spec_models import Tenant, TenantSpec, User


def test_parse_raw_json_valid():
    # Minimal valid TenantSpec JSON
    json_text = """
    {
        "tenant": {
            "id": "tenant-1",
            "display_name": "Test Tenant",
            "subscriptions": [],
            "users": [],
            "groups": [],
            "service_principals": [],
            "managed_identities": [],
            "admin_units": [],
            "rbac_assignments": [],
            "relationships": []
        }
    }
    """
    spec = TenantSpec.parse_raw_json(json_text)
    assert spec.tenant.id == "tenant-1"
    assert spec.tenant.display_name == "Test Tenant"


def test_aliases_and_camel_case_deserialization():
    # Test that both snake_case and camelCase/alias fields are accepted
    json_text = """
    {
        "tenant": {
            "tenantId": "tenant-2",
            "displayName": "Camel Tenant",
            "users": [
                {
                    "userId": "user-1",
                    "displayName": "Camel User",
                    "emailAddress": "camel@example.com"
                }
            ],
            "subscriptions": [],
            "groups": [],
            "servicePrincipals": [],
            "managedIdentities": [],
            "adminUnits": [],
            "rbacAssignments": [],
            "relationships": []
        }
    }
    """
    spec = TenantSpec.parse_raw_json(json_text)
    assert spec.tenant.id == "tenant-2"
    assert spec.tenant.display_name == "Camel Tenant"
    assert spec.tenant.users is not None
    assert spec.tenant.users[0].id == "user-1"
    assert spec.tenant.users[0].display_name == "Camel User"
    assert spec.tenant.users[0].email == "camel@example.com"


def test_class_docstrings_and_field_descriptions():
    # Check that class docstrings are present
    assert inspect.getdoc(User) is not None
    assert inspect.getdoc(Tenant) is not None

    # Check that field descriptions are present in the schema
    user_schema = User.model_json_schema()
    assert user_schema["properties"]["id"]["description"]
    assert user_schema["properties"]["display_name"]["description"]
    assert user_schema["properties"]["email"]["description"]

    tenant_schema = Tenant.model_json_schema()
    assert tenant_schema["properties"]["id"]["description"]
    assert tenant_schema["properties"]["display_name"]["description"]
    assert tenant_schema["properties"]["users"]["description"]
