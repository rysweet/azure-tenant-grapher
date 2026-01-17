"""CI/CD integration for property validation.

This module provides CI/CD pipeline integration for automated property
coverage validation in pull requests.

Philosophy:
- Automated quality gates
- Clear threshold enforcement
- Actionable feedback in PRs
- Zero-configuration defaults

Public API:
    PRChecker: Main validation checker for CI/CD
    ValidationThresholds: Coverage thresholds configuration
    ValidationResult: Validation check results

Scripts:
    pr_checker.py: CLI tool for PR validation

Configuration:
    thresholds.yaml: Coverage thresholds configuration

Usage in CI/CD:
    python -m property_validation.ci.pr_checker --handlers-dir ./src/iac/handlers
"""

from .pr_checker import PRChecker, ValidationResult, ValidationThresholds

__all__ = [
    "PRChecker",
    "ValidationResult",
    "ValidationThresholds",
]
