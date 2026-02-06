"""Unit tests for Diagnostic Settings handler registration and emission.

Testing Strategy (TDD - 60% Unit Tests):
- Test handler is properly registered in HandlerRegistry
- Test diagnostic settings emit correctly via handler
- Test handler can process diagnostic settings properties
- Test handler validates target resource references

These tests should FAIL before the fix (handler not imported) and PASS after.
"""

import logging
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import HandlerRegistry, ensure_handlers_registered
from src.iac.emitters.terraform.handlers.monitoring.diagnostic_settings import (
    DiagnosticSettingHandler,
)


class TestDiagnosticSettingsHandlerRegistration:
    """Unit tests for Diagnostic Settings handler registration (60% - Unit)."""

    def test_diagnostic_settings_handler_exists(self):
        """Test that DiagnosticSettingHandler class exists and can be imported.

        This verifies the handler file exists but doesn't check registration.
        """
        # Import only in this test to avoid polluting other tests
        from src.iac.emitters.terraform.handlers.monitoring.diagnostic_settings import (
            DiagnosticSettingHandler,
        )

        assert DiagnosticSettingHandler is not None
        assert hasattr(DiagnosticSettingHandler, "HANDLED_TYPES")
        assert "Microsoft.Insights/diagnosticSettings" in DiagnosticSettingHandler.HANDLED_TYPES

    def test_diagnostic_settings_handler_registered(self):
        """Test that DiagnosticSettingHandler is registered in HandlerRegistry.

        THIS TEST WILL FAIL BEFORE FIX:
        The handler exists but is not imported in handlers/__init__.py,
        so ensure_handlers_registered() won't register it.

        AFTER FIX:
        Handler will be imported and registered successfully.
        """
        # Ensure all handlers are registered
        ensure_handlers_registered()

        # Get handler for diagnostic settings type
        handler = HandlerRegistry.get_handler("Microsoft.Insights/diagnosticSettings")

        # Verify handler is registered and is correct type
        assert handler is not None, (
            "DiagnosticSettingHandler is not registered. "
            "Check that handlers/__init__.py imports diagnostic_settings module."
        )
        # Verify it's a ResourceHandler (we can't check exact type without importing)
        from src.iac.emitters.terraform.base_handler import ResourceHandler
        assert isinstance(handler, ResourceHandler), (
            f"Wrong handler type registered: {type(handler).__name__}"
        )
        assert type(handler).__name__ == "DiagnosticSettingHandler", (
            f"Wrong handler class: {type(handler).__name__}"
        )

    def test_diagnostic_settings_in_supported_types(self):
        """Test that diagnostic settings type appears in supported types list.

        THIS TEST WILL FAIL BEFORE FIX:
        Handler not imported, so type not in supported list.
        """
        ensure_handlers_registered()

        supported_types = HandlerRegistry.get_all_supported_types()

        assert "Microsoft.Insights/diagnosticSettings" in supported_types, (
            "Microsoft.Insights/diagnosticSettings not in supported types. "
            "Handler may not be imported in handlers/__init__.py."
        )

    def test_diagnostic_settings_handler_in_all_handlers(self):
        """Test that DiagnosticSettingHandler is in list of all handlers.

        THIS TEST WILL FAIL BEFORE FIX:
        Handler not imported, so not in handlers list.
        """
        ensure_handlers_registered()

        all_handlers = HandlerRegistry.get_all_handlers()
        handler_classes = [h.__name__ for h in all_handlers]

        assert "DiagnosticSettingHandler" in handler_classes, (
            f"DiagnosticSettingHandler not in registered handlers. "
            f"Registered handlers: {handler_classes}"
        )


class TestDiagnosticSettingsHandlerEmission:
    """Unit tests for Diagnostic Settings emission logic (60% - Unit)."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = DiagnosticSettingHandler()
        self.context = EmitterContext()

    def test_emit_diagnostic_setting_basic(self):
        """Test basic diagnostic setting emission."""
        resource = {
            "type": "Microsoft.Insights/diagnosticSettings",
            "name": "test-diag-setting",
            "id": (
                "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
                "Microsoft.Storage/storageAccounts/teststorage/providers/"
                "Microsoft.Insights/diagnosticSettings/test-diag-setting"
            ),
            "properties": {
                "workspaceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.OperationalInsights/workspaces/test-workspace",
                "logs": [
                    {"category": "StorageRead", "enabled": True},
                    {"category": "StorageWrite", "enabled": False},
                ],
                "metrics": [
                    {"category": "Transaction", "enabled": True},
                ],
            },
        }

        result = self.handler.emit(resource, self.context)

        assert result is not None, "Handler should emit diagnostic setting"
        terraform_type, name, config = result

        assert terraform_type == "azurerm_monitor_diagnostic_setting"
        assert name == "test_diag_setting"
        assert "target_resource_id" in config
        assert "log_analytics_workspace_id" in config
        assert "enabled_log" in config
        assert len(config["enabled_log"]) == 1  # Only enabled logs
        assert config["enabled_log"][0]["category"] == "StorageRead"

    def test_emit_diagnostic_setting_no_destination_returns_none(self):
        """Test that diagnostic setting with no destination is skipped."""
        resource = {
            "type": "Microsoft.Insights/diagnosticSettings",
            "name": "test-diag-setting",
            "id": (
                "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
                "Microsoft.Storage/storageAccounts/teststorage/providers/"
                "Microsoft.Insights/diagnosticSettings/test-diag-setting"
            ),
            "properties": {
                "logs": [{"category": "StorageRead", "enabled": True}],
            },
        }

        result = self.handler.emit(resource, self.context)

        assert result is None, "Handler should skip diagnostic setting with no destination"

    def test_emit_diagnostic_setting_invalid_id_returns_none(self):
        """Test that diagnostic setting with invalid ID format is skipped."""
        resource = {
            "type": "Microsoft.Insights/diagnosticSettings",
            "name": "test-diag-setting",
            "id": "invalid-resource-id",
            "properties": {
                "workspaceId": "/subscriptions/test/workspace",
                "logs": [{"category": "Test", "enabled": True}],
            },
        }

        result = self.handler.emit(resource, self.context)

        assert result is None, "Handler should skip diagnostic setting with invalid ID"

    def test_extract_target_resource_id(self):
        """Test target resource ID extraction from diagnostic setting ID."""
        diag_id = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Storage/storageAccounts/teststorage/providers/"
            "Microsoft.Insights/diagnosticSettings/test-diag-setting"
        )

        expected_target = (
            "/subscriptions/test-sub/resourceGroups/test-rg/providers/"
            "Microsoft.Storage/storageAccounts/teststorage"
        )

        target = self.handler._extract_target_resource_id(diag_id)

        assert target == expected_target

    def test_process_logs_filters_enabled_only(self):
        """Test that _process_logs filters to only enabled logs."""
        logs = [
            {"category": "Log1", "enabled": True},
            {"category": "Log2", "enabled": False},
            {"category": "Log3", "enabled": True},
        ]

        result = self.handler._process_logs(logs)

        assert len(result) == 2
        assert result[0]["category"] == "Log1"
        assert result[1]["category"] == "Log3"

    def test_process_metrics_includes_all_with_enabled_state(self):
        """Test that _process_metrics includes all metrics with enabled state."""
        metrics = [
            {"category": "Metric1", "enabled": True},
            {"category": "Metric2", "enabled": False},
        ]

        result = self.handler._process_metrics(metrics)

        assert len(result) == 2
        assert result[0]["category"] == "Metric1"
        assert result[0]["enabled"] is True
        assert result[1]["category"] == "Metric2"
        assert result[1]["enabled"] is False
