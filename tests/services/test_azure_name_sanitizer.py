"""Comprehensive tests for Azure Name Sanitizer Service (TDD approach).

These tests are written BEFORE implementation (TDD) and should FAIL until the
service is fully implemented. Tests follow the testing pyramid:
- 60% Unit tests (fast, heavily mocked)
- 30% Integration tests (multiple components)
- 10% E2E tests (complete workflows)

Philosophy:
    - Test behavior, not implementation
    - Focus on critical paths and edge cases
    - Each test has single, clear responsibility
    - Working tests only - no stubs

Testing Coverage:
    - All 10 CRITICAL resource types (Storage, ACR, Key Vault, SQL, PostgreSQL,
      MySQL, App Service, API Management, CDN, App Configuration)
    - Constraint enforcement (hyphen removal, length truncation, lowercase, character validation)
    - Edge cases (empty strings, max length, special characters)
    - Determinism (same input → same output)
    - Invalid resource types raise ValueError
"""

import pytest

from src.services.azure_name_sanitizer import AzureNameSanitizer, NamingConstraints

# =============================================================================
# UNIT TESTS (60% of test suite)
# =============================================================================


class TestStorageAccountSanitization:
    """Test Storage Account naming rules.

    Rules:
    - Max length: 24 chars
    - Lowercase alphanumeric ONLY (no hyphens)
    - DNS pattern: *.core.windows.net
    """

    def test_hyphen_removal(self):
        """Test that hyphens are removed from storage account names"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "storage-a1b2c3", "Microsoft.Storage/storageAccounts"
        )
        assert result == "storagea1b2c3"
        assert "-" not in result

    def test_lowercase_conversion(self):
        """Test that uppercase letters are converted to lowercase"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "StorageA1B2C3", "Microsoft.Storage/storageAccounts"
        )
        assert result == "storagea1b2c3"
        assert result.islower()

    def test_max_length_truncation(self):
        """Test that names longer than 24 chars are truncated"""
        sanitizer = AzureNameSanitizer()
        long_name = "storage-" + "a" * 50
        result = sanitizer.sanitize(long_name, "Microsoft.Storage/storageAccounts")
        assert len(result) <= 24

    def test_combined_hyphen_uppercase_removal(self):
        """Test combined transformation: uppercase + hyphens"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "Storage-Test-Name", "Microsoft.Storage/storageAccounts"
        )
        assert result == "storagetestname"
        assert "-" not in result
        assert result.islower()

    def test_multiple_consecutive_hyphens(self):
        """Test that consecutive hyphens are handled correctly"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "storage--test", "Microsoft.Storage/storageAccounts"
        )
        assert result == "storagetest"
        assert "--" not in result


class TestContainerRegistrySanitization:
    """Test Container Registry naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric ONLY (no hyphens, no special chars)
    - DNS pattern: *.azurecr.io
    """

    def test_hyphen_removal(self):
        """Test that hyphens are removed from ACR names"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "acr-x9y8z7", "Microsoft.ContainerRegistry/registries"
        )
        assert result == "acrx9y8z7"
        assert "-" not in result

    def test_alphanumeric_only(self):
        """Test that only alphanumeric characters are allowed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "acr_test-123", "Microsoft.ContainerRegistry/registries"
        )
        # Should remove both underscores and hyphens
        assert "_" not in result
        assert "-" not in result
        assert result.isalnum()

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "acr" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.ContainerRegistry/registries")
        assert len(result) <= 50

    def test_lowercase_conversion(self):
        """Test lowercase conversion for ACR"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "ACRTest123", "Microsoft.ContainerRegistry/registries"
        )
        assert result == "acrtest123"
        assert result.islower()


class TestKeyVaultSanitization:
    """Test Key Vault naming rules.

    Rules:
    - Max length: 24 chars
    - Alphanumeric + hyphens allowed
    - Must start with letter
    - Cannot end with hyphen
    - DNS pattern: *.vault.azure.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are PRESERVED in Key Vault names"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("vault-prod-east", "Microsoft.KeyVault/vaults")
        assert result == "vault-prod-east"
        assert "-" in result

    def test_must_start_with_letter(self):
        """Test that Key Vault names starting with number get letter prefix"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("1vault", "Microsoft.KeyVault/vaults")
        # Should add letter prefix or fail validation
        assert result[0].isalpha()

    def test_cannot_end_with_hyphen(self):
        """Test that trailing hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("vault-test-", "Microsoft.KeyVault/vaults")
        assert not result.endswith("-")

    def test_consecutive_hyphens_removed(self):
        """Test that consecutive hyphens are normalized"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("vault--prod", "Microsoft.KeyVault/vaults")
        assert "--" not in result

    def test_max_length_24(self):
        """Test max length of 24 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "vault-" + "a" * 30
        result = sanitizer.sanitize(long_name, "Microsoft.KeyVault/vaults")
        assert len(result) <= 24

    def test_lowercase_conversion(self):
        """Test lowercase conversion for Key Vault"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("Vault-Prod-East", "Microsoft.KeyVault/vaults")
        assert result == "vault-prod-east"
        assert result.islower() or "-" in result


class TestSQLServerSanitization:
    """Test SQL Server naming rules.

    Rules:
    - Max length: 63 chars
    - Lowercase alphanumeric + hyphens
    - Cannot start/end with hyphen
    - DNS pattern: *.database.windows.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved in SQL Server names"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("sql-server-01", "Microsoft.Sql/servers")
        assert result == "sql-server-01"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test that uppercase is converted to lowercase"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("SQL-Server-01", "Microsoft.Sql/servers")
        assert result == "sql-server-01"
        assert result.replace("-", "").islower()

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "sql-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Sql/servers")
        assert len(result) <= 63

    def test_cannot_start_with_hyphen(self):
        """Test that leading hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("-sql-server", "Microsoft.Sql/servers")
        assert not result.startswith("-")

    def test_cannot_end_with_hyphen(self):
        """Test that trailing hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("sql-server-", "Microsoft.Sql/servers")
        assert not result.endswith("-")


