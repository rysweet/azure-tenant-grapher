#!/usr/bin/env python3
"""
Pre-flight IaC Validation Script

Validates generated Infrastructure-as-Code (IaC) for common errors before deployment.
Catches placeholders, invalid IDs, subnet misconfigurations, and other issues that would
cause terraform plan/apply to fail.

Usage:
    python scripts/validate_generated_iac.py <iac_directory>
    python scripts/validate_generated_iac.py demos/simuland_iteration3/iteration16
    python scripts/validate_generated_iac.py --json demos/simuland_iteration3/iteration16

Exit Codes:
    0 - All validations passed
    1 - One or more validations failed
    2 - Script error (invalid arguments, file not found, etc.)
"""

import argparse
import ipaddress
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


@dataclass
class ValidationIssue:
    """Represents a single validation issue."""

    check_name: str
    severity: str  # "error", "warning"
    message: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    resource_type: Optional[str] = None
    resource_name: Optional[str] = None
    field_path: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of a validation check."""

    check_name: str
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings: List[ValidationIssue] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len([i for i in self.issues if i.severity == "error"])

    @property
    def warning_count(self) -> int:
        return len([i for i in self.issues if i.severity == "warning"])


class IaCValidator:
    """Validates generated IaC for common errors."""

    def __init__(self, iac_directory: Path):
        """
        Initialize the validator.

        Args:
            iac_directory: Path to directory containing generated IaC
        """
        self.iac_directory = iac_directory
        self.terraform_files: List[Path] = []
        self.terraform_data: Dict[str, Any] = {}

    def load_terraform_files(self) -> None:
        """Load all Terraform JSON files from the directory."""
        self.terraform_files = list(self.iac_directory.glob("*.tf.json"))

        if not self.terraform_files:
            console.print(
                f"[yellow]Warning: No *.tf.json files found in {self.iac_directory}[/yellow]"
            )
            return

        # Load the main terraform file (usually main.tf.json)
        main_tf = self.iac_directory / "main.tf.json"
        if main_tf.exists():
            with open(main_tf) as f:
                self.terraform_data = json.load(f)
        elif self.terraform_files:
            # Load the first .tf.json file found
            with open(self.terraform_files[0]) as f:
                self.terraform_data = json.load(f)

    def validate_all(self) -> List[ValidationResult]:
        """
        Run all validation checks.

        Returns:
            List of validation results
        """
        results = [
            self.check_no_placeholders(),
            self.check_valid_tenant_ids(),
            self.check_valid_subscription_ids(),
            self.check_subnet_cidrs(),
            self.check_duplicate_resources(),
            self.check_required_fields(),
            self.check_valid_resource_references(),
        ]
        return results

    def check_no_placeholders(self) -> ValidationResult:
        """Check for 'xxx' or other placeholder values in generated files."""
        result = ValidationResult(
            check_name="No Placeholders",
            passed=True,
        )

        placeholder_patterns = [
            r"\bxxx\b",
            r"\bXXX\b",
            r"\bTODO\b",
            r"\bFIXME\b",
            r"\bCHANGEME\b",
            r"\bPLACEHOLDER\b",
        ]

        for tf_file in self.terraform_files:
            with open(tf_file) as f:
                lines = f.readlines()

            for line_num, line in enumerate(lines, start=1):
                for pattern in placeholder_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        result.passed = False
                        result.issues.append(
                            ValidationIssue(
                                check_name="No Placeholders",
                                severity="error",
                                message=f"Found placeholder '{pattern}' in generated code",
                                file_path=str(tf_file.relative_to(self.iac_directory)),
                                line_number=line_num,
                            )
                        )

        return result

    def check_valid_tenant_ids(self) -> ValidationResult:
        """Check that all tenant IDs are valid UUIDs."""
        result = ValidationResult(
            check_name="Valid Tenant IDs",
            passed=True,
        )

        invalid_tenant_id = "00000000-0000-0000-0000-000000000000"
        uuid_pattern = re.compile(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
            re.IGNORECASE,
        )

        resources = self.terraform_data.get("resource", {})

        for resource_type, resources_dict in resources.items():
            for resource_name, resource_config in resources_dict.items():
                tenant_id = resource_config.get("tenant_id")

                if tenant_id:
                    if tenant_id == invalid_tenant_id:
                        result.passed = False
                        result.issues.append(
                            ValidationIssue(
                                check_name="Valid Tenant IDs",
                                severity="error",
                                message=f"Invalid tenant_id (all zeros): {tenant_id}",
                                resource_type=resource_type,
                                resource_name=resource_name,
                                field_path="tenant_id",
                            )
                        )
                    elif not uuid_pattern.match(str(tenant_id)):
                        result.passed = False
                        result.issues.append(
                            ValidationIssue(
                                check_name="Valid Tenant IDs",
                                severity="error",
                                message=f"Invalid tenant_id format: {tenant_id}",
                                resource_type=resource_type,
                                resource_name=resource_name,
                                field_path="tenant_id",
                            )
                        )

        return result

    def check_valid_subscription_ids(self) -> ValidationResult:
        """Check that subscription IDs are valid UUIDs (not placeholders)."""
        result = ValidationResult(
            check_name="Valid Subscription IDs",
            passed=True,
        )

        uuid_pattern = re.compile(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            re.IGNORECASE,
        )

        for tf_file in self.terraform_files:
            with open(tf_file) as f:
                content = f.read()

            # Find all /subscriptions/ paths
            subscription_refs = re.findall(r'/subscriptions/([^/\s\'"]+)', content)

            for sub_id in subscription_refs:
                # Skip Terraform interpolations
                if sub_id.startswith("${") or sub_id.startswith("var."):
                    continue

                if sub_id.lower() == "xxx" or sub_id.lower() == "placeholder":
                    result.passed = False
                    result.issues.append(
                        ValidationIssue(
                            check_name="Valid Subscription IDs",
                            severity="error",
                            message=f"Found placeholder subscription ID: {sub_id}",
                            file_path=str(tf_file.relative_to(self.iac_directory)),
                        )
                    )
                elif not uuid_pattern.match(sub_id):
                    result.passed = False
                    result.issues.append(
                        ValidationIssue(
                            check_name="Valid Subscription IDs",
                            severity="error",
                            message=f"Invalid subscription ID format: {sub_id}",
                            file_path=str(tf_file.relative_to(self.iac_directory)),
                        )
                    )

        return result

    def check_subnet_cidrs(self) -> ValidationResult:
        """Verify subnets fall within VNet address spaces."""
        result = ValidationResult(
            check_name="Subnet CIDR Validation",
            passed=True,
        )

        resources = self.terraform_data.get("resource", {})

        # Build VNet map
        vnets: Dict[str, Dict[str, Any]] = {}
        vnet_resources = resources.get("azurerm_virtual_network", {})

        for vnet_name, vnet_config in vnet_resources.items():
            address_space = vnet_config.get("address_space", [])
            if address_space:
                vnets[vnet_name] = {
                    "address_space": address_space,
                    "name": vnet_config.get("name", vnet_name),
                }

        # Check subnets
        subnet_resources = resources.get("azurerm_subnet", {})

        for subnet_name, subnet_config in subnet_resources.items():
            address_prefixes = subnet_config.get("address_prefixes", [])

            # Determine which VNet this subnet belongs to
            vnet_ref = subnet_config.get("virtual_network_name", "")

            # Extract VNet name from Terraform reference
            # Format: ${azurerm_virtual_network.VNet_Name.name}
            vnet_match = re.search(r"azurerm_virtual_network\.([^.}]+)", vnet_ref)
            if vnet_match:
                vnet_name = vnet_match.group(1)
            else:
                vnet_name = vnet_ref

            if vnet_name not in vnets:
                result.warnings.append(
                    ValidationIssue(
                        check_name="Subnet CIDR Validation",
                        severity="warning",
                        message=f"Cannot find VNet '{vnet_name}' for subnet validation",
                        resource_type="azurerm_subnet",
                        resource_name=subnet_name,
                    )
                )
                continue

            vnet_info = vnets[vnet_name]
            vnet_networks = []

            try:
                vnet_networks = [
                    ipaddress.ip_network(addr, strict=False)
                    for addr in vnet_info["address_space"]
                ]
            except ValueError as e:
                result.issues.append(
                    ValidationIssue(
                        check_name="Subnet CIDR Validation",
                        severity="error",
                        message=f"Invalid VNet address space: {e}",
                        resource_type="azurerm_virtual_network",
                        resource_name=vnet_name,
                    )
                )
                result.passed = False
                continue

            # Validate each subnet prefix
            for prefix in address_prefixes:
                try:
                    subnet_network = ipaddress.ip_network(prefix, strict=False)
                except ValueError as e:
                    result.passed = False
                    result.issues.append(
                        ValidationIssue(
                            check_name="Subnet CIDR Validation",
                            severity="error",
                            message=f"Invalid subnet CIDR '{prefix}': {e}",
                            resource_type="azurerm_subnet",
                            resource_name=subnet_name,
                            field_path="address_prefixes",
                        )
                    )
                    continue

                # Check if subnet is within VNet
                within_vnet = any(
                    subnet_network.subnet_of(vnet_net) for vnet_net in vnet_networks
                )

                if not within_vnet:
                    result.passed = False
                    result.issues.append(
                        ValidationIssue(
                            check_name="Subnet CIDR Validation",
                            severity="error",
                            message=f"Subnet CIDR '{prefix}' is outside VNet address space {vnet_info['address_space']}",
                            resource_type="azurerm_subnet",
                            resource_name=subnet_name,
                            field_path="address_prefixes",
                        )
                    )

        return result

    def check_duplicate_resources(self) -> ValidationResult:
        """Check for duplicate resource declarations."""
        result = ValidationResult(
            check_name="No Duplicate Resources",
            passed=True,
        )

        resources = self.terraform_data.get("resource", {})
        seen_names: Dict[str, Set[str]] = {}

        for resource_type, resources_dict in resources.items():
            seen_names[resource_type] = set()

            for resource_name in resources_dict.keys():
                if resource_name in seen_names[resource_type]:
                    result.passed = False
                    result.issues.append(
                        ValidationIssue(
                            check_name="No Duplicate Resources",
                            severity="error",
                            message="Duplicate resource declaration",
                            resource_type=resource_type,
                            resource_name=resource_name,
                        )
                    )
                else:
                    seen_names[resource_type].add(resource_name)

        return result

    def check_required_fields(self) -> ValidationResult:
        """Ensure critical fields aren't empty or null."""
        result = ValidationResult(
            check_name="Required Fields Populated",
            passed=True,
        )

        # Define required fields per resource type
        required_fields = {
            "azurerm_resource_group": ["name", "location"],
            "azurerm_virtual_network": ["name", "location", "address_space"],
            "azurerm_subnet": ["name", "address_prefixes", "virtual_network_name"],
            "azurerm_network_interface": ["name", "location"],
            "azurerm_linux_virtual_machine": [
                "name",
                "location",
                "size",
                "admin_username",
            ],
            "azurerm_windows_virtual_machine": [
                "name",
                "location",
                "size",
                "admin_username",
            ],
            "azurerm_storage_account": [
                "name",
                "location",
                "account_tier",
                "account_replication_type",
            ],
            "azurerm_key_vault": ["name", "location", "tenant_id", "sku_name"],
        }

        resources = self.terraform_data.get("resource", {})

        for resource_type, resources_dict in resources.items():
            if resource_type not in required_fields:
                continue

            for resource_name, resource_config in resources_dict.items():
                for field_name in required_fields[resource_type]:
                    value = resource_config.get(field_name)

                    if value is None or value == "" or value == []:
                        result.passed = False
                        result.issues.append(
                            ValidationIssue(
                                check_name="Required Fields Populated",
                                severity="error",
                                message=f"Required field '{field_name}' is empty or null",
                                resource_type=resource_type,
                                resource_name=resource_name,
                                field_path=field_name,
                            )
                        )

        return result

    def check_valid_resource_references(self) -> ValidationResult:
        """Check that resource references point to existing resources."""
        result = ValidationResult(
            check_name="Valid Resource References",
            passed=True,
        )

        resources = self.terraform_data.get("resource", {})

        # Build index of all resources
        resource_index: Set[str] = set()
        for resource_type, resources_dict in resources.items():
            for resource_name in resources_dict.keys():
                resource_index.add(f"{resource_type}.{resource_name}")

        # Check references in depends_on
        for resource_type, resources_dict in resources.items():
            for resource_name, resource_config in resources_dict.items():
                depends_on = resource_config.get("depends_on", [])

                for dependency in depends_on:
                    # Skip if it's a full path or module reference
                    if "/" in dependency or "module." in dependency:
                        continue

                    # Clean up the reference
                    clean_dep = dependency.strip()

                    if clean_dep not in resource_index:
                        result.warnings.append(
                            ValidationIssue(
                                check_name="Valid Resource References",
                                severity="warning",
                                message=f"Dependency references non-existent resource: {clean_dep}",
                                resource_type=resource_type,
                                resource_name=resource_name,
                                field_path="depends_on",
                            )
                        )

        # Check interpolation references like ${azurerm_virtual_network.VNet_Name.name}
        tf_json_str = json.dumps(self.terraform_data)
        interpolation_refs = re.findall(r"\$\{(azurerm_[a-z_]+)\.([^.}]+)", tf_json_str)

        for ref_type, ref_name in interpolation_refs:
            full_ref = f"{ref_type}.{ref_name}"
            if full_ref not in resource_index:
                result.warnings.append(
                    ValidationIssue(
                        check_name="Valid Resource References",
                        severity="warning",
                        message=f"Interpolation references non-existent resource: {full_ref}",
                    )
                )

        return result


