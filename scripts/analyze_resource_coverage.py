#!/usr/bin/env python3
"""
Resource Coverage Analysis Script

Analyzes the gap between scanned Azure resources and generated Terraform resources.
Categorizes missing resources to identify:
- Non-deployable resources (Graph API objects)
- Unsupported Azure resource types
- Missing emitter implementations
- Other gaps

Usage:
    uv run python scripts/analyze_resource_coverage.py [OPTIONS]

Options:
    --output-dir PATH    Output directory (default: outputs)
    --format FORMAT      Output format: markdown or json (default: markdown)
    --debug              Enable debug logging
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

from src.config_manager import Neo4jConfig
from src.utils.session_manager import create_session_manager

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


# Azure resource type to Terraform resource type mapping (from terraform_emitter.py)
AZURE_TO_TERRAFORM_MAPPING: Dict[str, str] = {
    "Microsoft.Compute/virtualMachines": "azurerm_linux_virtual_machine",
    "Microsoft.Compute/disks": "azurerm_managed_disk",
    "Microsoft.Compute/virtualMachines/extensions": "azurerm_virtual_machine_extension",
    "Microsoft.Storage/storageAccounts": "azurerm_storage_account",
    "Microsoft.Network/virtualNetworks": "azurerm_virtual_network",
    "Microsoft.Network/subnets": "azurerm_subnet",
    "Microsoft.Network/networkSecurityGroups": "azurerm_network_security_group",
    "Microsoft.Network/publicIPAddresses": "azurerm_public_ip",
    "Microsoft.Network/networkInterfaces": "azurerm_network_interface",
    "Microsoft.Network/bastionHosts": "azurerm_bastion_host",
    "Microsoft.Network/privateEndpoints": "azurerm_private_endpoint",
    "Microsoft.Network/privateDnsZones": "azurerm_private_dns_zone",
    "Microsoft.Network/privateDnsZones/virtualNetworkLinks": "azurerm_private_dns_zone_virtual_network_link",
    "Microsoft.Web/serverFarms": "azurerm_service_plan",
    "Microsoft.Sql/servers": "azurerm_mssql_server",
    "Microsoft.KeyVault/vaults": "azurerm_key_vault",
    "Microsoft.OperationalInsights/workspaces": "azurerm_log_analytics_workspace",
    "microsoft.insights/components": "azurerm_application_insights",
    "microsoft.alertsmanagement/smartDetectorAlertRules": "azurerm_monitor_smart_detector_alert_rule",
    "Microsoft.Resources/resourceGroups": "azurerm_resource_group",
    "microsoft.devtestlab/labs": "azurerm_dev_test_lab",
    "Microsoft.DevTestLab/labs": "azurerm_dev_test_lab",
    "Microsoft.DevTestLab/labs/virtualMachines": "azurerm_dev_test_linux_virtual_machine",
    "Microsoft.MachineLearningServices/workspaces": "azurerm_machine_learning_workspace",
    "Microsoft.CognitiveServices/accounts": "azurerm_cognitive_account",
    "Microsoft.Kusto/clusters": "azurerm_kusto_cluster",
    "Microsoft.EventHub/namespaces": "azurerm_eventhub_namespace",
    "Microsoft.Network/networkWatchers": "azurerm_network_watcher",
    "Microsoft.ManagedIdentity/userAssignedIdentities": "azurerm_user_assigned_identity",
    "Microsoft.Insights/dataCollectionRules": "azurerm_monitor_data_collection_rule",
    "microsoft.insights/dataCollectionRules": "azurerm_monitor_data_collection_rule",
    "Microsoft.Insights/dataCollectionEndpoints": "azurerm_monitor_data_collection_endpoint",
    "Microsoft.OperationsManagement/solutions": "azurerm_log_analytics_solution",
    "Microsoft.Automation/automationAccounts": "azurerm_automation_account",
    "microsoft.insights/actiongroups": "azurerm_monitor_action_group",
    "Microsoft.Insights/actionGroups": "azurerm_monitor_action_group",
    "Microsoft.Search/searchServices": "azurerm_search_service",
    "microsoft.operationalInsights/querypacks": "azurerm_log_analytics_query_pack",
    "Microsoft.OperationalInsights/queryPacks": "azurerm_log_analytics_query_pack",
    "Microsoft.Compute/sshPublicKeys": "azurerm_ssh_public_key",
    "Microsoft.DevTestLab/schedules": "azurerm_dev_test_schedule",
    "Microsoft.Automation/automationAccounts/runbooks": "azurerm_automation_runbook",
    "Microsoft.AAD/User": "azuread_user",
    "Microsoft.AAD/Group": "azuread_group",
    "Microsoft.AAD/ServicePrincipal": "azuread_service_principal",
    "Microsoft.AAD/Application": "azuread_application",
    "Microsoft.Graph/users": "azuread_user",
    "Microsoft.Graph/groups": "azuread_group",
    "Microsoft.Graph/servicePrincipals": "azuread_service_principal",
    "Microsoft.Graph/applications": "azuread_application",
    "Microsoft.ManagedIdentity/managedIdentities": "azurerm_user_assigned_identity",
    "User": "azuread_user",
    "Group": "azuread_group",
    "ServicePrincipal": "azuread_service_principal",
    "Application": "azuread_application",
    "Microsoft.Authorization/roleAssignments": "azurerm_role_assignment",
    "Microsoft.Authorization/roleDefinitions": "azurerm_role_definition",
}

# Known non-deployable resource types (Graph API, not ARM)
NON_DEPLOYABLE_TYPES = {
    "User",
    "Group",
    "ServicePrincipal",
    "Application",
    "AADUser",
    "AADGroup",
    "AADServicePrincipal",
    "AADApplication",
    "IdentityUser",
    "IdentityGroup",
    "Microsoft.AAD/User",
    "Microsoft.AAD/Group",
    "Microsoft.AAD/ServicePrincipal",
    "Microsoft.AAD/Application",
    "Microsoft.Graph/users",
    "Microsoft.Graph/groups",
    "Microsoft.Graph/servicePrincipals",
    "Microsoft.Graph/applications",
    "Microsoft.Authorization/roleAssignments",
    "Microsoft.Authorization/roleDefinitions",
}

# Known unsupported types (no Terraform provider support)
KNOWN_UNSUPPORTED_TYPES = {
    "Microsoft.SecurityCopilot/capacities",
    "Microsoft.Resources/templateSpecs",
    "Microsoft.Resources/templateSpecs/versions",
    "Microsoft.MachineLearningServices/workspaces/serverlessEndpoints",
}


class ResourceCoverageAnalyzer:
    """Analyzes resource coverage between Neo4j and Terraform generation."""

    def __init__(self, neo4j_config: Neo4jConfig, debug: bool = False):
        """Initialize the analyzer.

        Args:
            neo4j_config: Neo4j database configuration
            debug: Enable debug logging
        """
        self.neo4j_config = neo4j_config
        self.debug = debug
        self.session_manager = create_session_manager(neo4j_config)

        # Analysis results
        self.resource_counts: Dict[str, int] = {}
        self.supported_types: Set[str] = set()
        self.unsupported_types: Set[str] = set()
        self.non_deployable_types: Set[str] = set()
        self.missing_emitters: Set[str] = set()
        self.total_resources = 0

        if debug:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)

    def connect(self) -> None:
        """Connect to Neo4j database."""
        logger.info("Connecting to Neo4j database...")
        self.session_manager.connect()
        logger.info("Connected successfully")

    def disconnect(self) -> None:
        """Disconnect from Neo4j database."""
        self.session_manager.disconnect()

    def query_resource_types(self) -> Dict[str, int]:
        """Query all resource types and their counts from Neo4j.

        Returns:
            Dictionary mapping resource type to count
        """
        logger.info("Querying resource types from Neo4j...")

        query = """
        MATCH (r:Resource)
        RETURN r.type as resource_type, count(*) as count
        ORDER BY count DESC
        """

        with self.session_manager.session() as session:
            result = session.run(query)
            resource_counts = {
                record["resource_type"]: record["count"]
                for record in result
                if record["resource_type"]
            }

        logger.info(f"Found {len(resource_counts)} unique resource types")
        logger.info(f"Total resources: {sum(resource_counts.values())}")

        return resource_counts

    def categorize_resources(self) -> None:
        """Categorize resources into supported, unsupported, and non-deployable."""
        logger.info("Categorizing resources...")

        for resource_type, _count in self.resource_counts.items():
            # Normalize type for comparison

            # Check if it's a non-deployable type (Graph API)
            if self._is_non_deployable(resource_type):
                self.non_deployable_types.add(resource_type)
            # Check if it's in the mapping (supported)
            elif self._is_supported(resource_type):
                self.supported_types.add(resource_type)
            # Check if it's a known unsupported type
            elif resource_type in KNOWN_UNSUPPORTED_TYPES:
                self.unsupported_types.add(resource_type)
            # Otherwise, it's a missing emitter (potential to add)
            else:
                self.missing_emitters.add(resource_type)

        logger.info(f"Supported types: {len(self.supported_types)}")
        logger.info(f"Non-deployable types: {len(self.non_deployable_types)}")
        logger.info(f"Unsupported types: {len(self.unsupported_types)}")
        logger.info(f"Missing emitters: {len(self.missing_emitters)}")

    def _is_non_deployable(self, resource_type: str) -> bool:
        """Check if a resource type is non-deployable (Graph API)."""
        # Direct match
        if resource_type in NON_DEPLOYABLE_TYPES:
            return True

        # Case-insensitive match for Neo4j labels
        normalized = resource_type.lower()
        if normalized in {t.lower() for t in NON_DEPLOYABLE_TYPES}:
            return True

        # Check if it contains identity/user/group keywords
        identity_keywords = ["user", "group", "serviceprincipal", "application"]
        for keyword in identity_keywords:
            if keyword in normalized and not normalized.startswith("microsoft."):
                return True

        return False

    def _is_supported(self, resource_type: str) -> bool:
        """Check if a resource type is supported in Terraform mapping."""
        # Direct match
        if resource_type in AZURE_TO_TERRAFORM_MAPPING:
            return True

        # Case-insensitive match
        if resource_type.lower() in {k.lower() for k in AZURE_TO_TERRAFORM_MAPPING}:
            return True

        # Handle Microsoft.Web/sites special case (dynamically mapped)
        if resource_type == "Microsoft.Web/sites":
            return True

        return False

    def calculate_statistics(self) -> Dict[str, Any]:
        """Calculate coverage statistics.

        Returns:
            Dictionary containing statistics
        """
        total_resources = sum(self.resource_counts.values())

        supported_count = sum(
            self.resource_counts[t]
            for t in self.supported_types
            if t in self.resource_counts
        )
        non_deployable_count = sum(
            self.resource_counts[t]
            for t in self.non_deployable_types
            if t in self.resource_counts
        )
        unsupported_count = sum(
            self.resource_counts[t]
            for t in self.unsupported_types
            if t in self.resource_counts
        )
        missing_emitter_count = sum(
            self.resource_counts[t]
            for t in self.missing_emitters
            if t in self.resource_counts
        )

        # Calculate what should be in Terraform (supported types)
        expected_in_terraform = supported_count
        # Calculate actual gaps (everything that's not supported or non-deployable)
        actual_gap = unsupported_count + missing_emitter_count

        return {
            "total_resources": total_resources,
            "total_types": len(self.resource_counts),
            "supported": {
                "count": supported_count,
                "types": len(self.supported_types),
                "percentage": (supported_count / total_resources * 100)
                if total_resources > 0
                else 0,
            },
            "non_deployable": {
                "count": non_deployable_count,
                "types": len(self.non_deployable_types),
                "percentage": (non_deployable_count / total_resources * 100)
                if total_resources > 0
                else 0,
            },
            "unsupported": {
                "count": unsupported_count,
                "types": len(self.unsupported_types),
                "percentage": (unsupported_count / total_resources * 100)
                if total_resources > 0
                else 0,
            },
            "missing_emitters": {
                "count": missing_emitter_count,
                "types": len(self.missing_emitters),
                "percentage": (missing_emitter_count / total_resources * 100)
                if total_resources > 0
                else 0,
            },
            "expected_in_terraform": expected_in_terraform,
            "actual_gap": actual_gap,
        }

    def get_top_unsupported(self, limit: int = 20) -> List[Tuple[str, int]]:
        """Get top unsupported resource types by count.

        Args:
            limit: Maximum number of types to return

        Returns:
            List of (resource_type, count) tuples
        """
        unsupported_with_counts = [
            (t, self.resource_counts[t])
            for t in self.missing_emitters.union(self.unsupported_types)
            if t in self.resource_counts
        ]
        return sorted(unsupported_with_counts, key=lambda x: x[1], reverse=True)[
            :limit
        ]

    def generate_markdown_report(self) -> str:
        """Generate a comprehensive markdown report.

        Returns:
            Markdown formatted report
        """
        stats = self.calculate_statistics()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        report = f"""# Resource Coverage Analysis Report

