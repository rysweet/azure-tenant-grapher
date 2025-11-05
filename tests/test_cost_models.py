"""Unit tests for cost data models."""

from datetime import date

import pytest

from src.models.cost_models import (
    CostAnomaly,
    CostData,
    CostSummary,
    ForecastData,
    Granularity,
    SeverityLevel,
    TimeFrame,
)


class TestCostData:
    """Test cases for CostData model."""

    def test_valid_cost_data(self):
        """Test creation of valid cost data."""
        cost = CostData(
            resource_id="/subscriptions/123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1",
            date=date(2024, 1, 15),
            actual_cost=100.50,
            amortized_cost=95.00,
            usage_quantity=24.0,
            currency="USD",
            service_name="Virtual Machines",
            meter_category="Compute",
            meter_name="D2s v3",
            tags={"env": "prod", "owner": "team1"},
            subscription_id="123",
            resource_group="rg1",
        )

        assert cost.resource_id.endswith("vm1")
        assert cost.actual_cost == 100.50
        assert cost.currency == "USD"
        assert cost.tags["env"] == "prod"

    def test_negative_cost_raises_error(self):
        """Test that negative costs raise ValueError."""
        with pytest.raises(ValueError, match="Actual cost cannot be negative"):
            CostData(
                resource_id="/subscriptions/123/resources/vm1",
                date=date(2024, 1, 15),
                actual_cost=-10.0,
                amortized_cost=0.0,
                usage_quantity=0.0,
                currency="USD",
                service_name="Test",
                meter_category="Test",
                meter_name="Test",
            )

    def test_empty_currency_raises_error(self):
        """Test that empty currency raises ValueError."""
        with pytest.raises(ValueError, match="Currency must be specified"):
            CostData(
                resource_id="/subscriptions/123/resources/vm1",
                date=date(2024, 1, 15),
                actual_cost=10.0,
                amortized_cost=10.0,
                usage_quantity=1.0,
                currency="",
                service_name="Test",
                meter_category="Test",
                meter_name="Test",
            )

    def test_default_tags(self):
        """Test that tags default to empty dict."""
        cost = CostData(
            resource_id="/subscriptions/123/resources/vm1",
            date=date(2024, 1, 15),
            actual_cost=10.0,
            amortized_cost=10.0,
            usage_quantity=1.0,
            currency="USD",
            service_name="Test",
            meter_category="Test",
            meter_name="Test",
        )

        assert cost.tags == {}


class TestForecastData:
    """Test cases for ForecastData model."""

    def test_valid_forecast_data(self):
        """Test creation of valid forecast data."""
        forecast = ForecastData(
            scope="/subscriptions/123",
            forecast_date=date(2024, 2, 1),
            predicted_cost=150.0,
            confidence_lower=140.0,
            confidence_upper=160.0,
        )

        assert forecast.predicted_cost == 150.0
        assert forecast.confidence_interval == (140.0, 160.0)
        assert forecast.confidence_range == 20.0

    def test_negative_prediction_raises_error(self):
        """Test that negative prediction raises ValueError."""
        with pytest.raises(ValueError, match="Predicted cost cannot be negative"):
            ForecastData(
                scope="/subscriptions/123",
                forecast_date=date(2024, 2, 1),
                predicted_cost=-10.0,
                confidence_lower=-15.0,
                confidence_upper=-5.0,
            )

    def test_invalid_confidence_bounds_raise_error(self):
        """Test that invalid confidence bounds raise ValueError."""
        with pytest.raises(
            ValueError, match="Confidence lower bound cannot exceed predicted cost"
        ):
            ForecastData(
                scope="/subscriptions/123",
                forecast_date=date(2024, 2, 1),
                predicted_cost=100.0,
                confidence_lower=110.0,
                confidence_upper=120.0,
            )


class TestCostAnomaly:
    """Test cases for CostAnomaly model."""

    def test_valid_anomaly(self):
        """Test creation of valid anomaly."""
        anomaly = CostAnomaly(
            resource_id="/subscriptions/123/resources/vm1",
            date=date(2024, 1, 15),
            expected_cost=100.0,
            actual_cost=200.0,
            deviation_percent=100.0,
            severity=SeverityLevel.HIGH,
        )

        assert anomaly.absolute_deviation == 100.0
        assert anomaly.is_increase is True
        assert anomaly.is_decrease is False

    def test_cost_decrease_anomaly(self):
        """Test anomaly with cost decrease."""
        anomaly = CostAnomaly(
            resource_id="/subscriptions/123/resources/vm1",
            date=date(2024, 1, 15),
            expected_cost=100.0,
            actual_cost=50.0,
            deviation_percent=-50.0,
            severity=SeverityLevel.MEDIUM,
        )

        assert anomaly.is_decrease is True
        assert anomaly.is_increase is False
        assert anomaly.absolute_deviation == 50.0


class TestCostSummary:
    """Test cases for CostSummary model."""

    def test_valid_summary(self):
        """Test creation of valid summary."""
        summary = CostSummary(
            scope="/subscriptions/123",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            total_cost=3100.0,
            currency="USD",
            resource_count=10,
            service_breakdown={
                "Virtual Machines": 2000.0,
                "Storage": 1000.0,
                "Networking": 100.0,
            },
        )

        assert summary.total_cost == 3100.0
        assert summary.days_in_period == 31
        assert summary.average_daily_cost == 100.0
        assert summary.average_cost_per_resource == 310.0

    def test_zero_resources_average(self):
        """Test average calculation with zero resources."""
        summary = CostSummary(
            scope="/subscriptions/123",
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            total_cost=100.0,
            currency="USD",
            resource_count=0,
        )

        assert summary.average_cost_per_resource == 0.0

    def test_invalid_date_range_raises_error(self):
        """Test that invalid date range raises ValueError."""
        with pytest.raises(ValueError, match="Start date cannot be after end date"):
            CostSummary(
                scope="/subscriptions/123",
                start_date=date(2024, 2, 1),
                end_date=date(2024, 1, 1),
                total_cost=100.0,
                currency="USD",
                resource_count=5,
            )


class TestEnums:
    """Test cases for enum types."""

    def test_granularity_enum(self):
        """Test Granularity enum values."""
        assert Granularity.DAILY.value == "Daily"
        assert Granularity.MONTHLY.value == "Monthly"

    def test_timeframe_enum(self):
        """Test TimeFrame enum values."""
        assert TimeFrame.MONTH_TO_DATE.value == "MonthToDate"
        assert TimeFrame.CUSTOM.value == "Custom"

    def test_severity_enum(self):
        """Test SeverityLevel enum values."""
        assert SeverityLevel.LOW.value == "low"
        assert SeverityLevel.CRITICAL.value == "critical"
