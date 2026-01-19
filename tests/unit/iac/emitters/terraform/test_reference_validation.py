"""Tests for Terraform reference validation (Issue #566).

Tests validation of resource references in generated Terraform configuration
to prevent errors from references to undeclared/unemitted resources.
"""

from src.iac.emitters.terraform.emitter import TerraformEmitter


class TestReferenceValidation:
    """Test reference validation in Terraform emission."""

    def test_valid_resource_group_reference(self):
        """Valid resource group reference should pass validation."""
        emitter = TerraformEmitter()

        # Emit resource group first
        rg_resource = {
            "type": "Microsoft.Resources/resourceGroups",
            "name": "test-rg",
            "location": "eastus",
            "resource_group": "test-rg",
        }

        # Emit storage account referencing the RG
        storage_resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "eastus",
            "resource_group": "test-rg",
        }

        config = emitter.emit([rg_resource, storage_resource])

        # Should have both resources
        assert "azurerm_resource_group" in config["resource"]
        assert "azurerm_storage_account" in config["resource"]

        # Should have no validation errors
        assert len(emitter.context.missing_references) == 0

    def test_invalid_resource_group_reference(self):
        """Invalid resource group reference should be caught."""
        emitter = TerraformEmitter()

        # Emit storage account referencing non-existent RG
        storage_resource = {
            "type": "Microsoft.Storage/storageAccounts",
            "name": "teststorage",
            "location": "eastus",
            "resource_group": "nonexistent-rg",  # This RG was never emitted
        }

        config = emitter.emit([storage_resource])

        # Storage account should be emitted
        assert "azurerm_storage_account" in config["resource"]

        # Should track missing reference
        assert len(emitter.context.missing_references) > 0
        missing_ref = emitter.context.missing_references[0]
        assert missing_ref["resource_type"] == "azurerm_resource_group"
        assert "nonexistent-rg" in str(missing_ref)

    def test_skipped_azure_managed_workspace_reference(self):
        """Simulate Issue #566: References to skipped Azure-managed resources."""
        emitter = TerraformEmitter()

        # Azure-managed workspace (will be skipped by handler logic)
        managed_workspace = {
            "type": "Microsoft.OperationalInsights/workspaces",
            "name": "managed-workspace-12345",  # Starts with "managed-"
            "location": "eastus",
            "resource_group": "managed-rg",
            "properties": '{"sku": {"name": "PerGB2018"}}',
        }

        # Log Analytics Solution referencing the managed workspace
        solution = {
            "type": "Microsoft.OperationsManagement/solutions",
            "name": "SecurityInsights(managed-workspace-12345)",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": """{
                "workspaceResourceId": "/subscriptions/xxx/resourceGroups/managed-rg/providers/Microsoft.OperationalInsights/workspaces/managed-workspace-12345"
            }""",
        }

        config = emitter.emit([managed_workspace, solution])

        # Managed workspace should be skipped (not emitted)
        workspaces = config["resource"].get("azurerm_log_analytics_workspace", {})
        assert "managed-workspace-12345" not in str(workspaces)

        # Solution should either:
        # 1. Be skipped due to invalid workspace reference, OR
        # 2. Be emitted with tracked missing reference
        solutions = config["resource"].get("azurerm_log_analytics_solution", {})
        if not solutions:
            # Solution was skipped - good
            assert len(solutions) == 0
        else:
            # Solution was emitted - must have tracked missing reference
            assert len(emitter.context.missing_references) > 0

    def test_validation_summary_report(self):
        """Validation should provide summary of all issues."""
        emitter = TerraformEmitter()

        # Multiple resources with invalid references
        resources = [
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage1",
                "location": "eastus",
                "resource_group": "missing-rg-1",
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "name": "storage2",
                "location": "eastus",
                "resource_group": "missing-rg-2",
            },
        ]

        config = emitter.emit(resources)

        # Should have both storage accounts
        assert len(config["resource"]["azurerm_storage_account"]) == 2

        # Should track both missing RG references
        assert len(emitter.context.missing_references) >= 2

    def test_workspace_reference_validation(self):
        """Test validation of workspace_resource_id references."""
        emitter = TerraformEmitter()

        # Create a valid workspace
        workspace = {
            "type": "Microsoft.OperationalInsights/workspaces",
            "name": "valid-workspace",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": '{"sku": {"name": "PerGB2018"}}',
        }

        # Create solution with valid workspace reference
        solution_valid = {
            "type": "Microsoft.OperationsManagement/solutions",
            "name": "SecurityInsights(valid-workspace)",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": """{
                "workspaceResourceId": "/subscriptions/xxx/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/valid-workspace"
            }""",
        }

        # Create solution with invalid workspace reference
        solution_invalid = {
            "type": "Microsoft.OperationsManagement/solutions",
            "name": "SecurityInsights(invalid-workspace)",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": """{
                "workspaceResourceId": "/subscriptions/xxx/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/invalid-workspace"
            }""",
        }

        config = emitter.emit([workspace, solution_valid, solution_invalid])

        # Valid solution should be emitted
        solutions = config["resource"].get("azurerm_log_analytics_solution", {})
        assert len(solutions) >= 1  # At least the valid one

        # Invalid workspace reference should be tracked if solution was emitted
        # OR solution should be skipped
        if len(solutions) > 1:
            # Both emitted - must track invalid reference
            assert len(emitter.context.missing_references) > 0
