"""Data models for Azure cost tracking and analysis.

This module provides dataclasses and enums for representing cost data,
forecasts, and anomalies in the Azure Tenant Grapher system.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Granularity(str, Enum):
    """Cost data granularity options."""

    DAILY = "Daily"
    MONTHLY = "Monthly"


class TimeFrame(str, Enum):
    """Time frame options for cost queries."""

    MONTH_TO_DATE = "MonthToDate"
    BILLING_MONTH_TO_DATE = "BillingMonthToDate"
    THE_LAST_MONTH = "TheLastMonth"
    THE_LAST_BILLING_MONTH = "TheLastBillingMonth"
    WEEK_TO_DATE = "WeekToDate"
    CUSTOM = "Custom"


class SeverityLevel(str, Enum):
    """Severity levels for cost anomalies."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CostData:
    """Cost data for a resource or scope.

    Attributes:
        resource_id: Azure resource ID
        date: Date of the cost data
        actual_cost: Actual cost incurred
        amortized_cost: Amortized cost (includes reservations)
        usage_quantity: Quantity of usage
        currency: Currency code (e.g., USD, EUR)
        service_name: Azure service name
        meter_category: Meter category
        meter_name: Meter name
        tags: Resource tags as dictionary
        subscription_id: Subscription ID
        resource_group: Resource group name
    """

    resource_id: str
    date: date
    actual_cost: float
    amortized_cost: float
    usage_quantity: float
    currency: str
    service_name: str
    meter_category: str
    meter_name: str
    tags: dict[str, str] = field(default_factory=dict)
    subscription_id: Optional[str] = None
    resource_group: Optional[str] = None

    def __post_init__(self):
        """Validate cost data after initialization."""
        if self.actual_cost < 0:
            raise ValueError(f"Actual cost cannot be negative: {self.actual_cost}")
        if self.amortized_cost < 0:
            raise ValueError(
                f"Amortized cost cannot be negative: {self.amortized_cost}"
            )
        if not self.currency:
            raise ValueError("Currency must be specified")
        if not isinstance(self.date, date):
            raise TypeError(f"Date must be a date object, got {type(self.date)}")


@dataclass
class ForecastData:
    """Cost forecast data for a scope.

    Attributes:
        scope: Azure scope (subscription, resource group, etc.)
        forecast_date: Date for the forecast
        predicted_cost: Predicted cost amount
        confidence_lower: Lower bound of confidence interval
        confidence_upper: Upper bound of confidence interval
    """

    scope: str
    forecast_date: date
    predicted_cost: float
    confidence_lower: float
    confidence_upper: float

    def __post_init__(self):
        """Validate forecast data after initialization."""
        if self.predicted_cost < 0:
            raise ValueError(
                f"Predicted cost cannot be negative: {self.predicted_cost}"
            )
        if self.confidence_lower > self.predicted_cost:
            raise ValueError("Confidence lower bound cannot exceed predicted cost")
        if self.confidence_upper < self.predicted_cost:
            raise ValueError("Confidence upper bound cannot be below predicted cost")
        if not isinstance(self.forecast_date, date):
            raise TypeError(
                f"Forecast date must be a date object, got {type(self.forecast_date)}"
            )

    @property
    def confidence_interval(self) -> tuple[float, float]:
        """Get confidence interval as tuple."""
        return (self.confidence_lower, self.confidence_upper)

    @property
    def confidence_range(self) -> float:
        """Get the range of the confidence interval."""
        return self.confidence_upper - self.confidence_lower


@dataclass
class CostAnomaly:
    """Cost anomaly detection result.

    Attributes:
        resource_id: Azure resource ID
        date: Date of the anomaly
        expected_cost: Expected cost based on historical data
        actual_cost: Actual cost observed
        deviation_percent: Percentage deviation from expected
        severity: Severity level of the anomaly
    """

    resource_id: str
    date: date
    expected_cost: float
    actual_cost: float
    deviation_percent: float
    severity: SeverityLevel

    def __post_init__(self):
        """Validate anomaly data after initialization."""
        if self.expected_cost < 0:
            raise ValueError(f"Expected cost cannot be negative: {self.expected_cost}")
        if self.actual_cost < 0:
            raise ValueError(f"Actual cost cannot be negative: {self.actual_cost}")
        if not isinstance(self.date, date):
            raise TypeError(f"Date must be a date object, got {type(self.date)}")
        if not isinstance(self.severity, SeverityLevel):
            raise TypeError(
                f"Severity must be a SeverityLevel, got {type(self.severity)}"
            )

    @property
    def absolute_deviation(self) -> float:
        """Get absolute cost deviation."""
        return abs(self.actual_cost - self.expected_cost)

    @property
    def is_increase(self) -> bool:
        """Check if anomaly is a cost increase."""
        return self.actual_cost > self.expected_cost

    @property
    def is_decrease(self) -> bool:
        """Check if anomaly is a cost decrease."""
        return self.actual_cost < self.expected_cost


@dataclass
class CostSummary:
    """Summary of costs for a given scope and period.

    Attributes:
        scope: Azure scope
        start_date: Start date of the period
        end_date: End date of the period
        total_cost: Total cost for the period
        currency: Currency code
        resource_count: Number of resources
        service_breakdown: Cost breakdown by service
        tag_breakdown: Cost breakdown by tag (if applicable)
    """

    scope: str
    start_date: date
    end_date: date
    total_cost: float
    currency: str
    resource_count: int
    service_breakdown: dict[str, float] = field(default_factory=dict)
    tag_breakdown: dict[str, float] = field(default_factory=dict)

    def __post_init__(self):
        """Validate summary data after initialization."""
        if self.total_cost < 0:
            raise ValueError(f"Total cost cannot be negative: {self.total_cost}")
        if self.resource_count < 0:
            raise ValueError(
                f"Resource count cannot be negative: {self.resource_count}"
            )
        if self.start_date > self.end_date:
            raise ValueError("Start date cannot be after end date")

    @property
    def average_cost_per_resource(self) -> float:
        """Calculate average cost per resource."""
        if self.resource_count == 0:
            return 0.0
        return self.total_cost / self.resource_count

    @property
    def days_in_period(self) -> int:
        """Get number of days in the period."""
        return (self.end_date - self.start_date).days + 1

    @property
    def average_daily_cost(self) -> float:
        """Calculate average daily cost."""
        days = self.days_in_period
        if days == 0:
            return 0.0
        return self.total_cost / days
