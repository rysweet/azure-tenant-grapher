"""Test fixtures and mock data for CTF Overlay System tests.

Provides reusable test data for unit, integration, and E2E tests.
"""

import json
from pathlib import Path
from typing import Any, Dict, List

# ============================================================================
# Terraform State Fixtures
# ============================================================================


def get_m003_v1_base_terraform_state() -> Dict[str, Any]:
    """Get Terraform state for M003 v1-base scenario (3 resources)."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "azurerm_virtual_machine",
                "name": "target",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Compute/virtualMachines/target-vm",
                            "name": "target-vm",
                            "location": "eastus",
                            "vm_size": "Standard_B2s",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v1-base",
                                "ctf_role": "target",
                            },
                        }
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "azurerm_virtual_network",
                "name": "vnet",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Network/virtualNetworks/ctf-vnet",
                            "name": "ctf-vnet",
                            "location": "eastus",
                            "address_space": ["10.0.0.0/16"],
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v1-base",
                                "ctf_role": "infrastructure",
                            },
                        }
                    }
                ],
            },
            {
                "mode": "managed",
                "type": "azurerm_network_security_group",
                "name": "nsg",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Network/networkSecurityGroups/ctf-nsg",
                            "name": "ctf-nsg",
                            "location": "eastus",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v1-base",
                                "ctf_role": "infrastructure",
                            },
                        }
                    }
                ],
            },
        ],
    }


def get_m003_v2_cert_terraform_state() -> Dict[str, Any]:
    """Get Terraform state for M003 v2-cert scenario (5 resources)."""
    base_state = get_m003_v1_base_terraform_state()

    # Update scenario tags
    for resource in base_state["resources"]:
        for instance in resource["instances"]:
            instance["attributes"]["tags"]["ctf_scenario"] = "v2-cert"

    # Add attacker VM
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_virtual_machine",
            "name": "attacker",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Compute/virtualMachines/attacker-vm",
                        "name": "attacker-vm",
                        "location": "eastus",
                        "vm_size": "Standard_B2s",
                        "tags": {
                            "layer_id": "default",
                            "ctf_exercise": "M003",
                            "ctf_scenario": "v2-cert",
                            "ctf_role": "attacker",
                        },
                    }
                }
            ],
        }
    )

    # Add key vault for certificates
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_key_vault",
            "name": "keyvault",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.KeyVault/vaults/ctf-keyvault",
                        "name": "ctf-keyvault",
                        "location": "eastus",
                        "tags": {
                            "layer_id": "default",
                            "ctf_exercise": "M003",
                            "ctf_scenario": "v2-cert",
                            "ctf_role": "infrastructure",
                        },
                    }
                }
            ],
        }
    )

    return base_state


def get_m003_v3_ews_terraform_state() -> Dict[str, Any]:
    """Get Terraform state for M003 v3-ews scenario (4 resources with monitoring)."""
    base_state = get_m003_v1_base_terraform_state()

    # Update scenario tags
    for resource in base_state["resources"]:
        for instance in resource["instances"]:
            instance["attributes"]["tags"]["ctf_scenario"] = "v3-ews"

    # Add Log Analytics workspace for monitoring
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_log_analytics_workspace",
            "name": "law",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.OperationalInsights/workspaces/ctf-law",
                        "name": "ctf-law",
                        "location": "eastus",
                        "tags": {
                            "layer_id": "default",
                            "ctf_exercise": "M003",
                            "ctf_scenario": "v3-ews",
                            "ctf_role": "monitoring",
                        },
                    }
                }
            ],
        }
    )

    return base_state


def get_m003_v4_blob_terraform_state() -> Dict[str, Any]:
    """Get Terraform state for M003 v4-blob scenario (6 resources with storage)."""
    base_state = get_m003_v1_base_terraform_state()

    # Update scenario tags
    for resource in base_state["resources"]:
        for instance in resource["instances"]:
            instance["attributes"]["tags"]["ctf_scenario"] = "v4-blob"

    # Add storage account
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_storage_account",
            "name": "storage",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Storage/storageAccounts/ctfstorage",
                        "name": "ctfstorage",
                        "location": "eastus",
                        "account_tier": "Standard",
                        "account_replication_type": "LRS",
                        "tags": {
                            "layer_id": "default",
                            "ctf_exercise": "M003",
                            "ctf_scenario": "v4-blob",
                            "ctf_role": "infrastructure",
                        },
                    }
                }
            ],
        }
    )

    # Add blob container
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_storage_container",
            "name": "container",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Storage/storageAccounts/ctfstorage/blobServices/default/containers/ctf-container",
                        "name": "ctf-container",
                        "storage_account_name": "ctfstorage",
                        "container_access_type": "private",
                    }
                }
            ],
        }
    )

    # Add additional VM for blob access testing
    base_state["resources"].append(
        {
            "mode": "managed",
            "type": "azurerm_virtual_machine",
            "name": "blob_access_vm",
            "instances": [
                {
                    "attributes": {
                        "id": "/subscriptions/test-sub/resourceGroups/ctf-rg/providers/Microsoft.Compute/virtualMachines/blob-vm",
                        "name": "blob-vm",
                        "location": "eastus",
                        "vm_size": "Standard_B2s",
                        "tags": {
                            "layer_id": "default",
                            "ctf_exercise": "M003",
                            "ctf_scenario": "v4-blob",
                            "ctf_role": "target",
                        },
                    }
                }
            ],
        }
    )

    return base_state


# ============================================================================
# Neo4j Resource Fixtures
# ============================================================================


def get_sample_neo4j_resources() -> List[Dict[str, Any]]:
    """Get sample resources as they would appear in Neo4j."""
    return [
        {
            "id": "vm-target-001",
            "name": "target-vm",
            "resource_type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "layer_id": "default",
            "ctf_exercise": "M003",
            "ctf_scenario": "v2-cert",
            "ctf_role": "target",
            "created_at": "2025-12-02T10:00:00Z",
            "updated_at": "2025-12-02T10:00:00Z",
        },
        {
            "id": "vnet-001",
            "name": "ctf-vnet",
            "resource_type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "layer_id": "default",
            "ctf_exercise": "M003",
            "ctf_scenario": "v2-cert",
            "ctf_role": "infrastructure",
            "created_at": "2025-12-02T10:00:00Z",
            "updated_at": "2025-12-02T10:00:00Z",
        },
        {
            "id": "nsg-001",
            "name": "ctf-nsg",
            "resource_type": "Microsoft.Network/networkSecurityGroups",
            "location": "eastus",
            "layer_id": "default",
            "ctf_exercise": "M003",
            "ctf_scenario": "v2-cert",
            "ctf_role": "infrastructure",
            "created_at": "2025-12-02T10:00:00Z",
            "updated_at": "2025-12-02T10:00:00Z",
        },
    ]


def get_multi_layer_resources() -> List[Dict[str, Any]]:
    """Get resources across multiple layers for isolation testing."""
    resources = []

    for layer_num in range(1, 4):
        layer_id = f"layer{layer_num}"

        for scenario in ["v1-base", "v2-cert"]:
            resources.append(
                {
                    "id": f"vm-{layer_id}-{scenario}",
                    "name": f"vm-{layer_id}",
                    "resource_type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                    "layer_id": layer_id,
                    "ctf_exercise": "M003",
                    "ctf_scenario": scenario,
                    "ctf_role": "target",
                }
            )

    return resources


# ============================================================================
# Validation Fixtures
# ============================================================================


def get_valid_ctf_property_values() -> Dict[str, List[str]]:
    """Get valid CTF property values for validation testing."""
    return {
        "layer_id": ["default", "base", "test-layer", "layer_123", "my-custom-layer"],
        "ctf_exercise": ["M003", "M004", "test-exercise", "Exercise_123"],
        "ctf_scenario": ["v1-base", "v2-cert", "v3-ews", "v4-blob", "custom_scenario"],
        "ctf_role": ["target", "attacker", "infrastructure", "monitoring"],
    }


def get_invalid_ctf_property_values() -> Dict[str, List[str]]:
    """Get invalid CTF property values for validation testing."""
    return {
        "layer_id": [
            "'; DROP TABLE Resource; --",  # SQL injection
            "layer with spaces",  # Spaces not allowed
            "../../../etc/passwd",  # Path traversal
            "layer<script>",  # XSS attempt
            "",  # Empty string
        ],
        "ctf_exercise": [
            "M003; DELETE",  # Command injection
            'exercise" OR "1"="1',  # SQL injection
            "ex!@#$%",  # Special characters
        ],
        "ctf_scenario": [
            "v1'; DROP DATABASE; --",
            "scenario\nwith\nnewlines",
        ],
        "ctf_role": [
            "role<script>alert('xss')</script>",
            "role;DROP TABLE",
        ],
    }


# ============================================================================
# Terraform Configuration Fixtures
# ============================================================================


def get_sample_terraform_config() -> str:
    """Get sample generated Terraform configuration."""
    return """
