"""Monitoring handlers for Terraform emission."""

from .action_group import ActionGroupHandler
from .app_insights import ApplicationInsightsHandler
from .dcr import DataCollectionRuleHandler
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
    "LogAnalyticsQueryPackHandler",
    "LogAnalyticsSolutionHandler",
    "LogAnalyticsWorkspaceHandler",
    "MetricAlertHandler",
    "WorkbooksHandler",
]