class TestPostgreSQLServerSanitization:
    """Test PostgreSQL Server naming rules.

    Rules:
    - Max length: 63 chars
    - Lowercase alphanumeric + hyphens
    - DNS pattern: *.postgres.database.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "postgres-a1b2c3d4", "Microsoft.DBforPostgreSQL/servers"
        )
        assert result == "postgres-a1b2c3d4"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "Postgres-A1B2C3D4", "Microsoft.DBforPostgreSQL/servers"
        )
        assert result == "postgres-a1b2c3d4"
        assert result.replace("-", "").islower()

    def test_max_length_63(self):
        """Test max length"""
        sanitizer = AzureNameSanitizer()
        long_name = "postgres-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.DBforPostgreSQL/servers")
        assert len(result) <= 63


class TestMySQLServerSanitization:
    """Test MySQL Server naming rules.

    Rules:
    - Max length: 63 chars
    - Lowercase alphanumeric + hyphens
    - DNS pattern: *.mysql.database.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("mysql-a1b2c3d4", "Microsoft.DBforMySQL/servers")
        assert result == "mysql-a1b2c3d4"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("MySQL-A1B2C3D4", "Microsoft.DBforMySQL/servers")
        assert result == "mysql-a1b2c3d4"
        assert result.replace("-", "").islower()

    def test_max_length_63(self):
        """Test max length"""
        sanitizer = AzureNameSanitizer()
        long_name = "mysql-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.DBforMySQL/servers")
        assert len(result) <= 63


class TestAppServiceSanitization:
    """Test App Service (Web Apps) naming rules.

    Rules:
    - Max length: 60 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azurewebsites.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("webapp-prod-east", "Microsoft.Web/sites")
        assert result == "webapp-prod-east"
        assert "-" in result

    def test_max_length_60(self):
        """Test max length of 60 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "webapp-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Web/sites")
        assert len(result) <= 60

    def test_alphanumeric_hyphen_allowed(self):
        """Test that alphanumeric and hyphens are allowed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("app-123-test", "Microsoft.Web/sites")
        assert result == "app-123-test"


class TestAPIManagementSanitization:
    """Test API Management naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azure-api.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("apim-prod", "Microsoft.ApiManagement/service")
        assert result == "apim-prod"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "apim-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.ApiManagement/service")
        assert len(result) <= 50


class TestCDNProfileSanitization:
    """Test CDN Profile naming rules.

    Rules:
    - Max length: 260 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azureedge.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("cdn-profile-prod", "Microsoft.Cdn/profiles")
        assert result == "cdn-profile-prod"
        assert "-" in result

    def test_max_length_260(self):
        """Test max length of 260 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "cdn-" + "a" * 300
        result = sanitizer.sanitize(long_name, "Microsoft.Cdn/profiles")
        assert len(result) <= 260


