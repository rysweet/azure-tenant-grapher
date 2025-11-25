"""Azure Cost Management API data fetching module.

This module handles fetching cost data from the Azure Cost Management API,
including query construction, rate limiting, retry logic, and response parsing.
"""

import asyncio
import json
from datetime import date, datetime
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

from ...models.cost_models import CostData, Granularity, TimeFrame


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


class CostDataFetcher:
    """Service for fetching cost data from Azure Cost Management API.

    This service handles Azure API authentication, query construction,
    rate limiting, retry logic, and response parsing.
    """

    # Rate limiting configuration
    MAX_CALLS_PER_WINDOW = 20
    RATE_LIMIT_WINDOW = 10.0  # seconds

    def __init__(self, credential: TokenCredential):
        """Initialize the cost data fetcher.

        Args:
            credential: Azure credential for authentication
        """
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
