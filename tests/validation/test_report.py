"""Tests for report generation module."""

import json

import pytest

from src.validation.comparator import ComparisonResult
from src.validation.report import (
    _get_validation_status,
    generate_json_report,
    generate_markdown_report,
)


class TestGenerateMarkdownReport:
    """Tests for generate_markdown_report function."""

    def test_generate_report_complete_deployment(self):
        """Test report generation for complete deployment (100% similarity)."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=10,
            resource_type_counts={
                "Microsoft.Compute/virtualMachines": {"source": 5, "target": 5},
                "Microsoft.Network/virtualNetworks": {"source": 5, "target": 5},
            },
            missing_resources=[],
            extra_resources=[],
            similarity_score=100.0,
        )

        report = generate_markdown_report(result)

        assert "# Deployment Validation Report" in report
        assert "100.0%" in report
        assert "COMPLETE" in report
        assert "**Source Resources**: 10" in report
        assert "**Target Resources**: 10" in report
        assert "Microsoft.Compute/virtualMachines" in report
        assert "Microsoft.Network/virtualNetworks" in report

    def test_generate_report_with_tenant_ids(self):
        """Test report includes tenant IDs when provided."""
        result = ComparisonResult(
            source_resource_count=5,
            target_resource_count=5,
            resource_type_counts={},
            missing_resources=[],
            extra_resources=[],
            similarity_score=100.0,
        )

        report = generate_markdown_report(
            result,
            source_tenant_id="source-tenant-123",
            target_tenant_id="target-tenant-456",
        )

        assert "source-tenant-123" in report
        assert "target-tenant-456" in report

    def test_generate_report_with_missing_resources(self):
        """Test report includes missing resources section."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=8,
            resource_type_counts={
                "Microsoft.Compute/virtualMachines": {"source": 10, "target": 8}
            },
            missing_resources=["Microsoft.Compute/virtualMachines (2 missing)"],
            extra_resources=[],
            similarity_score=80.0,
        )

        report = generate_markdown_report(result)

        assert "## Missing Resources" in report
        assert "Microsoft.Compute/virtualMachines (2 missing)" in report

    def test_generate_report_with_extra_resources(self):
        """Test report includes extra resources section."""
        result = ComparisonResult(
            source_resource_count=5,
            target_resource_count=7,
            resource_type_counts={
                "Microsoft.Network/virtualNetworks": {"source": 5, "target": 7}
            },
            missing_resources=[],
            extra_resources=["Microsoft.Network/virtualNetworks (2 extra)"],
            similarity_score=71.43,
        )

        report = generate_markdown_report(result)

        assert "## Extra Resources" in report
        assert "Microsoft.Network/virtualNetworks (2 extra)" in report

    def test_generate_report_mostly_complete(self):
        """Test report for mostly complete deployment (80-95% similarity)."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=9,
            resource_type_counts={},
            missing_resources=["VM (1 missing)"],
            extra_resources=[],
            similarity_score=90.0,
        )

        report = generate_markdown_report(result)

        assert "MOSTLY COMPLETE" in report
        assert "## Recommendations" in report

    def test_generate_report_incomplete(self):
        """Test report for incomplete deployment (50-80% similarity)."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=6,
            resource_type_counts={},
            missing_resources=["VM (4 missing)"],
            extra_resources=[],
            similarity_score=60.0,
        )

        report = generate_markdown_report(result)

        assert "INCOMPLETE" in report
        assert "significant differences" in report

    def test_generate_report_failed(self):
        """Test report for failed deployment (<50% similarity)."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=3,
            resource_type_counts={},
            missing_resources=["VM (7 missing)"],
            extra_resources=[],
            similarity_score=30.0,
        )

        report = generate_markdown_report(result)

        assert "FAILED" in report
        assert "major differences" in report

    def test_resource_count_table_format(self):
        """Test that resource count comparison table is properly formatted."""
        result = ComparisonResult(
            source_resource_count=3,
            target_resource_count=3,
            resource_type_counts={
                "TypeA": {"source": 2, "target": 2},
                "TypeB": {"source": 1, "target": 1},
            },
            missing_resources=[],
            extra_resources=[],
            similarity_score=100.0,
        )

        report = generate_markdown_report(result)

        # Check table header
        assert "| Resource Type | Source | Target | Match |" in report
        # Check table separator
        assert "|---------------|--------|--------|-------|" in report
        # Check data rows
        assert "TypeA" in report
        assert "TypeB" in report


class TestGenerateJsonReport:
    """Tests for generate_json_report function."""

    def test_generate_json_report_structure(self):
        """Test that JSON report has correct structure."""
        result = ComparisonResult(
            source_resource_count=10,
            target_resource_count=10,
            resource_type_counts={"VM": {"source": 10, "target": 10}},
            missing_resources=[],
            extra_resources=[],
            similarity_score=100.0,
        )

        json_report = generate_json_report(result)

        assert "timestamp" in json_report
        assert "summary" in json_report
        assert "resource_type_counts" in json_report
        assert "missing_resources" in json_report
        assert "extra_resources" in json_report
        assert "validation_status" in json_report

    def test_json_report_summary(self):
        """Test JSON report summary contains correct data."""
        result = ComparisonResult(
            source_resource_count=15,
            target_resource_count=12,
            resource_type_counts={},
            missing_resources=["VM (3 missing)"],
            extra_resources=[],
            similarity_score=80.0,
        )

        json_report = generate_json_report(result)

        assert json_report["summary"]["similarity_score"] == 80.0
        assert json_report["summary"]["source_resource_count"] == 15
        assert json_report["summary"]["target_resource_count"] == 12
        assert json_report["summary"]["missing_count"] == 1
        assert json_report["summary"]["extra_count"] == 0

    def test_json_report_serializable(self):
        """Test that JSON report can be serialized to JSON string."""
        result = ComparisonResult(
            source_resource_count=5,
            target_resource_count=5,
            resource_type_counts={},
            missing_resources=[],
            extra_resources=[],
            similarity_score=100.0,
        )

        json_report = generate_json_report(result)

        # Should not raise exception
        json_str = json.dumps(json_report)
        assert isinstance(json_str, str)

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["summary"]["similarity_score"] == 100.0


class TestGetValidationStatus:
    """Tests for _get_validation_status helper function."""

    def test_status_complete(self):
        """Test status is 'complete' for 95%+ similarity."""
        assert _get_validation_status(100.0) == "complete"
        assert _get_validation_status(95.0) == "complete"

    def test_status_mostly_complete(self):
        """Test status is 'mostly_complete' for 80-95% similarity."""
        assert _get_validation_status(94.9) == "mostly_complete"
        assert _get_validation_status(80.0) == "mostly_complete"

    def test_status_incomplete(self):
        """Test status is 'incomplete' for 50-80% similarity."""
        assert _get_validation_status(79.9) == "incomplete"
        assert _get_validation_status(50.0) == "incomplete"

    def test_status_failed(self):
        """Test status is 'failed' for <50% similarity."""
        assert _get_validation_status(49.9) == "failed"
        assert _get_validation_status(0.0) == "failed"