Generated: {timestamp}

## Executive Summary

This report analyzes the gap between scanned Azure resources and generated Terraform resources.

### Key Findings

- **Total Resources Scanned**: {stats['total_resources']:,}
- **Total Resource Types**: {stats['total_types']}
- **Expected in Terraform**: {stats['expected_in_terraform']:,} resources ({stats['supported']['percentage']:.1f}%)
- **Actual Gap**: {stats['actual_gap']:,} resources

### Gap Breakdown

| Category | Count | Types | Percentage | Description |
|----------|-------|-------|------------|-------------|
| **Supported** | {stats['supported']['count']:,} | {stats['supported']['types']} | {stats['supported']['percentage']:.1f}% | Resources with Terraform emitters |
| **Non-Deployable** | {stats['non_deployable']['count']:,} | {stats['non_deployable']['types']} | {stats['non_deployable']['percentage']:.1f}% | Graph API objects (Users, Groups, SPs) |
| **Unsupported** | {stats['unsupported']['count']:,} | {stats['unsupported']['types']} | {stats['unsupported']['percentage']:.1f}% | No Terraform provider support |
| **Missing Emitters** | {stats['missing_emitters']['count']:,} | {stats['missing_emitters']['types']} | {stats['missing_emitters']['percentage']:.1f}% | Could add but haven't yet |