def print_results(results: List[ValidationResult], json_output: bool = False) -> int:
    """
    Print validation results.

    Args:
        results: List of validation results
        json_output: If True, output JSON instead of table

    Returns:
        Exit code (0 if all passed, 1 if any failed)
    """
    total_errors = sum(r.error_count for r in results)
    total_warnings = sum(r.warning_count for r in results)
    passed_checks = sum(1 for r in results if r.passed)
    total_checks = len(results)

    if json_output:
        output = {
            "summary": {
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": total_checks - passed_checks,
                "total_errors": total_errors,
                "total_warnings": total_warnings,
            },
            "checks": [],
        }

        for result in results:
            check_data = {
                "name": result.check_name,
                "passed": result.passed,
                "errors": result.error_count,
                "warnings": result.warning_count,
                "issues": [
                    {
                        "severity": issue.severity,
                        "message": issue.message,
                        "file": issue.file_path,
                        "line": issue.line_number,
                        "resource_type": issue.resource_type,
                        "resource_name": issue.resource_name,
                        "field": issue.field_path,
                    }
                    for issue in result.issues + result.warnings
                ],
            }
            output["checks"].append(check_data)

        console.print_json(data=output)
        return 0 if total_errors == 0 else 1

    # Create summary table
    table = Table(title="IaC Validation Results", box=box.ROUNDED)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", justify="center")
    table.add_column("Errors", justify="right", style="red")
    table.add_column("Warnings", justify="right", style="yellow")

    for result in results:
        status = "[green]PASS[/green]" if result.passed else "[red]FAIL[/red]"
        table.add_row(
            result.check_name,
            status,
            str(result.error_count) if result.error_count > 0 else "-",
            str(result.warning_count) if result.warning_count > 0 else "-",
        )

    console.print()
    console.print(table)
    console.print()

    # Print summary panel
    summary_text = f"""
Total Checks: {total_checks}
Passed: [green]{passed_checks}[/green]
Failed: [red]{total_checks - passed_checks}[/red]
Total Errors: [red]{total_errors}[/red]
Total Warnings: [yellow]{total_warnings}[/yellow]
    """

    if total_errors == 0:
        console.print(
            Panel(
                summary_text.strip(),
                title="Summary",
                border_style="green",
            )
        )
    else:
        console.print(
            Panel(
                summary_text.strip(),
                title="Summary",
                border_style="red",
            )
        )

    # Print detailed issues
    if total_errors > 0 or total_warnings > 0:
        console.print("\n[bold]Detailed Issues:[/bold]\n")

        for result in results:
            if not result.issues and not result.warnings:
                continue

            console.print(f"[bold cyan]{result.check_name}:[/bold cyan]")

            for issue in result.issues + result.warnings:
                severity_color = "red" if issue.severity == "error" else "yellow"
                severity_label = issue.severity.upper()

                location_parts = []
                if issue.file_path:
                    location_parts.append(f"File: {issue.file_path}")
                if issue.line_number:
                    location_parts.append(f"Line: {issue.line_number}")
                if issue.resource_type and issue.resource_name:
                    location_parts.append(
                        f"Resource: {issue.resource_type}.{issue.resource_name}"
                    )
                if issue.field_path:
                    location_parts.append(f"Field: {issue.field_path}")

                location = " | ".join(location_parts) if location_parts else ""

                console.print(
                    f"  [{severity_color}]{severity_label}[/{severity_color}]: {issue.message}"
                )
                if location:
                    console.print(f"    {location}")

            console.print()

    return 0 if total_errors == 0 else 1


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate generated IaC for common errors before deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s demos/simuland_iteration3/iteration16
  %(prog)s --json demos/simuland_iteration3/iteration16
  %(prog)s /path/to/iac/output
        """,
    )

    parser.add_argument(
        "iac_directory",
        type=Path,
        help="Path to directory containing generated IaC files",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format",
    )

    args = parser.parse_args()

    # Validate directory exists
    if not args.iac_directory.exists():
        console.print(
            f"[red]Error: Directory not found: {args.iac_directory}[/red]",
            file=sys.stderr,
        )
        return 2

    if not args.iac_directory.is_dir():
        console.print(
            f"[red]Error: Not a directory: {args.iac_directory}[/red]",
            file=sys.stderr,
        )
        return 2

    # Run validation
    validator = IaCValidator(args.iac_directory)

    try:
        validator.load_terraform_files()
    except Exception as e:
        console.print(
            f"[red]Error loading Terraform files: {e}[/red]",
            file=sys.stderr,
        )
        return 2

    if not validator.terraform_files:
        console.print(
            f"[yellow]No Terraform files found in {args.iac_directory}[/yellow]",
            file=sys.stderr,
        )
        return 2

    results = validator.validate_all()
    exit_code = print_results(results, json_output=args.json)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