class TestAppConfigurationSanitization:
    """Test App Configuration naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azconfig.io
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "appconfig-prod", "Microsoft.AppConfiguration/configurationStores"
        )
        assert result == "appconfig-prod"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "appconfig-" + "a" * 60
        result = sanitizer.sanitize(
            long_name, "Microsoft.AppConfiguration/configurationStores"
        )
        assert len(result) <= 50


# =============================================================================
# EDGE CASES & ERROR HANDLING
# =============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_empty_name_raises_error(self):
        """Test that empty names raise ValueError"""
        sanitizer = AzureNameSanitizer()
        with pytest.raises(ValueError, match="[Nn]ame cannot be empty"):
            sanitizer.sanitize("", "Microsoft.Storage/storageAccounts")

    def test_whitespace_only_name_raises_error(self):
        """Test that whitespace-only names raise ValueError"""
        sanitizer = AzureNameSanitizer()
        with pytest.raises(ValueError, match="[Nn]ame cannot be empty"):
            sanitizer.sanitize("   ", "Microsoft.Storage/storageAccounts")

    def test_unknown_resource_type_raises_error(self):
        """Test that unknown resource types raise ValueError"""
        sanitizer = AzureNameSanitizer()
        with pytest.raises(ValueError, match="[Uu]nknown resource type"):
            sanitizer.sanitize("test", "Microsoft.Unknown/resource")

    def test_special_characters_removed(self):
        """Test that special characters are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "storage@test#123", "Microsoft.Storage/storageAccounts"
        )
        # Should remove @ and # symbols
        assert "@" not in result
        assert "#" not in result

    def test_single_character_name(self):
        """Test single character names are handled"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("a", "Microsoft.Storage/storageAccounts")
        assert len(result) == 1
        assert result == "a"

    def test_exact_max_length(self):
        """Test names at exact max length are preserved"""
        sanitizer = AzureNameSanitizer()
        # Storage max length is 24
        exact_name = "a" * 24
        result = sanitizer.sanitize(exact_name, "Microsoft.Storage/storageAccounts")
        assert len(result) == 24

    def test_unicode_characters_handled(self):
        """Test that unicode characters are handled gracefully"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("storage-café", "Microsoft.Storage/storageAccounts")
        # Should remove or convert non-ASCII characters
        assert result.isascii()


# =============================================================================
# DETERMINISM TESTS
# =============================================================================


class TestDeterminism:
    """Test that sanitizer produces deterministic results"""

    def test_same_input_same_output(self):
        """Test that same input always produces same output"""
        sanitizer = AzureNameSanitizer()
        input_name = "storage-test-123"
        resource_type = "Microsoft.Storage/storageAccounts"

        result1 = sanitizer.sanitize(input_name, resource_type)
        result2 = sanitizer.sanitize(input_name, resource_type)
        result3 = sanitizer.sanitize(input_name, resource_type)

        assert result1 == result2 == result3

    def test_multiple_instances_same_output(self):
        """Test that different sanitizer instances produce same output"""
        sanitizer1 = AzureNameSanitizer()
        sanitizer2 = AzureNameSanitizer()

        input_name = "vault-prod-east"
        resource_type = "Microsoft.KeyVault/vaults"

        result1 = sanitizer1.sanitize(input_name, resource_type)
        result2 = sanitizer2.sanitize(input_name, resource_type)

        assert result1 == result2


# =============================================================================
# PUBLIC API TESTS
# =============================================================================


class TestPublicAPI:
    """Test the public API methods"""

    def test_is_globally_unique_for_storage(self):
        """Test is_globally_unique returns True for Storage Accounts"""
        sanitizer = AzureNameSanitizer()
        assert sanitizer.is_globally_unique("Microsoft.Storage/storageAccounts") is True

    def test_is_globally_unique_for_key_vault(self):
        """Test is_globally_unique returns True for Key Vaults"""
        sanitizer = AzureNameSanitizer()
        assert sanitizer.is_globally_unique("Microsoft.KeyVault/vaults") is True

    def test_is_globally_unique_for_vm_returns_false(self):
        """Test is_globally_unique returns False for non-global resources"""
        sanitizer = AzureNameSanitizer()
        # Virtual Machines are NOT globally unique
        assert (
            sanitizer.is_globally_unique("Microsoft.Compute/virtualMachines") is False
        )

    def test_get_constraints_returns_valid_object(self):
        """Test get_constraints returns NamingConstraints object"""
        sanitizer = AzureNameSanitizer()
        constraints = sanitizer.get_constraints("Microsoft.Storage/storageAccounts")

        assert isinstance(constraints, NamingConstraints)
        assert constraints.max_length == 24
        assert constraints.allowed_chars == "lowercase_alphanum"
        assert constraints.dns_pattern == "*.core.windows.net"

    def test_get_constraints_for_key_vault(self):
        """Test get_constraints returns correct Key Vault constraints"""
        sanitizer = AzureNameSanitizer()
        constraints = sanitizer.get_constraints("Microsoft.KeyVault/vaults")

        assert isinstance(constraints, NamingConstraints)
        assert constraints.max_length == 24
        assert constraints.allowed_chars == "alphanum_hyphen"
        assert constraints.dns_pattern == "*.vault.azure.net"
        assert constraints.must_start_with == "letter"

    def test_get_constraints_unknown_type_raises_error(self):
        """Test get_constraints raises error for unknown resource type"""
        sanitizer = AzureNameSanitizer()
        with pytest.raises(ValueError, match="[Uu]nknown resource type"):
            sanitizer.get_constraints("Microsoft.Unknown/resource")


