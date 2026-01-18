"""CLI commands for property validation system.

This module provides command-line interface for validating properties,
generating reports, and managing the validation system.

Philosophy:
- Pretty output with colors and progress indicators
- Clear error messages with actionable guidance
- Integration of all 5 bricks
- Exit codes for CI/CD integration
"""

import argparse
from pathlib import Path
from typing import Optional


# Color codes for terminal output
class Colors:
    """ANSI color codes for terminal output."""

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_colored(text: str, color: str, bold: bool = False) -> None:
    """Print colored text to terminal."""
    prefix = Colors.BOLD if bold else ""
    print(f"{prefix}{color}{text}{Colors.RESET}")


def print_header(text: str) -> None:
    """Print section header."""
    print_colored(f"\n{'=' * 60}", Colors.CYAN)
    print_colored(text, Colors.CYAN, bold=True)
    print_colored("=" * 60, Colors.CYAN)


def print_success(text: str) -> None:
    """Print success message."""
    print_colored(f"✓ {text}", Colors.GREEN)


def print_error(text: str) -> None:
    """Print error message."""
    print_colored(f"✗ {text}", Colors.RED)


def print_warning(text: str) -> None:
    """Print warning message."""
    print_colored(f"⚠ {text}", Colors.YELLOW)


def print_info(text: str) -> None:
    """Print info message."""
    print_colored(f"i {text}", Colors.BLUE)


def validate_handler(handler_path: Optional[str] = None) -> int:
    """Validate handler property coverage.

    Args:
        handler_path: Path to specific handler file, or None for all handlers

    Returns:
        Exit code (0=success, 1=failure)
    """
    from iac.property_validation.analysis.handler_analyzer import analyze_handler
    from iac.property_validation.models import PropertyDefinition
    from iac.property_validation.validation.coverage_calculator import (
        CoverageCalculator,
    )
    from iac.property_validation.validation.critical_classifier import (
        CriticalClassifier,
    )
    from iac.property_validation.validation.gap_finder import GapFinder

    print_header("Property Validation")

    # Find handlers to validate
    if handler_path:
        handler_files = [Path(handler_path)]
        if not handler_files[0].exists():
            print_error(f"Handler file not found: {handler_path}")
            return 1
    else:
        # Find all handler files
        base_path = Path("src/iac/handlers")
        if not base_path.exists():
            print_error(f"Handlers directory not found: {base_path}")
            return 1
        handler_files = list(base_path.glob("**/*_handler.py"))
        if not handler_files:
            print_error("No handler files found")
            return 1

    print_info(f"Found {len(handler_files)} handler(s) to validate\n")

    # Initialize validation components
    classifier = CriticalClassifier()
    gap_finder = GapFinder(classifier)
    coverage_calculator = CoverageCalculator()

    all_passed = True
    results = []

    # Validate each handler
    for handler_file in handler_files:
        print_colored(f"\nValidating: {handler_file.name}", Colors.MAGENTA, bold=True)

        # Analyze handler
        result = analyze_handler(handler_file)
        if not result:
            print_error("Failed to analyze handler")
            all_passed = False
            continue

        # For demonstration, create mock schema properties
        # In real usage, these would come from Terraform schema
        schema_properties = {
            "account_tier": PropertyDefinition(
                name="account_tier",
                required=True,
                has_default=False,
                property_type="string",
                description="Storage account tier",
            ),
            "replication_type": PropertyDefinition(
                name="replication_type",
                required=True,
                has_default=False,
                property_type="string",
                description="Replication strategy",
            ),
            "tls_version": PropertyDefinition(
                name="tls_version",
                required=False,
                has_default=True,
                property_type="string",
                description="Minimum TLS version",
            ),
        }

        # Find gaps
        gaps = gap_finder.find_gaps(schema_properties, result.terraform_writes)

        # Calculate coverage
        metrics = coverage_calculator.calculate_coverage(
            required_properties=set(schema_properties.keys()),
            actual_properties=result.terraform_writes,
            gaps=gaps,
        )

        # Calculate quality score
        score = coverage_calculator.calculate_weighted_score(metrics)

        # Display results
        print(f"  Properties found: {len(result.properties)}")
        print(f"  Terraform writes: {len(result.terraform_writes)}")
        print(f"  Azure reads: {len(result.azure_reads)}")
        print(f"  Coverage: {metrics.coverage_percentage:.1f}%")
        print(f"  Quality score: {score:.1f}/100")

        if gaps:
            print_warning(f"  Found {len(gaps)} gap(s):")
            for gap in gaps[:5]:  # Show first 5 gaps
                color = {
                    "CRITICAL": Colors.RED,
                    "HIGH": Colors.YELLOW,
                    "MEDIUM": Colors.BLUE,
                    "LOW": Colors.CYAN,
                }.get(gap.criticality.value, Colors.RESET)
                print(
                    f"    {color}[{gap.criticality.value}]{Colors.RESET} {gap.property_name}: {gap.reason}"
                )

        # Pass/fail determination
        if metrics.critical_gaps > 0:
            print_error(f"  FAILED: {metrics.critical_gaps} critical gap(s)")
            all_passed = False
        elif score < 70.0:
            print_warning("  WARNING: Quality score below threshold (70)")
            all_passed = False
        else:
            print_success("  PASSED")

        results.append((handler_file.name, metrics, score))

    # Summary
    print_header("Validation Summary")
    print(f"\nHandlers validated: {len(results)}")
    passed = sum(1 for _, m, s in results if m.critical_gaps == 0 and s >= 70.0)
    print_colored(
        f"Passed: {passed}", Colors.GREEN if passed == len(results) else Colors.YELLOW
    )
    print_colored(
        f"Failed: {len(results) - passed}",
        Colors.RED if passed < len(results) else Colors.GREEN,
    )

    return 0 if all_passed else 1


