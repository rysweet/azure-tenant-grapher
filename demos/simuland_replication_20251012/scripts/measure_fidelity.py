#!/usr/bin/env python3
"""
Simuland Replication Fidelity Measurement Engine

Quantifies the accuracy of Azure infrastructure replication by comparing
source and target tenants across three dimensions:
1. Resource Count Fidelity - Are all resources replicated?
2. Configuration Fidelity - Are configurations preserved?
3. Relationship Fidelity - Are relationships maintained?

Usage:
    python measure_fidelity.py \\
        --neo4j-uri bolt://localhost:7687 \\
        --neo4j-user neo4j \\
        --neo4j-password <password> \\
        --source-tenant <SOURCE_TENANT_ID> \\
        --target-tenant <TARGET_TENANT_ID>
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional

try:
    from neo4j import GraphDatabase
except ImportError:
    print("Error: neo4j-driver not installed")
    print("Install with: pip install neo4j")
    sys.exit(1)


@dataclass
class ResourceCountMetrics:
    """Metrics for resource count comparison."""
    source_count: int
    target_count: int
    matched: int
    missing: int
    extra: int
    fidelity: float


@dataclass
class ConfigurationMetrics:
    """Metrics for configuration comparison."""
    total_properties: int
    matched_properties: int
    different_properties: int
    fidelity: float
    differences: List[Dict[str, str]]


@dataclass
class RelationshipMetrics:
    """Metrics for relationship comparison."""
    source_count: int
    target_count: int
    matched: int
    missing: int
    extra: int
    fidelity: float


@dataclass
class FidelityReport:
    """Complete fidelity report."""
    timestamp: str
    source_tenant: str
    target_tenant: str
    resource_count_fidelity: float
    configuration_fidelity: float
    relationship_fidelity: float
    overall_fidelity: float
    resource_metrics: ResourceCountMetrics
    configuration_metrics: ConfigurationMetrics
    relationship_metrics: RelationshipMetrics


class ResourceCountFidelityCalculator:
    """Calculate resource count fidelity between source and target."""

    def __init__(self, driver):
        self.driver = driver

    def calculate(self, source_tenant: str, target_tenant: str) -> ResourceCountMetrics:
        """Calculate resource count fidelity."""
        with self.driver.session() as session:
            # Count source resources
            source_count = session.run(
                "MATCH (r:Resource) WHERE r.tenant_id = $tenant_id RETURN count(r) AS count",
                tenant_id=source_tenant
            ).single()["count"]

            # Count target resources
            target_count = session.run(
                "MATCH (r:Resource) WHERE r.tenant_id = $tenant_id RETURN count(r) AS count",
                tenant_id=target_tenant
            ).single()["count"]

            # Find matched resources (same name and type in both tenants)
            matched = session.run(
                """
                MATCH (source:Resource)
                WHERE source.tenant_id = $source_tenant
                MATCH (target:Resource {name: source.name, type: source.type})
                WHERE target.tenant_id = $target_tenant
                RETURN count(target) AS count
                """,
                source_tenant=source_tenant,
                target_tenant=target_tenant
            ).single()["count"]

            missing = source_count - matched
            extra = target_count - matched
            fidelity = matched / source_count if source_count > 0 else 1.0

            return ResourceCountMetrics(
                source_count=source_count,
                target_count=target_count,
                matched=matched,
                missing=missing,
                extra=extra,
                fidelity=fidelity
            )


class ConfigurationFidelityCalculator:
    """Calculate configuration fidelity between source and target."""

    def __init__(self, driver):
        self.driver = driver

    def calculate(self, source_tenant: str, target_tenant: str) -> ConfigurationMetrics:
        """Calculate configuration fidelity."""
        with self.driver.session() as session:
            # Compare VM configurations
            vm_config_results = self._compare_vm_configs(session, source_tenant, target_tenant)

            # Compare VNet configurations
            vnet_config_results = self._compare_vnet_configs(session, source_tenant, target_tenant)

            # Combine results
            total_properties = vm_config_results["total"] + vnet_config_results["total"]
            matched_properties = vm_config_results["matched"] + vnet_config_results["matched"]
            different_properties = total_properties - matched_properties

            differences = vm_config_results["differences"] + vnet_config_results["differences"]

            fidelity = matched_properties / total_properties if total_properties > 0 else 1.0

            return ConfigurationMetrics(
                total_properties=total_properties,
                matched_properties=matched_properties,
                different_properties=different_properties,
                fidelity=fidelity,
                differences=differences
            )

    def _compare_vm_configs(self, session, source_tenant: str, target_tenant: str) -> Dict[str, Any]:
        """Compare VM configurations."""
        results = session.run(
            """
            MATCH (source_vm:Resource {type: 'Microsoft.Compute/virtualMachines'})
            WHERE source_vm.tenant_id = $source_tenant
            MATCH (target_vm:Resource {name: source_vm.name, type: 'Microsoft.Compute/virtualMachines'})
            WHERE target_vm.tenant_id = $target_tenant
            RETURN
                source_vm.name AS vm_name,
                source_vm.properties.hardwareProfile.vmSize AS source_vm_size,
                target_vm.properties.hardwareProfile.vmSize AS target_vm_size,
                source_vm.properties.storageProfile.imageReference.sku AS source_os_sku,
                target_vm.properties.storageProfile.imageReference.sku AS target_os_sku,
                source_vm.properties.storageProfile.imageReference.publisher AS source_publisher,
                target_vm.properties.storageProfile.imageReference.publisher AS target_publisher
            """,
            source_tenant=source_tenant,
            target_tenant=target_tenant
        )

        total = 0
        matched = 0
        differences = []

        for record in results:
            # Check VM size
            total += 1
            if record["source_vm_size"] == record["target_vm_size"]:
                matched += 1
            else:
                differences.append({
                    "resource": record["vm_name"],
                    "property": "vm_size",
                    "source": record["source_vm_size"],
                    "target": record["target_vm_size"]
                })

            # Check OS SKU
            total += 1
            if record["source_os_sku"] == record["target_os_sku"]:
                matched += 1
            else:
                differences.append({
                    "resource": record["vm_name"],
                    "property": "os_sku",
                    "source": record["source_os_sku"],
                    "target": record["target_os_sku"]
                })

            # Check publisher
            total += 1
            if record["source_publisher"] == record["target_publisher"]:
                matched += 1
            else:
                differences.append({
                    "resource": record["vm_name"],
                    "property": "os_publisher",
                    "source": record["source_publisher"],
                    "target": record["target_publisher"]
                })

        return {
            "total": total,
            "matched": matched,
            "differences": differences
        }

    def _compare_vnet_configs(self, session, source_tenant: str, target_tenant: str) -> Dict[str, Any]:
        """Compare VNet configurations."""
        results = session.run(
            """
            MATCH (source_vnet:Resource {type: 'Microsoft.Network/virtualNetworks'})
            WHERE source_vnet.tenant_id = $source_tenant
            MATCH (target_vnet:Resource {name: source_vnet.name, type: 'Microsoft.Network/virtualNetworks'})
            WHERE target_vnet.tenant_id = $target_tenant
            RETURN
                source_vnet.name AS vnet_name,
                source_vnet.properties.addressSpace.addressPrefixes[0] AS source_address_space,
                target_vnet.properties.addressSpace.addressPrefixes[0] AS target_address_space
            """,
            source_tenant=source_tenant,
            target_tenant=target_tenant
        )

        total = 0
        matched = 0
        differences = []

        for record in results:
            total += 1
            if record["source_address_space"] == record["target_address_space"]:
                matched += 1
            else:
                differences.append({
                    "resource": record["vnet_name"],
                    "property": "address_space",
                    "source": record["source_address_space"],
                    "target": record["target_address_space"]
                })

        return {
            "total": total,
            "matched": matched,
            "differences": differences
        }


class RelationshipFidelityCalculator:
    """Calculate relationship fidelity between source and target."""

    def __init__(self, driver):
        self.driver = driver

    def calculate(self, source_tenant: str, target_tenant: str) -> RelationshipMetrics:
        """Calculate relationship fidelity."""
        with self.driver.session() as session:
            # Count source relationships
            source_count = session.run(
                """
                MATCH (source:Resource)-[r]->()
                WHERE source.tenant_id = $tenant_id
                RETURN count(r) AS count
                """,
                tenant_id=source_tenant
            ).single()["count"]

            # Count target relationships
            target_count = session.run(
                """
                MATCH (target:Resource)-[r]->()
                WHERE target.tenant_id = $tenant_id
                RETURN count(r) AS count
                """,
                tenant_id=target_tenant
            ).single()["count"]

            # Estimate matched relationships
            # This is a simplified calculation - in reality, you'd need to match
            # relationships by their source/target resource names and relationship types
            matched = min(source_count, target_count)
            missing = max(0, source_count - target_count)
            extra = max(0, target_count - source_count)

            fidelity = matched / source_count if source_count > 0 else 1.0

            return RelationshipMetrics(
                source_count=source_count,
                target_count=target_count,
                matched=matched,
                missing=missing,
                extra=extra,
                fidelity=fidelity
            )


class FidelityReportGenerator:
    """Generate comprehensive fidelity report."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close the Neo4j driver."""
        self.driver.close()

    def generate(self, source_tenant: str, target_tenant: str) -> FidelityReport:
        """Generate complete fidelity report."""
        resource_calc = ResourceCountFidelityCalculator(self.driver)
        config_calc = ConfigurationFidelityCalculator(self.driver)
        relationship_calc = RelationshipFidelityCalculator(self.driver)

        resource_metrics = resource_calc.calculate(source_tenant, target_tenant)
        config_metrics = config_calc.calculate(source_tenant, target_tenant)
        relationship_metrics = relationship_calc.calculate(source_tenant, target_tenant)

        # Calculate overall fidelity (weighted average)
        overall_fidelity = (
            resource_metrics.fidelity * 0.4 +
            config_metrics.fidelity * 0.4 +
            relationship_metrics.fidelity * 0.2
        )

        return FidelityReport(
            timestamp=datetime.utcnow().isoformat() + "Z",
            source_tenant=source_tenant,
            target_tenant=target_tenant,
            resource_count_fidelity=resource_metrics.fidelity,
            configuration_fidelity=config_metrics.fidelity,
            relationship_fidelity=relationship_metrics.fidelity,
            overall_fidelity=overall_fidelity,
            resource_metrics=resource_metrics,
            configuration_metrics=config_metrics,
            relationship_metrics=relationship_metrics
        )

    def export_json(self, report: FidelityReport, output_file: Optional[str] = None) -> str:
        """Export report as JSON."""
        report_dict = asdict(report)
        json_str = json.dumps(report_dict, indent=2)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(json_str)
            print(f"Report saved to: {output_file}")

        return json_str

    def print_summary(self, report: FidelityReport):
        """Print human-readable summary."""
        print("\n" + "=" * 70)
        print("SIMULAND REPLICATION FIDELITY REPORT")
        print("=" * 70)
        print(f"Timestamp: {report.timestamp}")
        print(f"Source Tenant: {report.source_tenant}")
        print(f"Target Tenant: {report.target_tenant}")
        print("\n" + "-" * 70)
        print("OVERALL FIDELITY SCORE")
        print("-" * 70)
        print(f"Overall: {report.overall_fidelity * 100:.1f}%")
        print(f"  - Resource Count:  {report.resource_count_fidelity * 100:.1f}%")
        print(f"  - Configuration:   {report.configuration_fidelity * 100:.1f}%")
        print(f"  - Relationships:   {report.relationship_fidelity * 100:.1f}%")

        print("\n" + "-" * 70)
        print("RESOURCE COUNT METRICS")
        print("-" * 70)
        rm = report.resource_metrics
        print(f"Source Resources: {rm.source_count}")
        print(f"Target Resources: {rm.target_count}")
        print(f"Matched:          {rm.matched}")
        print(f"Missing:          {rm.missing}")
        print(f"Extra:            {rm.extra}")

        print("\n" + "-" * 70)
        print("CONFIGURATION METRICS")
        print("-" * 70)
        cm = report.configuration_metrics
        print(f"Total Properties:     {cm.total_properties}")
        print(f"Matched Properties:   {cm.matched_properties}")
        print(f"Different Properties: {cm.different_properties}")

        if cm.differences:
            print(f"\nConfiguration Differences ({len(cm.differences)}):")
            for diff in cm.differences[:5]:  # Show first 5
                print(f"  - {diff['resource']}.{diff['property']}: "
                      f"{diff.get('source', 'N/A')} -> {diff.get('target', 'N/A')}")
            if len(cm.differences) > 5:
                print(f"  ... and {len(cm.differences) - 5} more")

        print("\n" + "-" * 70)
        print("RELATIONSHIP METRICS")
        print("-" * 70)
        rlm = report.relationship_metrics
        print(f"Source Relationships: {rlm.source_count}")
        print(f"Target Relationships: {rlm.target_count}")
        print(f"Matched:              {rlm.matched}")
        print(f"Missing:              {rlm.missing}")
        print(f"Extra:                {rlm.extra}")

        print("\n" + "=" * 70)
        print("ASSESSMENT")
        print("=" * 70)

        if report.overall_fidelity >= 0.95:
            print("Status: EXCELLENT - High fidelity replication")
        elif report.overall_fidelity >= 0.90:
            print("Status: GOOD - Acceptable fidelity with minor differences")
        elif report.overall_fidelity >= 0.80:
            print("Status: FAIR - Significant differences detected")
        else:
            print("Status: POOR - Major differences, review required")

        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Measure fidelity of Simuland replication",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate fidelity report
  python measure_fidelity.py \\
      --neo4j-uri bolt://localhost:7687 \\
      --neo4j-user neo4j \\
      --neo4j-password mypassword \\
      --source-tenant SOURCE_TENANT_ID \\
      --target-tenant TARGET_TENANT_ID

  # Save report to file
  python measure_fidelity.py \\
      --neo4j-uri bolt://localhost:7687 \\
      --neo4j-user neo4j \\
      --neo4j-password mypassword \\
      --source-tenant SOURCE_TENANT_ID \\
      --target-tenant TARGET_TENANT_ID \\
      --output fidelity_report.json
        """
    )

    parser.add_argument("--neo4j-uri", required=True, help="Neo4j connection URI")
    parser.add_argument("--neo4j-user", required=True, help="Neo4j username")
    parser.add_argument("--neo4j-password", required=True, help="Neo4j password")
    parser.add_argument("--source-tenant", required=True, help="Source tenant ID")
    parser.add_argument("--target-tenant", required=True, help="Target tenant ID")
    parser.add_argument("--output", help="Output JSON file path")

    args = parser.parse_args()

    # Generate report
    print("Connecting to Neo4j...")
    generator = FidelityReportGenerator(
        args.neo4j_uri,
        args.neo4j_user,
        args.neo4j_password
    )

    try:
        print("Calculating fidelity metrics...")
        report = generator.generate(args.source_tenant, args.target_tenant)

        # Print summary
        generator.print_summary(report)

        # Export JSON
        if args.output:
            generator.export_json(report, args.output)
        else:
            print("\nJSON Output:")
            print(generator.export_json(report))

    finally:
        generator.close()


if __name__ == "__main__":
    main()
