"""Azure Cost Management service for cost tracking and analysis.

This module provides the CostManagementService class for fetching, storing,
and analyzing Azure cost data using the Azure Cost Management API and Neo4j.
"""

import asyncio
import json
import statistics
from datetime import date, datetime, timedelta
from typing import Any, Optional

from azure.core.credentials import TokenCredential
from azure.core.exceptions import HttpResponseError
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.costmanagement.models import (
    QueryAggregation,
    QueryDataset,
    QueryDefinition,
    QueryGrouping,
    QueryTimePeriod,
    TimeframeType,
)
from neo4j import AsyncDriver

from ..models.cost_models import (
    CostAnomaly,
    CostData,
    CostSummary,
    ForecastData,
    Granularity,
    SeverityLevel,
    TimeFrame,
)


# Custom Exceptions
class CostManagementError(Exception):
    """Base exception for cost management errors."""

    pass


class APIRateLimitError(CostManagementError):
    """Exception raised when API rate limit is exceeded."""

    pass


class InvalidScopeError(CostManagementError):
    """Exception raised when an invalid scope is provided."""

    pass


class DataValidationError(CostManagementError):
    """Exception raised when data validation fails."""

    pass


class CostManagementService:
    """Service for Azure cost management operations.

    This service handles fetching cost data from Azure Cost Management API,
    storing it in Neo4j, and providing analysis capabilities including
    forecasting and anomaly detection.
    """

    # Rate limiting configuration
    MAX_CALLS_PER_WINDOW = 20
    RATE_LIMIT_WINDOW = 10.0  # seconds

    def __init__(
        self,
        neo4j_driver: AsyncDriver,
        credential: TokenCredential,
    ):
        """Initialize the cost management service.

        Args:
            neo4j_driver: Neo4j async driver for database operations
            credential: Azure credential for authentication
        """
        self.neo4j_driver = neo4j_driver
        self.credential = credential
        self.client: Optional[CostManagementClient] = None
        self._rate_limiter = RateLimiter(
            max_calls=self.MAX_CALLS_PER_WINDOW,
            window_seconds=self.RATE_LIMIT_WINDOW,
        )
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the Azure Cost Management client.

        Raises:
            CostManagementError: If initialization fails
        """
        try:
            self.client = CostManagementClient(credential=self.credential)
            self._initialized = True
        except Exception as e:
            raise CostManagementError(
                f"Failed to initialize Cost Management client: {e}"
            ) from e

    def _ensure_initialized(self) -> None:
        """Ensure the service is initialized.

        Raises:
            CostManagementError: If service is not initialized
        """
        if not self._initialized or self.client is None:
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
        self._ensure_initialized()
        self._validate_scope(scope)

        if time_frame == TimeFrame.CUSTOM:
            if not start_date or not end_date:
                raise DataValidationError(
                    "start_date and end_date required for CUSTOM time frame"
                )
            if start_date > end_date:
                raise DataValidationError("start_date cannot be after end_date")

        # Build query definition
        query_def = self._build_query_definition(
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date,
            granularity=granularity,
        )

        # Execute query with rate limiting and retry logic
        result = await self._execute_with_retry(
            lambda: self._query_usage(scope, query_def)
        )

        # Parse and return cost data
        return self._parse_cost_data(result, scope)

    async def store_costs(self, costs: list[CostData]) -> int:
        """Store cost data in Neo4j.

        Args:
            costs: List of CostData objects to store

        Returns:
            Number of cost records stored

        Raises:
            CostManagementError: If storage fails
        """
        if not costs:
            return 0

        try:
            async with self.neo4j_driver.session() as session:
                count = await session.execute_write(self._create_cost_nodes, costs)
                return count
        except Exception as e:
            raise CostManagementError(f"Failed to store costs in Neo4j: {e}") from e

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
        try:
            async with self.neo4j_driver.session() as session:
                result = await session.execute_read(
                    self._query_cost_summary,
                    scope,
                    start_date,
                    end_date,
                    group_by,
                    tag_key,
                )
                return result
        except Exception as e:
            raise CostManagementError(f"Failed to query costs from Neo4j: {e}") from e

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
            # Fetch historical costs (last 90 days)
            end_date = date.today()
            start_date = end_date - timedelta(days=90)

            async with self.neo4j_driver.session() as session:
                historical_costs = await session.execute_read(
                    self._fetch_historical_costs,
                    scope,
                    start_date,
                    end_date,
                )

            if len(historical_costs) < 14:
                raise DataValidationError(
                    f"Insufficient historical data for forecasting: {len(historical_costs)} days"
                )

            # Generate forecasts using linear regression
            forecasts = self._generate_forecasts(historical_costs, forecast_days, scope)

            # Store forecasts in Neo4j
            await self._store_forecasts(forecasts)

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
            end_date = date.today()
            start_date = end_date - timedelta(days=lookback_days)

            async with self.neo4j_driver.session() as session:
                daily_costs = await session.execute_read(
                    self._fetch_daily_costs_by_resource,
                    scope,
                    start_date,
                    end_date,
                )

            if not daily_costs:
                return []

            # Detect anomalies using Z-score
            anomalies = self._detect_anomalies_zscore(daily_costs, sensitivity)

            # Store anomalies in Neo4j
            if anomalies:
                await self._store_anomalies(anomalies)

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
        try:
            async with self.neo4j_driver.session() as session:
                allocation = await session.execute_read(
                    self._allocate_costs_by_tag,
                    tag_key,
                    start_date,
                    end_date,
                    subscription_ids,
                )
                return allocation
        except Exception as e:
            raise CostManagementError(f"Failed to allocate costs by tags: {e}") from e

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

            # Generate report
            if output_format == "markdown":
                return self._generate_markdown_report(summary, forecast, anomalies)
            elif output_format == "json":
                return self._generate_json_report(summary, forecast, anomalies)
            else:
                raise DataValidationError(f"Unsupported output format: {output_format}")

        except Exception as e:
            raise CostManagementError(f"Failed to generate report: {e}") from e

    # Private helper methods

    def _validate_scope(self, scope: str) -> None:
        """Validate Azure scope format.

        Args:
            scope: Azure scope string

        Raises:
            InvalidScopeError: If scope format is invalid
        """
        if not scope:
            raise InvalidScopeError("Scope cannot be empty")

        valid_prefixes = [
            "/subscriptions/",
            "/providers/Microsoft.Management/managementGroups/",
            "/providers/Microsoft.Billing/billingAccounts/",
        ]

        if not any(scope.startswith(prefix) for prefix in valid_prefixes):
            raise InvalidScopeError(
                f"Invalid scope format. Must start with one of: {valid_prefixes}"
            )

    def _build_query_definition(
        self,
        time_frame: TimeFrame,
        start_date: Optional[date],
        end_date: Optional[date],
        granularity: Granularity,
    ) -> QueryDefinition:
        """Build Azure Cost Management query definition.

        Args:
            time_frame: Time frame for the query
            start_date: Start date for custom time frame
            end_date: End date for custom time frame
            granularity: Data granularity

        Returns:
            QueryDefinition object
        """
        # Build time period
        time_period = None
        if time_frame == TimeFrame.CUSTOM and start_date and end_date:
            time_period = QueryTimePeriod(
                from_property=start_date.isoformat(),
                to=end_date.isoformat(),
            )

        # Build dataset
        dataset = QueryDataset(
            granularity=granularity.value,
            aggregation={
                "totalCost": QueryAggregation(name="Cost", function="Sum"),
                "totalCostUSD": QueryAggregation(name="CostUSD", function="Sum"),
            },
            grouping=[
                QueryGrouping(type="Dimension", name="ResourceId"),
                QueryGrouping(type="Dimension", name="ServiceName"),
                QueryGrouping(type="Dimension", name="MeterCategory"),
                QueryGrouping(type="Dimension", name="MeterName"),
                QueryGrouping(type="Dimension", name="ResourceGroupName"),
            ],
        )

        return QueryDefinition(
            type="Usage",
            timeframe=time_frame.value
            if time_frame != TimeFrame.CUSTOM
            else TimeframeType.CUSTOM,
            time_period=time_period,
            dataset=dataset,
        )

    async def _execute_with_retry(
        self,
        func,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ) -> Any:
        """Execute a function with exponential backoff retry logic.

        Args:
            func: Function to execute
            max_retries: Maximum number of retries
            base_delay: Base delay for exponential backoff

        Returns:
            Result of the function

        Raises:
            APIRateLimitError: If rate limited
            CostManagementError: If execution fails after retries
        """
        await self._rate_limiter.acquire()

        for attempt in range(max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    return await func()
                else:
                    return func()
            except HttpResponseError as e:
                if e.status_code == 429:
                    # Rate limited
                    if attempt == max_retries:
                        raise APIRateLimitError("API rate limit exceeded") from e
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
                elif e.status_code == 401:
                    raise CostManagementError("Authentication failed") from e
                elif e.status_code == 400:
                    raise DataValidationError(f"Invalid request: {e.message}") from e
                elif e.status_code == 404:
                    raise InvalidScopeError(f"Scope not found: {e.message}") from e
                else:
                    if attempt == max_retries:
                        raise CostManagementError(
                            f"API call failed: {e.message}"
                        ) from e
                    delay = base_delay * (2**attempt)
                    await asyncio.sleep(delay)
            except Exception as e:
                if attempt == max_retries:
                    raise CostManagementError(f"Unexpected error: {e}") from e
                delay = base_delay * (2**attempt)
                await asyncio.sleep(delay)

    def _query_usage(self, scope: str, query_def: QueryDefinition) -> Any:
        """Execute usage query against Azure Cost Management API.

        Args:
            scope: Azure scope
            query_def: Query definition

        Returns:
            Query result
        """
        return self.client.query.usage(scope=scope, parameters=query_def)

    def _parse_cost_data(self, result: Any, scope: str) -> list[CostData]:
        """Parse Azure Cost Management API response into CostData objects.

        Args:
            result: API response
            scope: Azure scope

        Returns:
            List of CostData objects
        """
        costs = []

        if not hasattr(result, "rows") or not result.rows:
            return costs

        # Extract column mapping
        columns = {col.name: idx for idx, col in enumerate(result.columns)}

        for row in result.rows:
            try:
                # Extract subscription ID from scope or resource ID
                subscription_id = self._extract_subscription_id(scope)
                resource_id = row[columns.get("ResourceId", 0)] or scope

                cost_data = CostData(
                    resource_id=resource_id,
                    date=self._parse_date(row[columns.get("UsageDate", 1)]),
                    actual_cost=float(row[columns.get("Cost", 2)] or 0),
                    amortized_cost=float(row[columns.get("CostUSD", 3)] or 0),
                    usage_quantity=float(row[columns.get("UsageQuantity", 4)] or 0),
                    currency=str(row[columns.get("Currency", 5)] or "USD"),
                    service_name=str(row[columns.get("ServiceName", 6)] or "Unknown"),
                    meter_category=str(
                        row[columns.get("MeterCategory", 7)] or "Unknown"
                    ),
                    meter_name=str(row[columns.get("MeterName", 8)] or "Unknown"),
                    tags=self._parse_tags(
                        row[columns.get("Tags", 9)] if columns.get("Tags") else None
                    ),
                    subscription_id=subscription_id,
                    resource_group=str(
                        row[columns.get("ResourceGroupName", 10)] or None
                    ),
                )
                costs.append(cost_data)
            except (ValueError, TypeError, IndexError):
                # Skip invalid rows
                continue

        return costs

    def _parse_date(self, date_value: Any) -> date:
        """Parse date from various formats.

        Args:
            date_value: Date value to parse

        Returns:
            date object
        """
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, datetime):
            return date_value.date()
        if isinstance(date_value, str):
            return datetime.fromisoformat(date_value.replace("Z", "+00:00")).date()
        if isinstance(date_value, int):
            # Assume Unix timestamp
            return datetime.fromtimestamp(date_value).date()
        return date.today()

    def _parse_tags(self, tags_value: Any) -> dict[str, str]:
        """Parse tags from various formats.

        Args:
            tags_value: Tags value to parse

        Returns:
            Dictionary of tags
        """
        if isinstance(tags_value, dict):
            return tags_value
        if isinstance(tags_value, str):
            try:
                return json.loads(tags_value)
            except json.JSONDecodeError:
                return {}
        return {}

    def _extract_subscription_id(self, scope: str) -> Optional[str]:
        """Extract subscription ID from scope.

        Args:
            scope: Azure scope

        Returns:
            Subscription ID or None
        """
        if "/subscriptions/" in scope:
            parts = scope.split("/subscriptions/")[1].split("/")
            return parts[0] if parts else None
        return None

    @staticmethod
    def _convert_neo4j_date(neo4j_date: Any) -> date:
        """Convert Neo4j Date object to Python date.

        Handles multiple date types from Neo4j driver including neo4j.time.Date,
        Python date, datetime, and ISO string formats.

        Args:
            neo4j_date: Date value from Neo4j (neo4j.time.Date, date, datetime, or str)

        Returns:
            Python date object

        Raises:
            TypeError: If value cannot be converted to date
        """
        from datetime import date, datetime

        # Handle Python date (passthrough)
        if isinstance(neo4j_date, date):
            return neo4j_date

        # Handle Neo4j Date objects (have year, month, day attributes)
        if (
            hasattr(neo4j_date, "year")
            and hasattr(neo4j_date, "month")
            and hasattr(neo4j_date, "day")
        ):
            return date(neo4j_date.year, neo4j_date.month, neo4j_date.day)

        # Handle datetime
        if isinstance(neo4j_date, datetime):
            return neo4j_date.date()

        # Handle ISO string
        if isinstance(neo4j_date, str):
            return datetime.fromisoformat(neo4j_date.replace("Z", "+00:00")).date()

        raise TypeError(f"Cannot convert {type(neo4j_date)} to date")

    @staticmethod
    async def _create_cost_nodes(tx, costs: list[CostData]) -> int:
        """Create Cost nodes in Neo4j.

        Args:
            tx: Neo4j transaction
            costs: List of CostData objects

        Returns:
            Number of nodes created
        """
        query = """
        UNWIND $costs AS cost
        MERGE (c:Cost {
            id: cost.resource_id + '_' + cost.date
        })
        SET c.resource_id = cost.resource_id,
            c.date = date(cost.date),
            c.actual_cost = cost.actual_cost,
            c.amortized_cost = cost.amortized_cost,
            c.usage_quantity = cost.usage_quantity,
            c.currency = cost.currency,
            c.service_name = cost.service_name,
            c.meter_category = cost.meter_category,
            c.meter_name = cost.meter_name,
            c.tags = cost.tags,
            c.subscription_id = cost.subscription_id,
            c.resource_group = cost.resource_group,
            c.updated_at = datetime()
        SET c.created_at = coalesce(c.created_at, datetime())

        WITH c, cost
        OPTIONAL MATCH (r:Resource {id: cost.resource_id})
        FOREACH (ignoreMe IN CASE WHEN r IS NOT NULL THEN [1] ELSE [] END |
            MERGE (r)-[:INCURS_COST]->(c)
        )

        WITH c, cost
        WHERE cost.resource_group IS NOT NULL
        OPTIONAL MATCH (rg:ResourceGroup {name: cost.resource_group})
        FOREACH (ignoreMe IN CASE WHEN rg IS NOT NULL THEN [1] ELSE [] END |
            MERGE (rg)-[:INCURS_COST]->(c)
        )

        WITH c, cost
        WHERE cost.subscription_id IS NOT NULL
        OPTIONAL MATCH (s:Subscription {subscription_id: cost.subscription_id})
        FOREACH (ignoreMe IN CASE WHEN s IS NOT NULL THEN [1] ELSE [] END |
            MERGE (s)-[:INCURS_COST]->(c)
        )

        RETURN count(c) AS count
        """

        cost_dicts = [
            {
                "resource_id": c.resource_id,
                "date": c.date.isoformat(),
                "actual_cost": c.actual_cost,
                "amortized_cost": c.amortized_cost,
                "usage_quantity": c.usage_quantity,
                "currency": c.currency,
                "service_name": c.service_name,
                "meter_category": c.meter_category,
                "meter_name": c.meter_name,
                "tags": json.dumps(c.tags),
                "subscription_id": c.subscription_id,
                "resource_group": c.resource_group,
            }
            for c in costs
        ]

        result = await tx.run(query, costs=cost_dicts)
        record = await result.single()
        return record["count"] if record else 0

    @staticmethod
    async def _query_cost_summary(
        tx,
        scope: str,
        start_date: date,
        end_date: date,
        group_by: Optional[str],
        tag_key: Optional[str],
    ) -> CostSummary:
        """Query cost summary from Neo4j.

        Args:
            tx: Neo4j transaction
            scope: Azure scope
            start_date: Start date
            end_date: End date
            group_by: Grouping field
            tag_key: Tag key for grouping

        Returns:
            CostSummary object
        """
        # Build scope filter
        if "/subscriptions/" in scope:
            subscription_id = scope.split("/subscriptions/")[1].split("/")[0]
            scope_filter = "c.subscription_id = $scope_id"
            scope_id = subscription_id
        else:
            scope_filter = "c.resource_id STARTS WITH $scope_id"
            scope_id = scope

        query = f"""
        MATCH (c:Cost)
        WHERE {scope_filter}
            AND c.date >= date($start_date)
            AND c.date <= date($end_date)
        WITH sum(c.actual_cost) AS total,
             collect(DISTINCT c.currency)[0] AS currency,
             count(DISTINCT c.resource_id) AS resource_count
        RETURN total, currency, resource_count
        """

        result = await tx.run(
            query,
            scope_id=scope_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )
        record = await result.single()

        if not record:
            return CostSummary(
                scope=scope,
                start_date=start_date,
                end_date=end_date,
                total_cost=0.0,
                currency="USD",
                resource_count=0,
            )

        # Query service breakdown if requested
        service_breakdown = {}
        if group_by == "service_name":
            service_query = f"""
            MATCH (c:Cost)
            WHERE {scope_filter}
                AND c.date >= date($start_date)
                AND c.date <= date($end_date)
            WITH c.service_name AS service, sum(c.actual_cost) AS cost
            RETURN service, cost
            ORDER BY cost DESC
            """
            service_result = await tx.run(
                service_query,
                scope_id=scope_id,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            async for service_record in service_result:
                service_breakdown[service_record["service"]] = service_record["cost"]

        return CostSummary(
            scope=scope,
            start_date=start_date,
            end_date=end_date,
            total_cost=float(record["total"] or 0),
            currency=str(record["currency"] or "USD"),
            resource_count=int(record["resource_count"] or 0),
            service_breakdown=service_breakdown,
        )

    @staticmethod
    async def _fetch_historical_costs(
        tx,
        scope: str,
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, float]]:
        """Fetch historical daily costs for forecasting.

        Args:
            tx: Neo4j transaction
            scope: Azure scope
            start_date: Start date
            end_date: End date

        Returns:
            List of (date, cost) tuples
        """
        if "/subscriptions/" in scope:
            subscription_id = scope.split("/subscriptions/")[1].split("/")[0]
            scope_filter = "c.subscription_id = $scope_id"
            scope_id = subscription_id
        else:
            scope_filter = "c.resource_id STARTS WITH $scope_id"
            scope_id = scope

        query = f"""
        MATCH (c:Cost)
        WHERE {scope_filter}
            AND c.date >= date($start_date)
            AND c.date <= date($end_date)
        WITH c.date AS cost_date, sum(c.actual_cost) AS daily_cost
        RETURN cost_date, daily_cost
        ORDER BY cost_date
        """

        result = await tx.run(
            query,
            scope_id=scope_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        costs = []
        async for record in result:
            costs.append(
                (
                    CostManagementService._convert_neo4j_date(record["cost_date"]),
                    float(record["daily_cost"]),
                )
            )

        return costs

    def _generate_forecasts(
        self,
        historical_costs: list[tuple[date, float]],
        forecast_days: int,
        scope: str,
    ) -> list[ForecastData]:
        """Generate cost forecasts using linear regression.

        Args:
            historical_costs: Historical cost data
            forecast_days: Number of days to forecast
            scope: Azure scope

        Returns:
            List of ForecastData objects
        """
        if not historical_costs:
            return []

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

    async def _store_forecasts(self, forecasts: list[ForecastData]) -> None:
        """Store forecast data in Neo4j.

        Args:
            forecasts: List of ForecastData objects
        """
        async with self.neo4j_driver.session() as session:
            await session.execute_write(self._create_forecast_nodes, forecasts)

    @staticmethod
    async def _create_forecast_nodes(tx, forecasts: list[ForecastData]) -> None:
        """Create CostForecast nodes in Neo4j.

        Args:
            tx: Neo4j transaction
            forecasts: List of ForecastData objects
        """
        query = """
        UNWIND $forecasts AS forecast
        CREATE (f:CostForecast {
            id: forecast.scope + '_' + forecast.forecast_date,
            scope: forecast.scope,
            forecast_date: date(forecast.forecast_date),
            predicted_cost: forecast.predicted_cost,
            confidence_lower: forecast.confidence_lower,
            confidence_upper: forecast.confidence_upper,
            model_version: 'linear_v1',
            created_at: datetime()
        })
        """

        forecast_dicts = [
            {
                "scope": f.scope,
                "forecast_date": f.forecast_date.isoformat(),
                "predicted_cost": f.predicted_cost,
                "confidence_lower": f.confidence_lower,
                "confidence_upper": f.confidence_upper,
            }
            for f in forecasts
        ]

        await tx.run(query, forecasts=forecast_dicts)

    @staticmethod
    async def _fetch_daily_costs_by_resource(
        tx,
        scope: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, list[tuple[date, float]]]:
        """Fetch daily costs grouped by resource.

        Args:
            tx: Neo4j transaction
            scope: Azure scope
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping resource IDs to list of (date, cost) tuples
        """
        if "/subscriptions/" in scope:
            subscription_id = scope.split("/subscriptions/")[1].split("/")[0]
            scope_filter = "c.subscription_id = $scope_id"
            scope_id = subscription_id
        else:
            scope_filter = "c.resource_id STARTS WITH $scope_id"
            scope_id = scope

        query = f"""
        MATCH (c:Cost)
        WHERE {scope_filter}
            AND c.date >= date($start_date)
            AND c.date <= date($end_date)
        RETURN c.resource_id AS resource_id, c.date AS cost_date, c.actual_cost AS cost
        ORDER BY c.resource_id, c.date
        """

        result = await tx.run(
            query,
            scope_id=scope_id,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )

        costs_by_resource = {}
        async for record in result:
            resource_id = record["resource_id"]
            if resource_id not in costs_by_resource:
                costs_by_resource[resource_id] = []
            costs_by_resource[resource_id].append(
                (
                    CostManagementService._convert_neo4j_date(record["cost_date"]),
                    float(record["cost"]),
                )
            )

        return costs_by_resource

    def _detect_anomalies_zscore(
        self,
        costs_by_resource: dict[str, list[tuple[date, float]]],
        sensitivity: float,
    ) -> list[CostAnomaly]:
        """Detect anomalies using Z-score method.

        Args:
            costs_by_resource: Daily costs by resource
            sensitivity: Z-score threshold

        Returns:
            List of CostAnomaly objects
        """
        anomalies = []

        for resource_id, daily_costs in costs_by_resource.items():
            if len(daily_costs) < 7:
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

                    # Determine severity
                    if z_score > 4:
                        severity = SeverityLevel.CRITICAL
                    elif z_score > 3:
                        severity = SeverityLevel.HIGH
                    elif z_score > 2.5:
                        severity = SeverityLevel.MEDIUM
                    else:
                        severity = SeverityLevel.LOW

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

    async def _store_anomalies(self, anomalies: list[CostAnomaly]) -> None:
        """Store anomaly data in Neo4j.

        Args:
            anomalies: List of CostAnomaly objects
        """
        async with self.neo4j_driver.session() as session:
            await session.execute_write(self._create_anomaly_nodes, anomalies)

    @staticmethod
    async def _create_anomaly_nodes(tx, anomalies: list[CostAnomaly]) -> None:
        """Create CostAnomaly nodes in Neo4j.

        Args:
            tx: Neo4j transaction
            anomalies: List of CostAnomaly objects
        """
        query = """
        UNWIND $anomalies AS anomaly
        CREATE (a:CostAnomaly {
            id: anomaly.resource_id + '_' + anomaly.date,
            resource_id: anomaly.resource_id,
            date: date(anomaly.date),
            expected_cost: anomaly.expected_cost,
            actual_cost: anomaly.actual_cost,
            deviation_percent: anomaly.deviation_percent,
            severity: anomaly.severity,
            detected_at: datetime()
        })
        """

        anomaly_dicts = [
            {
                "resource_id": a.resource_id,
                "date": a.date.isoformat(),
                "expected_cost": a.expected_cost,
                "actual_cost": a.actual_cost,
                "deviation_percent": a.deviation_percent,
                "severity": a.severity.value,
            }
            for a in anomalies
        ]

        await tx.run(query, anomalies=anomaly_dicts)

    @staticmethod
    async def _allocate_costs_by_tag(
        tx,
        tag_key: str,
        start_date: date,
        end_date: date,
        subscription_ids: Optional[list[str]],
    ) -> dict[str, float]:
        """Allocate costs by tag values.

        Args:
            tx: Neo4j transaction
            tag_key: Tag key to allocate by
            start_date: Start date
            end_date: End date
            subscription_ids: Optional subscription filter

        Returns:
            Dictionary mapping tag values to costs
        """
        subscription_filter = ""
        if subscription_ids:
            subscription_filter = "AND c.subscription_id IN $subscription_ids"

        query = f"""
        MATCH (c:Cost)
        WHERE c.date >= date($start_date)
            AND c.date <= date($end_date)
            {subscription_filter}
            AND c.tags IS NOT NULL
        WITH c,
             CASE
                WHEN c.tags CONTAINS $tag_key
                THEN apoc.convert.fromJsonMap(c.tags)[$tag_key]
                ELSE 'untagged'
             END AS tag_value
        RETURN tag_value, sum(c.actual_cost) AS total_cost
        ORDER BY total_cost DESC
        """

        params = {
            "tag_key": tag_key,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
        }

        if subscription_ids:
            params["subscription_ids"] = subscription_ids

        result = await tx.run(query, **params)

        allocation = {}
        async for record in result:
            allocation[record["tag_value"]] = float(record["total_cost"])

        return allocation

    def _generate_markdown_report(
        self,
        summary: CostSummary,
        forecast: Optional[list[ForecastData]],
        anomalies: Optional[list[CostAnomaly]],
    ) -> str:
        """Generate markdown cost report.

        Args:
            summary: Cost summary data
            forecast: Optional forecast data
            anomalies: Optional anomaly data

        Returns:
            Markdown report string
        """
        report = []
        report.append("# Azure Cost Report\n")
        report.append(f"**Scope:** {summary.scope}\n")
        report.append(f"**Period:** {summary.start_date} to {summary.end_date}\n")
        report.append(
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Summary section
        report.append("## Summary\n")
        report.append(
            f"- **Total Cost:** {summary.total_cost:.2f} {summary.currency}\n"
        )
        report.append(f"- **Resources:** {summary.resource_count}\n")
        report.append(
            f"- **Average Daily Cost:** {summary.average_daily_cost:.2f} {summary.currency}\n"
        )
        report.append(
            f"- **Average Cost per Resource:** {summary.average_cost_per_resource:.2f} {summary.currency}\n\n"
        )

        # Service breakdown
        if summary.service_breakdown:
            report.append("## Cost by Service\n")
            report.append("| Service | Cost | Percentage |\n")
            report.append("|---------|------|------------|\n")
            for service, cost in sorted(
                summary.service_breakdown.items(),
                key=lambda x: x[1],
                reverse=True,
            ):
                percentage = (
                    (cost / summary.total_cost * 100) if summary.total_cost > 0 else 0
                )
                report.append(
                    f"| {service} | {cost:.2f} {summary.currency} | {percentage:.1f}% |\n"
                )
            report.append("\n")

        # Forecast section
        if forecast:
            report.append("## 30-Day Forecast\n")
            total_forecast = sum(f.predicted_cost for f in forecast)
            report.append(
                f"- **Predicted Total:** {total_forecast:.2f} {summary.currency}\n"
            )
            report.append(
                f"- **Daily Average:** {total_forecast / len(forecast):.2f} {summary.currency}\n\n"
            )

            report.append("| Date | Predicted Cost | Confidence Range |\n")
            report.append("|------|----------------|------------------|\n")
            for f in forecast[:7]:  # Show first 7 days
                report.append(
                    f"| {f.forecast_date} | {f.predicted_cost:.2f} | "
                    f"{f.confidence_lower:.2f} - {f.confidence_upper:.2f} |\n"
                )
            report.append("\n")

        # Anomalies section
        if anomalies:
            report.append(f"## Cost Anomalies ({len(anomalies)} detected)\n")
            report.append(
                "| Date | Resource | Expected | Actual | Deviation | Severity |\n"
            )
            report.append(
                "|------|----------|----------|--------|-----------|----------|\n"
            )

            # Sort by severity and date
            sorted_anomalies = sorted(
                anomalies,
                key=lambda a: (a.severity.value, a.date),
                reverse=True,
            )

            for a in sorted_anomalies[:20]:  # Show top 20
                report.append(
                    f"| {a.date} | {a.resource_id.split('/')[-1]} | "
                    f"{a.expected_cost:.2f} | {a.actual_cost:.2f} | "
                    f"{a.deviation_percent:+.1f}% | {a.severity.value} |\n"
                )
            report.append("\n")

        return "".join(report)

    def _generate_json_report(
        self,
        summary: CostSummary,
        forecast: Optional[list[ForecastData]],
        anomalies: Optional[list[CostAnomaly]],
    ) -> str:
        """Generate JSON cost report.

        Args:
            summary: Cost summary data
            forecast: Optional forecast data
            anomalies: Optional anomaly data

        Returns:
            JSON report string
        """
        report = {
            "scope": summary.scope,
            "period": {
                "start_date": summary.start_date.isoformat(),
                "end_date": summary.end_date.isoformat(),
            },
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total_cost": summary.total_cost,
                "currency": summary.currency,
                "resource_count": summary.resource_count,
                "average_daily_cost": summary.average_daily_cost,
                "average_cost_per_resource": summary.average_cost_per_resource,
            },
            "service_breakdown": summary.service_breakdown,
        }

        if forecast:
            report["forecast"] = [
                {
                    "date": f.forecast_date.isoformat(),
                    "predicted_cost": f.predicted_cost,
                    "confidence_lower": f.confidence_lower,
                    "confidence_upper": f.confidence_upper,
                }
                for f in forecast
            ]

        if anomalies:
            report["anomalies"] = [
                {
                    "resource_id": a.resource_id,
                    "date": a.date.isoformat(),
                    "expected_cost": a.expected_cost,
                    "actual_cost": a.actual_cost,
                    "deviation_percent": a.deviation_percent,
                    "severity": a.severity.value,
                }
                for a in anomalies
            ]

        return json.dumps(report, indent=2)


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int, window_seconds: float):
        """Initialize rate limiter.

        Args:
            max_calls: Maximum calls per window
            window_seconds: Time window in seconds
        """
        self.max_calls = max_calls
        self.window_seconds = window_seconds
        self.calls: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        """Acquire permission to make an API call.

        Blocks until a call slot is available within the rate limit.
        """
        async with self._lock:
            now = asyncio.get_event_loop().time()

            # Remove calls outside the window
            self.calls = [
                call_time
                for call_time in self.calls
                if now - call_time < self.window_seconds
            ]

            # Wait if at limit
            if len(self.calls) >= self.max_calls:
                sleep_time = self.window_seconds - (now - self.calls[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    now = asyncio.get_event_loop().time()
                    self.calls = [
                        call_time
                        for call_time in self.calls
                        if now - call_time < self.window_seconds
                    ]

            # Record this call
            self.calls.append(now)