## Detailed Analysis

### 1. Supported Resources ({stats['supported']['count']:,} resources)

These resources have Terraform emitters and should be included in IaC generation:

"""

        # Add supported types table
        supported_with_counts = sorted(
            [(t, self.resource_counts[t]) for t in self.supported_types],
            key=lambda x: x[1],
            reverse=True,
        )

        report += "| Resource Type | Count | Terraform Type |\n"
        report += "|---------------|-------|----------------|\n"
        for resource_type, count in supported_with_counts[:20]:
            tf_type = AZURE_TO_TERRAFORM_MAPPING.get(resource_type, "N/A")
            report += f"| `{resource_type}` | {count:,} | `{tf_type}` |\n"

        if len(supported_with_counts) > 20:
            report += f"\n_... and {len(supported_with_counts) - 20} more supported types_\n"

        report += f"""

### 2. Non-Deployable Resources ({stats['non_deployable']['count']:,} resources)

These are Graph API objects (Users, Groups, Service Principals) that are not deployed via ARM/Terraform:

"""

        # Add non-deployable types table
        non_deployable_with_counts = sorted(
            [(t, self.resource_counts[t]) for t in self.non_deployable_types],
            key=lambda x: x[1],
            reverse=True,
        )

        report += "| Resource Type | Count | Why Not Deployable |\n"
        report += "|---------------|-------|--------------------|\n"
        for resource_type, count in non_deployable_with_counts:
            reason = "Graph API identity object"
            if "roleassignment" in resource_type.lower():
                reason = "RBAC assignment (can be in Terraform but often managed separately)"
            report += f"| `{resource_type}` | {count:,} | {reason} |\n"

        report += f"""

