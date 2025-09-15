#!/usr/bin/env python3
"""
Error Reporter Module

Purpose: Provide clear, actionable error messages with remediation steps
Contract: Format errors, suggest fixes, and help diagnose issues
"""

import logging
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ErrorReport:
    """Structured error report with context and remediation."""

    def __init__(self, error_type: str, message: str, context: Optional[Dict[str, Any]] = None):
        self.error_type = error_type
        self.message = message
        self.context = context or {}
        self.timestamp = datetime.now().isoformat()
        self.traceback = traceback.format_exc() if traceback.format_exc() != "NoneType: None\n" else None
        self.suggestions: List[str] = []

    def add_suggestion(self, suggestion: str) -> None:
        """Add a remediation suggestion."""
        self.suggestions.append(suggestion)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "error_type": self.error_type,
            "message": self.message,
            "timestamp": self.timestamp,
            "context": self.context,
            "suggestions": self.suggestions,
            "traceback": self.traceback
        }


class ErrorReporter:
    """
    Provides clear error reporting and remediation guidance.

    Public Interface:
        - report_error(error, context): Generate detailed error report
        - get_remediation(error_type): Get specific remediation steps
        - save_error_log(path): Save errors to file for analysis
        - format_for_console(): Format error for console display
    """

    def __init__(self):
        """Initialize error reporter."""
        self.errors: List[ErrorReport] = []
        self.remediation_map = self._build_remediation_map()

    def _build_remediation_map(self) -> Dict[str, List[str]]:
        """Build map of error types to remediation steps."""
        return {
            "connection_refused": [
                "Check if the application is running on the configured port",
                "Verify the URL in config.yaml (app.url)",
                "Try: npm start or yarn start in the application directory",
                "Check firewall settings if running remotely"
            ],
            "authentication_failed": [
                "Verify Azure credentials are configured",
                "Run: az login",
                "Check environment variables: AZURE_TENANT_ID, AZURE_CLIENT_ID",
                "Verify the service principal has required permissions"
            ],
            "browser_launch_failed": [
                "Install required browser dependencies",
                "For Chromium: playwright install chromium",
                "For Firefox: playwright install firefox",
                "Check system requirements for Playwright"
            ],
            "timeout": [
                "Increase timeout in config.yaml (test.timeout)",
                "Check if the application is responding slowly",
                "Verify network connectivity",
                "Consider running with --headless for faster execution"
            ],
            "element_not_found": [
                "Check if the UI has changed",
                "Verify selectors in scenario files",
                "Add wait conditions before interactions",
                "Use more specific selectors"
            ],
            "configuration_error": [
                "Check config.yaml exists and is valid YAML",
                "Verify all required fields are present",
                "Check environment variables are set",
                "Use --config to specify alternate config file"
            ],
            "scenario_not_found": [
                "Check scenarios directory exists",
                "Verify scenario name matches file name",
                "List available scenarios: ls scenarios/",
                "Create scenario file if missing"
            ],
            "permission_denied": [
                "Check file permissions in the demo directory",
                "Ensure write access to logs/ and screenshots/",
                "Run with appropriate user permissions",
                "Check disk space availability"
            ]
        }

    def report_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> ErrorReport:
        """
        Generate detailed error report with remediation.

        Args:
            error: The exception that occurred
            context: Additional context about the error

        Returns:
            ErrorReport with details and suggestions
        """
        error_type = self._classify_error(error)
        report = ErrorReport(error_type, str(error), context)

        # Add remediation suggestions
        suggestions = self.remediation_map.get(error_type, [])
        for suggestion in suggestions:
            report.add_suggestion(suggestion)

        # Add generic suggestions if no specific ones
        if not suggestions:
            report.add_suggestion("Check the logs for more details")
            report.add_suggestion("Run with --debug for verbose output")
            report.add_suggestion("Verify all dependencies are installed")

        self.errors.append(report)
        return report

    def _classify_error(self, error: Exception) -> str:
        """Classify error type for remediation lookup."""
        error_str = str(error).lower()
        error_type_name = type(error).__name__

        if "connection refused" in error_str or "econnrefused" in error_str or "connect call failed" in error_str:
            return "connection_refused"
        elif "authentication" in error_str or "unauthorized" in error_str:
            return "authentication_failed"
        elif "browser" in error_str and "launch" in error_str:
            return "browser_launch_failed"
        elif "timeout" in error_str or error_type_name == "TimeoutError":
            return "timeout"
        elif "not found" in error_str or "no such element" in error_str:
            return "element_not_found"
        elif "config" in error_str or "configuration" in error_str:
            return "configuration_error"
        elif "scenario" in error_str and "not found" in error_str:
            return "scenario_not_found"
        elif "permission denied" in error_str or error_type_name == "PermissionError":
            return "permission_denied"
        else:
            return "unknown_error"

    def format_for_console(self, report: ErrorReport) -> str:
        """
        Format error report for console display.

        Args:
            report: Error report to format

        Returns:
            Formatted string for console output
        """
        lines = [
            "\n" + "=" * 60,
            "❌ ERROR DETECTED",
            "=" * 60,
            f"Type: {report.error_type}",
            f"Time: {report.timestamp}",
            f"\nError: {report.message}",
        ]

        if report.context:
            lines.append("\nContext:")
            for key, value in report.context.items():
                lines.append(f"  {key}: {value}")

        if report.suggestions:
            lines.append("\n💡 Suggested Fixes:")
            for i, suggestion in enumerate(report.suggestions, 1):
                lines.append(f"  {i}. {suggestion}")

        if report.traceback and logger.level <= logging.DEBUG:
            lines.append("\nStack Trace:")
            lines.append(report.traceback)

        lines.append("=" * 60 + "\n")
        return "\n".join(lines)

    def save_error_log(self, path: Optional[str] = None) -> Path:
        """
        Save error log to file for analysis.

        Args:
            path: Optional path for error log

        Returns:
            Path to saved error log
        """
        if not self.errors:
            logger.info("No errors to save")
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = Path(path) if path else Path(f"logs/errors_{timestamp}.json")
        log_path.parent.mkdir(parents=True, exist_ok=True)

        error_data = {
            "timestamp": datetime.now().isoformat(),
            "total_errors": len(self.errors),
            "errors": [e.to_dict() for e in self.errors]
        }

        with open(log_path, 'w') as f:
            json.dump(error_data, f, indent=2, default=str)

        logger.info(f"Error log saved to {log_path}")
        return log_path

    def get_summary(self) -> str:
        """Get summary of all errors."""
        if not self.errors:
            return "No errors reported"

        error_types = {}
        for error in self.errors:
            error_types[error.error_type] = error_types.get(error.error_type, 0) + 1

        lines = [
            f"Total Errors: {len(self.errors)}",
            "Error Types:"
        ]
        for error_type, count in error_types.items():
            lines.append(f"  - {error_type}: {count}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all recorded errors."""
        self.errors = []

    def has_errors(self) -> bool:
        """Check if any errors have been reported."""
        return len(self.errors) > 0
