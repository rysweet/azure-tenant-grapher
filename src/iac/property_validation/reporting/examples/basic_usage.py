"""Basic usage examples for coverage reporting.

This example demonstrates:
- Creating coverage reports with metrics
- Generating HTML, Markdown, and JSON reports
- Creating interactive dashboards
- Adding historical trend data
- Saving reports to files
"""

from datetime import datetime, timedelta
from pathlib import Path

from ...models import CoverageMetrics, Criticality, PropertyGap
from ..dashboard import DashboardGenerator, HandlerCoverageSnapshot
from ..report_generator import CoverageReport, ReportGenerator


def example_1_single_handler_reports():
    """Example 1: Generate reports for a single handler."""
    print("\n" + "=" * 70)
    print("Example 1: Single Handler Reports")
    print("=" * 70 + "\n")

    # Create sample coverage metrics
    gaps = [
        PropertyGap(
            property_name="tls_version",
            criticality=Criticality.HIGH,
            reason="Security property - TLS version should be explicitly set",
            suggested_value="TLS1_2",
        ),
        PropertyGap(
            property_name="public_network_access",
            criticality=Criticality.HIGH,
            reason="Security property - public access should be explicitly configured",
            suggested_value="Disabled",
        ),
        PropertyGap(
            property_name="tags",
            criticality=Criticality.MEDIUM,
            reason="Operational property - tags recommended for resource management",
            suggested_value=None,
        ),
    ]

    metrics = CoverageMetrics(
        total_properties=12,
        covered_properties=9,
        missing_properties=3,
        coverage_percentage=75.0,
        gaps=gaps,
        critical_gaps=0,
        high_priority_gaps=2,
        medium_priority_gaps=1,
        low_priority_gaps=0,
    )

    # Create report
    report = CoverageReport(
        metrics=metrics,
        handler_name="StorageAccountHandler",
        quality_score=80.0,
        metadata={"version": "1.0", "run_id": "example_001"},
    )

    # Generate all formats
    generator = ReportGenerator()

    print("📄 Generating HTML report...")
    html = generator.generate_html(report)
    print(f"   Generated {len(html)} characters of HTML")

    print("📝 Generating Markdown report...")
    markdown = generator.generate_markdown(report)
    print(f"   Generated {len(markdown)} characters of Markdown")
    print("\nMarkdown Preview:")
    print("-" * 70)
    print(markdown[:500] + "...")
    print("-" * 70)

    print("🔧 Generating JSON report...")
    json_output = generator.generate_json(report)
    print(f"   Generated {len(json_output)} characters of JSON")

    # Save to files (optional)
    output_dir = Path("output/reports")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n💾 Saving reports to {output_dir}...")
    generator.save_report(report, output_dir / "storage_account.html", format="html")
    generator.save_report(
        report, output_dir / "storage_account.md", format="markdown"
    )
    generator.save_report(report, output_dir / "storage_account.json", format="json")

    print("✅ All reports saved successfully!")