# =============================================================================
# INTEGRATION TESTS (30% of test suite)
# =============================================================================


class TestSanitizerIntegration:
    """Test sanitizer integration patterns with handlers"""

    def test_storage_with_tenant_suffix(self):
        """Test storage account name with tenant suffix pattern"""
        sanitizer = AzureNameSanitizer()

        # Simulate IDAbstractionService output
        abstracted_name = "storage-a1b2c3d4"

        # Sanitize for Azure constraints
        sanitized_name = sanitizer.sanitize(
            abstracted_name, "Microsoft.Storage/storageAccounts"
        )

        # Simulate adding tenant suffix
        tenant_suffix = "abc123"  # Last 6 chars of tenant ID
        final_name = f"{sanitized_name}{tenant_suffix}"

        # Verify final name meets constraints
        assert len(final_name) <= 24
        assert "-" not in final_name
        assert final_name.islower()

    def test_key_vault_with_tenant_suffix_hyphen(self):
        """Test Key Vault name with tenant suffix using hyphen"""
        sanitizer = AzureNameSanitizer()

        abstracted_name = "vault-prod"
        sanitized_name = sanitizer.sanitize(
            abstracted_name, "Microsoft.KeyVault/vaults"
        )

        # Key Vaults allow hyphens, so add suffix with hyphen
        tenant_suffix = "abc123"
        final_name = f"{sanitized_name}-{tenant_suffix}"

        assert len(final_name) <= 24
        assert final_name == "vault-prod-abc123"

    def test_multiple_resource_types_parallel_sanitization(self):
        """Test sanitizing multiple resource types in parallel"""
        sanitizer = AzureNameSanitizer()

        resources = [
            ("storage-test", "Microsoft.Storage/storageAccounts"),
            ("vault-test", "Microsoft.KeyVault/vaults"),
            ("acr-test", "Microsoft.ContainerRegistry/registries"),
        ]

        results = [sanitizer.sanitize(name, rtype) for name, rtype in resources]

        # Verify each result
        assert results[0] == "storagetest"  # No hyphens
        assert results[1] == "vault-test"  # Hyphens preserved
        assert results[2] == "acrtest"  # No hyphens

    def test_cross_tenant_uniqueness_scenario(self):
        """Test cross-tenant deployment scenario"""
        sanitizer = AzureNameSanitizer()

        # Source tenant resource
        source_name = "storage-prod"
        source_tenant_id = "12345678-1234-1234-1234-123456789abc"

        # Target tenant needs unique name
        target_tenant_id = "87654321-4321-4321-4321-cba987654321"

        # Sanitize base name
        sanitized = sanitizer.sanitize(source_name, "Microsoft.Storage/storageAccounts")

        # Add suffix for cross-tenant uniqueness
        if source_tenant_id != target_tenant_id:
            tenant_suffix = target_tenant_id[-6:].replace("-", "").lower()
            final_name = f"{sanitized}{tenant_suffix}"
        else:
            final_name = sanitized

        assert len(final_name) <= 24
        assert final_name == "storageprod654321"


