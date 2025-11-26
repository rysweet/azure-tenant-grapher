"""Automation handlers for Terraform emission."""

from .automation_account import AutomationAccountHandler
from .runbook import AutomationRunbookHandler

__all__ = [
    "AutomationAccountHandler",
    "AutomationRunbookHandler",
]