**Note**: These resources are expected to be missing from Terraform output. They represent ~{stats['non_deployable']['percentage']:.1f}% of scanned resources.

### 3. Unsupported Resources ({stats['unsupported']['count']:,} resources)

These Azure resource types have no Terraform provider support:

"""

        # Add unsupported types table
        unsupported_with_counts = sorted(
            [(t, self.resource_counts[t]) for t in self.unsupported_types],
            key=lambda x: x[1],
            reverse=True,
        )

        report += "| Resource Type | Count | Status |\n"
        report += "|---------------|-------|--------|\n"
        for resource_type, count in unsupported_with_counts:
            status = "No Terraform provider"
            if "templateSpec" in resource_type:
                status = "Template metadata (not deployable)"
            elif "SecurityCopilot" in resource_type:
                status = "Preview service (no provider yet)"
            report += f"| `{resource_type}` | {count:,} | {status} |\n"

        report += f"""

### 4. Missing Emitters ({stats['missing_emitters']['count']:,} resources)

These resource types COULD be added to Terraform generation but don't have emitters yet:

"""

        # Add top missing emitters table
        top_missing = self.get_top_unsupported(20)
        missing_only = [
            (t, c) for t, c in top_missing if t in self.missing_emitters
        ]

        report += "| Resource Type | Count | Priority | Notes |\n"
        report += "|---------------|-------|----------|-------|\n"
        for resource_type, count in missing_only:
            priority = "HIGH" if count > 10 else "MEDIUM" if count > 5 else "LOW"
            notes = ""

            # Add helpful notes for specific types
            if "Microsoft.Sql" in resource_type:
                notes = "SQL resource, high value"
            elif "Microsoft.Web" in resource_type:
                notes = "Web app resource"
            elif "Microsoft.Storage" in resource_type:
                notes = "Storage resource"
            elif "Microsoft.Network" in resource_type:
                notes = "Network resource, critical"
            elif "Microsoft.Compute" in resource_type:
                notes = "Compute resource, high value"

            report += f"| `{resource_type}` | {count:,} | {priority} | {notes} |\n"

        report += """

