"""Interactive HTML dashboard for property validation coverage.

Generates comprehensive dashboards with:
- Overall coverage display
- Per-handler breakdown
- Historical trends
- Gap highlighting
- Sortable tables

Philosophy:
- Self-contained HTML with inline CSS/JS
- No external dependencies in browser
- Responsive design
- Historical trend visualization
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .report_generator import CoverageReport


@dataclass
class HandlerCoverageSnapshot:
    """Single handler's coverage at a point in time.

    Attributes:
        handler_name: Name of the handler
        timestamp: When this snapshot was taken
        coverage_percentage: Overall coverage percentage
        quality_score: Weighted quality score
        critical_gaps: Number of critical gaps
        high_gaps: Number of high-priority gaps
        total_properties: Total number of properties
        covered_properties: Number of covered properties
    """

    handler_name: str
    timestamp: datetime
    coverage_percentage: float
    quality_score: float
    critical_gaps: int
    high_gaps: int
    total_properties: int
    covered_properties: int


@dataclass
class DashboardData:
    """Complete dashboard data with historical trends.

    Attributes:
        current_reports: Current coverage reports by handler
        historical_snapshots: Historical coverage data for trends
        overall_coverage: Overall coverage across all handlers
        overall_quality: Overall quality score across all handlers
        total_handlers: Total number of handlers analyzed
        timestamp: When dashboard was generated
    """

    current_reports: Dict[str, CoverageReport] = field(default_factory=dict)
    historical_snapshots: List[HandlerCoverageSnapshot] = field(default_factory=list)
    overall_coverage: float = 0.0
    overall_quality: float = 0.0
    total_handlers: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


class DashboardGenerator:
    """Generate interactive HTML dashboard for coverage analysis.

    Creates self-contained HTML dashboards with:
    - Large overall coverage display
    - Sortable handler breakdown table
    - Critical/High gap highlighting
    - Historical trend charts
    - Drill-down to specific gaps
    """

    def __init__(self):
        """Initialize dashboard generator."""
        pass

    def generate_dashboard(
        self,
        reports: Dict[str, CoverageReport],
        historical_data: Optional[List[HandlerCoverageSnapshot]] = None,
    ) -> str:
        """Generate complete HTML dashboard.

        Args:
            reports: Dictionary mapping handler names to coverage reports
            historical_data: Optional historical snapshots for trend charts

        Returns:
            Self-contained HTML string with dashboard
        """
        dashboard_data = self._prepare_dashboard_data(reports, historical_data or [])
        return self._render_dashboard_html(dashboard_data)

    def save_dashboard(
        self,
        reports: Dict[str, CoverageReport],
        output_path: Path,
        historical_data: Optional[List[HandlerCoverageSnapshot]] = None,
    ) -> None:
        """Save dashboard to HTML file.

        Args:
            reports: Dictionary mapping handler names to coverage reports
            output_path: Path to save HTML file
            historical_data: Optional historical snapshots for trends
        """
        html = self.generate_dashboard(reports, historical_data)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html)

    def _prepare_dashboard_data(
        self,
        reports: Dict[str, CoverageReport],
        historical_data: List[HandlerCoverageSnapshot],
    ) -> DashboardData:
        """Prepare dashboard data from reports.

        Args:
            reports: Handler coverage reports
            historical_data: Historical snapshots

        Returns:
            Complete dashboard data
        """
        total_handlers = len(reports)
        if total_handlers == 0:
            return DashboardData(
                current_reports={},
                historical_snapshots=historical_data,
                overall_coverage=0.0,
                overall_quality=0.0,
                total_handlers=0,
            )

        # Calculate overall metrics
        total_coverage = sum(r.metrics.coverage_percentage for r in reports.values())
        overall_coverage = total_coverage / total_handlers

        total_quality = sum(r.quality_score for r in reports.values())
        overall_quality = total_quality / total_handlers

        return DashboardData(
            current_reports=reports,
            historical_snapshots=historical_data,
            overall_coverage=overall_coverage,
            overall_quality=overall_quality,
            total_handlers=total_handlers,
        )

    def _render_dashboard_html(self, data: DashboardData) -> str:
        """Render dashboard as self-contained HTML.

        Args:
            data: Dashboard data to render

        Returns:
            Complete HTML string
        """
        # Prepare handler table data
        handler_rows = []
        for handler_name, report in sorted(data.current_reports.items()):
            handler_rows.append(
                {
                    "handler_name": handler_name,
                    "coverage": report.metrics.coverage_percentage,
                    "quality_score": report.quality_score,
                    "total": report.metrics.total_properties,
                    "covered": report.metrics.covered_properties,
                    "missing": report.metrics.missing_properties,
                    "critical": report.metrics.critical_gaps,
                    "high": report.metrics.high_priority_gaps,
                    "medium": report.metrics.medium_priority_gaps,
                    "low": report.metrics.low_priority_gaps,
                    "gaps": [
                        {
                            "property": gap.property_name,
                            "criticality": gap.criticality.value,
                            "reason": gap.reason,
                            "suggestion": gap.suggested_value or "N/A",
                        }
                        for gap in report.metrics.gaps
                    ],
                }
            )

        # Prepare historical trend data
        historical_json = json.dumps(
            [
                {
                    "handler": snap.handler_name,
                    "timestamp": snap.timestamp.isoformat(),
                    "coverage": snap.coverage_percentage,
                    "quality": snap.quality_score,
                }
                for snap in data.historical_snapshots
            ]
        )

        # Generate self-contained HTML
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Property Validation Coverage Dashboard</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            padding: 30px;
        }}

        h1 {{
            color: #333;
            margin-bottom: 10px;
            font-size: 2.5em;
        }}

        .timestamp {{
            color: #666;
            font-size: 0.9em;
            margin-bottom: 30px;
        }}

        .overview {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 40px;
        }}

        .metric-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 8px;
            text-align: center;
        }}

        .metric-card.quality {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}

        .metric-card.handlers {{
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }}

        .metric-value {{
            font-size: 3em;
            font-weight: bold;
            margin: 10px 0;
        }}

        .metric-label {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .section {{
            margin-bottom: 40px;
        }}

        .section h2 {{
            color: #333;
            margin-bottom: 20px;
            font-size: 1.8em;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
        }}

        th {{
            background: #667eea;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            cursor: pointer;
            user-select: none;
        }}

        th:hover {{
            background: #5568d3;
        }}

        th.sorted-asc::after {{
            content: " ▲";
        }}

        th.sorted-desc::after {{
            content: " ▼";
        }}

        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}

        tr:hover {{
            background: #f9f9f9;
        }}

        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.85em;
            font-weight: 600;
        }}

        .badge.critical {{
            background: #dc3545;
            color: white;
        }}

        .badge.high {{
            background: #fd7e14;
            color: white;
        }}

        .badge.medium {{
            background: #ffc107;
            color: #333;
        }}

        .badge.low {{
            background: #6c757d;
            color: white;
        }}

        .coverage-bar {{
            width: 100%;
            height: 20px;
            background: #e9ecef;
            border-radius: 10px;
            overflow: hidden;
        }}

        .coverage-fill {{
            height: 100%;
            background: linear-gradient(90deg, #28a745 0%, #20c997 100%);
            transition: width 0.3s;
        }}

        .coverage-fill.low {{
            background: linear-gradient(90deg, #dc3545 0%, #fd7e14 100%);
        }}

        .coverage-fill.medium {{
            background: linear-gradient(90deg, #ffc107 0%, #fd7e14 100%);
        }}

        .gap-details {{
            display: none;
            margin-top: 10px;
            padding: 15px;
            background: #f8f9fa;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }}

        .gap-details.show {{
            display: block;
        }}

        .gap-item {{
            padding: 8px 0;
            border-bottom: 1px solid #dee2e6;
        }}

        .gap-item:last-child {{
            border-bottom: none;
        }}

        .expand-btn {{
            background: #667eea;
            color: white;
            border: none;
            padding: 6px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85em;
        }}

        .expand-btn:hover {{
            background: #5568d3;
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Property Validation Coverage Dashboard</h1>
        <div class="timestamp">Generated: {data.timestamp.strftime("%Y-%m-%d %H:%M:%S")}</div>

        <div class="overview">
            <div class="metric-card">
                <div class="metric-label">Overall Coverage</div>
                <div class="metric-value">{data.overall_coverage:.1f}%</div>
            </div>
            <div class="metric-card quality">
                <div class="metric-label">Quality Score</div>
                <div class="metric-value">{data.overall_quality:.1f}</div>
            </div>
            <div class="metric-card handlers">
                <div class="metric-label">Handlers Analyzed</div>
                <div class="metric-value">{data.total_handlers}</div>
            </div>
        </div>

        <div class="section">
            <h2>Handler Breakdown</h2>
            {self._render_handler_table(handler_rows) if handler_rows else '<div class="no-data">No handlers analyzed</div>'}
        </div>
    </div>

    <script>
        // Historical data for future trend charts
        const historicalData = {historical_json};

        // Table sorting functionality
        let sortColumn = null;
        let sortAscending = true;

        function sortTable(columnIndex) {{
            const table = document.querySelector('table');
            const tbody = table.querySelector('tbody');
            const rows = Array.from(tbody.querySelectorAll('tr'));

            // Update sort indicators
            const headers = table.querySelectorAll('th');
            headers.forEach((h, i) => {{
                h.classList.remove('sorted-asc', 'sorted-desc');
                if (i === columnIndex) {{
                    h.classList.add(sortAscending ? 'sorted-asc' : 'sorted-desc');
                }}
            }});

            // Sort rows
            rows.sort((a, b) => {{
                const aVal = a.cells[columnIndex].textContent.trim();
                const bVal = b.cells[columnIndex].textContent.trim();

                const aNum = parseFloat(aVal);
                const bNum = parseFloat(bVal);

                let comparison = 0;
                if (!isNaN(aNum) && !isNaN(bNum)) {{
                    comparison = aNum - bNum;
                }} else {{
                    comparison = aVal.localeCompare(bVal);
                }}

                return sortAscending ? comparison : -comparison;
            }});

            // Toggle sort direction for next click
            if (sortColumn === columnIndex) {{
                sortAscending = !sortAscending;
            }} else {{
                sortAscending = true;
                sortColumn = columnIndex;
            }}

            // Reorder rows
            rows.forEach(row => tbody.appendChild(row));
        }}

        // Gap details toggle
        function toggleGaps(button) {{
            const details = button.nextElementSibling;
            details.classList.toggle('show');
            button.textContent = details.classList.contains('show') ? 'Hide Gaps' : 'Show Gaps';
        }}
    </script>
</body>
</html>"""

        return html

    def _render_handler_table(self, handler_rows: List[Dict]) -> str:
        """Render handler breakdown table.

        Args:
            handler_rows: List of handler data dictionaries

        Returns:
            HTML table string
        """
        rows_html = []
        for idx, row in enumerate(handler_rows):
            coverage_class = (
                "low"
                if row["coverage"] < 50
                else "medium"
                if row["coverage"] < 80
                else ""
            )

            # Build gaps list
            gaps_html = ""
            if row["gaps"]:
                gaps_items = []
                for gap in row["gaps"]:
                    criticality_class = gap["criticality"]
                    gaps_items.append(
                        f'<div class="gap-item">'
                        f'<span class="badge {criticality_class}">{gap["criticality"].upper()}</span> '
                        f"<strong>{gap['property']}</strong>: {gap['reason']}<br>"
                        f"<small>Suggested: {gap['suggestion']}</small>"
                        f"</div>"
                    )
                gaps_html = "".join(gaps_items)

            critical_badge = (
                f'<span class="badge critical">{row["critical"]}</span>'
                if row["critical"] > 0
                else str(row["critical"])
            )
            high_badge = (
                f'<span class="badge high">{row["high"]}</span>'
                if row["high"] > 0
                else str(row["high"])
            )

            rows_html.append(
                f"""<tr>
                <td>{row["handler_name"]}</td>
                <td>
                    <div class="coverage-bar">
                        <div class="coverage-fill {coverage_class}" style="width: {row["coverage"]:.1f}%"></div>
                    </div>
                    {row["coverage"]:.1f}%
                </td>
                <td>{row["quality_score"]:.1f}</td>
                <td>{row["total"]}</td>
                <td>{row["covered"]}</td>
                <td>{row["missing"]}</td>
                <td>{critical_badge}</td>
                <td>{high_badge}</td>
                <td>{row["medium"]}</td>
                <td>{row["low"]}</td>
                <td>
                    {f'<button class="expand-btn" onclick="toggleGaps(this)">Show Gaps</button><div class="gap-details">{gaps_html}</div>' if gaps_html else "None"}
                </td>
            </tr>"""
            )

        return f"""<table>
            <thead>
                <tr>
                    <th onclick="sortTable(0)">Handler</th>
                    <th onclick="sortTable(1)">Coverage</th>
                    <th onclick="sortTable(2)">Quality</th>
                    <th onclick="sortTable(3)">Total</th>
                    <th onclick="sortTable(4)">Covered</th>
                    <th onclick="sortTable(5)">Missing</th>
                    <th onclick="sortTable(6)">Critical</th>
                    <th onclick="sortTable(7)">High</th>
                    <th onclick="sortTable(8)">Medium</th>
                    <th onclick="sortTable(9)">Low</th>
                    <th>Gaps</th>
                </tr>
            </thead>
            <tbody>
                {"".join(rows_html)}
            </tbody>
        </table>"""


__all__ = ["DashboardData", "DashboardGenerator", "HandlerCoverageSnapshot"]
