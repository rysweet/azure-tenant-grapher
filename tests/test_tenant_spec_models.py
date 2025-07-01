from src.tenant_spec_models import TenantSpec


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
