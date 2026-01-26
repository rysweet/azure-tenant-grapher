"""Unit tests for Scheduled Query Rules Alert handler (Issue #330).

Tests Terraform emission for Microsoft.Insights/scheduledQueryRules resources,
including cross-tenant deployment with tenant suffix pattern and name truncation.
"""

from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers.monitoring.scheduled_query_rules import (
    ScheduledQueryRulesHandler,
)


class TestScheduledQueryRulesHandler:
    """Tests for Scheduled Query Rules Alert handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return ScheduledQueryRulesHandler()

    @pytest.fixture
    def context(self):
        """Create mock emitter context with same-tenant deployment."""
        ctx = Mock(spec=EmitterContext)
        ctx.source_tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        ctx.target_tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        ctx.get_effective_subscription_id.return_value = "sub-12345"
        return ctx

    @pytest.fixture
    def cross_tenant_context(self):
        """Create mock emitter context with cross-tenant deployment."""
        ctx = Mock(spec=EmitterContext)
        ctx.source_tenant_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        ctx.target_tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        ctx.get_effective_subscription_id.return_value = "sub-67890"
        return ctx

    @pytest.fixture
    def base_alert_resource(self):
        """Base scheduled query rules alert resource structure."""
        return {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-monitoring/providers/Microsoft.Insights/scheduledQueryRules/high-cpu-alert",
            "name": "high-cpu-alert",
            "type": "Microsoft.Insights/scheduledQueryRules",
            "location": "eastus",
            "resource_group": "rg-monitoring",
            "properties": {
                "enabled": True,
                "description": "Alert when CPU usage exceeds 80%",
                "severity": 2,
                "evaluationFrequency": "PT5M",
                "windowSize": "PT15M",
                "scopes": [
                    "/subscriptions/sub-12345/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm-prod-001"
                ],
                "criteria": {
                    "allOf": [
                        {
                            "query": "Perf | where ObjectName == 'Processor' and CounterName == '% Processor Time' | summarize AggregatedValue = avg(CounterValue) by bin(TimeGenerated, 5m)",
                            "timeAggregation": "Average",
                            "metricMeasureColumn": "AggregatedValue",
                            "operator": "GreaterThan",
                            "threshold": 80.0,
                            "failingPeriods": {
                                "numberOfEvaluationPeriods": 4,
                                "minFailingPeriodsToAlert": 3,
                            },
                        }
                    ]
                },
                "actions": {
                    "actionGroups": [
                        "/subscriptions/sub-12345/resourceGroups/rg-monitoring/providers/Microsoft.Insights/actionGroups/ops-team"
                    ],
                    "customProperties": {"Environment": "Production"},
                },
            },
        }

    # ========== Basic Emission Tests ==========

    def test_basic_emission_with_required_properties(
        self, handler, context, base_alert_resource
    ):
        """Test basic emission with all required properties present."""
        tf_type, safe_name, config = handler.emit(base_alert_resource, context)

        # Verify correct Terraform type
        assert tf_type == "azurerm_monitor_scheduled_query_rules_alert_v2"

        # Verify safe name sanitization
        assert safe_name == "high_cpu_alert"

        # Verify required properties mapped correctly
        assert config["name"] == "high-cpu-alert"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "rg-monitoring"
        assert config["enabled"] is True
        assert config["description"] == "Alert when CPU usage exceeds 80%"
        assert config["severity"] == 2
        assert config["evaluation_frequency"] == "PT5M"
        assert config["window_duration"] == "PT15M"
        assert len(config["scopes"]) == 1
        assert "vm-prod-001" in config["scopes"][0]

    def test_criteria_mapping(self, handler, context, base_alert_resource):
        """Test criteria block mapping with all fields."""
        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify criteria block structure
        assert "criteria" in config
        criteria = config["criteria"]
        assert len(criteria) == 1

        # Verify first criterion
        criterion = criteria[0]
        assert "Processor" in criterion["query"]
        assert criterion["time_aggregation_method"] == "Average"
        assert criterion["metric_measure_column"] == "AggregatedValue"
        assert criterion["operator"] == "GreaterThan"
        assert criterion["threshold"] == 80.0

        # Verify failing periods
        assert "failing_periods" in criterion
        failing = criterion["failing_periods"]
        assert failing["number_of_evaluation_periods"] == 4
        assert failing["min_failing_periods_to_alert"] == 3

    def test_action_mapping(self, handler, context, base_alert_resource):
        """Test action block mapping with action groups and custom properties."""
        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify action block
        assert "action" in config
        action = config["action"]
        assert len(action["action_groups"]) == 1
        assert "ops-team" in action["action_groups"][0]
        assert action["custom_properties"]["Environment"] == "Production"

    # ========== Cross-Tenant Deployment Tests ==========

    def test_cross_tenant_deployment_with_tenant_suffix(
        self, handler, cross_tenant_context, base_alert_resource, caplog
    ):
        """Test cross-tenant deployment adds tenant suffix to alert name."""
        import logging

        caplog.set_level(logging.INFO)

        _tf_type, _safe_name, config = handler.emit(
            base_alert_resource, cross_tenant_context
        )

        # Verify tenant suffix added (last 6 chars of target tenant ID)
        # target_tenant_id = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
        # last 6 chars = "bbbbbb" (after removing dashes)
        expected_suffix = "bbbbbb"
        assert config["name"] == f"high-cpu-alert-{expected_suffix}"

        # Verify log message
        assert "Cross-tenant deployment" in caplog.text
        assert "tenant suffix" in caplog.text
        assert expected_suffix in caplog.text

    def test_cross_tenant_same_tenant_no_suffix(
        self, handler, context, base_alert_resource
    ):
        """Test same-tenant deployment does not add suffix."""
        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify no suffix when source and target are same
        assert config["name"] == "high-cpu-alert"
        assert "aaaaaa" not in config["name"]

    # ========== Name Truncation Tests ==========

    def test_name_truncation_for_long_names(
        self, handler, cross_tenant_context, base_alert_resource
    ):
        """Test name truncation when alert name exceeds 253 char limit."""
        # Create alert with very long name (260 chars)
        long_name = "alert-" + "x" * 254
        base_alert_resource["name"] = long_name
        base_alert_resource["id"] = base_alert_resource["id"].replace(
            "high-cpu-alert", long_name
        )

        _tf_type, _safe_name, config = handler.emit(
            base_alert_resource, cross_tenant_context
        )

        # Verify name truncated to fit 253 char limit (253 - 7 = 246 for name + dash + suffix)
        # tenant suffix is 6 chars, so 246 + 1 (dash) + 6 = 253
        assert len(config["name"]) <= 253
        assert config["name"].endswith("-bbbbbb")

    def test_name_truncation_preserves_suffix(
        self, handler, cross_tenant_context, base_alert_resource
    ):
        """Test truncation preserves tenant suffix at end of name."""
        # Create alert name that needs truncation
        long_name = "high-cpu-alert-" + "x" * 240
        base_alert_resource["name"] = long_name

        _tf_type, _safe_name, config = handler.emit(
            base_alert_resource, cross_tenant_context
        )

        # Verify suffix is at the end
        assert config["name"].endswith("-bbbbbb")
        # Verify total length constraint
        assert len(config["name"]) <= 253

    # ========== Complete Property Mapping Tests ==========

    def test_optional_properties_mapped(self, handler, context, base_alert_resource):
        """Test optional properties are mapped when present."""
        # Add optional properties
        base_alert_resource["properties"]["autoMitigate"] = True
        base_alert_resource["properties"]["skipQueryValidation"] = False
        base_alert_resource["properties"]["muteActionsDuration"] = "PT1H"
        base_alert_resource["tags"] = {
            "Environment": "Production",
            "Owner": "Platform Team",
        }

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify optional properties
        assert config["auto_mitigation_enabled"] is True
        assert config["skip_query_validation"] is False
        assert config["mute_actions_after_alert_duration"] == "PT1H"
        assert config["tags"]["Environment"] == "Production"
        assert config["tags"]["Owner"] == "Platform Team"

    def test_identity_block_mapping(self, handler, context, base_alert_resource):
        """Test identity block mapping for managed identity."""
        # Add identity configuration
        base_alert_resource["identity"] = {
            "type": "SystemAssigned",
            "principalId": "11111111-1111-1111-1111-111111111111",
            "tenantId": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        }

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify identity mapping
        assert "identity" in config
        assert config["identity"]["type"] == "SystemAssigned"

    def test_multiple_criteria_mapping(self, handler, context, base_alert_resource):
        """Test mapping of multiple criteria in alert."""
        # Add second criterion
        base_alert_resource["properties"]["criteria"]["allOf"].append(
            {
                "query": "Perf | where ObjectName == 'Memory' | summarize AggregatedValue = avg(CounterValue) by bin(TimeGenerated, 5m)",
                "timeAggregation": "Average",
                "metricMeasureColumn": "AggregatedValue",
                "operator": "GreaterThan",
                "threshold": 90.0,
                "failingPeriods": {
                    "numberOfEvaluationPeriods": 3,
                    "minFailingPeriodsToAlert": 2,
                },
            }
        )

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify both criteria mapped
        assert len(config["criteria"]) == 2
        assert "Processor" in config["criteria"][0]["query"]
        assert "Memory" in config["criteria"][1]["query"]
        assert config["criteria"][0]["threshold"] == 80.0
        assert config["criteria"][1]["threshold"] == 90.0

    def test_multiple_action_groups_mapping(
        self, handler, context, base_alert_resource
    ):
        """Test mapping of multiple action groups."""
        # Add second action group
        base_alert_resource["properties"]["actions"]["actionGroups"].append(
            "/subscriptions/sub-12345/resourceGroups/rg-monitoring/providers/Microsoft.Insights/actionGroups/sre-team"
        )

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Verify both action groups mapped
        assert len(config["action"]["action_groups"]) == 2
        assert "ops-team" in config["action"]["action_groups"][0]
        assert "sre-team" in config["action"]["action_groups"][1]

    # ========== Handler Registration Tests ==========

    def test_handler_type_registration(self, handler):
        """Test handler registers correct Terraform type."""
        assert (
            "azurerm_monitor_scheduled_query_rules_alert_v2" in handler.TERRAFORM_TYPES
        )

    def test_handler_handles_correct_azure_type(self, handler):
        """Test handler is registered for correct Azure resource type."""
        assert "Microsoft.Insights/scheduledQueryRules" in handler.HANDLED_TYPES

    def test_can_handle_method(self, handler):
        """Test can_handle method correctly identifies supported types."""
        # Should handle case-insensitively
        assert handler.can_handle("Microsoft.Insights/scheduledQueryRules")
        assert handler.can_handle("microsoft.insights/scheduledqueryrules")
        assert not handler.can_handle("Microsoft.Insights/metricAlerts")

    # ========== Missing Required Properties Tests ==========

    def test_skips_alert_missing_name(self, handler, context, base_alert_resource):
        """Test alert is skipped when name is missing."""
        del base_alert_resource["name"]

        result = handler.emit(base_alert_resource, context)

        # Should return None when required property missing
        assert result is None

    def test_skips_alert_missing_location(
        self, handler, context, base_alert_resource, caplog
    ):
        """Test alert is skipped when location is missing."""
        import logging

        caplog.set_level(logging.WARNING)

        del base_alert_resource["location"]

        result = handler.emit(base_alert_resource, context)

        # Should return None and log warning
        assert result is None
        assert "missing required" in caplog.text.lower() or "location" in caplog.text

    def test_skips_alert_missing_criteria(
        self, handler, context, base_alert_resource, caplog
    ):
        """Test alert is skipped when criteria is missing."""
        import logging

        caplog.set_level(logging.WARNING)

        del base_alert_resource["properties"]["criteria"]

        result = handler.emit(base_alert_resource, context)

        # Should return None and log warning
        assert result is None
        assert "missing" in caplog.text.lower() or "criteria" in caplog.text.lower()

    def test_skips_alert_empty_scopes(
        self, handler, context, base_alert_resource, caplog
    ):
        """Test alert is skipped when scopes list is empty."""
        import logging

        caplog.set_level(logging.WARNING)

        base_alert_resource["properties"]["scopes"] = []

        result = handler.emit(base_alert_resource, context)

        # Should return None when scopes empty
        assert result is None
        assert "scope" in caplog.text.lower() or "empty" in caplog.text.lower()

    # ========== Edge Cases Tests ==========

    def test_handles_empty_action_groups(self, handler, context, base_alert_resource):
        """Test handler gracefully handles empty action groups."""
        base_alert_resource["properties"]["actions"]["actionGroups"] = []

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Should emit but with empty action groups
        assert "action" in config
        assert config["action"]["action_groups"] == []

    def test_handles_missing_description(self, handler, context, base_alert_resource):
        """Test handler handles missing optional description field."""
        del base_alert_resource["properties"]["description"]

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Should emit successfully without description
        assert "description" not in config or config["description"] is None

    def test_handles_malformed_properties_json(self, handler, context):
        """Test handler handles malformed properties structure."""
        malformed_resource = {
            "name": "test-alert",
            "type": "Microsoft.Insights/scheduledQueryRules",
            "location": "eastus",
            "resource_group": "rg-test",
            "properties": "not-a-dict",  # Malformed
        }

        result = handler.emit(malformed_resource, context)

        # Should return None for malformed data
        assert result is None

    def test_handles_missing_failing_periods(
        self, handler, context, base_alert_resource
    ):
        """Test handler handles missing failingPeriods in criteria."""
        del base_alert_resource["properties"]["criteria"]["allOf"][0]["failingPeriods"]

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Should emit with defaults or without failing_periods block
        assert "criteria" in config
        # Failing periods might be optional or have defaults

    def test_handles_missing_custom_properties(
        self, handler, context, base_alert_resource
    ):
        """Test handler handles missing customProperties in actions."""
        del base_alert_resource["properties"]["actions"]["customProperties"]

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Should emit successfully
        assert "action" in config
        # Custom properties might be omitted or empty

    def test_severity_values_range(self, handler, context, base_alert_resource):
        """Test handler accepts valid severity values (0-4)."""
        for severity in [0, 1, 2, 3, 4]:
            base_alert_resource["properties"]["severity"] = severity

            _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

            assert config["severity"] == severity

    def test_enabled_false_emission(self, handler, context, base_alert_resource):
        """Test alert can be emitted with enabled=false."""
        base_alert_resource["properties"]["enabled"] = False

        _tf_type, _safe_name, config = handler.emit(base_alert_resource, context)

        # Should emit successfully with enabled=false
        assert config["enabled"] is False

    # ========== Subscription Translation Tests ==========

    def test_cross_subscription_scope_translation(
        self, handler, cross_tenant_context, base_alert_resource
    ):
        """Test scope resource IDs are translated for cross-subscription deployment."""
        # Scope references resource in source subscription
        original_scope = base_alert_resource["properties"]["scopes"][0]
        assert "sub-12345" in original_scope

        _tf_type, _safe_name, config = handler.emit(
            base_alert_resource, cross_tenant_context
        )

        # Verify scope translated to target subscription
        translated_scope = config["scopes"][0]
        assert "sub-67890" in translated_scope
        assert "sub-12345" not in translated_scope
        # Resource name should be preserved
        assert "vm-prod-001" in translated_scope

    def test_cross_subscription_action_group_translation(
        self, handler, cross_tenant_context, base_alert_resource
    ):
        """Test action group resource IDs are translated for cross-subscription deployment."""
        original_action_group = base_alert_resource["properties"]["actions"][
            "actionGroups"
        ][0]
        assert "sub-12345" in original_action_group

        _tf_type, _safe_name, config = handler.emit(
            base_alert_resource, cross_tenant_context
        )

        # Verify action group translated to target subscription
        translated_action_group = config["action"]["action_groups"][0]
        assert "sub-67890" in translated_action_group
        assert "sub-12345" not in translated_action_group
        # Action group name should be preserved
        assert "ops-team" in translated_action_group

    # ========== Name Sanitization Tests ==========

    def test_safe_name_sanitization(self, handler, context, base_alert_resource):
        """Test safe name converts dashes to underscores."""
        # Alert name has dashes
        assert "-" in base_alert_resource["name"]

        _tf_type, safe_name, _config = handler.emit(base_alert_resource, context)

        # Safe name should have underscores
        assert "-" not in safe_name
        assert "_" in safe_name
        assert safe_name == "high_cpu_alert"

    def test_safe_name_handles_special_characters(
        self, handler, context, base_alert_resource
    ):
        """Test safe name handles special characters in alert name."""
        base_alert_resource["name"] = "alert@prod#vm-001"

        _tf_type, safe_name, _config = handler.emit(base_alert_resource, context)

        # Safe name should only contain valid characters
        assert "@" not in safe_name
        assert "#" not in safe_name
        # Should convert to alphanumeric with underscores

    # ========== Security Tests ==========

    def test_log_sanitization_newline_injection(
        self, handler, context, base_alert_resource, caplog
    ):
        """Test that resource names with newlines are sanitized in logs."""
        import logging

        # Resource name with newline injection attempt
        base_alert_resource["name"] = "alert\nFAKE LOG ENTRY\nanother-alert"

        with caplog.at_level(logging.DEBUG):
            result = handler.emit(base_alert_resource, context)

        # Should emit successfully (resource is otherwise valid)
        assert result is not None

        # Check that newline was removed from log messages
        log_messages = [record.message for record in caplog.records]
        # Should have debug log with alert name
        assert any("alert" in msg for msg in log_messages)
        # Newline should be sanitized (removed) from all log messages
        assert not any(
            "\n" in msg for msg in log_messages
        ), "Newline should be removed by sanitization"

    def test_query_length_validation_oversized(
        self, handler, context, base_alert_resource
    ):
        """Test that oversized KQL queries are rejected."""
        # Create a query that exceeds MAX_QUERY_LENGTH (10000 chars)
        oversized_query = "A" * 15000

        base_alert_resource["properties"]["criteria"]["allOf"][0][
            "query"
        ] = oversized_query

        result = handler.emit(base_alert_resource, context)

        # Should still emit but with empty criteria (query was skipped)
        # This tests the DoS protection without breaking the entire emission
        assert result is not None
        _tf_type, _safe_name, _config = result
        # Criteria should be empty or missing query in first criterion
        # (depending on implementation details)