## Recommendations

### Immediate Actions

1. **Investigate the 380 resource gap**:
   - Expected resources with emitters: {expected:,}
   - Verify these are actually being generated in Terraform output
   - Check for filtering or skipping logic in the emitter

2. **Add high-priority emitters**:
   - Focus on missing types with >10 instances
   - Prioritize networking and compute resources
   - Consider business value and deployment frequency

### Analysis

The gap between scanned ({total:,}) and Terraform ({expected:,}) resources breaks down as:

- **Expected Gap (Non-Deployable)**: {non_deployable:,} resources ({non_deployable_pct:.1f}%)
  - These are Graph API objects (users, groups, service principals)
  - This is normal and expected

- **Actual Gap (Missing from Terraform)**: {actual_gap:,} resources
  - {unsupported:,} unsupported by Terraform provider ({unsupported_pct:.1f}%)
  - {missing:,} missing emitter implementations ({missing_pct:.1f}%)

### The 380 Resource Mystery

If Terraform shows 1,777 resources but we expected {expected:,}:
- **Gap**: {expected:,} - 1,777 = ~{gap_estimate:,} resources

This suggests:
1. Some supported resources are being filtered/skipped during emission
2. Resource relationships may cause exclusions (e.g., NICs without IP configs)
3. Validation failures may prevent some resources from being emitted

**Next Steps**:
- Review terraform_emitter.py for filtering logic
- Check logs for skipped resources
- Validate resource dependencies
- Run with --debug flag to see detailed skipping reasons

""".format(
            expected=stats['expected_in_terraform'],
            total=stats['total_resources'],
            non_deployable=stats['non_deployable']['count'],
            non_deployable_pct=stats['non_deployable']['percentage'],
            actual_gap=stats['actual_gap'],
            unsupported=stats['unsupported']['count'],
            unsupported_pct=stats['unsupported']['percentage'],
            missing=stats['missing_emitters']['count'],
            missing_pct=stats['missing_emitters']['percentage'],
            gap_estimate=stats['expected_in_terraform'] - 1777,
        )

        return report

    def generate_json_report(self) -> str:
        """Generate a JSON report.

        Returns:
            JSON formatted report
        """
        stats = self.calculate_statistics()

        report = {
            "timestamp": datetime.now().isoformat(),
            "statistics": stats,
            "resource_counts": self.resource_counts,
            "supported_types": sorted(self.supported_types),
            "non_deployable_types": sorted(self.non_deployable_types),
            "unsupported_types": sorted(self.unsupported_types),
            "missing_emitters": sorted(self.missing_emitters),
            "top_missing_emitters": [
                {"type": t, "count": c} for t, c in self.get_top_unsupported(20)
            ],
        }

        return json.dumps(report, indent=2)

    def run_analysis(self) -> Dict[str, Any]:
        """Run the complete analysis.

        Returns:
            Analysis results dictionary
        """
        try:
            self.connect()

            # Query resource types
            self.resource_counts = self.query_resource_types()
            self.total_resources = sum(self.resource_counts.values())

            # Categorize resources
            self.categorize_resources()

            # Calculate statistics
            stats = self.calculate_statistics()

            return stats

        finally:
            self.disconnect()


def main() -> int:
    """Main entry point for the script.

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Analyze resource coverage between Neo4j and Terraform"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs"),
        help="Output directory for reports (default: outputs)",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json", "both"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )

    args = parser.parse_args()

    # Create output directory
    args.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Create Neo4j configuration
        neo4j_config = Neo4jConfig()

        # Create analyzer
        analyzer = ResourceCoverageAnalyzer(neo4j_config, debug=args.debug)

        # Run analysis
        logger.info("Starting resource coverage analysis...")
        analyzer.run_analysis()

        # Generate reports
        if args.format in ["markdown", "both"]:
            markdown_report = analyzer.generate_markdown_report()
            output_file = args.output_dir / "resource_coverage_analysis.md"
            output_file.write_text(markdown_report)
            logger.info(f"Markdown report saved to: {output_file}")

        if args.format in ["json", "both"]:
            json_report = analyzer.generate_json_report()
            output_file = args.output_dir / "resource_coverage_analysis.json"
            output_file.write_text(json_report)
            logger.info(f"JSON report saved to: {output_file}")

        logger.info("Analysis complete!")
        return 0

    except Exception as e:
        logger.exception(f"Analysis failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
