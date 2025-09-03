"""Simple test script to verify Azure AD provider issue and fix."""

import sys
import os
import json
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.dirname(__file__))

# Import directly what we need
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


def test_current_behavior():
    """Test current behavior - should fail to include Azure AD provider."""
    print("Testing current behavior...")
    emitter = TerraformEmitter()
    
    # Check if Azure AD mappings exist
    print("\nChecking Azure AD resource mappings:")
    ad_types = ["Microsoft.AAD/User", "Microsoft.AAD/Group", "Microsoft.AAD/ServicePrincipal"]
    for ad_type in ad_types:
        if ad_type in emitter.AZURE_TO_TERRAFORM_MAPPING:
            print(f"  ✓ {ad_type} mapping exists")
        else:
            print(f"  ✗ {ad_type} mapping is MISSING")
    
    # Create test graph with Azure AD resources
    graph = TenantGraph()
    graph.resources = [
        {
            "type": "Microsoft.AAD/User",
            "name": "testuser",
            "userPrincipalName": "testuser@example.com",
        },
        {
            "type": "Microsoft.AAD/Group", 
            "name": "testgroup",
            "displayName": "Test Group",
        },
        {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "East US",
            "resourceGroup": "test-rg",
        },
    ]
    
    # Generate templates
    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = emitter.emit(graph, out_dir)
        
        # Read generated config
        with open(written_files[0]) as f:
            terraform_config = json.load(f)
        
        print("\nGenerated Terraform configuration:")
        print(json.dumps(terraform_config, indent=2))
        
        print("\nChecking providers:")
        providers = terraform_config.get("provider", {})
        if isinstance(providers, dict):
            print(f"  Provider is a dict with keys: {list(providers.keys())}")
        else:
            print(f"  Provider is a list with {len(providers)} items")
            for p in providers:
                print(f"    - {list(p.keys())}")
        
        # Check for Azure AD provider
        if isinstance(providers, dict):
            has_azuread = "azuread" in providers
        else:
            has_azuread = any("azuread" in p for p in providers)
        
        print(f"\n  Azure AD provider included: {'✓ YES' if has_azuread else '✗ NO'}")
        
        # Check required providers
        required_providers = terraform_config.get("terraform", {}).get("required_providers", {})
        print(f"\n  Required providers: {list(required_providers.keys())}")
        print(f"  Azure AD in required providers: {'✓ YES' if 'azuread' in required_providers else '✗ NO'}")


if __name__ == "__main__":
    test_current_behavior()