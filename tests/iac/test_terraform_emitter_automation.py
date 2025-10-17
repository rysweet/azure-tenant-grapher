"""Tests for Azure Automation resource type mappings in TerraformEmitter.

This module tests the Azure Automation resource types:
- Microsoft.Automation/automationAccounts (Automation Accounts)
- Microsoft.Automation/automationAccounts/runbooks (Automation Runbooks)
"""

import json
import pytest
from src.iac.emitters.terraform_emitter import TerraformEmitter


class TestAutomationResourceMappings:
    """Test Azure Automation resource type mappings."""

    def test_automation_account_mapping(self):
        """Test Microsoft.Automation/automationAccounts mapping."""
        emitter = TerraformEmitter()
        assert "Microsoft.Automation/automationAccounts" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Automation/automationAccounts"]
            == "azurerm_automation_account"
        )

    def test_automation_runbook_mapping(self):
        """Test Microsoft.Automation/automationAccounts/runbooks mapping."""
        emitter = TerraformEmitter()
        assert (
            "Microsoft.Automation/automationAccounts/runbooks"
            in emitter.AZURE_TO_TERRAFORM_MAPPING
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING[
                "Microsoft.Automation/automationAccounts/runbooks"
            ]
            == "azurerm_automation_runbook"
        )


class TestAutomationAccountConversion:
    """Test Automation Account conversion."""

    def test_basic_automation_account(self):
        """Test converting a basic Automation Account."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account",
            "name": "test-account",
            "type": "Microsoft.Automation/automationAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "sku": {
                    "name": "Basic",
                    "capacity": None,
                    "family": None,
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_automation_account"
        assert safe_name == "test_account"
        assert config["name"] == "test-account"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["sku_name"] == "Basic"

    def test_automation_account_free_tier(self):
        """Test converting an Automation Account with Free tier."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/free-account",
            "name": "free-account",
            "type": "Microsoft.Automation/automationAccounts",
            "location": "westus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "sku": {
                    "name": "Free",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_automation_account"
        assert config["sku_name"] == "Free"

    def test_automation_account_with_tags(self):
        """Test converting an Automation Account with tags."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/tagged-account",
            "name": "tagged-account",
            "type": "Microsoft.Automation/automationAccounts",
            "location": "eastus",
            "resource_group": "test-rg",
            "tags": json.dumps({
                "Environment": "Production",
                "Team": "DevOps",
            }),
            "properties": json.dumps({
                "sku": {
                    "name": "Basic",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert "tags" in config
        assert config["tags"]["Environment"] == "Production"
        assert config["tags"]["Team"] == "DevOps"


class TestAutomationRunbookConversion:
    """Test Automation Runbook conversion."""

    def test_runbook_with_content_link(self):
        """Test converting a runbook with publish content link."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/test-runbook",
            "name": "test-account/test-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "PowerShell",
                "logProgress": True,
                "logVerbose": False,
                "publishContentLink": {
                    "uri": "https://example.com/runbook.ps1",
                    "version": "1.0.0.0",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_automation_runbook"
        assert safe_name == "test_account_test_runbook"
        assert config["name"] == "test-runbook"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["automation_account_name"] == "test-account"
        assert config["runbook_type"] == "PowerShell"
        assert config["log_progress"] is True
        assert config["log_verbose"] is False
        assert "publish_content_link" in config
        assert config["publish_content_link"]["uri"] == "https://example.com/runbook.ps1"
        assert config["publish_content_link"]["version"] == "1.0.0.0"

    def test_runbook_without_content_link(self):
        """Test converting a runbook without publish content link (uses placeholder content)."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/empty-runbook",
            "name": "test-account/empty-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "PowerShell",
                "logProgress": False,
                "logVerbose": False,
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_automation_runbook"
        assert config["name"] == "empty-runbook"
        assert config["automation_account_name"] == "test-account"
        assert "content" in config
        assert "Placeholder runbook content" in config["content"]
        assert "publish_content_link" not in config

    def test_runbook_python_type(self):
        """Test converting a Python runbook."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/python-runbook",
            "name": "test-account/python-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "westus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "Python3",
                "logProgress": True,
                "logVerbose": True,
                "publishContentLink": {
                    "uri": "https://example.com/runbook.py",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["runbook_type"] == "Python3"
        assert config["log_progress"] is True
        assert config["log_verbose"] is True

    def test_runbook_graph_type(self):
        """Test converting a Graph runbook."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/graph-runbook",
            "name": "test-account/graph-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus2",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "GraphPowerShell",
                "logProgress": False,
                "logVerbose": False,
                "publishContentLink": {
                    "uri": "https://example.com/graph-runbook.json",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["runbook_type"] == "GraphPowerShell"

    def test_runbook_workflow_type(self):
        """Test converting a PowerShell Workflow runbook."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/workflow-runbook",
            "name": "test-account/workflow-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "centralus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "PowerShellWorkflow",
                "logProgress": True,
                "logVerbose": False,
                "publishContentLink": {
                    "uri": "https://example.com/workflow.ps1",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["runbook_type"] == "PowerShellWorkflow"

    def test_runbook_name_sanitization(self):
        """Test that runbook names with special characters are sanitized."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/my-account/runbooks/My-Runbook-2024",
            "name": "my-account/My-Runbook-2024",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({
                "runbookType": "PowerShell",
                "logProgress": False,
                "logVerbose": False,
                "publishContentLink": {
                    "uri": "https://example.com/runbook.ps1",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        # Terraform resource name should be sanitized (no hyphens)
        assert safe_name == "my_account_My_Runbook_2024"
        # But the actual resource name should be preserved
        assert config["name"] == "My-Runbook-2024"
        assert config["automation_account_name"] == "my-account"

    def test_runbook_with_tags(self):
        """Test converting a runbook with tags."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/tagged-runbook",
            "name": "test-account/tagged-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "tags": json.dumps({
                "Purpose": "Backup",
                "Schedule": "Daily",
            }),
            "properties": json.dumps({
                "runbookType": "PowerShell",
                "logProgress": False,
                "logVerbose": False,
                "publishContentLink": {
                    "uri": "https://example.com/backup.ps1",
                },
            }),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert "tags" in config
        assert config["tags"]["Purpose"] == "Backup"
        assert config["tags"]["Schedule"] == "Daily"


class TestAutomationRunbookDefaults:
    """Test Automation Runbook default values."""

    def test_runbook_default_runbook_type(self):
        """Test that runbook defaults to PowerShell type if not specified."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/default-runbook",
            "name": "test-account/default-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({}),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["runbook_type"] == "PowerShell"

    def test_runbook_default_log_progress(self):
        """Test that runbook defaults log_progress to True if not specified."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/default-runbook",
            "name": "test-account/default-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({}),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["log_progress"] is True

    def test_runbook_default_log_verbose(self):
        """Test that runbook defaults log_verbose to False if not specified."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Automation/automationAccounts/test-account/runbooks/default-runbook",
            "name": "test-account/default-runbook",
            "type": "Microsoft.Automation/automationAccounts/runbooks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps({}),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["log_verbose"] is False
