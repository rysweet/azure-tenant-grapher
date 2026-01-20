"""Report generation for property validation coverage.

Generates coverage reports in HTML, Markdown, and JSON formats with
clear highlighting of critical and high-priority gaps.

Philosophy:
- Multiple formats for different audiences (HTML for humans, JSON for tools)
- Clear highlighting of critical issues
- Actionable recommendations
- Jinja2 templates for maintainability
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import CoverageMetrics, Criticality, PropertyGap


@dataclass
class CoverageReport:
    """Coverage report with timestamp and metadata.

    Attributes:
        metrics: Coverage metrics from analysis
        handler_name: Name of the handler analyzed
        timestamp: When the report was generated
        quality_score: Weighted quality score (0-100)
        metadata: Additional metadata (version, run_id, etc.)
    """

    metrics: CoverageMetrics
    handler_name: str
    timestamp: datetime = field(default_factory=datetime.now)
    quality_score: float = 0.0
    metadata: Dict[str, str] = field(default_factory=dict)


class ReportGenerator:
    """Generate coverage reports in multiple formats.

    Supports HTML, Markdown, and JSON output formats with consistent
    structure and highlighting of critical gaps.

    Attributes:
        template_dir: Directory containing Jinja2 templates
        env: Jinja2 environment for template rendering
    """

    def __init__(self, template_dir: Optional[Path] = None):
        """Initialize report generator.

        Args:
            template_dir: Optional custom template directory.
                         Defaults to templates/ in this module.
        """
        if template_dir is None:
            template_dir = Path(__file__).parent / "templates"

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

        # Add custom filters for templates
        self.env.filters["format_percentage"] = self._format_percentage
        self.env.filters["criticality_class"] = self._criticality_class
        self.env.filters["criticality_badge"] = self._criticality_badge

    def generate_html(self, report: CoverageReport) -> str:
        """Generate HTML report.

        Args:
            report: Coverage report to render

        Returns:
            HTML string with styled report
        """
        template = self.env.get_template("html_report.jinja2")
        return template.render(
            report=report,
            metrics=report.metrics,
            handler_name=report.handler_name,
            timestamp=report.timestamp,
            quality_score=report.quality_score,
            critical_gaps=self._filter_gaps(report.metrics.gaps, Criticality.CRITICAL),
            high_gaps=self._filter_gaps(report.metrics.gaps, Criticality.HIGH),
            medium_gaps=self._filter_gaps(report.metrics.gaps, Criticality.MEDIUM),
            low_gaps=self._filter_gaps(report.metrics.gaps, Criticality.LOW),
        )

    def generate_markdown(self, report: CoverageReport) -> str:
        """Generate Markdown report.

        Suitable for GitHub PR comments and documentation.

        Args:
            report: Coverage report to render

        Returns:
            Markdown string with report
        """
        template = self.env.get_template("markdown_report.jinja2")
        return template.render(
            report=report,
            metrics=report.metrics,
            handler_name=report.handler_name,
            timestamp=report.timestamp,
            quality_score=report.quality_score,
            critical_gaps=self._filter_gaps(report.metrics.gaps, Criticality.CRITICAL),
            high_gaps=self._filter_gaps(report.metrics.gaps, Criticality.HIGH),
            pass_threshold=70.0,  # Configurable threshold
            passes=(
                report.metrics.coverage_percentage >= 70.0
                and report.metrics.critical_gaps == 0
            ),
        )

    def generate_json(self, report: CoverageReport) -> str:
        """Generate JSON report.

        Suitable for tool integration and automated processing.

        Args:
            report: Coverage report to render

        Returns:
            JSON string with complete report data
        """
        data = {
            "handler_name": report.handler_name,
            "timestamp": report.timestamp.isoformat(),
            "quality_score": report.quality_score,
            "metadata": report.metadata,
            "metrics": {
                "total_properties": report.metrics.total_properties,
                "covered_properties": report.metrics.covered_properties,
                "missing_properties": report.metrics.missing_properties,
                "coverage_percentage": report.metrics.coverage_percentage,
                "critical_gaps": report.metrics.critical_gaps,
                "high_priority_gaps": report.metrics.high_priority_gaps,
                "medium_priority_gaps": report.metrics.medium_priority_gaps,
                "low_priority_gaps": report.metrics.low_priority_gaps,
            },
            "gaps": [
                {
                    "property_name": gap.property_name,
                    "criticality": gap.criticality.value,
                    "reason": gap.reason,
                    "suggested_value": gap.suggested_value,
                }
                for gap in report.metrics.gaps
            ],
        }
        return json.dumps(data, indent=2)

    def save_report(
        self, report: CoverageReport, output_path: Path, format: str = "html"
    ) -> None:
        """Save report to file.

        Args:
            report: Coverage report to save
            output_path: Path to save file
            format: Output format ("html", "markdown", "json")

        Raises:
            ValueError: If format is not supported
        """
        format = format.lower()
        if format == "html":
            content = self.generate_html(report)
        elif format in ("markdown", "md"):
            content = self.generate_markdown(report)
        elif format == "json":
            content = self.generate_json(report)
        else:
            raise ValueError(f"Unsupported format: {format}")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content)

    # Helper methods

    def _filter_gaps(
        self, gaps: List[PropertyGap], criticality: Criticality
    ) -> List[PropertyGap]:
        """Filter gaps by criticality level."""
        return [gap for gap in gaps if gap.criticality == criticality]

    @staticmethod
    def _format_percentage(value: float) -> str:
        """Format percentage with 1 decimal place."""
        return f"{value:.1f}"

    @staticmethod
    def _criticality_class(criticality: Criticality) -> str:
        """Get CSS class name for criticality level."""
        return {
            Criticality.CRITICAL: "critical",
            Criticality.HIGH: "high",
            Criticality.MEDIUM: "medium",
            Criticality.LOW: "low",
        }.get(criticality, "low")

    @staticmethod
    def _criticality_badge(criticality: Criticality) -> str:
        """Get emoji badge for criticality level."""
        return {
            Criticality.CRITICAL: "🔴",
            Criticality.HIGH: "🟠",
            Criticality.MEDIUM: "🟡",
            Criticality.LOW: "⚪",
        }.get(criticality, "⚪")


__all__ = ["CoverageReport", "ReportGenerator"]
