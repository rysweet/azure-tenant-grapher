"""
Comprehensive threat model report builder module.
Generates detailed security assessment reports with STRIDE analysis and Azure Security Benchmark mappings.
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class ThreatModelReportBuilder:
    """
    Comprehensive threat model report builder that generates detailed security assessment reports.
    Supports multiple output formats and includes STRIDE analysis, ASB mappings, and implementation guidance.
    """

    def __init__(self):
        """Initialize the report builder."""
        self.logger = logging.getLogger("ThreatModelReportBuilder")

    def build_comprehensive_report(
        self,
        dfd_artifact: str,
        enriched_threats: List[Dict[str, Any]],
        spec_path: str,
        output_format: str = "markdown",
        include_implementation_guide: bool = True,
        logger: Optional[logging.Logger] = None,
    ) -> Optional[str]:
        """
        Build a comprehensive threat model report with detailed analysis and recommendations.

        Args:
            dfd_artifact: DFD specification or artifact
            enriched_threats: List of threats with ASB control mappings
            spec_path: Path to the specification file
            output_format: Output format ('markdown', 'html', 'json')
            include_implementation_guide: Include implementation guidance
            logger: Optional logger

        Returns:
            Path to generated report or None if failed
        """
        if logger is None:
            logger = self.logger

        try:
            if output_format.lower() == "markdown":
                return self._build_markdown_report(
                    dfd_artifact,
                    enriched_threats,
                    spec_path,
                    include_implementation_guide,
                    logger,
                )
            elif output_format.lower() == "html":
                return self._build_html_report(
                    dfd_artifact,
                    enriched_threats,
                    spec_path,
                    include_implementation_guide,
                    logger,
                )
            elif output_format.lower() == "json":
                return self._build_json_report(
                    dfd_artifact,
                    enriched_threats,
                    spec_path,
                    include_implementation_guide,
                    logger,
                )
            else:
                logger.error(str(f"Unsupported output format: {output_format}"))
                return None

        except Exception as e:
            logger.error(str(f"Failed to build comprehensive report: {e}"))
            return None

    def _build_markdown_report(
        self,
        dfd_artifact: str,
        enriched_threats: List[Dict[str, Any]],
        spec_path: str,
        include_implementation_guide: bool,
        logger: logging.Logger,
    ) -> Optional[str]:
        """Build a comprehensive Markdown threat model report."""

        # Generate report content
        report_lines = []

        # Header and metadata
        report_lines.extend(self._generate_markdown_header(spec_path, enriched_threats))

        # Executive summary
        report_lines.extend(self._generate_executive_summary(enriched_threats))

        # Threat analysis overview
        report_lines.extend(self._generate_threat_overview(enriched_threats))

        # Data flow diagram
        report_lines.extend(self._generate_dfd_section(dfd_artifact))

        # Detailed threat analysis
        report_lines.extend(self._generate_detailed_threat_analysis(enriched_threats))

        # ASB control mappings
        report_lines.extend(self._generate_asb_mappings_section(enriched_threats))

        # Implementation guidance
        if include_implementation_guide:
            report_lines.extend(
                self._generate_implementation_guidance(enriched_threats)
            )

        # Risk matrix and recommendations
        report_lines.extend(self._generate_risk_matrix(enriched_threats))
        report_lines.extend(self._generate_recommendations(enriched_threats))

        # Appendices
        report_lines.extend(self._generate_appendices(enriched_threats))

        # Write report to file
        return self._write_report_file(report_lines, spec_path, "md", logger)

    def _generate_markdown_header(
        self, spec_path: str, threats: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate markdown report header."""
        total_threats = len(threats)
        critical_threats = len([t for t in threats if t.get("severity") == "Critical"])
        high_threats = len([t for t in threats if t.get("severity") == "High"])

        return [
            "# Azure Threat Model Report",
            "",
            "## Report Metadata",
            "",
            f"- **Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
            f"- **Specification:** `{os.path.basename(spec_path)}`",
            f"- **Total Threats Identified:** {total_threats}",
            f"- **Critical Threats:** {critical_threats}",
            f"- **High Severity Threats:** {high_threats}",
            "- **Analysis Framework:** STRIDE Methodology",
            "- **Security Benchmark:** Azure Security Benchmark v3",
            "",
            "---",
            "",
        ]

    def _generate_executive_summary(self, threats: List[Dict[str, Any]]) -> List[str]:
        """Generate executive summary section."""
        if not threats:
            return [
                "## Executive Summary",
                "",
                "No threats were identified during the analysis.",
                "",
            ]

        # Calculate summary statistics
        total_threats = len(threats)
        severity_counts = {}
        stride_counts = {}
        resource_types = set()

        for threat in threats:
            severity = threat.get("severity", "Unknown")
            stride = threat.get("stride", "Unknown")
            resource_type = threat.get("resource_type", "Unknown")

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            stride_counts[stride] = stride_counts.get(stride, 0) + 1
            if resource_type != "Unknown":
                resource_types.add(resource_type)

        # Risk level assessment
        critical_count = severity_counts.get("Critical", 0)
        high_count = severity_counts.get("High", 0)

        if critical_count > 0:
            risk_level = "**CRITICAL**"
            risk_description = "Immediate action required to address critical security vulnerabilities."
        elif high_count > 5:
            risk_level = "**HIGH**"
            risk_description = "High priority security issues require prompt attention."
        elif high_count > 0:
            risk_level = "**MEDIUM-HIGH**"
            risk_description = "Several high-priority security issues identified."
        else:
            risk_level = "**MEDIUM**"
            risk_description = (
                "Moderate security risks identified that should be addressed."
            )

        lines = [
            "## Executive Summary",
            "",
            f"This threat model analysis identified **{total_threats}** potential security threats across **{len(resource_types)}** Azure resource types. The overall risk assessment is {risk_level}.",
            "",
            f"**Risk Assessment:** {risk_description}",
            "",
            "### Key Findings",
            "",
        ]

        # Add severity breakdown
        for severity in ["Critical", "High", "Medium", "Low"]:
            count = severity_counts.get(severity, 0)
            if count > 0:
                lines.append(f"- **{severity} Severity:** {count} threats")

        lines.append("")

        # Add STRIDE breakdown
        lines.append("### STRIDE Category Breakdown")
        lines.append("")
        stride_names = {
            "S": "Spoofing",
            "T": "Tampering",
            "R": "Repudiation",
            "I": "Information Disclosure",
            "D": "Denial of Service",
            "E": "Elevation of Privilege",
        }

        for stride_code, stride_name in stride_names.items():
            count = stride_counts.get(stride_code, 0)
            if count > 0:
                lines.append(f"- **{stride_name} ({stride_code}):** {count} threats")

        lines.extend(["", "---", ""])
        return lines

    def _generate_threat_overview(self, threats: List[Dict[str, Any]]) -> List[str]:
        """Generate threat overview section with summary table."""
        if not threats:
            return []

        lines = [
            "## Threat Analysis Overview",
            "",
            "The following table provides a high-level overview of all identified threats:",
            "",
            "| # | Threat | Severity | STRIDE | Resource Type | ASB Controls |",
            "|---|--------|----------|--------|---------------|--------------|",
        ]

        for idx, threat in enumerate(threats, 1):
            title = threat.get("title", "Unknown Threat")
            severity = threat.get("severity", "N/A")
            stride = threat.get("stride", "")
            resource_type = threat.get("resource_type", "").replace("Microsoft.", "")

            # Get ASB control count
            asb_controls = threat.get("asb_controls", [])
            control_count = len(asb_controls)
            control_display = (
                f"{control_count} controls" if control_count > 0 else "No controls"
            )

            # Format severity with appropriate emphasis
            if severity == "Critical":
                severity_display = f"🔴 **{severity}**"
            elif severity == "High":
                severity_display = f"🟠 **{severity}**"
            elif severity == "Medium":
                severity_display = f"🟡 {severity}"
            else:
                severity_display = severity

            lines.append(
                f"| {idx} | {title} | {severity_display} | {stride} | {resource_type} | {control_display} |"
            )

        lines.extend(["", "---", ""])
        return lines

    def _generate_dfd_section(self, dfd_artifact: str) -> List[str]:
        """Generate data flow diagram section."""
        lines = [
            "## System Architecture Overview",
            "",
            "The following diagram represents the system architecture analyzed for threats:",
            "",
        ]

        if dfd_artifact and dfd_artifact.strip():
            # Check if it's a Mermaid diagram
            if any(
                keyword in dfd_artifact.lower()
                for keyword in ["flowchart", "graph", "-->", "mermaid"]
            ):
                lines.extend(["```mermaid", dfd_artifact.strip(), "```"])
            else:
                lines.extend(["```", dfd_artifact.strip(), "```"])
        else:
            lines.append(
                "*System architecture diagram not provided or could not be parsed.*"
            )

        lines.extend(["", "---", ""])
        return lines

    def _generate_detailed_threat_analysis(
        self, threats: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate detailed threat analysis section."""
        if not threats:
            return []

        lines = [
            "## Detailed Threat Analysis",
            "",
            "This section provides comprehensive analysis of each identified threat, including impact assessment, likelihood evaluation, and recommended mitigations.",
            "",
        ]

        # Group threats by severity for better organization
        threats_by_severity = {}
        for threat in threats:
            severity = threat.get("severity", "Unknown")
            if severity not in threats_by_severity:
                threats_by_severity[severity] = []
            threats_by_severity[severity].append(threat)

        # Process threats in severity order
        for severity in ["Critical", "High", "Medium", "Low", "Unknown"]:
            if severity not in threats_by_severity:
                continue

            severity_threats = threats_by_severity[severity]
            if not severity_threats:
                continue

            lines.append(f"### {severity} Severity Threats")
            lines.append("")

            for idx, threat in enumerate(severity_threats, 1):
                lines.extend(self._format_detailed_threat(threat, idx))

        lines.extend(["---", ""])
        return lines

    def _format_detailed_threat(self, threat: Dict[str, Any], index: int) -> List[str]:
        """Format detailed threat information."""
        title = threat.get("title", "Unknown Threat")
        description = threat.get("description", "No description available")
        severity = threat.get("severity", "Unknown")
        stride = threat.get("stride", "")
        stride_category = threat.get("category", "")
        element = threat.get("element", "Unknown")
        resource_type = threat.get("resource_type", "")
        impact = threat.get("impact", "Unknown")
        likelihood = threat.get("likelihood", "Unknown")

        lines = [
            f"#### T-{index}: {title}",
            "",
            f"**Resource:** {element} ({resource_type})",
            f"**STRIDE Category:** {stride_category} ({stride})",
            f"**Severity:** {severity}",
            f"**Likelihood:** {likelihood}",
            f"**Impact:** {impact}",
            "",
            "**Description:**",
            f"{description}",
            "",
        ]

        # Add ASB controls if available
        asb_controls = threat.get("asb_controls", [])
        if asb_controls:
            lines.append("**Recommended Security Controls:**")
            lines.append("")
            for control in asb_controls:
                control_id = control.get("control_id", "")
                control_title = control.get("title", "")
                control_desc = control.get("description", "")
                priority = control.get("priority", "Medium")

                lines.append(f"- **{control_id}** - {control_title}")
                lines.append(f"  - *Priority: {priority}*")
                lines.append(f"  - {control_desc}")

                # Add implementation steps if available
                implementation = control.get("implementation", [])
                if implementation:
                    lines.append("  - **Implementation Steps:**")
                    for step in implementation:
                        lines.append(f"    - {step}")
                lines.append("")

        lines.append("---")
        lines.append("")
        return lines

    def _generate_asb_mappings_section(
        self, threats: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate Azure Security Benchmark mappings section."""
        lines = [
            "## Azure Security Benchmark Control Mappings",
            "",
            "This section maps identified threats to Azure Security Benchmark (ASB) v3 controls, providing a structured approach to security implementation.",
            "",
        ]

        # Collect all unique controls
        all_controls = {}
        for threat in threats:
            asb_controls = threat.get("asb_controls", [])
            for control in asb_controls:
                control_id = control.get("control_id", "")
                if control_id and control_id not in all_controls:
                    all_controls[control_id] = control

        if not all_controls:
            lines.append("No ASB control mappings available.")
            lines.extend(["", "---", ""])
            return lines

        # Group controls by category
        controls_by_category = {}
        for control in all_controls.values():
            category = control.get("category", "Unknown")
            if category not in controls_by_category:
                controls_by_category[category] = []
            controls_by_category[category].append(control)

        # Generate control mappings by category
        for category, controls in controls_by_category.items():
            lines.append(f"### {category}")
            lines.append("")

            for control in controls:
                control_id = control.get("control_id", "")
                title = control.get("title", "")
                description = control.get("description", "")
                guidance = control.get("guidance", "")

                lines.append(f"#### {control_id}: {title}")
                lines.append("")
                lines.append(f"**Description:** {description}")
                lines.append("")
                if guidance:
                    lines.append(f"**Implementation Guidance:** {guidance}")
                    lines.append("")

        lines.extend(["---", ""])
        return lines

    def _generate_implementation_guidance(
        self, threats: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate implementation guidance section."""
        lines = [
            "## Implementation Guidance",
            "",
            "This section provides prioritized implementation recommendations based on threat severity and business impact.",
            "",
        ]

        # Collect implementation priorities
        immediate_actions = []
        high_priority = []
        medium_priority = []
        low_priority = []

        for threat in threats:
            asb_controls = threat.get("asb_controls", [])
            for control in asb_controls:
                urgency = control.get("implementation_urgency", "Medium")
                if urgency == "Immediate":
                    immediate_actions.append((threat, control))
                elif urgency == "High":
                    high_priority.append((threat, control))
                elif urgency == "Medium":
                    medium_priority.append((threat, control))
                else:
                    low_priority.append((threat, control))

        # Generate implementation roadmap
        if immediate_actions:
            lines.append("### Immediate Actions Required (Within 24 Hours)")
            lines.append("")
            for threat, control in immediate_actions:
                lines.append(
                    f"- **{control.get('control_id', '')}**: {control.get('title', '')}"
                )
                lines.append(f"  - **Threat:** {threat.get('title', '')}")
                lines.append(f"  - **Resource:** {threat.get('element', '')}")
                implementation = control.get("implementation", [])
                if implementation:
                    lines.append("  - **Actions:**")
                    for action in implementation:
                        lines.append(f"    - {action}")
                lines.append("")

        if high_priority:
            lines.append("### High Priority (Within 1 Week)")
            lines.append("")
            for threat, control in high_priority:
                lines.append(
                    f"- **{control.get('control_id', '')}**: {control.get('title', '')}"
                )
                lines.append(f"  - **Threat:** {threat.get('title', '')}")
                lines.append("")

        if medium_priority:
            lines.append("### Medium Priority (Within 1 Month)")
            lines.append("")
            for _threat, control in medium_priority:
                lines.append(
                    f"- **{control.get('control_id', '')}**: {control.get('title', '')}"
                )
                lines.append("")

        lines.extend(["---", ""])
        return lines

    def _generate_risk_matrix(self, threats: List[Dict[str, Any]]) -> List[str]:
        """Generate risk matrix section."""
        lines = [
            "## Risk Assessment Matrix",
            "",
            "The following matrix shows the distribution of threats by severity and likelihood:",
            "",
            "| Likelihood \\ Severity | Critical | High | Medium | Low |",
            "|----------------------|----------|------|--------|-----|",
        ]

        # Build risk matrix
        matrix = {}
        for threat in threats:
            severity = threat.get("severity", "Unknown")
            likelihood = threat.get("likelihood", "Unknown")

            if likelihood not in matrix:
                matrix[likelihood] = {}
            if severity not in matrix[likelihood]:
                matrix[likelihood][severity] = 0
            matrix[likelihood][severity] += 1

        # Generate matrix rows
        for likelihood in ["High", "Medium", "Low"]:
            row = f"| {likelihood} |"
            for severity in ["Critical", "High", "Medium", "Low"]:
                count = matrix.get(likelihood, {}).get(severity, 0)
                row += f" {count} |"
            lines.append(row)

        lines.extend(["", "---", ""])
        return lines

    def _generate_recommendations(self, threats: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations section."""
        lines = [
            "## Recommendations",
            "",
            "Based on the threat analysis, the following strategic recommendations are provided:",
            "",
        ]

        # Calculate high-level recommendations
        critical_threats = [t for t in threats if t.get("severity") == "Critical"]
        high_threats = [t for t in threats if t.get("severity") == "High"]

        if critical_threats:
            lines.extend(
                [
                    "### Critical Priority Recommendations",
                    "",
                    f"- **Immediate attention required** for {len(critical_threats)} critical threats",
                    "- Implement emergency incident response procedures",
                    "- Conduct security control gap analysis",
                    "- Establish continuous monitoring for affected resources",
                    "",
                ]
            )

        if high_threats:
            lines.extend(
                [
                    "### High Priority Recommendations",
                    "",
                    f"- Address {len(high_threats)} high severity threats within one week",
                    "- Implement defense-in-depth security controls",
                    "- Enhance logging and monitoring capabilities",
                    "- Conduct security awareness training for relevant teams",
                    "",
                ]
            )

        lines.extend(
            [
                "### Strategic Recommendations",
                "",
                "- Implement a formal threat modeling process as part of the development lifecycle",
                "- Establish regular security assessments and penetration testing",
                "- Develop incident response and disaster recovery procedures",
                "- Create security metrics and KPIs for continuous improvement",
                "",
                "---",
                "",
            ]
        )

        return lines

    def _generate_appendices(self, threats: List[Dict[str, Any]]) -> List[str]:
        """Generate appendices section."""
        lines = [
            "## Appendices",
            "",
            "### Appendix A: STRIDE Methodology Reference",
            "",
            "- **S - Spoofing:** Identity spoofing attacks",
            "- **T - Tampering:** Data or process tampering attacks",
            "- **R - Repudiation:** Non-repudiation attacks",
            "- **I - Information Disclosure:** Information disclosure attacks",
            "- **D - Denial of Service:** Availability attacks",
            "- **E - Elevation of Privilege:** Authorization attacks",
            "",
            "### Appendix B: Azure Security Benchmark Reference",
            "",
            "This report uses Azure Security Benchmark v3 as the foundation for security control recommendations.",
            "For complete ASB documentation, visit: https://docs.microsoft.com/en-us/security/benchmark/azure/",
            "",
            "### Appendix C: Report Generation Details",
            "",
            "- **Analysis Framework:** STRIDE Threat Modeling",
            "- **Security Benchmark:** Azure Security Benchmark v3",
            f"- **Total Threats Analyzed:** {len(threats)}",
            f"- **Report Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC",
            "",
        ]

        return lines

    def _build_html_report(
        self,
        dfd_artifact: str,
        enriched_threats: List[Dict[str, Any]],
        spec_path: str,
        include_implementation_guide: bool,
        logger: logging.Logger,
    ) -> Optional[str]:
        """Build HTML report (simplified implementation)."""
        # For now, convert markdown to HTML-friendly format
        md_lines = []
        md_lines.extend(self._generate_markdown_header(spec_path, enriched_threats))
        md_lines.extend(self._generate_executive_summary(enriched_threats))
        md_lines.extend(self._generate_detailed_threat_analysis(enriched_threats))

        # Convert to basic HTML
        html_lines = [
            "<!DOCTYPE html>",
            "<html><head><title>Threat Model Report</title>",
            "<style>body{font-family:Arial,sans-serif;margin:40px;} h1,h2,h3{color:#333;} table{border-collapse:collapse;width:100%;} th,td{border:1px solid #ddd;padding:8px;text-align:left;} th{background-color:#f2f2f2;}</style>",
            "</head><body>",
        ]

        # Simple markdown to HTML conversion
        for line in md_lines:
            if line.startswith("# "):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith("## "):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith("### "):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            elif line.strip() == "":
                html_lines.append("<br>")
            else:
                html_lines.append(f"<p>{line}</p>")

        html_lines.append("</body></html>")

        return self._write_report_file(html_lines, spec_path, "html", logger)

    def _build_json_report(
        self,
        dfd_artifact: str,
        enriched_threats: List[Dict[str, Any]],
        spec_path: str,
        include_implementation_guide: bool,
        logger: logging.Logger,
    ) -> Optional[str]:
        """Build JSON report."""
        report_data = {
            "metadata": {
                "generated": datetime.now(timezone.utc).isoformat(),
                "specification": spec_path,
                "total_threats": len(enriched_threats),
                "analysis_framework": "STRIDE",
                "security_benchmark": "Azure Security Benchmark v3",
            },
            "dfd_artifact": dfd_artifact,
            "threats": enriched_threats,
            "summary": self._generate_summary_statistics(enriched_threats),
        }

        json_content = json.dumps(report_data, indent=2, ensure_ascii=False)
        return self._write_report_file([json_content], spec_path, "json", logger)

    def _generate_summary_statistics(
        self, threats: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate summary statistics for JSON report."""
        severity_counts = {}
        stride_counts = {}
        resource_types = set()

        for threat in threats:
            severity = threat.get("severity", "Unknown")
            stride = threat.get("stride", "Unknown")
            resource_type = threat.get("resource_type", "")

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            stride_counts[stride] = stride_counts.get(stride, 0) + 1
            if resource_type:
                resource_types.add(resource_type)

        return {
            "total_threats": len(threats),
            "severity_distribution": severity_counts,
            "stride_distribution": stride_counts,
            "resource_types_analyzed": len(resource_types),
            "unique_resource_types": list(resource_types),
        }

    def _write_report_file(
        self,
        content_lines: List[str],
        spec_path: str,
        extension: str,
        logger: logging.Logger,
    ) -> Optional[str]:
        """Write report content to file."""
        try:
            # Determine output path
            base_name = os.path.splitext(os.path.basename(spec_path))[0]
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            report_filename = f"threat_model_report_{base_name}_{timestamp}.{extension}"
            report_dir = os.path.join(os.path.dirname(spec_path) or ".", "reports")
            os.makedirs(report_dir, exist_ok=True)
            report_path = os.path.join(report_dir, report_filename)

            # Write report
            with open(report_path, "w", encoding="utf-8") as f:
                if extension == "json":
                    f.write(content_lines[0])  # JSON is already a single string
                else:
                    f.write("\n".join(content_lines))

            logger.info(str(f"Threat model report generated at: {report_path}"))
            return report_path

        except Exception as e:
            logger.error(str(f"Failed to write report file: {e}"))
            return None


def build_markdown(
    dfd_artifact: str,
    enriched_threats: List[Dict[str, Any]],
    spec_path: str,
    logger: Optional[logging.Logger] = None,
) -> Optional[str]:
    """
    Legacy function for compatibility.
    Builds a comprehensive Markdown threat model report.
    """
    builder = ThreatModelReportBuilder()
    return builder.build_comprehensive_report(
        dfd_artifact, enriched_threats, spec_path, "markdown", True, logger
    )