class TestConstraintValidation:
    """Test constraint validation across multiple resource types"""

    def test_all_critical_resources_have_constraints(self):
        """Test that all 10 CRITICAL resource types have defined constraints"""
        sanitizer = AzureNameSanitizer()

        critical_types = [
            "Microsoft.Storage/storageAccounts",
            "Microsoft.KeyVault/vaults",
            "Microsoft.Web/sites",
            "Microsoft.Sql/servers",
            "Microsoft.ContainerRegistry/registries",
            "Microsoft.DBforPostgreSQL/servers",
            "Microsoft.DBforMySQL/servers",
            "Microsoft.ApiManagement/service",
            "Microsoft.Cdn/profiles",
            "Microsoft.AppConfiguration/configurationStores",
        ]

        for resource_type in critical_types:
            # Should not raise error
            constraints = sanitizer.get_constraints(resource_type)
            assert isinstance(constraints, NamingConstraints)
            assert constraints.max_length > 0
            assert constraints.allowed_chars is not None
            assert constraints.dns_pattern is not None


# =============================================================================
# E2E TESTS (10% of test suite)
# =============================================================================


class TestEndToEnd:
    """Test complete end-to-end workflows"""

    def test_full_discovery_to_iac_workflow(self):
        """Test full workflow: discovery → abstraction → sanitization → IaC"""
        sanitizer = AzureNameSanitizer()

        # Simulate discovery phase - original Azure name would be "my-storage-account-prod"

        # Simulate ID abstraction phase - generic abstracted name
        # (In reality, this would come from IDAbstractionService)
        abstracted_name = "storage-a1b2c3d4"

        # Sanitization phase - apply Azure constraints
        sanitized_name = sanitizer.sanitize(
            abstracted_name, "Microsoft.Storage/storageAccounts"
        )

        # Verify sanitized name meets all constraints
        assert len(sanitized_name) <= 24
        assert "-" not in sanitized_name
        assert sanitized_name.islower()
        assert sanitized_name == "storagea1b2c3d4"

        # This name is now ready for Terraform config generation
        terraform_config = {
            "name": sanitized_name,
            "resource_group_name": "rg-test",
            "location": "eastus",
        }

        assert terraform_config["name"] == "storagea1b2c3d4"

    def test_multi_resource_iac_generation(self):
        """Test IaC generation for multiple resource types"""
        sanitizer = AzureNameSanitizer()

        # Simulate multiple discovered resources
        resources = [
            {
                "original_name": "my-storage",
                "abstracted_name": "storage-a1b2",
                "resource_type": "Microsoft.Storage/storageAccounts",
            },
            {
                "original_name": "my-vault",
                "abstracted_name": "vault-b3c4",
                "resource_type": "Microsoft.KeyVault/vaults",
            },
            {
                "original_name": "my-acr",
                "abstracted_name": "acr-d5e6",
                "resource_type": "Microsoft.ContainerRegistry/registries",
            },
        ]

        # Sanitize all names
        terraform_configs = []
        for resource in resources:
            sanitized = sanitizer.sanitize(
                resource["abstracted_name"], resource["resource_type"]
            )
            terraform_configs.append(
                {
                    "resource_type": resource["resource_type"],
                    "name": sanitized,
                }
            )

        # Verify all configs have valid names
        assert terraform_configs[0]["name"] == "storagea1b2"
        assert terraform_configs[1]["name"] == "vault-b3c4"
        assert terraform_configs[2]["name"] == "acrd5e6"

    def test_real_world_storage_account_scenario(self):
        """Test real-world storage account naming scenario"""
        sanitizer = AzureNameSanitizer()

        # Real-world scenario: complicated name with various issues
        problematic_name = "Storage-Account-For-PROD-Environment-2024"

        # Sanitize
        result = sanitizer.sanitize(
            problematic_name, "Microsoft.Storage/storageAccounts"
        )

        # Verify all constraints met
        assert len(result) <= 24
        assert "-" not in result
        assert result.islower()
        assert result.isalnum()
        assert result == "storageaccountforprodenv"  # Truncated to 24 chars

    def test_real_world_key_vault_scenario(self):
        """Test real-world Key Vault naming scenario"""
        sanitizer = AzureNameSanitizer()

        # Real-world scenario: Key Vault with region and environment
        vault_name = "KV-PROD-EASTUS-2024"

        # Sanitize
        result = sanitizer.sanitize(vault_name, "Microsoft.KeyVault/vaults")

        # Verify constraints met
        assert len(result) <= 24
        assert result[0].isalpha()  # Must start with letter
        assert not result.endswith("-")
        assert result.lower() == result  # Lowercase


# =============================================================================
# PHASE 2 TESTS: NEW RESOURCE TYPES (24 types)
# =============================================================================


# =========================================
# Integration/Messaging (4 types)
# =========================================


