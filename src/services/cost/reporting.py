"""Cost reporting module for Markdown and JSON reports.

This module provides report generation capabilities for cost data,
including summaries, forecasts, and anomalies in multiple formats.
"""

import json
from datetime import datetime
from typing import Optional

from ...models.cost_models import CostAnomaly, CostSummary, ForecastData


class DataValidationError(Exception):
    """Exception raised when data validation fails."""

    pass


class CostReporter:
    """Service for generating cost reports.

    This service creates formatted reports from cost data in
    markdown or JSON format, including summaries, forecasts, and anomalies.
    """

    def generate_markdown_report(
        self,
        summary: CostSummary,
        forecast: Optional[list[ForecastData]] = None,
        anomalies: Optional[list[CostAnomaly]] = None,
    ) -> str:
        """Generate markdown cost report.

        Args:
            summary: Cost summary data
            forecast: Optional forecast data
            anomalies: Optional anomaly data

        Returns:
            Markdown report string
        """
        report = []
        report.append("# Azure Cost Report\n")
        report.append(f"**Scope:** {summary.scope}\n")
        report.append(f"**Period:** {summary.start_date} to {summary.end_date}\n")
        report.append(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Summary section
        report.append("## Summary\n")
        report.append(
            f"- **Total Cost:** {summary.total_cost:.2f} {summary.currency}\n"
        )
        report.append(f"- **Resources:** {summary.resource_count}\n")
        report.append(
            f"- **Average Daily Cost:** {summary.average_daily_cost:.2f} {summary.currency}\n"
        )
        report.append(
            f"- **Average Cost per Resource:** {summary.average_cost_per_resource:.2f} {summary.currency}\n\n"
        )

        # Service breakdown
        if summary.service_breakdown:
            report.append("## Cost by Service\n")
            report.append("| Service | Cost | Percentage |\n")
            report.append("|---------|------|------------|\n")
            for service, cost in sorted(
                summary.service_breakdown.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                percentage = (
                    (cost / summary.total_cost * 100) if summary.total_cost > 0 else 0
                )
                report.append(
                    f"| {service} | {cost:.2f} {summary.currency} | {percentage:.1f}% |\n"
                )
            report.append("\n")

        # Forecast section
        if forecast:
            report.append("## 30-Day Forecast\n")
            total_forecast = sum(f.predicted_cost for f in forecast)
            report.append(
                f"- **Predicted Total:** {total_forecast:.2f} {summary.currency}\n"
            )
            report.append(
                f"- **Daily Average:** {total_forecast / len(forecast):.2f} {summary.currency}\n\n"
            )

            report.append("| Date | Predicted Cost | Confidence Range |\n")
            report.append("|------|----------------|------------------|\n")
            for f in forecast[:7]:  # Show first 7 days
                report.append(
                    f"| {f.forecast_date} | {f.predicted_cost:.2f} | "
                    f"{f.confidence_lower:.2f} - {f.confidence_upper:.2f} |\n"
                )
            report.append("\n")

        # Anomalies section
        if anomalies:
            report.append(f"## Cost Anomalies ({len(anomalies)} detected)\n")
            report.append(
                "| Date | Resource | Expected | Actual | Deviation | Severity |\n"
            )
            report.append(
                "|------|----------|----------|--------|-----------|----------|\n"
            )

            # Sort by severity and date
            sorted_anomalies = sorted(
                anomalies,
                key=lambda a: (a.severity.value, a.date),
                reverse=True,
            )

            for a in sorted_anomalies[:20]:  # Show top 20
                report.append(
                    f"| {a.date} | {a.resource_id.split('/')[-1]} | "
                    f"{a.expected_cost:.2f} | {a.actual_cost:.2f} | "
                    f"{a.deviation_percent:+.1f}% | {a.severity.value} |\n"
                )
            report.append("\n")

        return "".join(report)

    def generate_json_report(
        self,
        summary: CostSummary,
        forecast: Optional[list[ForecastData]] = None,
        anomalies: Optional[list[CostAnomaly]] = None,
    ) -> str:
        """Generate JSON cost report.

        Args:
            summary: Cost summary data
            forecast: Optional forecast data
            anomalies: Optional anomaly data

        Returns:
            JSON report string
        """
        report = {
            "scope": summary.scope,
            "period": {
                "start_date": summary.start_date.isoformat(),
                "end_date": summary.end_date.isoformat(),
            },
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_cost": summary.total_cost,
                "currency": summary.currency,
                "resource_count": summary.resource_count,
                "average_daily_cost": summary.average_daily_cost,
                "average_cost_per_resource": summary.average_cost_per_resource,
            },
            "service_breakdown": summary.service_breakdown,
        }

        if forecast:
            report["forecast"] = [
                {
                    "date": f.forecast_date.isoformat(),
                    "predicted_cost": f.predicted_cost,
                    "confidence_lower": f.confidence_lower,
                    "confidence_upper": f.confidence_upper,
                }
                for f in forecast
            ]

        if anomalies:
            report["anomalies"] = [
                {
                    "resource_id": a.resource_id,
                    "date": a.date.isoformat(),
                    "expected_cost": a.expected_cost,
                    "actual_cost": a.actual_cost,
                    "deviation_percent": a.deviation_percent,
                    "severity": a.severity.value,
                }
                for a in anomalies
            ]

        return json.dumps(report, indent=2)

    def generate_csv_summary(
        self,
        summary: CostSummary,
    ) -> str:
        """Generate CSV format cost summary.

        Args:
            summary: Cost summary data

        Returns:
            CSV formatted string
        """
        lines = []
        lines.append("Metric,Value")
        lines.append(f"Scope,{summary.scope}")
        lines.append(f"Start Date,{summary.start_date.isoformat()}")
        lines.append(f"End Date,{summary.end_date.isoformat()}")
        lines.append(f"Total Cost,{summary.total_cost}")
        lines.append(f"Currency,{summary.currency}")
        lines.append(f"Resource Count,{summary.resource_count}")
        lines.append(f"Average Daily Cost,{summary.average_daily_cost:.2f}")
        lines.append(
            f"Average Cost per Resource,{summary.average_cost_per_resource:.2f}"
        )

        if summary.service_breakdown:
            lines.append("\nService,Cost,Percentage")
            for service, cost in sorted(
                summary.service_breakdown.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                percentage = (
                    (cost / summary.total_cost * 100) if summary.total_cost > 0 else 0
                )
                lines.append(f"{service},{cost:.2f},{percentage:.1f}")

        return "\n".join(lines)

    def format_forecast_table(
        self,
        forecasts: list[ForecastData],
    ) -> str:
        """Format forecast data as ASCII table.

        Args:
            forecasts: List of forecast data

        Returns:
            ASCII table string
        """
        if not forecasts:
            return "No forecast data available"

        lines = []
        lines.append(f"{'Date':<12} {'Predicted Cost':>15} {'Confidence Range':>25}")
        lines.append("-" * 55)

        for f in forecasts:
            lines.append(
                f"{f.forecast_date!s:<12} "
                f"{f.predicted_cost:>15.2f} "
                f"{f.confidence_lower:>10.2f} - {f.confidence_upper:<10.2f}"
            )

        return "\n".join(lines)

    def format_anomaly_summary(
        self,
        anomalies: list[CostAnomaly],
    ) -> str:
        """Format anomaly summary as text.

        Args:
            anomalies: List of anomalies

        Returns:
            Summary text
        """
        if not anomalies:
            return "No anomalies detected"

        by_severity = {}
        for anomaly in anomalies:
            severity = anomaly.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1

        lines = []
        lines.append(f"Total Anomalies Detected: {len(anomalies)}\n")
        lines.append("Breakdown by Severity:")

        for severity in ["critical", "high", "medium", "low"]:
            count = by_severity.get(severity, 0)
            if count > 0:
                lines.append(f"  - {severity.title()}: {count}")

        increases = len([a for a in anomalies if a.is_increase])
        decreases = len([a for a in anomalies if a.is_decrease])
        lines.append(f"\nCost Increases: {increases}")
        lines.append(f"Cost Decreases: {decreases}")

        return "\n".join(lines)

    def validate_output_format(self, output_format: str) -> bool:
        """Validate output format.

        Args:
            output_format: Format to validate

        Returns:
            True if valid, raises exception otherwise

        Raises:
            DataValidationError: If format is invalid
        """
        valid_formats = ["markdown", "json", "csv"]
        if output_format.lower() not in valid_formats:
            raise DataValidationError(
                f"Unsupported output format: {output_format}. "
                f"Valid formats are: {', '.join(valid_formats)}"
            )
        return True
