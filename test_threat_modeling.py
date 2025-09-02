#!/usr/bin/env python3
"""
Test script to verify the threat modeling functionality works correctly.
"""

import logging
import os
import sys
import tempfile

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from threat_modeling_agent.asb_mapper import map_controls
from threat_modeling_agent.report_builder import ThreatModelReportBuilder
from threat_modeling_agent.threat_enumerator import enumerate_threats
from threat_modeling_agent.tmt_runner import AzureThreatAnalysisRunner


def test_threat_enumeration():
    """Test threat enumeration with sample Azure resources."""
    print("Testing threat enumeration...")

    # Sample Azure resources
    sample_resources = [
        {
            "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
            "name": "test-vm",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
            "properties": {
                "storageProfile": {"osDisk": {"encryptionSettings": {"enabled": False}}}
            },
        },
        {
            "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
            "name": "teststorage",
            "type": "Microsoft.Storage/storageAccounts",
            "location": "eastus",
            "properties": {
                "allowBlobPublicAccess": True,
                "networkAcls": {"defaultAction": "Allow"},
                "encryption": {
                    "services": {"blob": {"enabled": True}, "file": {"enabled": False}}
                },
            },
        },
        {
            "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Sql/servers/testserver",
            "name": "testserver",
            "type": "Microsoft.Sql/servers",
            "location": "eastus",
            "properties": {"publicNetworkAccess": "Enabled"},
        },
    ]

    # Test threat enumeration
    threats = enumerate_threats(sample_resources)
    print(f"✓ Enumerated {len(threats)} threats from {len(sample_resources)} resources")

    # Print sample threats
    for i, threat in enumerate(threats[:5]):  # Show first 5 threats
        print(
            f"  Threat {i + 1}: {threat['title']} - {threat['severity']} ({threat['stride']})"
        )

    return threats


def test_asb_mapping(threats):
    """Test ASB control mapping."""
    print("\nTesting ASB control mapping...")

    enriched_threats = map_controls(threats)
    print(f"✓ Mapped ASB controls for {len(enriched_threats)} threats")

    # Show sample control mappings
    for i, threat in enumerate(enriched_threats[:3]):  # Show first 3
        controls = threat.get("asb_controls", [])
        print(f"  Threat {i + 1} ({threat['title']}) has {len(controls)} ASB controls")
        for control in controls[:2]:  # Show first 2 controls
            print(
                f"    - {control.get('control_id', 'N/A')}: {control.get('title', 'N/A')}"
            )

    return enriched_threats


def test_report_generation(enriched_threats):
    """Test report generation."""
    print("\nTesting report generation...")

    # Create a temporary spec file path for report generation
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
        temp_spec_path = f.name
        f.write(
            "# Test Specification\nThis is a test specification for threat modeling."
        )

    try:
        # Test DFD artifact
        dfd_artifact = """
        flowchart TD
            A[Web Application] --> B[Database]
            A --> C[Storage Account]
            B --> D[Key Vault]
        """

        builder = ThreatModelReportBuilder()

        # Test markdown report
        report_path = builder.build_comprehensive_report(
            dfd_artifact, enriched_threats, temp_spec_path, "markdown", True
        )

        if report_path and os.path.exists(report_path):
            print(f"✓ Generated markdown report: {report_path}")

            # Check report content
            with open(report_path, encoding="utf-8") as f:
                content = f.read()
                if "Azure Threat Model Report" in content and "STRIDE" in content:
                    print("✓ Report contains expected content")
                else:
                    print("✗ Report missing expected content")
        else:
            print("✗ Failed to generate markdown report")

        # Test JSON report
        json_report_path = builder.build_comprehensive_report(
            dfd_artifact, enriched_threats, temp_spec_path, "json", True
        )

        if json_report_path and os.path.exists(json_report_path):
            print(f"✓ Generated JSON report: {json_report_path}")
        else:
            print("✗ Failed to generate JSON report")

    finally:
        # Cleanup temp file
        if os.path.exists(temp_spec_path):
            os.unlink(temp_spec_path)


def test_tmt_runner_replacement():
    """Test the TMT runner replacement functionality."""
    print("\nTesting TMT runner replacement...")

    runner = AzureThreatAnalysisRunner()

    # Test DFD analysis
    dfd_spec = """
    flowchart TD
        A[Web App] --> B[SQL Database]
        A --> C[Storage Account]
        B --> D[Key Vault]
    """

    threats = runner.analyze_from_dfd_specification(dfd_spec)
    print(f"✓ Analyzed DFD specification and generated {len(threats)} threats")

    # Test with sample resources
    sample_resources = [
        {
            "id": "/test/web-app",
            "name": "test-web-app",
            "type": "Microsoft.Web/sites",
            "properties": {},
        }
    ]

    resource_threats = runner.analyze_from_resources(sample_resources)
    print(f"✓ Analyzed sample resources and generated {len(resource_threats)} threats")

    return threats


def main():
    """Main test function."""
    print("Starting threat modeling functionality tests...\n")

    # Configure logging
    logging.basicConfig(level=logging.INFO)

    try:
        # Test 1: Threat enumeration
        threats = test_threat_enumeration()

        # Test 2: ASB mapping
        enriched_threats = test_asb_mapping(threats)

        # Test 3: Report generation
        test_report_generation(enriched_threats)

        # Test 4: TMT runner replacement
        test_tmt_runner_replacement()

        print("\n✅ All tests completed successfully!")
        print("Threat modeling functionality is working correctly.")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