class TestServiceBusSanitization:
    """Test Service Bus Namespace naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.servicebus.windows.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("sb-prod-east", "Microsoft.ServiceBus/namespaces")
        assert result == "sb-prod-east"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "sb-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.ServiceBus/namespaces")
        assert len(result) <= 50

    def test_alphanumeric_hyphen_allowed(self):
        """Test that alphanumeric and hyphens are allowed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("sb-123-test", "Microsoft.ServiceBus/namespaces")
        assert result == "sb-123-test"


class TestEventHubSanitization:
    """Test Event Hub Namespace naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.servicebus.windows.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("eh-prod-east", "Microsoft.EventHub/namespaces")
        assert result == "eh-prod-east"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "eh-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.EventHub/namespaces")
        assert len(result) <= 50

    def test_uppercase_conversion(self):
        """Test uppercase conversion"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("EH-Prod-123", "Microsoft.EventHub/namespaces")
        # alphanum_hyphen allows uppercase, but sanitizer should handle consistently
        assert (
            result.replace("-", "")
            .replace("123", "")
            .replace("prod", "")
            .replace("eh", "")
            == ""
        )


class TestEventGridSanitization:
    """Test Event Grid Domain naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.eventgrid.azure.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("eg-domain-prod", "Microsoft.EventGrid/domains")
        assert result == "eg-domain-prod"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "eg-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.EventGrid/domains")
        assert len(result) <= 50


class TestSignalRSanitization:
    """Test SignalR Service naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.service.signalr.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "signalr-prod-east", "Microsoft.SignalRService/signalR"
        )
        assert result == "signalr-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "signalr-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.SignalRService/signalR")
        assert len(result) <= 63


# =========================================
# API/Networking (2 types)
# =========================================


class TestFrontDoorSanitization:
    """Test Azure Front Door naming rules.

    Rules:
    - Max length: 64 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azurefd.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("frontdoor-prod", "Microsoft.Network/frontDoors")
        assert result == "frontdoor-prod"
        assert "-" in result

    def test_max_length_64(self):
        """Test max length of 64 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "fd-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Network/frontDoors")
        assert len(result) <= 64


class TestTrafficManagerSanitization:
    """Test Traffic Manager Profile naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.trafficmanager.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "tm-prod-east", "Microsoft.Network/trafficManagerProfiles"
        )
        assert result == "tm-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "tm-" + "a" * 70
        result = sanitizer.sanitize(
            long_name, "Microsoft.Network/trafficManagerProfiles"
        )
        assert len(result) <= 63


# =========================================
# Data/Analytics (10 types)
# =========================================


class TestMariaDBServerSanitization:
    """Test MariaDB Server naming rules.

    Rules:
    - Max length: 63 chars
    - Lowercase alphanumeric + hyphens
    - DNS pattern: *.mariadb.database.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "mariadb-a1b2c3d4", "Microsoft.DBforMariaDB/servers"
        )
        assert result == "mariadb-a1b2c3d4"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "MariaDB-A1B2C3D4", "Microsoft.DBforMariaDB/servers"
        )
        assert result == "mariadb-a1b2c3d4"
        assert result.replace("-", "").islower()

    def test_max_length_63(self):
        """Test max length"""
        sanitizer = AzureNameSanitizer()
        long_name = "mariadb-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.DBforMariaDB/servers")
        assert len(result) <= 63


class TestCosmosDBSanitization:
    """Test Cosmos DB Account naming rules.

    Rules:
    - Max length: 44 chars
    - Lowercase alphanumeric + hyphens
    - DNS pattern: *.documents.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "cosmos-prod", "Microsoft.DocumentDB/databaseAccounts"
        )
        assert result == "cosmos-prod"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "Cosmos-PROD-123", "Microsoft.DocumentDB/databaseAccounts"
        )
        assert result == "cosmos-prod-123"
        assert result.replace("-", "").islower()

    def test_max_length_44(self):
        """Test max length of 44 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "cosmos-" + "a" * 50
        result = sanitizer.sanitize(long_name, "Microsoft.DocumentDB/databaseAccounts")
        assert len(result) <= 44