def example_2_multi_handler_dashboard():
    """Example 2: Generate dashboard for multiple handlers."""
    print("\n" + "=" * 70)
    print("Example 2: Multi-Handler Dashboard")
    print("=" * 70 + "\n")

    # Create reports for multiple handlers
    reports = {}

    # Storage Account Handler (Good coverage)
    reports["StorageAccount"] = CoverageReport(
        metrics=CoverageMetrics(
            total_properties=12,
            covered_properties=10,
            missing_properties=2,
            coverage_percentage=83.3,
            gaps=[
                PropertyGap(
                    property_name="tls_version",
                    criticality=Criticality.HIGH,
                    reason="Security property missing",
                    suggested_value="TLS1_2",
                )
            ],
            critical_gaps=0,
            high_priority_gaps=1,
            medium_priority_gaps=0,
            low_priority_gaps=1,
        ),
        handler_name="StorageAccountHandler",
        quality_score=85.0,
    )

    # Virtual Machine Handler (Needs improvement)
    reports["VirtualMachine"] = CoverageReport(
        metrics=CoverageMetrics(
            total_properties=20,
            covered_properties=12,
            missing_properties=8,
            coverage_percentage=60.0,
            gaps=[
                PropertyGap(
                    property_name="sku_tier",
                    criticality=Criticality.CRITICAL,
                    reason="Required property with no default",
                    suggested_value="Standard",
                ),
                PropertyGap(
                    property_name="admin_password",
                    criticality=Criticality.HIGH,
                    reason="Security property - password should be set",
                    suggested_value="[secure]",
                ),
            ],
            critical_gaps=1,
            high_priority_gaps=1,
            medium_priority_gaps=3,
            low_priority_gaps=3,
        ),
        handler_name="VirtualMachineHandler",
        quality_score=50.0,
    )

    # Key Vault Handler (Excellent coverage)
    reports["KeyVault"] = CoverageReport(
        metrics=CoverageMetrics(
            total_properties=8,
            covered_properties=8,
            missing_properties=0,
            coverage_percentage=100.0,
            gaps=[],
            critical_gaps=0,
            high_priority_gaps=0,
            medium_priority_gaps=0,
            low_priority_gaps=0,
        ),
        handler_name="KeyVaultHandler",
        quality_score=100.0,
    )

    # App Service Handler (Moderate coverage)
    reports["AppService"] = CoverageReport(
        metrics=CoverageMetrics(
            total_properties=15,
            covered_properties=11,
            missing_properties=4,
            coverage_percentage=73.3,
            gaps=[
                PropertyGap(
                    property_name="https_only",
                    criticality=Criticality.HIGH,
                    reason="Security property - HTTPS should be enforced",
                    suggested_value="true",
                ),
                PropertyGap(
                    property_name="client_cert_enabled",
                    criticality=Criticality.MEDIUM,
                    reason="Security property recommended",
                    suggested_value="true",
                ),
            ],
            critical_gaps=0,
            high_priority_gaps=1,
            medium_priority_gaps=1,
            low_priority_gaps=2,
        ),
        handler_name="AppServiceHandler",
        quality_score=75.0,
    )

    print(f"📊 Generating dashboard for {len(reports)} handlers...")

    # Generate dashboard
    dashboard = DashboardGenerator()
    html = dashboard.generate_dashboard(reports)

    print(f"   Generated {len(html)} characters of HTML")
    print(f"   Overall coverage: {sum(r.metrics.coverage_percentage for r in reports.values()) / len(reports):.1f}%")
    print(f"   Overall quality: {sum(r.quality_score for r in reports.values()) / len(reports):.1f}")

    # Save dashboard
    output_dir = Path("output/dashboard")
    output_dir.mkdir(parents=True, exist_ok=True)

    dashboard_path = output_dir / "coverage_dashboard.html"
    dashboard.save_dashboard(reports, dashboard_path)

    print(f"\n💾 Dashboard saved to: {dashboard_path}")
    print("✅ Open dashboard.html in a browser to view interactive report!")


