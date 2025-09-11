"""Test Terraform validation fixes for Issue #206."""

import json
from pathlib import Path

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph


class TestTerraformValidation:
    """Test that Terraform generation produces valid configuration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.emitter = TerraformEmitter()
        self.test_output_dir = Path("/tmp/test_terraform_output")
        if self.test_output_dir.exists():
            import shutil

            shutil.rmtree(self.test_output_dir)

    def test_provider_uses_correct_field(self):
        """Test that provider uses 'resource_provider_registrations' instead of deprecated 'skip_provider_registration'."""
        # Create a simple graph
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "test-rg",
                "location": "eastus",
            }
        ]

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read and parse the generated template
        with open(output_files[0]) as f:
            template = json.load(f)

        # Verify provider configuration
        assert "provider" in template
        assert "azurerm" in template["provider"]
        provider_config = template["provider"]["azurerm"]

        # Check for correct field
        assert "resource_provider_registrations" in provider_config
        assert provider_config["resource_provider_registrations"] == "none"

        # Ensure deprecated field is not present
        assert "skip_provider_registration" not in provider_config

    def test_location_is_never_null(self):
        """Test that location is never null, defaulting to 'eastus' if missing."""
        test_cases = [
            # Resource with no location
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage-no-location",
            },
            # Resource with null location
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "vnet-null-location",
                "location": None,
            },
            # Resource with "null" string location
            {
                "type": "Microsoft.Network/publicIPAddresses",
                "name": "pip-null-string",
                "location": "null",
            },
            # Resource with "none" string location
            {
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "nsg-none-string",
                "location": "none",
            },
            # Resource with valid location
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-valid-location",
                "location": "westus2",
            },
        ]

        graph = TenantGraph()
        graph.resources = test_cases

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read and parse the generated template
        with open(output_files[0]) as f:
            template = json.load(f)

        # Check each resource
        assert "resource" in template

        # Storage account
        storage = template["resource"]["azurerm_storage_account"]["storage_no_location"]
        assert storage["location"] == "eastus"

        # Virtual network
        vnet = template["resource"]["azurerm_virtual_network"]["vnet_null_location"]
        assert vnet["location"] == "eastus"

        # Public IP
        pip = template["resource"]["azurerm_public_ip"]["pip_null_string"]
        assert pip["location"] == "eastus"

        # NSG
        nsg = template["resource"]["azurerm_network_security_group"]["nsg_none_string"]
        assert nsg["location"] == "eastus"

        # VM with valid location
        vm = template["resource"]["azurerm_linux_virtual_machine"]["vm_valid_location"]
        assert vm["location"] == "westus2"

    def test_resources_have_required_properties(self):
        """Test that all resources have their required properties."""
        resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "test-storage",
                "location": "eastus",
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test-vnet",
                "location": "eastus",
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "location": "eastus",
            },
            {
                "type": "Microsoft.Network/publicIPAddresses",
                "name": "test-pip",
                "location": "eastus",
            },
            {"type": "Microsoft.Web/sites", "name": "test-app", "location": "eastus"},
            {"type": "Microsoft.Sql/servers", "name": "test-sql", "location": "eastus"},
            {
                "type": "Microsoft.KeyVault/vaults",
                "name": "test-kv",
                "location": "eastus",
            },
        ]

        graph = TenantGraph()
        graph.resources = resources

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read and parse the generated template
        with open(output_files[0]) as f:
            template = json.load(f)

        # Verify Storage Account has required properties
        storage = template["resource"]["azurerm_storage_account"]["test_storage"]
        assert "name" in storage
        assert "location" in storage
        assert "resource_group_name" in storage
        assert "account_tier" in storage
        assert "account_replication_type" in storage

        # Verify Virtual Network has required properties
        vnet = template["resource"]["azurerm_virtual_network"]["test_vnet"]
        assert "name" in vnet
        assert "location" in vnet
        assert "resource_group_name" in vnet
        assert "address_space" in vnet
        assert isinstance(vnet["address_space"], list)

        # Verify VM has required properties
        vm = template["resource"]["azurerm_linux_virtual_machine"]["test_vm"]
        assert "name" in vm
        assert "location" in vm
        assert "resource_group_name" in vm
        assert "size" in vm
        assert "admin_username" in vm
        assert "admin_ssh_key" in vm  # SSH key instead of password
        assert "os_disk" in vm
        assert "source_image_reference" in vm

        # Verify SSH key is generated via TLS provider
        assert "tls_private_key" in template["resource"]
        assert "test_vm_ssh_key" in template["resource"]["tls_private_key"]
        ssh_key = template["resource"]["tls_private_key"]["test_vm_ssh_key"]
        assert ssh_key["algorithm"] == "RSA"
        assert ssh_key["rsa_bits"] == 4096

        # Verify Public IP has required properties
        pip = template["resource"]["azurerm_public_ip"]["test_pip"]
        assert "name" in pip
        assert "location" in pip
        assert "resource_group_name" in pip
        assert "allocation_method" in pip

        # Verify App Service has required properties
        app = template["resource"]["azurerm_app_service"]["test_app"]
        assert "name" in app
        assert "location" in app
        assert "resource_group_name" in app
        assert "app_service_plan_id" in app

        # Verify SQL Server has required properties
        sql = template["resource"]["azurerm_mssql_server"]["test_sql"]
        assert "name" in sql
        assert "location" in sql
        assert "resource_group_name" in sql
        assert "version" in sql
        assert "administrator_login" in sql
        assert "administrator_login_password" in sql

        # Verify password is generated via random_password resource, not hardcoded
        assert "random_password" in template["resource"]
        assert "test_sql_password" in template["resource"]["random_password"]
        password_resource = template["resource"]["random_password"]["test_sql_password"]
        assert password_resource["length"] == 20
        assert password_resource["special"]
        assert password_resource["min_lower"] == 1
        assert password_resource["min_upper"] == 1
        assert password_resource["min_numeric"] == 1
        assert password_resource["min_special"] == 1

        # Verify SQL Server references the random password
        assert (
            "${random_password.test_sql_password.result}"
            in sql["administrator_login_password"]
        )

        # Verify Key Vault has required properties
        kv = template["resource"]["azurerm_key_vault"]["test_kv"]
        assert "name" in kv
        assert "location" in kv
        assert "resource_group_name" in kv
        assert "tenant_id" in kv
        assert "sku_name" in kv

    def test_no_hardcoded_passwords(self):
        """Test that no hardcoded passwords are present in the generated Terraform."""
        resources = [
            {
                "type": "Microsoft.Sql/servers",
                "name": "test-sql-server",
                "location": "eastus",
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "test-vm",
                "location": "eastus",
            },
        ]

        graph = TenantGraph()
        graph.resources = resources

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read the generated template as text to check for hardcoded passwords
        with open(output_files[0]) as f:
            template_text = f.read()

        # Parse the JSON to check for actual password values
        template = json.loads(template_text)

        # Check for hardcoded passwords in resource configurations
        def check_for_hardcoded_passwords(obj, path=""):
            """Recursively check for hardcoded password values in the configuration."""
            if isinstance(obj, dict):
                for key, value in obj.items():
                    # Skip checking the keys themselves or Terraform references
                    if isinstance(value, str):
                        # Skip Terraform interpolations (they reference generated passwords)
                        if value.startswith("${") and value.endswith("}"):
                            continue
                        # Check if this is a password field with a hardcoded value
                        if (
                            "password" in key.lower()
                            or key == "administrator_login_password"
                        ):
                            # These are known bad passwords that should never be hardcoded
                            forbidden_passwords = [
                                "P@ssw0rd",
                                "Password123",
                                "Admin123",
                                "password123",
                                "admin",
                                "administrator",
                                "root",
                                "test",
                                "demo",
                            ]
                            for forbidden in forbidden_passwords:
                                assert forbidden.lower() not in value.lower(), (
                                    f"Found hardcoded password containing '{forbidden}' at {path}.{key}: {value}"
                                )
                    else:
                        check_for_hardcoded_passwords(value, f"{path}.{key}")
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    check_for_hardcoded_passwords(item, f"{path}[{i}]")

        check_for_hardcoded_passwords(template)

        # Verify proper password/key generation resources are used instead
        assert "random_password" in template["resource"], (
            "Should use random_password for SQL Server"
        )
        assert "tls_private_key" in template["resource"], (
            "Should use tls_private_key for VM SSH"
        )

    def test_terraform_template_structure(self):
        """Test that the generated Terraform template has the correct structure."""
        graph = TenantGraph()
        graph.resources = [
            {
                "type": "Microsoft.Resources/resourceGroups",
                "name": "test-rg",
                "location": "eastus",
            }
        ]

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read and parse the generated template
        with open(output_files[0]) as f:
            template = json.load(f)

        # Verify top-level structure
        assert "terraform" in template
        assert "provider" in template
        assert "resource" in template

        # Verify terraform block
        terraform_block = template["terraform"]
        assert "required_providers" in terraform_block
        assert "azurerm" in terraform_block["required_providers"]
        azurerm_provider = terraform_block["required_providers"]["azurerm"]
        assert azurerm_provider["source"] == "hashicorp/azurerm"
        assert azurerm_provider["version"] == ">=3.0"

        # Verify provider block
        provider_block = template["provider"]
        assert "azurerm" in provider_block
        assert "features" in provider_block["azurerm"]

    def test_resource_name_sanitization(self):
        """Test that resource names are properly sanitized for Terraform."""
        resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "test-storage-account",  # Contains hyphens
                "location": "eastus",
            },
            {
                "type": "Microsoft.Network/virtualNetworks",
                "name": "test.vnet.name",  # Contains dots
                "location": "eastus",
            },
            {
                "type": "Microsoft.Compute/virtualMachines",
                "name": "123-vm",  # Starts with number
                "location": "eastus",
            },
        ]

        graph = TenantGraph()
        graph.resources = resources

        # Generate the template
        output_files = self.emitter.emit(graph, self.test_output_dir)

        # Read and parse the generated template
        with open(output_files[0]) as f:
            template = json.load(f)

        # Check sanitized names
        storage_names = list(template["resource"]["azurerm_storage_account"].keys())
        assert "test_storage_account" in storage_names

        vnet_names = list(template["resource"]["azurerm_virtual_network"].keys())
        assert "test_vnet_name" in vnet_names

        vm_names = list(template["resource"]["azurerm_linux_virtual_machine"].keys())
        assert "resource_123_vm" in vm_names