class TestRedisCacheSanitization:
    """Test Redis Cache naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.redis.cache.windows.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("redis-prod-east", "Microsoft.Cache/redis")
        assert result == "redis-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "redis-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Cache/redis")
        assert len(result) <= 63


class TestSearchServiceSanitization:
    """Test Azure Search Service naming rules.

    Rules:
    - Max length: 60 chars
    - Lowercase alphanumeric + hyphens
    - DNS pattern: *.search.windows.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("search-prod", "Microsoft.Search/searchServices")
        assert result == "search-prod"
        assert "-" in result

    def test_lowercase_enforced(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "Search-PROD-123", "Microsoft.Search/searchServices"
        )
        assert result == "search-prod-123"
        assert result.replace("-", "").islower()

    def test_max_length_60(self):
        """Test max length of 60 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "search-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Search/searchServices")
        assert len(result) <= 60


class TestDataFactorySanitization:
    """Test Data Factory naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.datafactory.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("adf-prod-east", "Microsoft.DataFactory/factories")
        assert result == "adf-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "adf-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.DataFactory/factories")
        assert len(result) <= 63


class TestSynapseWorkspaceSanitization:
    """Test Synapse Workspace naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.sql.azuresynapse.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("synapse-prod", "Microsoft.Synapse/workspaces")
        assert result == "synapse-prod"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "synapse-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.Synapse/workspaces")
        assert len(result) <= 50


class TestDatabricksWorkspaceSanitization:
    """Test Databricks Workspace naming rules.

    Rules:
    - Max length: 64 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azuredatabricks.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "databricks-prod", "Microsoft.Databricks/workspaces"
        )
        assert result == "databricks-prod"
        assert "-" in result

    def test_max_length_64(self):
        """Test max length of 64 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "databricks-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.Databricks/workspaces")
        assert len(result) <= 64


class TestHDInsightClusterSanitization:
    """Test HDInsight Cluster naming rules.

    Rules:
    - Max length: 59 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azurehdinsight.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("hdinsight-prod", "Microsoft.HDInsight/clusters")
        assert result == "hdinsight-prod"
        assert "-" in result

    def test_max_length_59(self):
        """Test max length of 59 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "hdinsight-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.HDInsight/clusters")
        assert len(result) <= 59


class TestDataLakeStoreSanitization:
    """Test Data Lake Store naming rules.

    Rules:
    - Max length: 24 chars
    - Lowercase alphanumeric ONLY (no hyphens)
    - DNS pattern: *.azuredatalakestore.net
    """

    def test_hyphen_removal(self):
        """Test that hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("dls-a1b2c3", "Microsoft.DataLakeStore/accounts")
        assert result == "dlsa1b2c3"
        assert "-" not in result

    def test_lowercase_conversion(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("DLS-A1B2C3", "Microsoft.DataLakeStore/accounts")
        assert result == "dlsa1b2c3"
        assert result.islower()

    def test_max_length_24(self):
        """Test max length of 24 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "datalake-" + "a" * 30
        result = sanitizer.sanitize(long_name, "Microsoft.DataLakeStore/accounts")
        assert len(result) <= 24


class TestDataLakeAnalyticsSanitization:
    """Test Data Lake Analytics naming rules.

    Rules:
    - Max length: 24 chars
    - Lowercase alphanumeric ONLY (no hyphens)
    - DNS pattern: *.azuredatalakeanalytics.net
    """

    def test_hyphen_removal(self):
        """Test that hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "dla-a1b2c3", "Microsoft.DataLakeAnalytics/accounts"
        )
        assert result == "dlaa1b2c3"
        assert "-" not in result

    def test_lowercase_conversion(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "DLA-A1B2C3", "Microsoft.DataLakeAnalytics/accounts"
        )
        assert result == "dlaa1b2c3"
        assert result.islower()

    def test_max_length_24(self):
        """Test max length of 24 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "analytics-" + "a" * 30
        result = sanitizer.sanitize(long_name, "Microsoft.DataLakeAnalytics/accounts")
        assert len(result) <= 24


# =========================================
# AI/ML/IoT (4 types)
# =========================================


class TestCognitiveServicesSanitization:
    """Test Cognitive Services naming rules.

    Rules:
    - Max length: 64 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.cognitiveservices.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "cog-prod-east", "Microsoft.CognitiveServices/accounts"
        )
        assert result == "cog-prod-east"
        assert "-" in result

    def test_max_length_64(self):
        """Test max length of 64 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "cognitive-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.CognitiveServices/accounts")
        assert len(result) <= 64


class TestMLWorkspaceSanitization:
    """Test ML Workspace naming rules.

    Rules:
    - Max length: 33 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.api.azureml.ms
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "ml-prod-east", "Microsoft.MachineLearningServices/workspaces"
        )
        assert result == "ml-prod-east"
        assert "-" in result

    def test_max_length_33(self):
        """Test max length of 33 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "ml-workspace-" + "a" * 40
        result = sanitizer.sanitize(
            long_name, "Microsoft.MachineLearningServices/workspaces"
        )
        assert len(result) <= 33


class TestIoTHubSanitization:
    """Test IoT Hub naming rules.

    Rules:
    - Max length: 50 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azure-devices.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("iot-prod-east", "Microsoft.Devices/IotHubs")
        assert result == "iot-prod-east"
        assert "-" in result

    def test_max_length_50(self):
        """Test max length of 50 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "iot-" + "a" * 60
        result = sanitizer.sanitize(long_name, "Microsoft.Devices/IotHubs")
        assert len(result) <= 50


class TestIoTCentralSanitization:
    """Test IoT Central naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azureiotcentral.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("iotc-prod-east", "Microsoft.IoTCentral/IoTApps")
        assert result == "iotc-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "iotc-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.IoTCentral/IoTApps")
        assert len(result) <= 63


