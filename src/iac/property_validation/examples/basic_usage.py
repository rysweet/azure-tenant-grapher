"""Basic usage example for Property Validation Engine.

This example demonstrates how to use the validation engine to analyze
property coverage in generated IaC.
"""

import sys
from pathlib import Path

# Add parent directory to path for direct imports (avoiding iac.__init__)
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from property_validation.models import Criticality, PropertyDefinition
from property_validation.validation import (
    CoverageCalculator,
    CriticalClassifier,
    GapFinder,
)


def main():
    """Demonstrate basic validation workflow."""
    print("Property Validation Engine - Basic Usage Example\n")
    print("=" * 60)

    # Step 1: Define schema properties (from Terraform provider schema)
    print("\n1. Defining schema properties...")
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
            has_default=False,
            property_type="string",
            description="Minimum TLS version",
        ),
        "https_only": PropertyDefinition(
            name="https_only",
            required=False,
            has_default=False,
            property_type="bool",
            description="Require HTTPS",
        ),
        "tags": PropertyDefinition(
            name="tags",
            required=False,
            has_default=False,
            property_type="map",
            description="Resource tags",
        ),
        "lifecycle_policy": PropertyDefinition(
            name="lifecycle_policy",
            required=False,
            has_default=False,
            property_type="object",
            description="Lifecycle management",
        ),
    }
    print(f"   Defined {len(schema_properties)} properties from schema")

    # Step 2: Simulate actual properties in generated IaC
    print("\n2. Checking properties in generated IaC...")
    actual_properties = {
        "account_tier",  # Present
        "replication_type",  # Present
        "tags",  # Present
        # Missing: tls_version, https_only, lifecycle_policy
    }
    print(f"   Found {len(actual_properties)} properties in generated code")

    # Step 3: Initialize validation components
    print("\n3. Initializing validation engine...")
    classifier = CriticalClassifier()
    finder = GapFinder(classifier)
    calculator = CoverageCalculator()
    print("   ✓ Validation engine ready")

    # Step 4: Find property gaps
    print("\n4. Analyzing property gaps...")
    gaps = finder.find_gaps(schema_properties, actual_properties)
    print(f"   Found {len(gaps)} missing properties")

    # Step 5: Calculate coverage metrics
    print("\n5. Calculating coverage metrics...")
    required_set = set(schema_properties.keys())
    metrics = calculator.calculate_coverage(required_set, actual_properties, gaps)

    print(f"\n   Coverage Results:")
    print(f"   - Total properties: {metrics.total_properties}")
    print(f"   - Covered: {metrics.covered_properties}")
    print(f"   - Missing: {metrics.missing_properties}")
    print(f"   - Coverage: {metrics.coverage_percentage:.1f}%")

    # Step 6: Analyze gaps by criticality
    print(f"\n6. Gap analysis by criticality:")
    print(f"   - CRITICAL gaps: {metrics.critical_gaps}")
    print(f"   - HIGH priority: {metrics.high_priority_gaps}")
    print(f"   - MEDIUM priority: {metrics.medium_priority_gaps}")
    print(f"   - LOW priority: {metrics.low_priority_gaps}")

    # Step 7: Calculate weighted quality score
    print("\n7. Calculating quality score...")
    score = calculator.calculate_weighted_score(metrics)
    print(f"   Quality Score: {score:.1f}/100")

    # Step 8: Display gap details
    print("\n8. Detailed gap analysis:")
    print("-" * 60)
    for gap in gaps:
        print(f"\n   Property: {gap.property_name}")
        print(f"   Criticality: {gap.criticality.value.upper()}")
        print(f"   Reason: {gap.reason}")
        if gap.suggested_value:
            print(f"   Suggested: {gap.suggested_value}")

    # Step 9: Recommendations
    print("\n" + "=" * 60)
    print("9. Recommendations:")
    print("-" * 60)

    if metrics.critical_gaps > 0:
        print(f"   ⚠️  URGENT: {metrics.critical_gaps} CRITICAL gap(s) block deployment")
        print("   Action: Add these properties immediately")

    if metrics.high_priority_gaps > 0:
        print(
            f"   ⚠️  HIGH: {metrics.high_priority_gaps} security/compliance gap(s) found"
        )
        print("   Action: Add these properties to meet security standards")

    if metrics.medium_priority_gaps > 0:
        print(f"   ℹ️  MEDIUM: {metrics.medium_priority_gaps} operational gap(s) found")
        print("   Action: Consider adding for better operations")

    if metrics.low_priority_gaps > 0:
        print(f"   ℹ️  LOW: {metrics.low_priority_gaps} optional feature(s) missing")
        print("   Action: Add if needed for specific use cases")

    if metrics.coverage_percentage == 100.0:
        print("\n   ✅ Perfect coverage! All properties present.")

    print("\n" + "=" * 60)
    print("Validation complete!\n")


if __name__ == "__main__":
    main()
