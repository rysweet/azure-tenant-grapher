"""
Threat model report builder module.
"""

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def build_markdown(
    dfd_artifact: str,
    enriched_threats: List[Dict[str, Any]],
    spec_path: str,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Builds a Markdown threat model report from the DFD artifact, enriched threats, and spec path.
    Returns the path to the generated report, or None if failed.
    """
    if logger is None:
        logger = logging.getLogger("ThreatModelReportBuilder")

    try:
        # Compose stub Markdown content
        report_lines = [
            "# Threat Modeling Report",
            "",
            f"**Specification Path:** `{spec_path}`",
            f"**Generated:** {datetime.now(timezone.utc).isoformat()} UTC",
            "",
            "## Data Flow Diagram",
            "",
            "```mermaid",
            dfd_artifact if dfd_artifact else "(No DFD artifact provided)",
            "```",
            "",
            "## Threats (Enriched with ASB Mappings)",
            "",
        ]
        if enriched_threats:
            # Add summary table
            report_lines.append("| # | Title | Severity | STRIDE | ASB Controls |")
            report_lines.append("|---|-------|----------|--------|--------------|")
            for idx, threat in enumerate(enriched_threats, 1):
                asb_controls = threat.get("asb_controls", [])
                asb_ids = (
                    ", ".join(c["control_id"] for c in asb_controls)
                    if asb_controls
                    else "None"
                )
                stride = threat.get("stride", "")
                sev = threat.get("severity", "N/A")
                sev_display = f"**{sev}**" if sev.lower() == "high" else sev
                report_lines.append(
                    f"| {idx} | {threat.get('title', 'Untitled')} | {sev_display} | {stride} | {asb_ids} |"
                )
            report_lines.append("")

            # Add detailed threat breakdown
            for idx, threat in enumerate(enriched_threats, 1):
                report_lines.append(
                    f"### Threat {idx}: {threat.get('title', 'Untitled')}"
                )
                sev = threat.get("severity", "N/A")
                sev_display = f"**{sev}**" if sev.lower() == "high" else sev
                report_lines.append(f"- **Severity:** {sev_display}")
                report_lines.append(
                    f"- **Description:** {threat.get('description', 'N/A')}"
                )
                report_lines.append(
                    f"- **STRIDE Category:** {threat.get('stride', '')}"
                )
                asb_controls = threat.get("asb_controls", [])
                if asb_controls:
                    report_lines.append("- **ASB Controls:**")
                    for c in asb_controls:
                        report_lines.append(
                            f"  - `{c['control_id']}`: {c['title']} - {c['description']}"
                        )
                else:
                    report_lines.append("- **ASB Controls:** None")
                report_lines.append("")
        else:
            report_lines.append("_No threats identified or enrichment failed._")

        # Determine output path
        base_name = os.path.splitext(os.path.basename(spec_path))[0]
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        report_filename = f"threat_model_report_{base_name}_{timestamp}.md"
        report_dir = os.path.join(os.path.dirname(spec_path) or ".", "reports")
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, report_filename)

        # Write report
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        logger.info(f"Threat model report generated at: {report_path}")
        return report_path

    except Exception as e:
        logger.error(f"Failed to generate threat model report: {e}")
        return None