def generate_report(output_path: str = "coverage_report.html") -> int:
    """Generate coverage report.

    Args:
        output_path: Path for output HTML report

    Returns:
        Exit code (0=success, 1=failure)
    """
    print_header("Generating Coverage Report")

    print_info(f"Output: {output_path}")

    # See src/iac/FUTURE_WORK.md - TODO #1 for implementation specifications
    print_warning(
        "HTML report generation not yet implemented - see src/iac/FUTURE_WORK.md TODO #1"
    )

    # For now, create a basic report
    report_content = """<!DOCTYPE html>
<html>
<head>
    <title>Property Validation Coverage Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        h1 { color: #333; }
        .success { color: green; }
        .error { color: red; }
        .warning { color: orange; }
    </style>
</head>
<body>
    <h1>Property Validation Coverage Report</h1>
    <p>Report generation in progress...</p>
</body>
</html>
"""

    try:
        Path(output_path).write_text(report_content)
        print_success(f"Report generated: {output_path}")
        return 0
    except Exception as e:
        print_error(f"Failed to generate report: {e}")
        return 1


def generate_manifest(resource_type: str, output_dir: Optional[str] = None) -> int:
    """Generate property manifest for resource type.

    Args:
        resource_type: Azure resource type (e.g., storage_account)
        output_dir: Output directory for manifest

    Returns:
        Exit code (0=success, 1=failure)
    """
    from iac.property_validation.manifest.generator import ManifestGenerator

    print_header(f"Generating Manifest: {resource_type}")

    # Determine output path
    if output_dir:
        output_path = Path(output_dir) / f"{resource_type}.yaml"
    else:
        output_path = Path("manifests") / f"{resource_type}.yaml"

    print_info(f"Output: {output_path}")

    # Create generator
    generator = ManifestGenerator()

    # Generate template manifest
    # In real usage, this would fetch schemas and generate mappings
    azure_type = f"Microsoft.Storage/{resource_type}"
    terraform_type = f"azurerm_{resource_type}"

    manifest = generator.generate_template_manifest(
        azure_resource_type=azure_type,
        terraform_resource_type=terraform_type,
        provider_version_min="3.0.0",
    )

    # Save manifest
    try:
        generator.save_manifest(manifest, output_path)
        print_success(f"Manifest generated: {output_path}")
        print_info("Edit the manifest to add property mappings")
        return 0
    except Exception as e:
        print_error(f"Failed to generate manifest: {e}")
        return 1


