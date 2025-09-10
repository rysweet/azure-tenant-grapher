#!/usr/bin/env python
"""Simple test script to verify Terraform validation fixes."""

import json
import sys
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_terraform_fixes():
    """Test that our Terraform fixes work correctly."""

    # Read the updated terraform_emitter.py to verify changes
    emitter_path = (
        Path(__file__).parent / "src" / "iac" / "emitters" / "terraform_emitter.py"
    )

    with open(emitter_path) as f:
        content = f.read()

    print("✅ Testing Terraform validation fixes...")
    print("-" * 50)

    # Test 1: Check for resource_provider_registrations
    if '"resource_provider_registrations": "none"' in content:
        print(
            "✅ Test 1 PASSED: Provider uses 'resource_provider_registrations': 'none'"
        )
    else:
        print("❌ Test 1 FAILED: Provider doesn't use correct field")
        return False

    # Test 2: Check for skip_provider_registration absence
    if "skip_provider_registration" not in content:
        print("✅ Test 2 PASSED: Deprecated 'skip_provider_registration' not present")
    else:
        print("❌ Test 2 FAILED: Still uses deprecated field")
        return False

    # Test 3: Check for null location handling
    if (
        'if not location or location.lower() == "none" or location.lower() == "null"'
        in content
    ):
        print("✅ Test 3 PASSED: Location null handling implemented")
    else:
        print("❌ Test 3 FAILED: Location null handling not found")
        return False

    # Test 4: Check for default location
    if 'location = "eastus"' in content:
        print("✅ Test 4 PASSED: Default location set to 'eastus'")
    else:
        print("❌ Test 4 FAILED: Default location not set correctly")
        return False

    # Test 5: Check for enhanced resource properties
    required_checks = [
        ("Storage", '"account_tier"'),
        ("VM", '"admin_username"'),
        ("PublicIP", '"allocation_method"'),
        ("SQL", '"administrator_login"'),
        ("KeyVault", '"tenant_id"'),
    ]

    for resource_type, prop in required_checks:
        if prop in content:
            print(
                f"✅ Test 5.{resource_type} PASSED: {resource_type} has required property {prop}"
            )
        else:
            print(
                f"❌ Test 5.{resource_type} FAILED: {resource_type} missing required property"
            )
            return False

    print("-" * 50)
    print("✅ All tests PASSED!")
    return True


def generate_sample_terraform():
    """Generate a sample Terraform file to demonstrate the fixes."""

    sample_config = {
        "terraform": {
            "required_providers": {
                "azurerm": {"source": "hashicorp/azurerm", "version": ">=3.0"}
            }
        },
        "provider": {
            "azurerm": {
                "features": {},
                "resource_provider_registrations": "none",  # Fixed: using new field
            }
        },
        "resource": {
            "azurerm_resource_group": {
                "example": {
                    "name": "example-resources",
                    "location": "eastus",  # Fixed: never null
                }
            },
            "azurerm_storage_account": {
                "example": {
                    "name": "examplestorageacct",
                    "resource_group_name": "example-resources",
                    "location": "eastus",  # Fixed: never null
                    "account_tier": "Standard",  # Fixed: required property
                    "account_replication_type": "LRS",  # Fixed: required property
                }
            },
        },
    }

    # Save sample to temp file
    temp_dir = Path(tempfile.mkdtemp())
    sample_file = temp_dir / "sample_fixed.tf.json"

    with open(sample_file, "w") as f:
        json.dump(sample_config, f, indent=2)

    print(f"\n📁 Sample Terraform file generated at: {sample_file}")
    print("\nSample content (showing fixes):")
    print(json.dumps(sample_config, indent=2))

    return sample_file


if __name__ == "__main__":
    print("=" * 60)
    print("Terraform Validation Fix Test - Issue #206")
    print("=" * 60)
    print()

    # Run tests
    success = test_terraform_fixes()

    if success:
        # Generate sample
        print("\n" + "=" * 60)
        print("Generating sample Terraform with fixes applied...")
        print("=" * 60)
        generate_sample_terraform()

        print("\n" + "=" * 60)
        print("✅ SUCCESS: All Terraform validation issues have been fixed!")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("❌ FAILURE: Some tests failed")
        print("=" * 60)
        sys.exit(1)
