"""Cost forecasting module using linear regression.

This module provides cost forecasting capabilities using
linear regression on historical cost data with confidence intervals.
"""

import statistics
from datetime import date, timedelta
from typing import Optional

from ...models.cost_models import ForecastData


class DataValidationError(Exception):
    """Exception raised when data validation fails."""

    pass


class CostForecaster:
    """Service for forecasting future costs.

    This service uses linear regression on historical cost data
    to predict future costs with confidence intervals.
    """

    # Minimum days of historical data required for forecasting
    MIN_HISTORICAL_DAYS = 14

    def generate_forecasts(
        self,
        historical_costs: list[tuple[date, float]],
        forecast_days: int,
        scope: str,
    ) -> list[ForecastData]:
        """Generate cost forecasts using linear regression.

        Args:
            historical_costs: Historical cost data as (date, cost) tuples
            forecast_days: Number of days to forecast
            scope: Azure scope

        Returns:
            List of ForecastData objects

        Raises:
            DataValidationError: If insufficient historical data
        """
        if forecast_days <= 0:
            raise DataValidationError("forecast_days must be positive")

        if not historical_costs:
            return []

        if len(historical_costs) < self.MIN_HISTORICAL_DAYS:
            raise DataValidationError(
                f"Insufficient historical data for forecasting: "
                f"{len(historical_costs)} days (minimum {self.MIN_HISTORICAL_DAYS})"
            )

        # Prepare data for linear regression
        x = list(range(len(historical_costs)))
        y = [cost for _, cost in historical_costs]

        # Calculate linear regression parameters
        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        # Calculate slope and intercept
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

        # Calculate standard error for confidence intervals
        predictions = [slope * xi + intercept for xi in x]
        residuals = [yi - pred for yi, pred in zip(y, predictions)]
        std_error = statistics.stdev(residuals) if len(residuals) > 1 else 0

        # Generate forecasts
        forecasts = []
        last_date = historical_costs[-1][0]

        for i in range(1, forecast_days + 1):
            forecast_date = last_date + timedelta(days=i)
            x_value = len(historical_costs) + i - 1
            predicted_cost = max(0, slope * x_value + intercept)

            # Calculate confidence interval (95% = ~2 std errors)
            confidence_range = 2 * std_error
            confidence_lower = max(0, predicted_cost - confidence_range)
            confidence_upper = predicted_cost + confidence_range

            forecasts.append(
                ForecastData(
                    scope=scope,
                    forecast_date=forecast_date,
                    predicted_cost=predicted_cost,
                    confidence_lower=confidence_lower,
                    confidence_upper=confidence_upper,
                )
            )

        return forecasts

    def calculate_trend(
        self, historical_costs: list[tuple[date, float]]
    ) -> tuple[float, float]:
        """Calculate cost trend (slope and intercept) from historical data.

        Args:
            historical_costs: Historical cost data as (date, cost) tuples

        Returns:
            Tuple of (slope, intercept) representing the cost trend

        Raises:
            DataValidationError: If insufficient data
        """
        if not historical_costs:
            raise DataValidationError("No historical data provided")

        if len(historical_costs) < 2:
            raise DataValidationError("At least 2 data points required for trend")

        x = list(range(len(historical_costs)))
        y = [cost for _, cost in historical_costs]

        n = len(x)
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)

        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
        intercept = (sum_y - slope * sum_x) / n

        return (slope, intercept)

    def estimate_monthly_cost(
        self, historical_costs: list[tuple[date, float]]
    ) -> Optional[float]:
        """Estimate average monthly cost based on historical data.

        Args:
            historical_costs: Historical cost data as (date, cost) tuples

        Returns:
            Estimated monthly cost or None if insufficient data
        """
        if not historical_costs or len(historical_costs) < 7:
            return None

        # Calculate daily average
        total_cost = sum(cost for _, cost in historical_costs)
        daily_average = total_cost / len(historical_costs)

        # Extrapolate to monthly (30 days)
        return daily_average * 30

    def calculate_forecast_accuracy(
        self,
        historical_costs: list[tuple[date, float]],
        forecast_days: int = 7,
    ) -> Optional[float]:
        """Calculate forecast accuracy by back-testing on historical data.

        Args:
            historical_costs: Historical cost data as (date, cost) tuples
            forecast_days: Number of days to forecast for testing

        Returns:
            Mean absolute percentage error (MAPE) or None if insufficient data
        """
        if len(historical_costs) < self.MIN_HISTORICAL_DAYS + forecast_days:
            return None

        # Split data into training and testing
        training_data = historical_costs[:-forecast_days]
        testing_data = historical_costs[-forecast_days:]

        # Generate forecasts using training data
        scope = "accuracy_test"
        forecasts = self.generate_forecasts(training_data, forecast_days, scope)

        # Calculate MAPE
        errors = []
        for forecast, (_, actual_cost) in zip(forecasts, testing_data):
            if actual_cost > 0:
                error = abs(forecast.predicted_cost - actual_cost) / actual_cost
                errors.append(error)

        if not errors:
            return None

        # Return MAPE as percentage
        return (sum(errors) / len(errors)) * 100
