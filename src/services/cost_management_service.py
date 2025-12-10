"""Azure Cost Management service orchestrator.

This module provides the CostManagementService class that orchestrates
cost operations by delegating to specialized modules following the
Bricks & Studs pattern.

Philosophy:
- Ruthless simplicity through delegation
- Each module is a self-contained "brick"
- Public API is the "stud" that consumers depend on
- Zero breaking changes to existing interface
"""

from datetime import date, timedelta
from typing import Optional

from azure.core.credentials import TokenCredential
from neo4j import AsyncDriver

from ..models.cost_models import (
    CostAnomaly,
    CostData,
    CostSummary,
    ForecastData,
    Granularity,
    TimeFrame,
)
from .cost.anomaly_detection import AnomalyDetector
from .cost.data_fetch import (
    APIRateLimitError,
    CostDataFetcher,
    CostManagementError,
    DataValidationError,
    InvalidScopeError,
)
from .cost.forecasting import CostForecaster
from .cost.query import CostQueryService
from .cost.reporting import CostReporter
from .cost.storage import CostStorageService

# Re-export exceptions from data_fetch for backward compatibility
__all__ = [
    "APIRateLimitError",
    "CostManagementError",
    "CostManagementService",
    "DataValidationError",
    "InvalidScopeError",
]


