"""Neo4j cost data query module.

This module handles querying cost data from Neo4j, including
cost summaries, historical data retrieval, and tag-based allocation.
"""

from datetime import date, datetime
from typing import Optional

from neo4j import AsyncDriver

from ...models.cost_models import CostSummary


class CostManagementError(Exception):
    """Base exception for cost management errors."""

    pass


class CostQueryService:
    """Service for querying cost data from Neo4j.

    This service handles retrieving and aggregating cost data
    from the graph database with various grouping and filtering options.
    """

    def __init__(self, neo4j_driver: AsyncDriver):
        """Initialize the cost query service.

        Args:
            neo4j_driver: Neo4j async driver for database operations
        """
        self.neo4j_driver = neo4j_driver

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

    async def fetch_historical_costs(
        self,
        scope: str,
        start_date: date,
        end_date: date,
    ) -> list[tuple[date, float]]:
        """Fetch historical daily costs for forecasting.

        Args:
            scope: Azure scope
            start_date: Start date
            end_date: End date

        Returns:
            List of (date, cost) tuples

        Raises:
            CostManagementError: If query fails
        """
        try:
            async with self.neo4j_driver.session() as session:
                costs = await session.execute_read(
                    self._fetch_historical_costs,
                    scope,
                    start_date,
                    end_date,
                )
                return costs
        except Exception as e:
            raise CostManagementError(f"Failed to fetch historical costs: {e}") from e

    async def fetch_daily_costs_by_resource(
        self,
        scope: str,
        start_date: date,
        end_date: date,
    ) -> dict[str, list[tuple[date, float]]]:
        """Fetch daily costs grouped by resource.

        Args:
            scope: Azure scope
            start_date: Start date
            end_date: End date

        Returns:
            Dictionary mapping resource IDs to list of (date, cost) tuples

        Raises:
            CostManagementError: If query fails
        """
        try:
            async with self.neo4j_driver.session() as session:
                costs = await session.execute_read(
                    self._fetch_daily_costs_by_resource,
                    scope,
                    start_date,
                    end_date,
                )
                return costs
        except Exception as e:
            raise CostManagementError(
                f"Failed to fetch daily costs by resource: {e}"
            ) from e

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

    @staticmethod
    def _convert_neo4j_date(neo4j_date) -> date:
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
        from datetime import date

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
                    CostQueryService._convert_neo4j_date(record["cost_date"]),
                    float(record["daily_cost"]),
                )
            )

        return costs

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
                    CostQueryService._convert_neo4j_date(record["cost_date"]),
                    float(record["cost"]),
                )
            )

        return costs_by_resource

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
            params["subscription_ids"] = subscription_ids  # type: ignore[arg-type]

        result = await tx.run(query, **params)

        allocation = {}
        async for record in result:
            allocation[record["tag_value"]] = float(record["total_cost"])

        return allocation
