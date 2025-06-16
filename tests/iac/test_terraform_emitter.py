"""Tests for Terraform emitter functionality.

Tests the TerraformEmitter class for generating Terraform templates.
"""

import json
import tempfile
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformEmitter:
    """Test cases for TerraformEmitter class."""
    
    def test_emitter_initialization(self) -> None:
        """Test that TerraformEmitter initializes correctly."""
        emitter = TerraformEmitter()
        assert emitter.config == {}
    
    def test_emit_creates_terraform_file(self) -> None:
        """Test that emit creates main.tf.json file."""
        emitter = TerraformEmitter()
        
        # Create test graph with sample resources
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "teststorage",
                "location": "East US",
                "resourceGroup": "test-rg"
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "testvm",
                "location": "West US",
                "resourceGroup": "vm-rg",
                "tags": {"environment": "test"}
            }
        ]
        
        # Create temporary output directory
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            
            # Generate templates
            written_files = emitter.emit(graph, out_dir)
            
            # Verify file was created
            assert len(written_files) == 1
            assert written_files[0].name == "main.tf.json"
            assert written_files[0].exists()
            
            # Verify content structure
            with open(written_files[0]) as f:
                terraform_config = json.load(f)
            
            # Check required top-level keys
            assert "terraform" in terraform_config
            assert "provider" in terraform_config
            assert "resource" in terraform_config
            
            # Check terraform block
            assert "required_providers" in terraform_config["terraform"]
            assert "azurerm" in terraform_config["terraform"]["required_providers"]
            
            # Check provider block
            assert "azurerm" in terraform_config["provider"]
            assert "features" in terraform_config["provider"]["azurerm"]
            
            # Check resources were converted
            assert "azurerm_storage_account" in terraform_config["resource"]
            assert "azurerm_linux_virtual_machine" in terraform_config["resource"]
    
    def test_azure_to_terraform_mapping(self) -> None:
        """Test Azure resource type to Terraform mapping."""
        emitter = TerraformEmitter()
        
        # Test known mappings
        assert "Microsoft.Storage/storageAccounts" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Storage/storageAccounts"] == "azurerm_storage_account"
        
        assert "Microsoft.Compute/virtualMachines" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Compute/virtualMachines"] == "azurerm_linux_virtual_machine"
    
    def test_get_supported_resource_types(self) -> None:
        """Test getting supported resource types."""
        emitter = TerraformEmitter()
        supported_types = emitter.get_supported_resource_types()
        
        assert isinstance(supported_types, list)
        assert len(supported_types) > 0
        assert "Microsoft.Storage/storageAccounts" in supported_types
        assert "Microsoft.Compute/virtualMachines" in supported_types
    
    def test_validate_template_basic(self) -> None:
        """Test basic template validation."""
        emitter = TerraformEmitter()
        
        # Valid template
        valid_template = {
            "terraform": {"required_providers": {}},
            "provider": {"azurerm": {}},
            "resource": {}
        }
        assert emitter.validate_template(valid_template) is True
        
        # Invalid template (missing required keys)
        invalid_template = {
            "terraform": {"required_providers": {}},
            "provider": {"azurerm": {}}
            # Missing "resource" key
        }
        assert emitter.validate_template(invalid_template) is False
    
    def test_sanitize_terraform_name(self) -> None:
        """Test Terraform name sanitization."""
        emitter = TerraformEmitter()
        
        # Test various name formats
        assert emitter._sanitize_terraform_name("test-vm") == "test_vm"
        assert emitter._sanitize_terraform_name("test.storage") == "test_storage"
        assert emitter._sanitize_terraform_name("123invalid") == "resource_123invalid"
        assert emitter._sanitize_terraform_name("") == "unnamed_resource"
        assert emitter._sanitize_terraform_name("valid_name") == "valid_name"


class TestTerraformEmitterIntegration:
    """Integration tests for TerraformEmitter."""
    
    def test_emit_template_legacy_method(self) -> None:
        """Test the legacy emit_template method."""
        emitter = TerraformEmitter()
        
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage",
                "location": "East US"
            }
        ]
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test legacy method (async)
            import asyncio
            result = asyncio.run(emitter.emit_template(graph, temp_dir))
            
            assert "files_written" in result
            assert "resource_count" in result
            assert result["resource_count"] == 1
            assert len(result["files_written"]) == 1