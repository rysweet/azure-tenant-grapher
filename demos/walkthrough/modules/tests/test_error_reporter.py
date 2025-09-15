#!/usr/bin/env python3
"""Tests for ErrorReporter module"""

import pytest
import tempfile
import json
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.error_reporter import ErrorReporter, ErrorReport


class TestErrorReporter:
    """Test suite for ErrorReporter"""

    def setup_method(self):
        """Setup test environment"""
        self.reporter = ErrorReporter()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_report_creation(self):
        """Test creating error reports"""
        error = ValueError("Test error message")
        context = {"file": "test.py", "line": 42}

        report = self.reporter.report_error(error, context)

        assert report.error_type == "unknown_error"
        assert report.message == "Test error message"
        assert report.context == context
        assert len(report.suggestions) > 0

    def test_error_classification(self):
        """Test error type classification"""
        test_cases = [
            (ConnectionRefusedError("Connection refused"), "connection_refused"),
            (Exception("Authentication failed"), "authentication_failed"),
            (TimeoutError("Operation timed out"), "timeout"),
            (FileNotFoundError("Scenario not found"), "scenario_not_found"),
            (PermissionError("Permission denied"), "permission_denied"),
            (Exception("Unknown error"), "unknown_error")
        ]

        for error, expected_type in test_cases:
            report = self.reporter.report_error(error)
            assert report.error_type == expected_type

    def test_remediation_suggestions(self):
        """Test remediation suggestions for different errors"""
        connection_error = ConnectionRefusedError("Connection refused")
        report = self.reporter.report_error(connection_error)

        assert len(report.suggestions) > 0
        assert any("Check if the application is running" in s for s in report.suggestions)

    def test_console_formatting(self):
        """Test console output formatting"""
        error = ValueError("Test error")
        report = self.reporter.report_error(error, {"test": "context"})

        formatted = self.reporter.format_for_console(report)

        assert "ERROR DETECTED" in formatted
        assert "Test error" in formatted
        assert "Suggested Fixes" in formatted

    def test_save_error_log(self):
        """Test saving error log to file"""
        # Create some errors
        self.reporter.report_error(ValueError("Error 1"))
        self.reporter.report_error(TypeError("Error 2"))

        log_path = Path(self.temp_dir) / "errors.json"
        saved_path = self.reporter.save_error_log(str(log_path))

        assert saved_path == log_path
        assert log_path.exists()

        # Verify content
        with open(log_path) as f:
            data = json.load(f)

        assert data["total_errors"] == 2
        assert len(data["errors"]) == 2

    def test_error_summary(self):
        """Test error summary generation"""
        # No errors
        assert self.reporter.get_summary() == "No errors reported"

        # Add errors
        self.reporter.report_error(ConnectionRefusedError("Connection refused"))
        self.reporter.report_error(TimeoutError("Timeout"))
        self.reporter.report_error(ConnectionRefusedError("Another connection error"))

        summary = self.reporter.get_summary()

        assert "Total Errors: 3" in summary
        assert "connection_refused: 2" in summary
        assert "timeout: 1" in summary

    def test_clear_errors(self):
        """Test clearing error history"""
        self.reporter.report_error(ValueError("Error"))
        assert self.reporter.has_errors()

        self.reporter.clear()
        assert not self.reporter.has_errors()
        assert self.reporter.get_summary() == "No errors reported"

    def test_error_report_to_dict(self):
        """Test ErrorReport serialization"""
        report = ErrorReport("test_error", "Test message", {"key": "value"})
        report.add_suggestion("Try this fix")

        data = report.to_dict()

        assert data["error_type"] == "test_error"
        assert data["message"] == "Test message"
        assert data["context"]["key"] == "value"
        assert "Try this fix" in data["suggestions"]
        assert "timestamp" in data
