"""Neo4j cost data storage module.

This module handles persisting cost data, forecasts, and anomalies
to Neo4j graph database with proper relationship management.
"""

import json

from neo4j import AsyncDriver

from ...models.cost_models import CostAnomaly, CostData, ForecastData


class CostManagementError(Exception):
    """Base exception for cost management errors."""

    pass


class CostStorageService:
    """Service for storing cost data in Neo4j.

    This service handles creating Cost nodes and relationships to
    Resources, ResourceGroups, and Subscriptions in the graph database.
    """

    def __init__(self, neo4j_driver: AsyncDriver):
        """Initialize the cost storage service.

        Args:
            neo4j_driver: Neo4j async driver for database operations
        """
        self.neo4j_driver = neo4j_driver

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

    async def store_forecasts(self, forecasts: list[ForecastData]) -> None:
        """Store forecast data in Neo4j.

        Args:
            forecasts: List of ForecastData objects

        Raises:
            CostManagementError: If storage fails
        """
        try:
            async with self.neo4j_driver.session() as session:
                await session.execute_write(self._create_forecast_nodes, forecasts)
        except Exception as e:
            raise CostManagementError(f"Failed to store forecasts in Neo4j: {e}") from e

    async def store_anomalies(self, anomalies: list[CostAnomaly]) -> None:
        """Store anomaly data in Neo4j.

        Args:
            anomalies: List of CostAnomaly objects

        Raises:
            CostManagementError: If storage fails
        """
        try:
            async with self.neo4j_driver.session() as session:
                await session.execute_write(self._create_anomaly_nodes, anomalies)
        except Exception as e:
            raise CostManagementError(f"Failed to store anomalies in Neo4j: {e}") from e

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
