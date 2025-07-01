from unittest.mock import AsyncMock

import pytest

from src.tenant_creator import TenantCreator
from src.tenant_spec_models import TenantSpec


@pytest.mark.asyncio
async def test_narrative_markdown_llm_to_spec(monkeypatch):
    # Narrative-only markdown (no JSON block)
    narrative_md = """
# Azure Tenant Overview

This tenant contains a single subscription for production workloads. The subscription has one resource group named "prod-rg" in East US, which contains a single virtual machine called "vm-prod". The tenant ID is "tenant-001".

Users and groups are not described.
    """

    # Minimal valid JSON spec to be returned by the mock LLM
    minimal_json = """
{
  "tenant": {
    "id": "tenant-001",
    "display_name": "Example Tenant",
    "subscriptions": [
      {
        "id": "sub-001",
        "name": "Production",
        "resource_groups": [
          {
            "id": "rg-001",
            "name": "prod-rg",
            "location": "eastus",
            "resources": [
              {
                "id": "res-001",
                "name": "vm-prod",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
                "properties": {}
              }
            ]
          }
        ]
      }
    ],
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

    # Mock the LLM generator's _llm_generate_tenant_spec to return the minimal JSON
    creator = TenantCreator(llm_generator=None)
    creator._llm_generate_tenant_spec = AsyncMock(return_value=minimal_json)

    spec = await creator.create_from_markdown(narrative_md)
    assert isinstance(spec, TenantSpec)
    assert spec.tenant.id == "tenant-001"
    assert (
        spec.tenant.subscriptions[0].resource_groups[0].resources[0].name == "vm-prod"
    )


@pytest.mark.asyncio
async def test_llm_invalid_json_raises_llm_generation_error(monkeypatch):
    """Test that invalid LLM output raises LLMGenerationError with context."""
    from src.exceptions import LLMGenerationError
    from src.tenant_creator import TenantCreator

    # Simulate LLM output that is not valid JSON
    invalid_json = "this is not valid json"

    creator = TenantCreator(llm_generator=None)
    creator._llm_generate_tenant_spec = AsyncMock(return_value=invalid_json)

    markdown = "Some narrative text with no JSON block."
    with pytest.raises(LLMGenerationError) as excinfo:
        await creator.create_from_markdown(markdown)
    err = excinfo.value
    # The error should include the prompt and raw response in context
    assert "prompt" in err.context
    assert "raw_response" in err.context
    assert err.context["raw_response"] == invalid_json
    assert "Failed to parse LLM output as valid JSON." in str(err)


@pytest.mark.asyncio
async def test_llm_rbac_assignment_field_normalization(monkeypatch):
    # Simulate LLM output with variant field names
    llm_json = """
    {
      "tenant": {
        "id": "tenant-001",
        "display_name": "Example Tenant",
        "subscriptions": [],
        "users": [],
        "groups": [],
        "service_principals": [],
        "managed_identities": [],
        "admin_units": [],
        "rbac_assignments": [
          {
            "role_definition": "Owner",
            "principalId": "user-123",
            "scope": "sub-001"
          },
          {
            "roleDefinitionName": "Contributor",
            "principal_id": "user-456",
            "scope": "sub-002"
          },
          {
            "role_definition_name": "Reader",
            "principalId": "user-789",
            "scope": "sub-003"
          }
        ],
        "relationships": []
      }
    }
    """

    creator = TenantCreator(llm_generator=None)
    # Patch the LLM call to return our test JSON
    creator._llm_generate_tenant_spec = AsyncMock(return_value=llm_json)

    # No JSON block in markdown, so LLM will be called
    markdown = "Some narrative text with no JSON block."
    spec = await creator.create_from_markdown(markdown)

    rbac = spec.tenant.rbac_assignments
    assert len(rbac) == 3
    # All assignments should have canonical field names
    assert rbac[0].role == "Owner"
    assert rbac[0].principal_id == "user-123"
    assert rbac[0].scope == "sub-001"
    assert rbac[1].role == "Contributor"
    assert rbac[1].principal_id == "user-456"
    assert rbac[1].scope == "sub-002"
    assert rbac[2].role == "Reader"
    assert rbac[2].principal_id == "user-789"
    assert rbac[2].scope == "sub-003"