terraform {
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "ctf" {
  name     = "ctf-rg-default-M003-v2-cert"
  location = "eastus"

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v2-cert"
  }
}

resource "azurerm_virtual_machine" "target" {
  name                = "vm-default-M003-v2-cert-target"
  location            = azurerm_resource_group.ctf.location
  resource_group_name = azurerm_resource_group.ctf.name
  vm_size             = "Standard_B2s"

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v2-cert"
    ctf_role     = "target"
  }

  # ... additional VM configuration ...
}

resource "azurerm_virtual_network" "vnet" {
  name                = "vnet-default-M003-v2-cert"
  location            = azurerm_resource_group.ctf.location
  resource_group_name = azurerm_resource_group.ctf.name
  address_space       = ["10.0.0.0/16"]

  tags = {
    layer_id     = "default"
    ctf_exercise = "M003"
    ctf_scenario = "v2-cert"
    ctf_role     = "infrastructure"
  }
}
"""


# ============================================================================
# Helper Functions
# ============================================================================


def save_terraform_state_to_file(state: Dict[str, Any], filepath: Path):
    """Save Terraform state to file for testing."""
    with open(filepath, "w") as f:
        json.dump(state, f, indent=2)


def load_terraform_state_from_file(filepath: Path) -> Dict[str, Any]:
    """Load Terraform state from file."""
    with open(filepath) as f:
        return json.load(f)


def create_mock_neo4j_records(resources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert resource list to Neo4j record format."""
    return [{"r": resource} for resource in resources]


