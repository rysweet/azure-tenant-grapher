"""
Tests for the IaC validation script.
"""

import json
import sys
import tempfile
from pathlib import Path

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from validate_generated_iac import IaCValidator, ValidationIssue, ValidationResult


@pytest.fixture
def temp_iac_dir():
    """Create a temporary directory for test IaC files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def valid_terraform_config():
    """Valid Terraform configuration for testing."""
    return {
        "terraform": {
            "required_providers": {
                "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"}
            }
        },
        "provider": {"azurerm": {"features": {}}},
        "resource": {
            "azurerm_resource_group": {
                "test_rg": {"name": "test-rg", "location": "eastus"}
            },
            "azurerm_virtual_network": {
                "test_vnet": {
                    "name": "test-vnet",
                    "location": "eastus",
                    "resource_group_name": "test-rg",
                    "address_space": ["10.0.0.0/16"],
                }
            },
            "azurerm_subnet": {
                "test_subnet": {
                    "name": "test-subnet",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["10.0.1.0/24"],
                }
            },
        },
    }


def test_validator_initialization(temp_iac_dir):
    """Test validator can be initialized."""
    validator = IaCValidator(temp_iac_dir)
    assert validator.iac_directory == temp_iac_dir
    assert validator.terraform_files == []
    assert validator.terraform_data == {}


def test_load_terraform_files(temp_iac_dir, valid_terraform_config):
    """Test loading Terraform JSON files."""
    # Create a test terraform file
    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(valid_terraform_config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    assert len(validator.terraform_files) == 1
    assert validator.terraform_data == valid_terraform_config


def test_check_no_placeholders_pass(temp_iac_dir, valid_terraform_config):
    """Test placeholder check passes with valid config."""
    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(valid_terraform_config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_no_placeholders()
    assert result.passed
    assert len(result.issues) == 0


def test_check_no_placeholders_fail(temp_iac_dir):
    """Test placeholder check fails with xxx placeholder."""
    config = {
        "resource": {
            "azurerm_storage_account": {"test": {"name": "xxx", "location": "eastus"}}
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_no_placeholders()
    assert not result.passed
    assert len(result.issues) > 0
    assert any("xxx" in issue.message.lower() for issue in result.issues)


def test_check_valid_tenant_ids_pass(temp_iac_dir):
    """Test tenant ID validation passes with valid UUID."""
    config = {
        "resource": {
            "azurerm_key_vault": {
                "test_kv": {
                    "name": "test-kv",
                    "location": "eastus",
                    "tenant_id": "12345678-1234-1234-1234-123456789012",
                    "sku_name": "standard",
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_valid_tenant_ids()
    assert result.passed
    assert len(result.issues) == 0


def test_check_valid_tenant_ids_fail_zeros(temp_iac_dir):
    """Test tenant ID validation fails with all-zeros UUID."""
    config = {
        "resource": {
            "azurerm_key_vault": {
                "test_kv": {
                    "name": "test-kv",
                    "location": "eastus",
                    "tenant_id": "00000000-0000-0000-0000-000000000000",
                    "sku_name": "standard",
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_valid_tenant_ids()
    assert not result.passed
    assert len(result.issues) == 1
    assert "all zeros" in result.issues[0].message


def test_check_valid_subscription_ids_pass(temp_iac_dir):
    """Test subscription ID validation passes with valid UUID."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test": {
                    "name": "test",
                    "location": "eastus",
                    "tags": {
                        "subscription": "/subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/test"
                    },
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_valid_subscription_ids()
    assert result.passed


def test_check_valid_subscription_ids_fail(temp_iac_dir):
    """Test subscription ID validation fails with placeholder."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test": {
                    "name": "test",
                    "location": "eastus",
                    "id": "/subscriptions/xxx/resourceGroups/test",
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_valid_subscription_ids()
    assert not result.passed
    assert len(result.issues) == 1


def test_check_subnet_cidrs_pass(temp_iac_dir):
    """Test subnet CIDR validation passes with valid subnets."""
    config = {
        "resource": {
            "azurerm_virtual_network": {
                "test_vnet": {"name": "test-vnet", "address_space": ["10.0.0.0/16"]}
            },
            "azurerm_subnet": {
                "test_subnet": {
                    "name": "test-subnet",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["10.0.1.0/24"],
                }
            },
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_subnet_cidrs()
    assert result.passed


def test_check_subnet_cidrs_fail_out_of_range(temp_iac_dir):
    """Test subnet CIDR validation fails when subnet is outside VNet."""
    config = {
        "resource": {
            "azurerm_virtual_network": {
                "test_vnet": {"name": "test-vnet", "address_space": ["10.0.0.0/16"]}
            },
            "azurerm_subnet": {
                "test_subnet": {
                    "name": "test-subnet",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["192.168.1.0/24"],  # Outside 10.0.0.0/16
                }
            },
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_subnet_cidrs()
    assert not result.passed
    assert len(result.issues) == 1
    assert "outside VNet address space" in result.issues[0].message


def test_check_duplicate_resources_pass(temp_iac_dir, valid_terraform_config):
    """Test duplicate resource check passes with unique resources."""
    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(valid_terraform_config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_duplicate_resources()
    assert result.passed


def test_check_required_fields_pass(temp_iac_dir):
    """Test required fields check passes with all fields populated."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test_rg": {"name": "test-rg", "location": "eastus"}
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_required_fields()
    assert result.passed


def test_check_required_fields_fail_missing_name(temp_iac_dir):
    """Test required fields check fails when required field is missing."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test_rg": {
                    "location": "eastus"
                    # Missing "name" field
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_required_fields()
    assert not result.passed
    assert len(result.issues) == 1
    assert "name" in result.issues[0].message


def test_check_required_fields_fail_empty_value(temp_iac_dir):
    """Test required fields check fails when field is empty."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test_rg": {
                    "name": "",  # Empty string
                    "location": "eastus",
                }
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_required_fields()
    assert not result.passed


def test_check_valid_resource_references_pass(temp_iac_dir):
    """Test resource reference check passes with valid references."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test_rg": {"name": "test-rg", "location": "eastus"}
            },
            "azurerm_virtual_network": {
                "test_vnet": {
                    "name": "test-vnet",
                    "location": "eastus",
                    "depends_on": ["azurerm_resource_group.test_rg"],
                }
            },
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_valid_resource_references()
    assert result.passed or len(result.warnings) == 0  # Only warnings, not errors


def test_validate_all(temp_iac_dir, valid_terraform_config):
    """Test running all validations."""
    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(valid_terraform_config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    results = validator.validate_all()

    # Should return results for all checks
    assert len(results) == 7

    # All checks should pass for valid config
    check_names = [r.check_name for r in results]
    assert "No Placeholders" in check_names
    assert "Valid Tenant IDs" in check_names
    assert "Valid Subscription IDs" in check_names
    assert "Subnet CIDR Validation" in check_names
    assert "No Duplicate Resources" in check_names
    assert "Required Fields Populated" in check_names
    assert "Valid Resource References" in check_names


def test_validation_result_counts():
    """Test ValidationResult error/warning counts."""
    result = ValidationResult(
        check_name="Test Check",
        passed=False,
        issues=[
            ValidationIssue(
                check_name="Test Check", severity="error", message="Error 1"
            ),
            ValidationIssue(
                check_name="Test Check", severity="warning", message="Warning 1"
            ),
            ValidationIssue(
                check_name="Test Check", severity="error", message="Error 2"
            ),
        ],
    )

    assert result.error_count == 2
    assert result.warning_count == 1


def test_check_subnet_cidrs_invalid_vnet_cidr(temp_iac_dir):
    """Test subnet validation handles invalid VNet CIDR gracefully."""
    config = {
        "resource": {
            "azurerm_virtual_network": {
                "test_vnet": {"name": "test-vnet", "address_space": ["invalid-cidr"]}
            },
            "azurerm_subnet": {
                "test_subnet": {
                    "name": "test-subnet",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["10.0.1.0/24"],
                }
            },
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_subnet_cidrs()
    assert not result.passed
    assert any("Invalid VNet address space" in issue.message for issue in result.issues)


def test_check_subnet_cidrs_invalid_subnet_cidr(temp_iac_dir):
    """Test subnet validation detects invalid subnet CIDR."""
    config = {
        "resource": {
            "azurerm_virtual_network": {
                "test_vnet": {"name": "test-vnet", "address_space": ["10.0.0.0/16"]}
            },
            "azurerm_subnet": {
                "test_subnet": {
                    "name": "test-subnet",
                    "virtual_network_name": "${azurerm_virtual_network.test_vnet.name}",
                    "address_prefixes": ["not-a-cidr"],
                }
            },
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_subnet_cidrs()
    assert not result.passed
    assert any("Invalid subnet CIDR" in issue.message for issue in result.issues)


def test_multiple_placeholder_patterns(temp_iac_dir):
    """Test detection of various placeholder patterns."""
    config = {
        "resource": {
            "azurerm_resource_group": {
                "test1": {"name": "TODO", "location": "eastus"},
                "test2": {"name": "FIXME", "location": "eastus"},
                "test3": {"name": "CHANGEME", "location": "eastus"},
            }
        }
    }

    tf_file = temp_iac_dir / "main.tf.json"
    with open(tf_file, "w") as f:
        json.dump(config, f)

    validator = IaCValidator(temp_iac_dir)
    validator.load_terraform_files()

    result = validator.check_no_placeholders()
    assert not result.passed
    assert len(result.issues) >= 3  # Should catch TODO, FIXME, CHANGEME
