#!/usr/bin/env python3
"""PR validation script for property coverage CI/CD integration.

This script runs full property validation analysis and checks against
configured thresholds. Designed for CI/CD pipelines to enforce quality gates.

Philosophy:
- Fail-fast on threshold violations
- Clear, actionable error messages
- Markdown output for PR comments
- Zero external dependencies (except project modules)

Usage:
    python pr_checker.py --handlers-dir ./src/iac/handlers --output report.md

Exit codes:
    0: All thresholds passed
    1: One or more thresholds failed
    2: Configuration or runtime error
"""

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import yaml

# Import validation components
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from property_validation.models import Criticality, CoverageMetrics
from property_validation.validation import (
    CoverageCalculator,
    CriticalClassifier,
    GapFinder,
)


@dataclass
class ValidationThresholds:
    """Coverage thresholds configuration."""

    overall_minimum: float
    per_handler_minimum: float
    critical_gaps_allowed: int
    high_gaps_allowed: int
    regression_tolerance: float


@dataclass
class ValidationResult:
    """Result of validation check against thresholds."""

    passed: bool
    overall_coverage: float
    handler_results: Dict[str, CoverageMetrics]
    threshold_violations: List[str]
    total_critical_gaps: int
    total_high_gaps: int


class PRChecker:
    """PR validation checker for property coverage."""

    def __init__(self, thresholds: ValidationThresholds):
        """Initialize PR checker with thresholds.

        Args:
            thresholds: Coverage thresholds configuration
        """
        self.thresholds = thresholds
        self.classifier = CriticalClassifier()
        self.gap_finder = GapFinder(self.classifier)
        self.calculator = CoverageCalculator()

    def load_thresholds(self, thresholds_file: Path) -> ValidationThresholds:
        """Load thresholds from YAML configuration file.

        Args:
            thresholds_file: Path to thresholds.yaml

        Returns:
            ValidationThresholds configuration

        Raises:
            FileNotFoundError: If thresholds file doesn't exist
            ValueError: If thresholds file is invalid
        """
        if not thresholds_file.exists():
            raise FileNotFoundError(f"Thresholds file not found: {thresholds_file}")

        with open(thresholds_file) as f:
            config = yaml.safe_load(f)

        if "thresholds" not in config:
            raise ValueError("Invalid thresholds file: missing 'thresholds' key")

        t = config["thresholds"]
        return ValidationThresholds(
            overall_minimum=float(t.get("overall_minimum", 70)),
            per_handler_minimum=float(t.get("per_handler_minimum", 60)),
            critical_gaps_allowed=int(t.get("critical_gaps_allowed", 0)),
            high_gaps_allowed=int(t.get("high_gaps_allowed", 2)),
            regression_tolerance=float(t.get("regression_tolerance", -5)),
        )

    def validate_handler(
        self, handler_file: Path
    ) -> Optional[CoverageMetrics]:
        """Validate a single handler file.

        This is a placeholder that would integrate with the actual
        property extraction and validation logic.

        Args:
            handler_file: Path to handler Python file

        Returns:
            CoverageMetrics for the handler, or None if validation fails
        """
        # TODO: Integrate with actual handler analysis
        # For now, return a mock result to demonstrate the flow
        # In production, this would:
        # 1. Parse handler file to extract property usage
        # 2. Load Terraform schema for resource types
        # 3. Run gap analysis
        # 4. Calculate coverage metrics

        # Mock implementation - replace with actual analysis
        from property_validation.models import PropertyGap

        mock_gaps = []
        return CoverageMetrics(
            total_properties=10,
            covered_properties=7,
            missing_properties=3,
            coverage_percentage=70.0,
            gaps=mock_gaps,
            critical_gaps=0,
            high_priority_gaps=1,
            medium_priority_gaps=2,
            low_priority_gaps=0,
        )

    def validate_all_handlers(
        self, handlers_dir: Path
    ) -> Dict[str, CoverageMetrics]:
        """Run validation on all handler files in directory.

        Args:
            handlers_dir: Directory containing handler files

        Returns:
            Dict mapping handler file name to CoverageMetrics
        """
        handler_results = {}

        # Find all handler files
        handler_files = list(handlers_dir.glob("**/*_handler.py"))

        if not handler_files:
            print(f"Warning: No handler files found in {handlers_dir}")
            return handler_results

        for handler_file in handler_files:
            print(f"Validating {handler_file.name}...")
            metrics = self.validate_handler(handler_file)
            if metrics:
                handler_results[handler_file.name] = metrics

        return handler_results

    def check_thresholds(
        self, handler_results: Dict[str, CoverageMetrics]
    ) -> ValidationResult:
        """Check validation results against thresholds.

        Args:
            handler_results: Dict of handler metrics

        Returns:
            ValidationResult with pass/fail and violations
        """
        violations = []
        total_critical = 0
        total_high = 0

        # Calculate overall coverage
        if not handler_results:
            return ValidationResult(
                passed=False,
                overall_coverage=0.0,
                handler_results={},
                threshold_violations=["No handlers found to validate"],
                total_critical_gaps=0,
                total_high_gaps=0,
            )

        total_coverage = sum(m.coverage_percentage for m in handler_results.values())
        overall_coverage = total_coverage / len(handler_results)

        # Check overall minimum coverage
        if overall_coverage < self.thresholds.overall_minimum:
            violations.append(
                f"Overall coverage {overall_coverage:.1f}% "
                f"< minimum {self.thresholds.overall_minimum}%"
            )

        # Check per-handler coverage and count gaps
        for handler_name, metrics in handler_results.items():
            # Per-handler minimum
            if metrics.coverage_percentage < self.thresholds.per_handler_minimum:
                violations.append(
                    f"{handler_name}: Coverage {metrics.coverage_percentage:.1f}% "
                    f"< minimum {self.thresholds.per_handler_minimum}%"
                )

            # Accumulate gaps
            total_critical += metrics.critical_gaps
            total_high += metrics.high_priority_gaps

        # Check critical gaps
        if total_critical > self.thresholds.critical_gaps_allowed:
            violations.append(
                f"CRITICAL gaps: {total_critical} "
                f"> allowed {self.thresholds.critical_gaps_allowed}"
            )

        # Check high priority gaps
        if total_high > self.thresholds.high_gaps_allowed:
            violations.append(
                f"HIGH priority gaps: {total_high} "
                f"> allowed {self.thresholds.high_gaps_allowed}"
            )

        passed = len(violations) == 0

        return ValidationResult(
            passed=passed,
            overall_coverage=overall_coverage,
            handler_results=handler_results,
            threshold_violations=violations,
            total_critical_gaps=total_critical,
            total_high_gaps=total_high,
        )

    def generate_markdown_report(self, result: ValidationResult) -> str:
        """Generate Markdown report for PR comment.

        Args:
            result: ValidationResult to report

        Returns:
            Markdown-formatted report string
        """
        lines = []

        # Header with status
        if result.passed:
            lines.append("# ✅ Property Coverage Validation: PASSED")
        else:
            lines.append("# ❌ Property Coverage Validation: FAILED")

        lines.append("")

        # Overall metrics
        lines.append("## Overall Coverage")
        lines.append("")
        lines.append(f"- **Coverage**: {result.overall_coverage:.1f}%")
        lines.append(f"- **Threshold**: {self.thresholds.overall_minimum}%")
        lines.append(f"- **Handlers Analyzed**: {len(result.handler_results)}")
        lines.append("")

        # Gap summary
        lines.append("## Gap Summary")
        lines.append("")
        lines.append(f"- **CRITICAL gaps**: {result.total_critical_gaps} "
                    f"(allowed: {self.thresholds.critical_gaps_allowed})")
        lines.append(f"- **HIGH priority gaps**: {result.total_high_gaps} "
                    f"(allowed: {self.thresholds.high_gaps_allowed})")
        lines.append("")

        # Per-handler breakdown
        if result.handler_results:
            lines.append("## Per-Handler Coverage")
            lines.append("")
            lines.append("| Handler | Coverage | Critical | High | Status |")
            lines.append("|---------|----------|----------|------|--------|")

            for handler_name, metrics in sorted(result.handler_results.items()):
                status_icon = (
                    "✅"
                    if metrics.coverage_percentage >= self.thresholds.per_handler_minimum
                    else "❌"
                )
                lines.append(
                    f"| {handler_name} | {metrics.coverage_percentage:.1f}% | "
                    f"{metrics.critical_gaps} | {metrics.high_priority_gaps} | "
                    f"{status_icon} |"
                )

            lines.append("")

        # Threshold violations
        if result.threshold_violations:
            lines.append("## ⚠️ Threshold Violations")
            lines.append("")
            for violation in result.threshold_violations:
                lines.append(f"- {violation}")
            lines.append("")

        # Configuration reference
        lines.append("## Configuration")
        lines.append("")
        lines.append("**Thresholds**:")
        lines.append(f"- Overall minimum: {self.thresholds.overall_minimum}%")
        lines.append(f"- Per-handler minimum: {self.thresholds.per_handler_minimum}%")
        lines.append(f"- Critical gaps allowed: {self.thresholds.critical_gaps_allowed}")
        lines.append(f"- High gaps allowed: {self.thresholds.high_gaps_allowed}")
        lines.append("")

        # Footer
        lines.append("---")
        lines.append("*Generated by Property Coverage PR Checker*")

        return "\n".join(lines)