class CostManagementService:
    """Orchestrator for Azure cost management operations.

    This service coordinates specialized modules for:
    - Fetching cost data from Azure API (CostDataFetcher)
    - Storing costs in Neo4j (CostStorageService)
    - Querying cost data (CostQueryService)
    - Forecasting future costs (CostForecaster)
    - Detecting anomalies (AnomalyDetector)
    - Generating reports (CostReporter)

    Public API is preserved for backward compatibility.
    """

    # Rate limiting configuration (for reference - actual limiting in CostDataFetcher)
    MAX_CALLS_PER_WINDOW = 20
    RATE_LIMIT_WINDOW = 10.0  # seconds

    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        credential: TokenCredential,
    ):
        """Initialize the cost management service orchestrator.

        Args:
            neo4j_driver: Neo4j async driver for database operations
            credential: Azure credential for authentication
        """
        self.neo4j_driver = neo4j_driver
        self.credential = credential

        # Initialize specialized modules
        self.fetcher = CostDataFetcher(credential=credential)
        self.storage = CostStorageService(neo4j_driver=neo4j_driver)
        self.query = CostQueryService(neo4j_driver=neo4j_driver)
        self.forecaster = CostForecaster()
        self.anomaly_detector = AnomalyDetector()
        self.reporter = CostReporter()

        # Maintain backward compatibility
        self.client = None  # Will be set by fetcher.initialize()
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Azure Cost Management client.

        Raises:
            CostManagementError: If initialization fails
        """
        await self.fetcher.initialize()
        self.client = self.fetcher.client  # For backward compatibility
        self._initialized = True

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized.

        Raises:
            CostManagementError: If service is not initialized
        """
        if not self._initialized:
            raise CostManagementError(
                "Service not initialized. Call initialize() first."
            )

    async def fetch_costs(
        self,
        scope: str,
        time_frame: TimeFrame = TimeFrame.MONTH_TO_DATE,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        granularity: Granularity = Granularity.DAILY,
    ) -> list[CostData]:
        """Fetch cost data from Azure Cost Management API.

        Args:
            scope: Azure scope (e.g., /subscriptions/{subscription-id})
            time_frame: Predefined time frame for the query
            start_date: Start date for custom time frame
            end_date: End date for custom time frame
            granularity: Data granularity (daily or monthly)

        Returns:
            List of CostData objects

        Raises:
            InvalidScopeError: If scope format is invalid
            APIRateLimitError: If rate limit is exceeded
            CostManagementError: If API call fails
        """
        return await self.fetcher.fetch_costs(
            scope=scope,
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )

    async def store_costs(self, costs: list[CostData]) -> int:
        """Store cost data in Neo4j.

        Args:
            costs: List of CostData objects to store

        Returns:
            Number of cost records stored

        Raises:
            CostManagementError: If storage fails
        """
        return await self.storage.store_costs(costs)

    async def query_costs(
        self,
        scope: str,
        start_date: date,
        end_date: date,
        group_by: Optional[str] = None,
        tag_key: Optional[str] = None,
    ) -> CostSummary:
        """Query cost data from Neo4j.

        Args:
            scope: Azure scope to query
            start_date: Start date of the period
            end_date: End date of the period
            group_by: Optional grouping field (service_name, resource_group)
            tag_key: Optional tag key for grouping

        Returns:
            CostSummary object with aggregated data

        Raises:
            CostManagementError: If query fails
        """
        return await self.query.query_costs(
            scope=scope,
            start_date=start_date,
            end_date=end_date,
            group_by=group_by,
            tag_key=tag_key,
        )

    async def forecast_costs(
        self,
        scope: str,
        forecast_days: int = 30,
    ) -> list[ForecastData]:
        """Forecast future costs using linear regression.

        Args:
            scope: Azure scope to forecast
            forecast_days: Number of days to forecast

        Returns:
            List of ForecastData objects

        Raises:
            CostManagementError: If forecasting fails
            DataValidationError: If insufficient historical data
        """
        if forecast_days <= 0:
            raise DataValidationError("forecast_days must be positive")

        try:
            # Fetch historical costs (last 90 days) from Neo4j
            end_date = date.today()
            start_date = end_date - timedelta(days=90)

            historical_costs = await self.query.fetch_historical_costs(
                scope=scope,
                start_date=start_date,
                end_date=end_date,
            )

            if len(historical_costs) < 14:
                raise DataValidationError(
                    f"Insufficient historical data for forecasting: {len(historical_costs)} days"
                )

            # Generate forecasts using linear regression
            forecasts = self.forecaster.generate_forecasts(
                historical_costs=historical_costs,
                forecast_days=forecast_days,
                scope=scope,
            )

            # Store forecasts in Neo4j
            await self.storage.store_forecasts(forecasts)

            return forecasts

        except DataValidationError:
            raise
        except Exception as e:
            raise CostManagementError(f"Failed to forecast costs: {e}") from e

    async def detect_anomalies(
        self,
        scope: str,
        lookback_days: int = 30,
        sensitivity: float = 2.0,
    ) -> list[CostAnomaly]:
        """Detect cost anomalies using Z-score method.

        Args:
            scope: Azure scope to analyze
            lookback_days: Number of days to analyze
            sensitivity: Z-score threshold (default: 2.0 standard deviations)

        Returns:
            List of CostAnomaly objects

        Raises:
            CostManagementError: If anomaly detection fails
            DataValidationError: If insufficient data
        """
        if lookback_days < 7:
            raise DataValidationError("lookback_days must be at least 7")
        if sensitivity <= 0:
            raise DataValidationError("sensitivity must be positive")

        try:
            # Fetch daily costs by resource from Neo4j
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            costs_by_resource = await self.query.fetch_daily_costs_by_resource(
                scope=scope,
                start_date=start_date,
                end_date=end_date,
            )

            if not costs_by_resource:
                return []

            # Detect anomalies using Z-score
            anomalies = self.anomaly_detector.detect_anomalies(
                costs_by_resource=costs_by_resource,
                sensitivity=sensitivity,
            )

            # Store anomalies in Neo4j
            if anomalies:
                await self.storage.store_anomalies(anomalies)

            return anomalies

        except DataValidationError:
            raise
        except Exception as e:
            raise CostManagementError(f"Failed to detect anomalies: {e}") from e

    async def allocate_by_tags(
        self,
        tag_key: str,
        start_date: date,
        end_date: date,
        subscription_ids: Optional[list[str]] = None,
    ) -> dict[str, float]:
        """Allocate costs by tag values.

        Args:
            tag_key: Tag key to allocate by
            start_date: Start date of the period
            end_date: End date of the period
            subscription_ids: Optional list of subscription IDs to filter

        Returns:
            Dictionary mapping tag values to total costs

        Raises:
            CostManagementError: If allocation fails
        """
        return await self.query.allocate_by_tags(
            tag_key=tag_key,
            start_date=start_date,
            end_date=end_date,
            subscription_ids=subscription_ids,
        )

    async def generate_report(
        self,
        scope: str,
        start_date: date,
        end_date: date,
        output_format: str = "markdown",
        include_forecast: bool = False,
        include_anomalies: bool = False,
    ) -> str:
        """Generate a cost report.

        Args:
            scope: Azure scope for the report
            start_date: Start date of the period
            end_date: End date of the period
            output_format: Output format (markdown, json)
            include_forecast: Include cost forecast
            include_anomalies: Include anomaly detection

        Returns:
            Report content as string

        Raises:
            CostManagementError: If report generation fails
        """
        try:
            # Validate format first
            self.reporter.validate_output_format(output_format)

            # Fetch cost summary
            summary = await self.query_costs(
                scope=scope,
                start_date=start_date,
                end_date=end_date,
                group_by="service_name",
            )

            # Optionally fetch forecast
            forecast = None
            if include_forecast:
                forecast = await self.forecast_costs(scope, forecast_days=30)

            # Optionally detect anomalies
            anomalies = None
            if include_anomalies:
                anomalies = await self.detect_anomalies(scope, lookback_days=30)

            # Generate report using appropriate format
            if output_format.lower() == "markdown":
                return self.reporter.generate_markdown_report(
                    summary=summary,
                    forecast=forecast,
                    anomalies=anomalies,
                )
            elif output_format.lower() == "json":
                return self.reporter.generate_json_report(
                    summary=summary,
                    forecast=forecast,
                    anomalies=anomalies,
                )
            else:
                raise DataValidationError(f"Unsupported output format: {output_format}")

        except Exception as e:
            raise CostManagementError(f"Failed to generate report: {e}") from e
