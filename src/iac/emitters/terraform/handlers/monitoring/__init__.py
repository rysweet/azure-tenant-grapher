"""Monitoring handlers for Terraform emission."""

from .action_group import ActionGroupHandler
from .app_insights import ApplicationInsightsHandler
from .dcr import DataCollectionRuleHandler
from .diagnostic_settings import DiagnosticSettingHandler
from .log_analytics import (
    LogAnalyticsQueryPackHandler,
    LogAnalyticsSolutionHandler,
    LogAnalyticsWorkspaceHandler,
)
from .metric_alert import MetricAlertHandler
from .workbook import WorkbooksHandler

__all__ = [
    "ActionGroupHandler",
    "ApplicationInsightsHandler",
    "DataCollectionRuleHandler",
    "DiagnosticSettingHandler",
    "LogAnalyticsQueryPackHandler",
    "LogAnalyticsSolutionHandler",
    "LogAnalyticsWorkspaceHandler",
    "MetricAlertHandler",
    "WorkbooksHandler",
]