# ============================================================================
# Test Scenario Metadata
# ============================================================================


M003_SCENARIOS = {
    "v1-base": {
        "description": "Basic M003 scenario with target VM and infrastructure",
        "resource_count": 3,
        "roles": ["target", "infrastructure"],
        "terraform_state_generator": get_m003_v1_base_terraform_state,
    },
    "v2-cert": {
        "description": "Certificate authentication scenario with attacker VM",
        "resource_count": 5,
        "roles": ["target", "attacker", "infrastructure"],
        "terraform_state_generator": get_m003_v2_cert_terraform_state,
    },
    "v3-ews": {
        "description": "Exchange Web Services scenario with monitoring",
        "resource_count": 4,
        "roles": ["target", "infrastructure", "monitoring"],
        "terraform_state_generator": get_m003_v3_ews_terraform_state,
    },
    "v4-blob": {
        "description": "Blob storage scenario with multiple targets",
        "resource_count": 6,
        "roles": ["target", "infrastructure"],
        "terraform_state_generator": get_m003_v4_blob_terraform_state,
    },
}


def get_all_m003_terraform_states() -> Dict[str, Dict[str, Any]]:
    """Get all M003 scenario Terraform states."""
    return {
        scenario_id: metadata["terraform_state_generator"]()
        for scenario_id, metadata in M003_SCENARIOS.items()
    }


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Terraform state fixtures
    "get_m003_v1_base_terraform_state",
    "get_m003_v2_cert_terraform_state",
    "get_m003_v3_ews_terraform_state",
    "get_m003_v4_blob_terraform_state",
    "get_all_m003_terraform_states",
    # Neo4j resource fixtures
    "get_sample_neo4j_resources",
    "get_multi_layer_resources",
    # Validation fixtures
    "get_valid_ctf_property_values",
    "get_invalid_ctf_property_values",
    # Terraform config fixtures
    "get_sample_terraform_config",
    # Helper functions
    "save_terraform_state_to_file",
    "load_terraform_state_from_file",
    "create_mock_neo4j_records",
    # Metadata
    "M003_SCENARIOS",
]
