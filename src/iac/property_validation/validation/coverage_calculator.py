"""Coverage calculation for property validation.

Calculates what percentage of required properties are present in generated IaC.

Philosophy:
- Simple percentage calculation
- Clear metrics for decision-making
- No complex statistical models
"""

from typing import List, Set

from ..models import CoverageMetrics, Criticality, PropertyGap


class CoverageCalculator:
    """Calculate property coverage metrics."""

    def calculate_coverage(
        self,
        required_properties: Set[str],
        actual_properties: Set[str],
        gaps: List[PropertyGap],
    ) -> CoverageMetrics:
        """Calculate coverage metrics from property sets.

        Args:
            required_properties: Set of all properties from schema
            actual_properties: Set of properties in generated IaC
            gaps: List of identified property gaps with criticality

        Returns:
            CoverageMetrics with complete analysis
        """
        total = len(required_properties)
        covered = len(actual_properties & required_properties)
        missing = total - covered

        # Calculate percentage (handle edge case of no properties)
        coverage_pct = (covered / total * 100.0) if total > 0 else 100.0

        # Count gaps by criticality
        critical_count = sum(
            1 for gap in gaps if gap.criticality == Criticality.CRITICAL
        )
        high_count = sum(1 for gap in gaps if gap.criticality == Criticality.HIGH)
        medium_count = sum(1 for gap in gaps if gap.criticality == Criticality.MEDIUM)
        low_count = sum(1 for gap in gaps if gap.criticality == Criticality.LOW)

        return CoverageMetrics(
            total_properties=total,
            covered_properties=covered,
            missing_properties=missing,
            coverage_percentage=coverage_pct,
            gaps=gaps,
            critical_gaps=critical_count,
            high_priority_gaps=high_count,
            medium_priority_gaps=medium_count,
            low_priority_gaps=low_count,
        )

    def calculate_weighted_score(self, metrics: CoverageMetrics) -> float:
        """Calculate weighted quality score based on gap criticality.

        Weights:
        - CRITICAL gap: -25 points each (blocks deployment)
        - HIGH gap: -10 points each (security risk)
        - MEDIUM gap: -5 points each (operational issue)
        - LOW gap: -1 point each (nice to have)

        Args:
            metrics: Coverage metrics with gap analysis

        Returns:
            Score from 0-100, where 100 is perfect coverage
        """
        base_score = 100.0

        # Deduct points based on criticality
        deductions = (
            metrics.critical_gaps * 25.0
            + metrics.high_priority_gaps * 10.0
            + metrics.medium_priority_gaps * 5.0
            + metrics.low_priority_gaps * 1.0
        )

        return max(0.0, base_score - deductions)


__all__ = ["CoverageCalculator"]
