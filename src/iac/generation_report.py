"""Generation reporting module for IaC generation pipeline.

This module provides comprehensive metrics and reporting for the IaC generation
process, tracking everything from graph traversal through Terraform emission.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class UnsupportedTypeInfo:
    """Information about an unsupported resource type."""

    resource_type: str
    count: int
    examples: List[str] = field(default_factory=list)


@dataclass
class GenerationMetrics:
    """Metrics collected during IaC generation process."""

    # Source Analysis
    source_resources_scanned: int = 0
    source_non_deployable: int = 0
    source_unsupported: int = 0
    source_deployable: int = 0

    # Terraform Generation
    terraform_resources_generated: int = 0
    terraform_files_created: int = 0
    terraform_success_rate: float = 0.0

    # Cross-Tenant Translation (optional)
    translation_enabled: bool = False
    translation_identities_mapped: int = 0
    translation_users_mapped: int = 0
    translation_groups_mapped: int = 0
    translation_sps_mapped: int = 0

    # Terraform Import (optional)
    import_enabled: bool = False
    import_strategy: Optional[str] = None
    import_commands_generated: int = 0

    # Unsupported Types Analysis
    unsupported_types: Dict[str, UnsupportedTypeInfo] = field(default_factory=dict)

    def calculate_success_rate(self) -> None:
        """Calculate the Terraform generation success rate."""
        if self.source_deployable > 0:
            self.terraform_success_rate = (
                self.terraform_resources_generated / self.source_deployable
            ) * 100.0
        else:
            self.terraform_success_rate = 0.0


@dataclass
class GenerationReport:
    """Complete generation report with metrics and formatting."""

    metrics: GenerationMetrics
    output_directory: Path
    timestamp: str

    def format_report(self) -> str:
        """Format the generation report as a human-readable string.

        Returns:
            Formatted report string ready for display.
        """
        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append("IaC GENERATION REPORT")
        lines.append("=" * 80)
        lines.append("")

        # Source Analysis Section
        lines.append("SOURCE ANALYSIS")
        lines.append("-" * 80)
        lines.append(
            f"  Resources Scanned:        {self.metrics.source_resources_scanned}"
        )
        lines.append(
            f"  Non-Deployable Resources: {self.metrics.source_non_deployable}"
        )
        lines.append(f"  Unsupported Types:        {self.metrics.source_unsupported}")
        lines.append(f"  Deployable Resources:     {self.metrics.source_deployable}")
        lines.append("")

        # Terraform Generation Section
        lines.append("TERRAFORM GENERATION")
        lines.append("-" * 80)
        lines.append(
            f"  Resources Generated:      {self.metrics.terraform_resources_generated}"
        )
        lines.append(
            f"  Files Created:            {self.metrics.terraform_files_created}"
        )
        lines.append(
            f"  Success Rate:             {self.metrics.terraform_success_rate:.1f}%"
        )
        lines.append("")

        # Cross-Tenant Translation Section (if applicable)
        if self.metrics.translation_enabled:
            lines.append("CROSS-TENANT TRANSLATION")
            lines.append("-" * 80)
            lines.append(
                f"  Total Identities Mapped:  {self.metrics.translation_identities_mapped}"
            )
            lines.append(
                f"    Users:                  {self.metrics.translation_users_mapped}"
            )
            lines.append(
                f"    Groups:                 {self.metrics.translation_groups_mapped}"
            )
            lines.append(
                f"    Service Principals:     {self.metrics.translation_sps_mapped}"
            )
            lines.append("")

        # Terraform Import Section (if applicable)
        if self.metrics.import_enabled:
            lines.append("TERRAFORM IMPORT")
            lines.append("-" * 80)
            lines.append(
                f"  Import Strategy:          {self.metrics.import_strategy or 'N/A'}"
            )
            lines.append(
                f"  Import Commands:          {self.metrics.import_commands_generated}"
            )
            lines.append("")

        # Unsupported Resource Types Section
        if self.metrics.unsupported_types:
            lines.append("UNSUPPORTED RESOURCE TYPES (Top 10)")
            lines.append("-" * 80)

            # Sort by count (descending) and take top 10
            sorted_types = sorted(
                self.metrics.unsupported_types.values(),
                key=lambda x: x.count,
                reverse=True,
            )[:10]

            for type_info in sorted_types:
                lines.append(f"  {type_info.resource_type}")
                lines.append(f"    Count: {type_info.count}")
                if type_info.examples:
                    # Show first 2 examples
                    examples_str = ", ".join(type_info.examples[:2])
                    lines.append(f"    Examples: {examples_str}")
                lines.append("")

        # Next Steps Section
        lines.append("NEXT STEPS")
        lines.append("-" * 80)
        lines.append(f"  1. Review generated files in: {self.output_directory}")
        lines.append("  2. Run: terraform init")
        lines.append("  3. Run: terraform plan")
        lines.append("  4. Run: terraform apply")
        if self.metrics.unsupported_types:
            lines.append(
                f"  5. Consider adding support for {len(self.metrics.unsupported_types)} unsupported types"
            )
        lines.append("")

        # Notes Section
        lines.append("NOTES")
        lines.append("-" * 80)
        if self.metrics.source_non_deployable > 0:
            lines.append(
                f"  • {self.metrics.source_non_deployable} non-deployable resources were skipped "
                "(subscriptions, tenants, etc.)"
            )
        if self.metrics.source_unsupported > 0:
            lines.append(
                f"  • {self.metrics.source_unsupported} resources have unsupported types "
                "and cannot be generated"
            )
        if self.metrics.terraform_success_rate < 100.0:
            missing = (
                self.metrics.source_deployable
                - self.metrics.terraform_resources_generated
            )
            lines.append(
                f"  • {missing} deployable resources were not generated "
                "(may require additional emitter support)"
            )
        if not self.metrics.translation_enabled and not self.metrics.import_enabled:
            lines.append("  • This was a standard same-tenant deployment")
        lines.append("")
        lines.append("=" * 80)
        lines.append("")

        return "\n".join(lines)

    def save_to_file(self, filename: str = "generation_report.txt") -> Path:
        """Save the report to a file in the output directory.

        Args:
            filename: Name of the report file (default: generation_report.txt)

        Returns:
            Path to the saved report file.
        """
        report_path = self.output_directory / filename
        report_content = self.format_report()

        try:
            with open(report_path, "w") as f:
                f.write(report_content)
            return report_path
        except Exception as e:
            # Non-blocking - log error but don't fail generation
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to save generation report: {e}")
            return report_path
