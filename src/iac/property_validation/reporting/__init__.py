"""Coverage reporting for property validation.

This module generates human-readable coverage reports in multiple formats:
HTML, Markdown, and JSON.

Philosophy:
- Multiple output formats for different audiences
- Clear, actionable reports highlighting critical gaps
- Historical trend tracking in dashboard
- Standard library + Jinja2 for templating

Public API:
    ReportGenerator: Generate reports in HTML/Markdown/JSON
    DashboardGenerator: Generate HTML dashboard with trends
    CoverageReport: Report data with timestamp
"""

from .dashboard import DashboardGenerator
from .report_generator import CoverageReport, ReportGenerator

__all__ = ["CoverageReport", "DashboardGenerator", "ReportGenerator"]
