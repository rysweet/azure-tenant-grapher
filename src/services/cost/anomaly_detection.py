"""Cost anomaly detection module using Z-score analysis.

This module provides anomaly detection capabilities for cost data
using statistical Z-score method to identify unusual spending patterns.
"""

import statistics
from datetime import date
from typing import Optional

from ...models.cost_models import CostAnomaly, SeverityLevel


class DataValidationError(Exception):
    """Exception raised when data validation fails."""

    pass


class AnomalyDetector:
    """Service for detecting cost anomalies.

    This service uses Z-score statistical method to detect
    unusual cost patterns based on historical spending data.
    """

    # Minimum days required for anomaly detection
    MIN_LOOKBACK_DAYS = 7

    # Default Z-score thresholds for severity levels
    SEVERITY_THRESHOLDS = {
        SeverityLevel.CRITICAL: 4.0,
        SeverityLevel.HIGH: 3.0,
        SeverityLevel.MEDIUM: 2.5,
        SeverityLevel.LOW: 2.0,
    }

    def detect_anomalies(
        self,
        costs_by_resource: dict[str, list[tuple[date, float]]],
        sensitivity: float = 2.0,
    ) -> list[CostAnomaly]:
        """Detect cost anomalies using Z-score method.

        Args:
            costs_by_resource: Daily costs by resource as dict mapping
                               resource IDs to list of (date, cost) tuples
            sensitivity: Z-score threshold (default: 2.0 standard deviations)

        Returns:
            List of CostAnomaly objects

        Raises:
            DataValidationError: If sensitivity is invalid
        """
        if sensitivity <= 0:
            raise DataValidationError("sensitivity must be positive")

        anomalies = []

        for resource_id, daily_costs in costs_by_resource.items():
            if len(daily_costs) < self.MIN_LOOKBACK_DAYS:
                continue

            costs = [cost for _, cost in daily_costs]

            # Calculate mean and standard deviation
            mean_cost = statistics.mean(costs)
            std_cost = statistics.stdev(costs) if len(costs) > 1 else 0

            if std_cost == 0:
                continue

            # Detect anomalies
            for cost_date, actual_cost in daily_costs:
                z_score = abs((actual_cost - mean_cost) / std_cost)

                if z_score > sensitivity:
                    deviation_percent = ((actual_cost - mean_cost) / mean_cost) * 100
                    severity = self._determine_severity(z_score)

                    anomalies.append(
                        CostAnomaly(
                            resource_id=resource_id,
                            date=cost_date,
                            expected_cost=mean_cost,
                            actual_cost=actual_cost,
                            deviation_percent=deviation_percent,
                            severity=severity,
                        )
                    )

        return anomalies

    def detect_anomalies_with_window(
        self,
        costs_by_resource: dict[str, list[tuple[date, float]]],
        window_size: int = 7,
        sensitivity: float = 2.0,
    ) -> list[CostAnomaly]:
        """Detect anomalies using a rolling window approach.

        This method compares each day's cost against a rolling window
        of previous days, which can better detect recent changes in spending patterns.

        Args:
            costs_by_resource: Daily costs by resource
            window_size: Size of rolling window in days
            sensitivity: Z-score threshold

        Returns:
            List of CostAnomaly objects

        Raises:
            DataValidationError: If parameters are invalid
        """
        if window_size < 3:
            raise DataValidationError("window_size must be at least 3")
        if sensitivity <= 0:
            raise DataValidationError("sensitivity must be positive")

        anomalies = []

        for resource_id, daily_costs in costs_by_resource.items():
            if len(daily_costs) < window_size + 1:
                continue

            for i in range(window_size, len(daily_costs)):
                # Get rolling window
                window_costs = [daily_costs[j][1] for j in range(i - window_size, i)]
                current_date, current_cost = daily_costs[i]

                # Calculate statistics for window
                mean_cost = statistics.mean(window_costs)
                std_cost = (
                    statistics.stdev(window_costs) if len(window_costs) > 1 else 0
                )

                if std_cost == 0:
                    continue

                # Check if current cost is anomalous
                z_score = abs((current_cost - mean_cost) / std_cost)

                if z_score > sensitivity:
                    deviation_percent = ((current_cost - mean_cost) / mean_cost) * 100
                    severity = self._determine_severity(z_score)

                    anomalies.append(
                        CostAnomaly(
                            resource_id=resource_id,
                            date=current_date,
                            expected_cost=mean_cost,
                            actual_cost=current_cost,
                            deviation_percent=deviation_percent,
                            severity=severity,
                        )
                    )

        return anomalies

    def calculate_z_score(
        self, value: float, historical_values: list[float]
    ) -> Optional[float]:
        """Calculate Z-score for a value against historical data.

        Args:
            value: Current value to test
            historical_values: Historical values for comparison

        Returns:
            Z-score or None if insufficient data
        """
        if len(historical_values) < 2:
            return None

        mean = statistics.mean(historical_values)
        std_dev = statistics.stdev(historical_values)

        if std_dev == 0:
            return None

        return abs((value - mean) / std_dev)

    def _determine_severity(self, z_score: float) -> SeverityLevel:
        """Determine severity level based on Z-score.

        Args:
            z_score: Z-score value

        Returns:
            SeverityLevel enum
        """
        if z_score >= self.SEVERITY_THRESHOLDS[SeverityLevel.CRITICAL]:
            return SeverityLevel.CRITICAL
        elif z_score >= self.SEVERITY_THRESHOLDS[SeverityLevel.HIGH]:
            return SeverityLevel.HIGH
        elif z_score >= self.SEVERITY_THRESHOLDS[SeverityLevel.MEDIUM]:
            return SeverityLevel.MEDIUM
        else:
            return SeverityLevel.LOW

    def filter_anomalies_by_severity(
        self,
        anomalies: list[CostAnomaly],
        min_severity: SeverityLevel = SeverityLevel.LOW,
    ) -> list[CostAnomaly]:
        """Filter anomalies by minimum severity level.

        Args:
            anomalies: List of anomalies to filter
            min_severity: Minimum severity level to include

        Returns:
            Filtered list of anomalies
        """
        severity_order = {
            SeverityLevel.LOW: 1,
            SeverityLevel.MEDIUM: 2,
            SeverityLevel.HIGH: 3,
            SeverityLevel.CRITICAL: 4,
        }

        min_level = severity_order[min_severity]
        return [a for a in anomalies if severity_order[a.severity] >= min_level]

    def get_anomaly_summary(self, anomalies: list[CostAnomaly]) -> dict[str, any]:
        """Get summary statistics for detected anomalies.

        Args:
            anomalies: List of anomalies

        Returns:
            Dictionary with summary statistics
        """
        if not anomalies:
            return {
                "total_count": 0,
                "by_severity": {},
                "total_deviation": 0.0,
                "avg_deviation": 0.0,
            }

        by_severity = {}
        for severity in SeverityLevel:
            count = len([a for a in anomalies if a.severity == severity])
            if count > 0:
                by_severity[severity.value] = count

        total_deviation = sum(a.absolute_deviation for a in anomalies)
        avg_deviation = total_deviation / len(anomalies)

        return {
            "total_count": len(anomalies),
            "by_severity": by_severity,
            "total_deviation": total_deviation,
            "avg_deviation": avg_deviation,
            "increases": len([a for a in anomalies if a.is_increase]),
            "decreases": len([a for a in anomalies if a.is_decrease]),
        }
