"""
Agentic Testing System for Azure Tenant Grapher

An autonomous AI-powered testing system that tests both CLI and Electron GUI interfaces,
discovers issues, and automatically documents them as GitHub issues.
"""

__version__ = "1.0.0"

from .config import TestConfig
from .models import TestFailure, TestResult, TestScenario
from .orchestrator import ATGTestingOrchestrator

__all__ = [
    "ATGTestingOrchestrator",
    "TestConfig",
    "TestFailure",
    "TestResult",
    "TestScenario",
]