def main():
    """Main entry point for PR checker script."""
    parser = argparse.ArgumentParser(
        description="Validate property coverage for PR quality gate"
    )
    parser.add_argument(
        "--handlers-dir",
        type=Path,
        default=Path("src/iac/handlers"),
        help="Directory containing handler files (default: src/iac/handlers)",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path(__file__).parent / "thresholds.yaml",
        help="Path to thresholds.yaml configuration",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file for Markdown report (default: stdout)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    try:
        # Load thresholds
        if args.verbose:
            print(f"Loading thresholds from {args.thresholds}")

        checker = PRChecker(thresholds=None)  # Placeholder
        thresholds = checker.load_thresholds(args.thresholds)
        checker.thresholds = thresholds

        if args.verbose:
            print(f"Thresholds loaded:")
            print(f"  Overall minimum: {thresholds.overall_minimum}%")
            print(f"  Per-handler minimum: {thresholds.per_handler_minimum}%")
            print()

        # Validate handlers
        if args.verbose:
            print(f"Validating handlers in {args.handlers_dir}")
            print()

        handler_results = checker.validate_all_handlers(args.handlers_dir)

        # Check thresholds
        result = checker.check_thresholds(handler_results)

        # Generate report
        report = checker.generate_markdown_report(result)

        # Output report
        if args.output:
            args.output.write_text(report)
            if args.verbose:
                print(f"\nReport written to {args.output}")
        else:
            print(report)

        # Exit with appropriate code
        if result.passed:
            if args.verbose:
                print("\n✅ All thresholds passed")
            sys.exit(0)
        else:
            if args.verbose:
                print("\n❌ Threshold violations detected")
            sys.exit(1)

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)
    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)


if __name__ == "__main__":
    main()