def example_3_historical_trends():
    """Example 3: Dashboard with historical trend data."""
    print("\n" + "=" * 70)
    print("Example 3: Historical Trend Tracking")
    print("=" * 70 + "\n")

    # Create current report
    current_report = CoverageReport(
        metrics=CoverageMetrics(
            total_properties=12,
            covered_properties=10,
            missing_properties=2,
            coverage_percentage=83.3,
            gaps=[],
            critical_gaps=0,
            high_priority_gaps=1,
            medium_priority_gaps=0,
            low_priority_gaps=1,
        ),
        handler_name="StorageAccountHandler",
        quality_score=85.0,
    )

    # Create historical snapshots showing improvement over time
    base_date = datetime.now() - timedelta(days=30)
    historical_data = []

    # Week 1: Poor coverage
    historical_data.append(
        HandlerCoverageSnapshot(
            handler_name="StorageAccountHandler",
            timestamp=base_date,
            coverage_percentage=50.0,
            quality_score=45.0,
            critical_gaps=2,
            high_gaps=3,
            total_properties=12,
            covered_properties=6,
        )
    )

    # Week 2: Some improvement
    historical_data.append(
        HandlerCoverageSnapshot(
            handler_name="StorageAccountHandler",
            timestamp=base_date + timedelta(days=7),
            coverage_percentage=66.7,
            quality_score=60.0,
            critical_gaps=1,
            high_gaps=2,
            total_properties=12,
            covered_properties=8,
        )
    )

    # Week 3: Good progress
    historical_data.append(
        HandlerCoverageSnapshot(
            handler_name="StorageAccountHandler",
            timestamp=base_date + timedelta(days=14),
            coverage_percentage=75.0,
            quality_score=75.0,
            critical_gaps=0,
            high_gaps=2,
            total_properties=12,
            covered_properties=9,
        )
    )

    # Week 4: Current state
    historical_data.append(
        HandlerCoverageSnapshot(
            handler_name="StorageAccountHandler",
            timestamp=base_date + timedelta(days=21),
            coverage_percentage=83.3,
            quality_score=85.0,
            critical_gaps=0,
            high_gaps=1,
            total_properties=12,
            covered_properties=10,
        )
    )

    print("📈 Historical trend data:")
    for i, snapshot in enumerate(historical_data, 1):
        print(
            f"   Week {i}: {snapshot.coverage_percentage:.1f}% coverage, "
            f"{snapshot.quality_score:.1f} quality"
        )

    # Generate dashboard with trends
    dashboard = DashboardGenerator()
    reports = {"StorageAccount": current_report}

    html = dashboard.generate_dashboard(reports, historical_data)

    # Save dashboard
    output_dir = Path("output/trends")
    output_dir.mkdir(parents=True, exist_ok=True)

    dashboard_path = output_dir / "trends_dashboard.html"
    dashboard.save_dashboard(reports, dashboard_path, historical_data)

    print(f"\n💾 Dashboard with trends saved to: {dashboard_path}")
    print("✅ Trend data is prepared for future chart visualization!")


def example_4_pr_comment_report():
    """Example 4: Generate Markdown report for PR comment."""
    print("\n" + "=" * 70)
    print("Example 4: PR Comment Report")
    print("=" * 70 + "\n")

    # Create a report that would fail PR checks
    gaps = [
        PropertyGap(
            property_name="sku_tier",
            criticality=Criticality.CRITICAL,
            reason="Required property with no default - blocks deployment",
            suggested_value="Standard",
        ),
        PropertyGap(
            property_name="tls_version",
            criticality=Criticality.HIGH,
            reason="Security property - TLS version must be explicitly set",
            suggested_value="TLS1_2",
        ),
        PropertyGap(
            property_name="public_network_access",
            criticality=Criticality.HIGH,
            reason="Security property - public access should be explicitly disabled",
            suggested_value="Disabled",
        ),
    ]

    metrics = CoverageMetrics(
        total_properties=15,
        covered_properties=12,
        missing_properties=3,
        coverage_percentage=80.0,
        gaps=gaps,
        critical_gaps=1,
        high_priority_gaps=2,
        medium_priority_gaps=0,
        low_priority_gaps=0,
    )

    report = CoverageReport(
        metrics=metrics,
        handler_name="StorageAccountHandler",
        quality_score=55.0,  # Low due to critical gap
    )

    # Generate Markdown for PR comment
    generator = ReportGenerator()
    markdown = generator.generate_markdown(report)

    print("📝 PR Comment Report (Markdown):")
    print("-" * 70)
    print(markdown)
    print("-" * 70)

    print("\n💡 This report shows FAIL status due to critical gap")
    print("   Use this in CI/CD to block PRs with critical issues!")


def main():
    """Run all examples."""
    print("\n" + "=" * 70)
    print("🚀 Property Validation Coverage Reporting Examples")
    print("=" * 70)

    example_1_single_handler_reports()
    example_2_multi_handler_dashboard()
    example_3_historical_trends()
    example_4_pr_comment_report()

    print("\n" + "=" * 70)
    print("✅ All examples completed successfully!")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