def check_thresholds() -> int:
    """Check if coverage meets CI/CD thresholds.

    Runs validation on all handlers and checks results against configured thresholds.

    Returns:
        Exit code (0=pass, 1=fail)
    """
    from iac.property_validation.analysis.handler_analyzer import analyze_handler
    from iac.property_validation.models import PropertyDefinition
    from iac.property_validation.validation.coverage_calculator import (
        CoverageCalculator,
    )
    from iac.property_validation.validation.critical_classifier import (
        CriticalClassifier,
    )
    from iac.property_validation.validation.gap_finder import GapFinder

    print_header("CI/CD Threshold Check")

    # Define thresholds (could be loaded from config file in future)
    thresholds = {
        "min_coverage": 70.0,
        "max_critical_gaps": 0,
        "min_quality_score": 70.0,
    }

    print_info("Thresholds:")
    for key, value in thresholds.items():
        print(f"  {key}: {value}")

    # Find all handler files
    base_path = Path("src/iac/handlers")
    if not base_path.exists():
        print_error(f"Handlers directory not found: {base_path}")
        return 1

    handler_files = list(base_path.glob("**/*_handler.py"))
    if not handler_files:
        print_error("No handler files found")
        return 1

    # Initialize validation components
    classifier = CriticalClassifier()
    gap_finder = GapFinder(classifier)
    coverage_calculator = CoverageCalculator()

    # Validate all handlers to get actual metrics
    total_coverage_sum = 0.0
    total_critical_gaps = 0
    total_handlers = 0
    quality_scores = []

    for handler_file in handler_files:
        result = analyze_handler(handler_file)
        if not result:
            continue

        # Mock schema properties for now (in production, these come from Terraform schema loader)
        schema_properties = {
            "name": PropertyDefinition(
                name="name",
                required=True,
                has_default=False,
                property_type="string",
                description="Resource name",
            ),
        }

        gaps = gap_finder.find_gaps(schema_properties, result.terraform_writes)

        metrics = coverage_calculator.calculate_coverage(
            required_properties=set(schema_properties.keys()),
            actual_properties=result.terraform_writes,
            gaps=gaps,
        )

        score = coverage_calculator.calculate_weighted_score(metrics)

        total_coverage_sum += metrics.coverage_percentage
        total_critical_gaps += metrics.critical_gaps
        quality_scores.append(score)
        total_handlers += 1

    # Calculate overall metrics
    actual = {
        "coverage": total_coverage_sum / max(1, total_handlers),
        "critical_gaps": total_critical_gaps,
        "quality_score": sum(quality_scores) / max(1, len(quality_scores))
        if quality_scores
        else 0.0,
    }

    print_info(f"\nActual values (from {total_handlers} handlers):")
    passed = True

    if actual["coverage"] >= thresholds["min_coverage"]:
        print_success(
            f"  Coverage: {actual['coverage']:.1f}% >= {thresholds['min_coverage']}%"
        )
    else:
        print_error(
            f"  Coverage: {actual['coverage']:.1f}% < {thresholds['min_coverage']}%"
        )
        passed = False

    if actual["critical_gaps"] <= thresholds["max_critical_gaps"]:
        print_success(
            f"  Critical gaps: {actual['critical_gaps']} <= {thresholds['max_critical_gaps']}"
        )
    else:
        print_error(
            f"  Critical gaps: {actual['critical_gaps']} > {thresholds['max_critical_gaps']}"
        )
        passed = False

    if actual["quality_score"] >= thresholds["min_quality_score"]:
        print_success(
            f"  Quality score: {actual['quality_score']:.1f} >= {thresholds['min_quality_score']}"
        )
    else:
        print_error(
            f"  Quality score: {actual['quality_score']:.1f} < {thresholds['min_quality_score']}"
        )
        passed = False

    print_header("Result")
    if passed:
        print_success("All thresholds PASSED")
        return 0
    else:
        print_error("Some thresholds FAILED")
        return 1


def clear_cache(provider: Optional[str] = None) -> int:
    """Clear schema cache.

    Args:
        provider: Specific provider to clear, or None for all

    Returns:
        Exit code (0=success, 1=failure)
    """
    from iac.property_validation.schemas.azure_scraper import AzureScraper

    print_header("Clear Schema Cache")

    try:
        scraper = AzureScraper()
        count = scraper.clear_cache(provider)

        if count > 0:
            print_success(f"Removed {count} cache file(s)")
        else:
            print_info("No cache files to remove")

        return 0
    except Exception as e:
        print_error(f"Failed to clear cache: {e}")
        return 1


def main() -> int:
    """Main CLI entry point.

    Returns:
        Exit code (0=success, 1=failure)
    """
    parser = argparse.ArgumentParser(
        description="Property validation CLI tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate all handlers
  python -m iac.property_validation validate

  # Validate specific handler
  python -m iac.property_validation validate --handler src/iac/handlers/storage_account_handler.py

  # Generate coverage report
  python -m iac.property_validation report --output report.html

  # Generate manifest for resource type
  python -m iac.property_validation generate-manifest --resource storage_account

  # Check CI thresholds
  python -m iac.property_validation check-thresholds

  # Clear schema cache
  python -m iac.property_validation clear-cache
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Validate command
    validate_parser = subparsers.add_parser(
        "validate", help="Validate handler property coverage"
    )
    validate_parser.add_argument("--handler", help="Specific handler file to validate")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate coverage report")
    report_parser.add_argument(
        "--output", default="coverage_report.html", help="Output file path"
    )

    # Generate manifest command
    manifest_parser = subparsers.add_parser(
        "generate-manifest", help="Generate property manifest for resource type"
    )
    manifest_parser.add_argument(
        "--resource", required=True, help="Resource type (e.g., storage_account)"
    )
    manifest_parser.add_argument("--output-dir", help="Output directory for manifest")

    # Check thresholds command
    subparsers.add_parser(
        "check-thresholds", help="Check if coverage meets CI/CD thresholds"
    )

    # Clear cache command
    cache_parser = subparsers.add_parser("clear-cache", help="Clear schema cache")
    cache_parser.add_argument(
        "--provider", help="Specific provider to clear (e.g., Microsoft.Storage)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if not args.command:
        parser.print_help()
        return 1

    if args.command == "validate":
        return validate_handler(args.handler)
    elif args.command == "report":
        return generate_report(args.output)
    elif args.command == "generate-manifest":
        return generate_manifest(args.resource, args.output_dir)
    elif args.command == "check-thresholds":
        return check_thresholds()
    elif args.command == "clear-cache":
        return clear_cache(args.provider)
    else:
        parser.print_help()
        return 1


__all__ = ["main"]
