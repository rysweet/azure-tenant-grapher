"""Tests for newly added resource type mappings in TerraformEmitter.

This module tests the 5 new resource types added to increase fidelity:
- Microsoft.Web/serverFarms (App Service Plans)
- Microsoft.Compute/disks (Managed Disks)
- Microsoft.Compute/virtualMachines/extensions (VM Extensions)
- Microsoft.OperationalInsights/workspaces (Log Analytics)
- microsoft.insights/components (Application Insights)
"""

import json

from src.iac.emitters.terraform_emitter import TerraformEmitter


class TestNewResourceTypeMappings:
    """Test new resource type mappings."""

    def test_service_plan_mapping(self):
        """Test Microsoft.Web/serverFarms mapping."""
        emitter = TerraformEmitter()
        assert "Microsoft.Web/serverFarms" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Web/serverFarms"]
            == "azurerm_service_plan"
        )

    def test_managed_disk_mapping(self):
        """Test Microsoft.Compute/disks mapping."""
        emitter = TerraformEmitter()
        assert "Microsoft.Compute/disks" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Compute/disks"]
            == "azurerm_managed_disk"
        )

    def test_vm_extension_mapping(self):
        """Test Microsoft.Compute/virtualMachines/extensions mapping."""
        emitter = TerraformEmitter()
        assert (
            "Microsoft.Compute/virtualMachines/extensions"
            in emitter.AZURE_TO_TERRAFORM_MAPPING
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING[
                "Microsoft.Compute/virtualMachines/extensions"
            ]
            == "azurerm_virtual_machine_extension"
        )

    def test_log_analytics_mapping(self):
        """Test Microsoft.OperationalInsights/workspaces mapping."""
        emitter = TerraformEmitter()
        assert (
            "Microsoft.OperationalInsights/workspaces"
            in emitter.AZURE_TO_TERRAFORM_MAPPING
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING[
                "Microsoft.OperationalInsights/workspaces"
            ]
            == "azurerm_log_analytics_workspace"
        )

    def test_application_insights_mapping(self):
        """Test Microsoft.Insights/components mapping with case normalization."""
        emitter = TerraformEmitter()
        # Test proper-case variant is in mapping
        assert "Microsoft.Insights/components" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Insights/components"]
            == "azurerm_application_insights"
        )
        # Test that lowercase variant is normalized to proper-case via _normalize_azure_type
        normalized = emitter._normalize_azure_type("microsoft.insights/components")
        assert normalized == "Microsoft.Insights/components"
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING.get(normalized)
            == "azurerm_application_insights"
        )


