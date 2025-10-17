"""Validation report generation for deployment comparisons.

This module generates human-readable markdown reports from graph comparison results,
providing detailed analysis of deployment validation outcomes.
"""

from datetime import datetime
from typing import Optional

from .comparator import ComparisonResult


def generate_markdown_report(
    result: ComparisonResult,
    source_tenant_id: Optional[str] = None,
    target_tenant_id: Optional[str] = None,
) -> str:
    """Generate a markdown validation report from comparison results.

    This function creates a comprehensive markdown report including:
    - Executive summary with similarity score
    - Resource count comparison table
    - Missing and extra resource details
    - Validation status assessment

    Args:
        result: ComparisonResult from graph comparison
        source_tenant_id: Optional source tenant ID for context
        target_tenant_id: Optional target tenant ID for context

    Returns:
        Formatted markdown report as string

    Example:
        >>> result = ComparisonResult(
        ...     source_resource_count=10,
        ...     target_resource_count=10,
        ...     resource_type_counts={},
        ...     missing_resources=[],
        ...     extra_resources=[],
        ...     similarity_score=100.0
        ... )
        >>> report = generate_markdown_report(result)
        >>> assert "100.0%" in report
    """
    # Build header with timestamp and tenant info
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report = f"""# Deployment Validation Report

**Generated**: {timestamp}
"""

    if source_tenant_id and target_tenant_id:
        report += f"""**Source Tenant**: `{source_tenant_id}`
**Target Tenant**: `{target_tenant_id}`

"""

    # Summary section
    report += f"""## Summary

- **Overall Similarity**: {result.similarity_score:.1f}%
- **Source Resources**: {result.source_resource_count}
- **Target Resources**: {result.target_resource_count}
- **Missing Resources**: {len(result.missing_resources)}
- **Extra Resources**: {len(result.extra_resources)}

"""

    # Resource count comparison table
    report += """## Resource Count Comparison

| Resource Type | Source | Target | Match |
|---------------|--------|--------|-------|
"""

    for rtype, counts in sorted(result.resource_type_counts.items()):
        source = counts["source"]
        target = counts["target"]
        match = "OK" if source == target else "DIFF"
        report += f"| {rtype} | {source} | {target} | {match} |\n"

    # Missing resources section
    if result.missing_resources:
        report += "\n## Missing Resources\n\n"
        report += "The following resources are present in the source but missing in the target:\n\n"
        for resource in result.missing_resources:
            report += f"- {resource}\n"

    # Extra resources section
    if result.extra_resources:
        report += "\n## Extra Resources\n\n"
        report += "The following resources are present in the target but not in the source:\n\n"
        for resource in result.extra_resources:
            report += f"- {resource}\n"

    # Validation status with recommendations
    report += "\n## Validation Status\n\n"

    if result.similarity_score >= 95:
        report += "**COMPLETE**: Deployment is complete and matches source.\n\n"
        report += (
            "The target deployment successfully replicates the source configuration. "
        )
        report += "All resource types are present in expected quantities.\n"
    elif result.similarity_score >= 80:
        report += "**MOSTLY COMPLETE**: Deployment is mostly complete with minor discrepancies.\n\n"
        report += "The target deployment is largely successful but has some differences from the source. "
        report += "Review the missing/extra resources sections above to determine if these differences are intentional.\n"
    elif result.similarity_score >= 50:
        report += (
            "**INCOMPLETE**: Deployment has significant differences from source.\n\n"
        )
        report += "The target deployment differs substantially from the source. "
        report += "This may indicate an incomplete deployment or intentional configuration differences. "
        report += "Please review the comparison details carefully.\n"
    else:
        report += "**FAILED**: Deployment has major differences from source.\n\n"
        report += "The target deployment does not match the source configuration. "
        report += "This likely indicates a failed or incomplete deployment process. "
        report += "Immediate investigation is recommended.\n"

    # Add recommendations section
    report += "\n## Recommendations\n\n"

    if result.similarity_score < 95:
        if result.missing_resources:
            report += "1. **Investigate Missing Resources**: Review the missing resources list and determine if they should be deployed to the target.\n"
        if result.extra_resources:
            report += "2. **Review Extra Resources**: Verify if the extra resources in the target are intentional or should be removed.\n"
        report += "3. **Re-run Deployment**: Consider re-running the deployment process if discrepancies are unintentional.\n"
    else:
        report += "No action required. Deployment validation successful.\n"

    return report


def generate_json_report(result: ComparisonResult) -> dict:
    """Generate a JSON-serializable report from comparison results.

    Args:
        result: ComparisonResult from graph comparison

    Returns:
        Dictionary containing report data

    Example:
        >>> result = ComparisonResult(
        ...     source_resource_count=5,
        ...     target_resource_count=5,
        ...     resource_type_counts={},
        ...     missing_resources=[],
        ...     extra_resources=[],
        ...     similarity_score=100.0
        ... )
        >>> json_report = generate_json_report(result)
        >>> assert json_report["similarity_score"] == 100.0
    """
    return {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "similarity_score": result.similarity_score,
            "source_resource_count": result.source_resource_count,
            "target_resource_count": result.target_resource_count,
            "missing_count": len(result.missing_resources),
            "extra_count": len(result.extra_resources),
        },
        "resource_type_counts": result.resource_type_counts,
        "missing_resources": result.missing_resources,
        "extra_resources": result.extra_resources,
        "validation_status": _get_validation_status(result.similarity_score),
    }


def _get_validation_status(similarity_score: float) -> str:
    """Determine validation status from similarity score.

    Args:
        similarity_score: Similarity percentage (0-100)

    Returns:
        Status string: "complete", "mostly_complete", "incomplete", or "failed"
    """
    if similarity_score >= 95:
        return "complete"
    elif similarity_score >= 80:
        return "mostly_complete"
    elif similarity_score >= 50:
        return "incomplete"
    else:
        return "failed"