# =========================================
# Specialized (6 types)
# =========================================


class TestBotServiceSanitization:
    """Test Bot Service naming rules.

    Rules:
    - Max length: 64 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.botframework.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("bot-prod-east", "Microsoft.BotService/botServices")
        assert result == "bot-prod-east"
        assert "-" in result

    def test_max_length_64(self):
        """Test max length of 64 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "bot-" + "a" * 70
        result = sanitizer.sanitize(long_name, "Microsoft.BotService/botServices")
        assert len(result) <= 64


class TestCommunicationServiceSanitization:
    """Test Communication Service naming rules.

    Rules:
    - Max length: 63 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.communication.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize(
            "comm-prod-east", "Microsoft.Communication/communicationServices"
        )
        assert result == "comm-prod-east"
        assert "-" in result

    def test_max_length_63(self):
        """Test max length of 63 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "comm-" + "a" * 70
        result = sanitizer.sanitize(
            long_name, "Microsoft.Communication/communicationServices"
        )
        assert len(result) <= 63


class TestSpringCloudSanitization:
    """Test Spring Cloud naming rules.

    Rules:
    - Max length: 32 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azuremicroservices.io
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("spring-prod", "Microsoft.AppPlatform/Spring")
        assert result == "spring-prod"
        assert "-" in result

    def test_max_length_32(self):
        """Test max length of 32 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "spring-" + "a" * 40
        result = sanitizer.sanitize(long_name, "Microsoft.AppPlatform/Spring")
        assert len(result) <= 32


class TestStaticWebAppSanitization:
    """Test Static Web App naming rules.

    Rules:
    - Max length: 40 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.azurestaticapps.net
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("static-prod", "Microsoft.Web/staticSites")
        assert result == "static-prod"
        assert "-" in result

    def test_max_length_40(self):
        """Test max length of 40 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "static-" + "a" * 50
        result = sanitizer.sanitize(long_name, "Microsoft.Web/staticSites")
        assert len(result) <= 40


class TestKustoClusterSanitization:
    """Test Kusto Cluster naming rules.

    Rules:
    - Max length: 22 chars
    - Lowercase alphanumeric ONLY (no hyphens)
    - DNS pattern: *.kusto.windows.net
    """

    def test_hyphen_removal(self):
        """Test that hyphens are removed"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("kusto-a1b2", "Microsoft.Kusto/clusters")
        assert result == "kustoa1b2"
        assert "-" not in result

    def test_lowercase_conversion(self):
        """Test lowercase enforcement"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("KUSTO-A1B2", "Microsoft.Kusto/clusters")
        assert result == "kustoa1b2"
        assert result.islower()

    def test_max_length_22(self):
        """Test max length of 22 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "kusto-" + "a" * 30
        result = sanitizer.sanitize(long_name, "Microsoft.Kusto/clusters")
        assert len(result) <= 22


class TestGrafanaSanitization:
    """Test Grafana naming rules.

    Rules:
    - Max length: 23 chars
    - Alphanumeric + hyphens
    - DNS pattern: *.grafana.azure.com
    """

    def test_hyphens_preserved(self):
        """Test that hyphens are preserved"""
        sanitizer = AzureNameSanitizer()
        result = sanitizer.sanitize("grafana-prod", "Microsoft.Dashboard/grafana")
        assert result == "grafana-prod"
        assert "-" in result

    def test_max_length_23(self):
        """Test max length of 23 characters"""
        sanitizer = AzureNameSanitizer()
        long_name = "grafana-" + "a" * 30
        result = sanitizer.sanitize(long_name, "Microsoft.Dashboard/grafana")
        assert len(result) <= 23