class TestServicePlanConversion:
    """Test App Service Plan (serverFarms) conversion."""

    def test_linux_service_plan(self):
        """Test converting a Linux App Service Plan."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Web/serverFarms/test-plan",
            "name": "test-plan",
            "type": "Microsoft.Web/serverFarms",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "kind": "linux",
                    "sku": {
                        "name": "P1v2",
                        "tier": "PremiumV2",
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_service_plan"
        assert safe_name == "test_plan"
        assert config["name"] == "test-plan"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["os_type"] == "Linux"
        assert config["sku_name"] == "P1v2"

    def test_windows_service_plan(self):
        """Test converting a Windows App Service Plan."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Web/serverFarms/test-plan",
            "name": "test-plan",
            "type": "Microsoft.Web/serverFarms",
            "location": "westus2",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "kind": "app",
                    "sku": {
                        "name": "B1",
                        "tier": "Basic",
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["os_type"] == "Windows"
        assert config["sku_name"] == "B1"


class TestManagedDiskConversion:
    """Test Managed Disk conversion."""

    def test_standard_disk(self):
        """Test converting a Standard LRS managed disk."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/disks/test-disk",
            "name": "test-disk",
            "type": "Microsoft.Compute/disks",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "diskSizeGB": 128,
                    "sku": {
                        "name": "Standard_LRS",
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_managed_disk"
        assert safe_name == "test_disk"
        assert config["name"] == "test-disk"
        assert config["storage_account_type"] == "Standard_LRS"
        assert config["create_option"] == "Empty"
        assert config["disk_size_gb"] == 128

    def test_premium_disk(self):
        """Test converting a Premium SSD managed disk."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/disks/premium-disk",
            "name": "premium-disk",
            "type": "Microsoft.Compute/disks",
            "location": "westus2",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "diskSizeGB": 512,
                    "sku": {
                        "name": "Premium_LRS",
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["storage_account_type"] == "Premium_LRS"
        assert config["disk_size_gb"] == 512


class TestVMExtensionConversion:
    """Test VM Extension conversion."""

    def test_vm_extension_with_valid_vm(self):
        """Test converting a VM extension with valid parent VM."""
        emitter = TerraformEmitter()

        # Track the parent VM as available
        emitter._available_resources = {"azurerm_linux_virtual_machine": {"test_vm"}}

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm/extensions/custom-script",
            "name": "test-vm/custom-script",  # Azure format includes VM name
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publisher": "Microsoft.Azure.Extensions",
                    "type": "CustomScript",
                    "typeHandlerVersion": "2.1",
                    "settings": {
                        "commandToExecute": "echo 'hello world'",
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_virtual_machine_extension"
        # Note: safe_name is auto-generated from "test-vm/custom-script"
        assert config["name"] == "custom-script"  # Should strip VM prefix
        assert (
            config["virtual_machine_id"]
            == "${azurerm_linux_virtual_machine.test_vm.id}"
        )
        assert config["publisher"] == "Microsoft.Azure.Extensions"
        assert config["type"] == "CustomScript"
        assert config["type_handler_version"] == "2.1"
        assert "settings" in config

    def test_vm_extension_with_missing_vm(self):
        """Test that VM extension is skipped if parent VM is missing."""
        emitter = TerraformEmitter()
        emitter._available_resources = {}

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/missing-vm/extensions/custom-script",
            "name": "custom-script",
            "type": "Microsoft.Compute/virtualMachines/extensions",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publisher": "Microsoft.Azure.Extensions",
                    "type": "CustomScript",
                    "typeHandlerVersion": "2.1",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is None


class TestLogAnalyticsConversion:
    """Test Log Analytics Workspace conversion."""

    def test_log_analytics_workspace(self):
        """Test converting a Log Analytics workspace."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "PerGB2018",
                    },
                    "retentionInDays": 90,
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_log_analytics_workspace"
        assert safe_name == "test_workspace"
        assert config["name"] == "test-workspace"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["sku"] == "PerGB2018"
        assert config["retention_in_days"] == 90

    def test_log_analytics_workspace_defaults(self):
        """Test Log Analytics workspace with default values."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": "{}",
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["sku"] == "PerGB2018"
        assert config["retention_in_days"] == 30

    def test_log_analytics_workspace_case_normalization(self):
        """Test that lowercase SKU from Azure is normalized to PascalCase for Terraform."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "pergb2018",  # Lowercase from Azure
                    },
                    "retentionInDays": 90,
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["sku"] == "PerGB2018"  # Should be normalized to PascalCase
        assert config["retention_in_days"] == 90

    def test_log_analytics_workspace_with_daily_quota(self):
        """Test Log Analytics workspace with daily quota configured."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "PerGB2018",
                    },
                    "retentionInDays": 90,
                    "workspaceCapping": {
                        "dailyQuotaGb": 5.0,
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_log_analytics_workspace"
        assert config["name"] == "test-workspace"
        assert config["sku"] == "PerGB2018"
        assert config["retention_in_days"] == 90
        assert config["daily_quota_gb"] == 5.0

    def test_log_analytics_workspace_without_daily_quota(self):
        """Test Log Analytics workspace without daily quota (should not include field)."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
            "name": "test-workspace",
            "type": "Microsoft.OperationalInsights/workspaces",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "sku": {
                        "name": "PerGB2018",
                    },
                    "retentionInDays": 90,
                    "workspaceCapping": {},  # Empty capping config
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_log_analytics_workspace"
        assert config["sku"] == "PerGB2018"
        assert "daily_quota_gb" not in config  # Should not include empty daily quota


class TestApplicationInsightsConversion:
    """Test Application Insights conversion."""

    def test_application_insights_basic(self):
        """Test converting an Application Insights component."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.insights/components/test-insights",
            "name": "test-insights",
            "type": "microsoft.insights/components",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "Application_Type": "web",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_application_insights"
        assert safe_name == "test_insights"
        assert config["name"] == "test-insights"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["application_type"] == "web"

    def test_application_insights_with_workspace(self):
        """Test Application Insights with Log Analytics workspace link."""
        emitter = TerraformEmitter()

        # Track the Log Analytics workspace as available
        emitter._available_resources = {
            "azurerm_log_analytics_workspace": {"test_workspace"}
        }

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.insights/components/test-insights",
            "name": "test-insights",
            "type": "microsoft.insights/components",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "Application_Type": "web",
                    "WorkspaceResourceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert config["application_type"] == "web"
        assert (
            config["workspace_id"]
            == "${azurerm_log_analytics_workspace.test_workspace.id}"
        )


class TestResourceTypeCount:
    """Test that all expected resource types are mapped."""

    def test_total_resource_type_count(self):
        """Verify we have all expected resource type mappings."""
        emitter = TerraformEmitter()

        # Count should be at least 27 (26 from previous + 1 new smartDetectorAlertRules)
        assert len(emitter.AZURE_TO_TERRAFORM_MAPPING) >= 27

    def test_new_types_included_in_supported_types(self):
        """Verify new types appear in supported resource types list."""
        emitter = TerraformEmitter()
        supported_types = emitter.get_supported_resource_types()

        assert "Microsoft.Web/serverFarms" in supported_types
        assert "Microsoft.Compute/disks" in supported_types
        assert "Microsoft.Compute/virtualMachines/extensions" in supported_types
        assert "Microsoft.OperationalInsights/workspaces" in supported_types
        assert "microsoft.insights/components" in supported_types


class TestSmartDetectorAlertRuleMapping:
    """Test Smart Detector Alert Rule mapping and conversion."""

    def test_smart_detector_alert_rule_mapping(self):
        """Test microsoft.alertsmanagement/smartDetectorAlertRules mapping."""
        emitter = TerraformEmitter()
        assert (
            "microsoft.alertsmanagement/smartDetectorAlertRules"
            in emitter.AZURE_TO_TERRAFORM_MAPPING
        )
        assert (
            emitter.AZURE_TO_TERRAFORM_MAPPING[
                "microsoft.alertsmanagement/smartDetectorAlertRules"
            ]
            == "azurerm_monitor_smart_detector_alert_rule"
        )

    def test_smart_detector_alert_rule_conversion(self):
        """Test converting a Smart Detector Alert Rule."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.alertsmanagement/smartDetectorAlertRules/failure-anomalies",
            "name": "Failure Anomalies - test",
            "type": "microsoft.alertsmanagement/smartDetectorAlertRules",
            "location": "global",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "description": "Failure Anomalies notifies you of an unusual rise in the rate of failed HTTP requests or dependency calls.",
                    "state": "Enabled",
                    "severity": "Sev3",
                    "frequency": "PT1M",
                    "detector": {
                        "id": "FailureAnomaliesDetector",
                        "name": "Failure Anomalies",
                    },
                    "scope": [
                        "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.insights/components/test-insights"
                    ],
                    "actionGroups": {"groupIds": []},
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_monitor_smart_detector_alert_rule"
        assert config["name"] == "Failure Anomalies - test"
        assert config["detector_type"] == "FailureAnomaliesDetector"
        assert config["severity"] == "Sev3"  # Keep as "Sev3" format
        assert config["frequency"] == "PT1M"
        assert config["enabled"] is True
        assert len(config["scope_resource_ids"]) == 1

    def test_smart_detector_severity_mapping(self):
        """Test severity stays in Azure format (Sev0-Sev4) for Terraform."""
        emitter = TerraformEmitter()

        severity_tests = [
            "Sev0",
            "Sev1",
            "Sev2",
            "Sev3",
            "Sev4",
        ]

        for sev_str in severity_tests:
            resource = {
                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.alertsmanagement/smartDetectorAlertRules/test",
                "name": "test-rule",
                "type": "microsoft.alertsmanagement/smartDetectorAlertRules",
                "location": "global",
                "resource_group": "test-rg",
                "properties": json.dumps(
                    {
                        "state": "Enabled",
                        "severity": sev_str,
                        "frequency": "PT1M",
                        "detector": {"id": "FailureAnomaliesDetector"},
                        "scope": [],
                    }
                ),
            }

            result = emitter._convert_resource(resource, {"resource": {}})
            assert result is not None
            _, _, config = result
            assert config["severity"] == sev_str  # Should keep original format

    def test_smart_detector_disabled_state(self):
        """Test that disabled alert rules are properly converted."""
        emitter = TerraformEmitter()
        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.alertsmanagement/smartDetectorAlertRules/test",
            "name": "test-rule",
            "type": "microsoft.alertsmanagement/smartDetectorAlertRules",
            "location": "global",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "state": "Disabled",
                    "severity": "Sev3",
                    "frequency": "PT1M",
                    "detector": {"id": "FailureAnomaliesDetector"},
                    "scope": [],
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        _, _, config = result
        assert config["enabled"] is False

    def test_smart_detector_cross_tenant_scope_translation(self):
        """Test that scope resource IDs are translated to target subscription in cross-tenant mode."""
        # Create emitter with target subscription (cross-tenant mode)
        target_subscription = "target-subscription-id"
        emitter = TerraformEmitter(target_subscription_id=target_subscription)

        # Resource from source tenant with source subscription in scope
        resource = {
            "id": "/subscriptions/source-sub/resourceGroups/test-rg/providers/microsoft.alertsmanagement/smartDetectorAlertRules/test",
            "name": "test-rule",
            "type": "microsoft.alertsmanagement/smartDetectorAlertRules",
            "location": "global",
            "resource_group": "test-rg",
            "subscription_id": "source-sub",
            "properties": json.dumps(
                {
                    "state": "Enabled",
                    "severity": "Sev3",
                    "frequency": "PT1M",
                    "detector": {"id": "FailureAnomaliesDetector"},
                    "scope": [
                        "/subscriptions/source-sub/resourceGroups/test-rg/providers/microsoft.insights/components/test-insights"
                    ],
                    "actionGroups": {
                        "groupIds": [
                            "/subscriptions/source-sub/resourceGroups/test-rg/providers/microsoft.insights/actionGroups/test-ag"
                        ]
                    },
                }
            ),
        }

        result = emitter._convert_resource(resource, {"resource": {}})
        assert result is not None
        _, _, config = result

        # Verify scope resource IDs use target subscription
        assert len(config["scope_resource_ids"]) == 1
        scope_id = config["scope_resource_ids"][0]
        assert target_subscription in scope_id
        assert "source-sub" not in scope_id
        assert scope_id == f"/subscriptions/{target_subscription}/resourceGroups/test-rg/providers/microsoft.insights/components/test-insights"

        # Verify action group IDs also use target subscription
        assert "action_group" in config
        assert len(config["action_group"]["ids"]) == 1
        ag_id = config["action_group"]["ids"][0]
        assert target_subscription in ag_id
        assert "source-sub" not in ag_id
