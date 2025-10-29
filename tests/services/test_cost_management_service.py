"""Integration tests for Azure Cost Management Service.

This module provides comprehensive test coverage for the CostManagementService,
including Azure API integration, Neo4j storage, cost querying, forecasting,
anomaly detection, and report generation.
"""

import json
from datetime import date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest
from azure.core.exceptions import HttpResponseError
from neo4j import AsyncDriver, AsyncGraphDatabase

from src.models.cost_models import (
    CostAnomaly,
    CostData,
    CostSummary,
    ForecastData,
    Granularity,
    SeverityLevel,
    TimeFrame,
)
from src.services.cost_management_service import (
    APIRateLimitError,
    CostManagementError,
    CostManagementService,
    DataValidationError,
    InvalidScopeError,
)


class TestCostManagementService:
    """Test cases for CostManagementService."""

    @pytest.fixture
    async def neo4j_driver(self) -> AsyncDriver:
        """Create Neo4j driver for testing.

        Uses the environment Neo4j instance configured in conftest.py.
        """
        import os

        uri = os.getenv("NEO4J_URI", "bolt://localhost:7688")
        user = os.getenv("NEO4J_USER", "neo4j")
        password = os.getenv("NEO4J_PASSWORD")

        if not password:
            raise ValueError("NEO4J_PASSWORD environment variable is required")

        driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

        # Clean up any existing test data
        async with driver.session() as session:
            await session.run("MATCH (n) WHERE n.id CONTAINS 'test-' DETACH DELETE n")
            await session.run("MATCH (n:Cost) DETACH DELETE n")
            await session.run("MATCH (n:CostForecast) DETACH DELETE n")
            await session.run("MATCH (n:CostAnomaly) DETACH DELETE n")

        yield driver

        # Cleanup after test
        async with driver.session() as session:
            await session.run("MATCH (n) WHERE n.id CONTAINS 'test-' DETACH DELETE n")
            await session.run("MATCH (n:Cost) DETACH DELETE n")
            await session.run("MATCH (n:CostForecast) DETACH DELETE n")
            await session.run("MATCH (n:CostAnomaly) DETACH DELETE n")

        await driver.close()

    @pytest.fixture
    def mock_credential(self) -> Mock:
        """Mock Azure credential for testing."""
        credential = Mock()
        credential.get_token.return_value = Mock(token="test-token")
        return credential

    @pytest.fixture
    def mock_cost_client(self) -> Mock:
        """Mock Azure Cost Management client."""
        client = Mock()

        # Mock query result structure
        mock_result = Mock()
        mock_result.rows = [
            [
                "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                "2025-10-15",
                150.75,
                150.75,
                100.0,
                "USD",
                "Virtual Machines",
                "Compute",
                "Standard_D2s_v3",
                '{"Environment": "Production", "CostCenter": "IT"}',
                "test-rg",
            ],
            [
                "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                "2025-10-15",
                25.50,
                25.50,
                500.0,
                "USD",
                "Storage",
                "Storage",
                "Standard LRS",
                '{"Environment": "Production"}',
                "test-rg",
            ],
        ]

        # Mock columns - must set .name attribute explicitly
        def create_column_mock(col_name: str) -> Mock:
            col = Mock()
            col.name = col_name
            return col

        mock_result.columns = [
            create_column_mock("ResourceId"),
            create_column_mock("UsageDate"),
            create_column_mock("Cost"),
            create_column_mock("CostUSD"),
            create_column_mock("UsageQuantity"),
            create_column_mock("Currency"),
            create_column_mock("ServiceName"),
            create_column_mock("MeterCategory"),
            create_column_mock("MeterName"),
            create_column_mock("Tags"),
            create_column_mock("ResourceGroupName"),
        ]

        client.query.usage.return_value = mock_result
        return client

    @pytest.fixture
    async def cost_service(
        self, neo4j_driver: AsyncDriver, mock_credential: Mock, mock_cost_client: Mock
    ) -> CostManagementService:
        """Create CostManagementService with mocked client."""
        service = CostManagementService(
            neo4j_driver=neo4j_driver,
            credential=mock_credential,
        )
        await service.initialize()

        # Inject mock client
        service.client = mock_cost_client

        return service

    @pytest.mark.asyncio
    async def test_initialize(
        self, neo4j_driver: AsyncDriver, mock_credential: Mock
    ) -> None:
        """Test service initialization."""
        service = CostManagementService(
            neo4j_driver=neo4j_driver,
            credential=mock_credential,
        )

        assert service.client is None
        assert not service._initialized

        await service.initialize()

        assert service.client is not None
        assert service._initialized

    @pytest.mark.asyncio
    async def test_fetch_costs_subscription_scope(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test fetching costs for subscription scope."""
        scope = "/subscriptions/test-sub-id"

        costs = await cost_service.fetch_costs(
            scope=scope,
            time_frame=TimeFrame.MONTH_TO_DATE,
            granularity=Granularity.DAILY,
        )

        assert len(costs) == 2

        # Verify first cost record
        cost1 = costs[0]
        assert cost1.resource_id.endswith("test-vm")
        assert cost1.actual_cost == 150.75
        assert cost1.service_name == "Virtual Machines"
        assert cost1.subscription_id == "test-sub-id"  # Extracted from scope
        assert cost1.resource_group == "test-rg"
        assert "Environment" in cost1.tags

        # Verify second cost record
        cost2 = costs[1]
        assert cost2.service_name == "Storage"
        assert cost2.actual_cost == 25.50

        # Verify client was called correctly
        mock_cost_client.query.usage.assert_called_once()
        call_args = mock_cost_client.query.usage.call_args
        assert call_args[1]["scope"] == scope

    @pytest.mark.asyncio
    async def test_fetch_costs_custom_time_frame(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test fetching costs with custom time frame."""
        scope = "/subscriptions/test-sub-id"
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 15)

        costs = await cost_service.fetch_costs(
            scope=scope,
            time_frame=TimeFrame.CUSTOM,
            start_date=start_date,
            end_date=end_date,
            granularity=Granularity.DAILY,
        )

        assert len(costs) == 2

        # Verify query definition includes time period
        mock_cost_client.query.usage.assert_called_once()
        call_args = mock_cost_client.query.usage.call_args
        query_def = call_args[1]["parameters"]
        assert query_def.time_period is not None
        assert query_def.time_period.from_property == start_date.isoformat()
        assert query_def.time_period.to == end_date.isoformat()

    @pytest.mark.asyncio
    async def test_fetch_costs_invalid_scope(
        self, cost_service: CostManagementService
    ) -> None:
        """Test fetching costs with invalid scope."""
        invalid_scope = "invalid-scope-format"

        with pytest.raises(InvalidScopeError, match="Invalid scope format"):
            await cost_service.fetch_costs(
                scope=invalid_scope,
                time_frame=TimeFrame.MONTH_TO_DATE,
            )

    @pytest.mark.asyncio
    async def test_fetch_costs_custom_time_frame_missing_dates(
        self, cost_service: CostManagementService
    ) -> None:
        """Test fetching costs with custom time frame but missing dates."""
        scope = "/subscriptions/test-sub-id"

        with pytest.raises(
            DataValidationError,
            match="start_date and end_date required for CUSTOM time frame",
        ):
            await cost_service.fetch_costs(
                scope=scope,
                time_frame=TimeFrame.CUSTOM,
            )

    @pytest.mark.asyncio
    async def test_fetch_costs_invalid_date_range(
        self, cost_service: CostManagementService
    ) -> None:
        """Test fetching costs with invalid date range."""
        scope = "/subscriptions/test-sub-id"
        start_date = date(2025, 10, 15)
        end_date = date(2025, 10, 1)

        with pytest.raises(
            DataValidationError, match="start_date cannot be after end_date"
        ):
            await cost_service.fetch_costs(
                scope=scope,
                time_frame=TimeFrame.CUSTOM,
                start_date=start_date,
                end_date=end_date,
            )

    @pytest.mark.asyncio
    async def test_fetch_costs_empty_result(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test fetching costs with empty API result."""
        scope = "/subscriptions/test-sub-id"

        # Mock empty result
        mock_result = Mock()
        mock_result.rows = []
        mock_result.columns = []
        mock_cost_client.query.usage.return_value = mock_result

        costs = await cost_service.fetch_costs(
            scope=scope,
            time_frame=TimeFrame.MONTH_TO_DATE,
        )

        assert len(costs) == 0

    @pytest.mark.asyncio
    async def test_fetch_costs_api_error_retry(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test fetching costs with API error and retry."""
        scope = "/subscriptions/test-sub-id"

        # Mock API error on first call, success on second
        call_count = {"count": 0}

        def mock_usage(*args, **kwargs):
            call_count["count"] += 1
            if call_count["count"] == 1:
                raise HttpResponseError(message="Transient error", response=Mock(status_code=500))

            # Return successful result on retry
            mock_result = Mock()
            mock_result.rows = []
            mock_result.columns = []
            return mock_result

        mock_cost_client.query.usage.side_effect = mock_usage

        costs = await cost_service.fetch_costs(
            scope=scope,
            time_frame=TimeFrame.MONTH_TO_DATE,
        )

        assert len(costs) == 0
        assert call_count["count"] == 2

    @pytest.mark.asyncio
    async def test_fetch_costs_rate_limit_error(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test fetching costs with rate limit error."""
        scope = "/subscriptions/test-sub-id"

        # Mock rate limit error
        mock_cost_client.query.usage.side_effect = HttpResponseError(
            message="Rate limited", response=Mock(status_code=429)
        )

        with pytest.raises(APIRateLimitError, match="API rate limit exceeded"):
            await cost_service.fetch_costs(
                scope=scope,
                time_frame=TimeFrame.MONTH_TO_DATE,
            )

    @pytest.mark.asyncio
    async def test_store_costs_creates_nodes_and_relationships(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test storing costs creates Cost nodes and INCURS_COST relationships."""
        # Create test subscription and resource in Neo4j
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (s:Subscription {
                    subscription_id: 'test-sub',
                    id: '/subscriptions/test-sub'
                })
                CREATE (r:Resource {
                    id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm',
                    name: 'test-vm',
                    type: 'Microsoft.Compute/virtualMachines'
                })
                CREATE (rg:ResourceGroup {
                    name: 'test-rg',
                    id: '/subscriptions/test-sub/resourceGroups/test-rg'
                })
                """
            )

        # Create cost data
        costs = [
            CostData(
                resource_id="/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
                date=date(2025, 10, 15),
                actual_cost=150.75,
                amortized_cost=150.75,
                usage_quantity=100.0,
                currency="USD",
                service_name="Virtual Machines",
                meter_category="Compute",
                meter_name="Standard_D2s_v3",
                tags={"Environment": "Production"},
                subscription_id="test-sub",
                resource_group="test-rg",
            )
        ]

        # Store costs
        count = await cost_service.store_costs(costs)

        assert count == 1

        # Verify Cost node was created
        async with neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (c:Cost)
                WHERE c.resource_id CONTAINS 'test-vm'
                RETURN c
                """
            )
            record = await result.single()
            assert record is not None
            cost_node = record["c"]
            assert cost_node["actual_cost"] == 150.75
            assert cost_node["service_name"] == "Virtual Machines"
            assert cost_node["subscription_id"] == "test-sub"

        # Verify INCURS_COST relationship from Resource
        async with neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (r:Resource)-[:INCURS_COST]->(c:Cost)
                WHERE r.id CONTAINS 'test-vm'
                RETURN count(c) as cost_count
                """
            )
            record = await result.single()
            assert record["cost_count"] == 1

        # Verify INCURS_COST relationship from Subscription
        async with neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (s:Subscription)-[:INCURS_COST]->(c:Cost)
                WHERE s.subscription_id = 'test-sub'
                RETURN count(c) as cost_count
                """
            )
            record = await result.single()
            assert record["cost_count"] == 1

        # Verify INCURS_COST relationship from ResourceGroup
        async with neo4j_driver.session() as session:
            result = await session.run(
                """
                MATCH (rg:ResourceGroup)-[:INCURS_COST]->(c:Cost)
                WHERE rg.name = 'test-rg'
                RETURN count(c) as cost_count
                """
            )
            record = await result.single()
            assert record["cost_count"] == 1

    @pytest.mark.asyncio
    async def test_store_costs_empty_list(
        self, cost_service: CostManagementService
    ) -> None:
        """Test storing empty cost list."""
        count = await cost_service.store_costs([])
        assert count == 0

    @pytest.mark.asyncio
    async def test_query_costs_basic(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test querying costs without grouping."""
        # Create test data
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (c1:Cost {
                    id: 'test-cost-1',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                    date: date('2025-10-15'),
                    actual_cost: 100.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines'
                })
                CREATE (c2:Cost {
                    id: 'test-cost-2',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1',
                    date: date('2025-10-15'),
                    actual_cost: 50.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Storage'
                })
                """
            )

        # Query costs
        summary = await cost_service.query_costs(
            scope="/subscriptions/test-sub",
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
        )

        assert isinstance(summary, CostSummary)
        assert summary.total_cost == 150.0
        assert summary.currency == "USD"
        assert summary.resource_count == 2
        assert summary.average_cost_per_resource == 75.0

    @pytest.mark.asyncio
    async def test_query_costs_group_by_service(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test querying costs grouped by service name."""
        # Create test data
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (c1:Cost {
                    id: 'test-cost-1',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                    date: date('2025-10-15'),
                    actual_cost: 100.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines'
                })
                CREATE (c2:Cost {
                    id: 'test-cost-2',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm2',
                    date: date('2025-10-16'),
                    actual_cost: 150.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines'
                })
                CREATE (c3:Cost {
                    id: 'test-cost-3',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1',
                    date: date('2025-10-15'),
                    actual_cost: 50.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Storage'
                })
                """
            )

        # Query costs grouped by service
        summary = await cost_service.query_costs(
            scope="/subscriptions/test-sub",
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
            group_by="service_name",
        )

        assert summary.total_cost == 300.0
        assert len(summary.service_breakdown) == 2
        assert summary.service_breakdown["Virtual Machines"] == 250.0
        assert summary.service_breakdown["Storage"] == 50.0

    @pytest.mark.asyncio
    async def test_forecast_costs_linear_trend(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test cost forecasting with linear trend."""
        # Create historical cost data with linear trend
        async with neo4j_driver.session() as session:
            # Create costs for last 30 days with increasing trend
            for i in range(30):
                cost_date = date.today() - timedelta(days=30 - i)
                cost_value = 100.0 + (i * 5.0)  # Linear increase

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: $cost,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                    cost=cost_value,
                )

        # Generate forecast
        forecasts = await cost_service.forecast_costs(
            scope="/subscriptions/test-sub",
            forecast_days=7,
        )

        assert len(forecasts) == 7

        # Verify forecast structure
        forecast = forecasts[0]
        assert isinstance(forecast, ForecastData)
        assert forecast.scope == "/subscriptions/test-sub"
        assert forecast.predicted_cost > 0
        assert forecast.confidence_lower <= forecast.predicted_cost
        assert forecast.confidence_upper >= forecast.predicted_cost

        # Verify forecast trend (should be increasing)
        assert forecasts[6].predicted_cost > forecasts[0].predicted_cost

    @pytest.mark.asyncio
    async def test_forecast_costs_insufficient_data(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test forecasting with insufficient historical data."""
        # Create only 5 days of data (minimum is 14)
        async with neo4j_driver.session() as session:
            for i in range(5):
                cost_date = date.today() - timedelta(days=5 - i)

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: 100.0,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                )

        with pytest.raises(
            DataValidationError, match="Insufficient historical data for forecasting"
        ):
            await cost_service.forecast_costs(
                scope="/subscriptions/test-sub",
                forecast_days=7,
            )

    @pytest.mark.asyncio
    async def test_detect_anomalies_identifies_spikes(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test anomaly detection identifies cost spikes."""
        # Create normal cost pattern with one spike
        async with neo4j_driver.session() as session:
            for i in range(30):
                cost_date = date.today() - timedelta(days=30 - i)

                # Normal cost around 100, with one spike at day 15
                if i == 15:
                    cost_value = 500.0  # Spike
                else:
                    cost_value = 100.0 + (i % 5) * 2  # Normal variation

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: $cost,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                    cost=cost_value,
                )

        # Detect anomalies
        anomalies = await cost_service.detect_anomalies(
            scope="/subscriptions/test-sub",
            lookback_days=30,
            sensitivity=2.0,
        )

        assert len(anomalies) > 0

        # Verify spike was detected
        spike_anomaly = next(
            (a for a in anomalies if a.actual_cost == 500.0), None
        )
        assert spike_anomaly is not None
        assert spike_anomaly.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        assert spike_anomaly.actual_cost > spike_anomaly.expected_cost
        assert spike_anomaly.deviation_percent > 0

    @pytest.mark.asyncio
    async def test_detect_anomalies_no_anomalies(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test anomaly detection with stable costs."""
        # Create stable cost pattern
        async with neo4j_driver.session() as session:
            for i in range(30):
                cost_date = date.today() - timedelta(days=30 - i)

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: 100.0,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                )

        # Detect anomalies with high sensitivity
        anomalies = await cost_service.detect_anomalies(
            scope="/subscriptions/test-sub",
            lookback_days=30,
            sensitivity=2.0,
        )

        assert len(anomalies) == 0

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires APOC plugin installed in Neo4j - install APOC or mock for production testing")
    async def test_allocate_by_tags(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test cost allocation by tag values.

        Note: This test requires the APOC plugin to be installed in Neo4j.
        Install APOC: https://neo4j.com/labs/apoc/
        """
        # Create costs with different tag values
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (c1:Cost {
                    id: 'test-cost-1',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                    date: date('2025-10-15'),
                    actual_cost: 100.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines',
                    tags: '{"CostCenter": "IT", "Environment": "Production"}'
                })
                CREATE (c2:Cost {
                    id: 'test-cost-2',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm2',
                    date: date('2025-10-15'),
                    actual_cost: 150.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines',
                    tags: '{"CostCenter": "Marketing", "Environment": "Production"}'
                })
                CREATE (c3:Cost {
                    id: 'test-cost-3',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1',
                    date: date('2025-10-15'),
                    actual_cost: 50.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Storage',
                    tags: '{"CostCenter": "IT", "Environment": "Development"}'
                })
                """
            )

        # Allocate costs by CostCenter tag
        allocation = await cost_service.allocate_by_tags(
            tag_key="CostCenter",
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
        )

        assert len(allocation) == 2
        assert allocation["IT"] == 150.0
        assert allocation["Marketing"] == 150.0

    @pytest.mark.asyncio
    async def test_generate_report_markdown_format(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test report generation in markdown format."""
        # Create test cost data
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (c1:Cost {
                    id: 'test-cost-1',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                    date: date('2025-10-15'),
                    actual_cost: 100.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines'
                })
                CREATE (c2:Cost {
                    id: 'test-cost-2',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1',
                    date: date('2025-10-15'),
                    actual_cost: 50.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Storage'
                })
                """
            )

        # Generate markdown report
        report = await cost_service.generate_report(
            scope="/subscriptions/test-sub",
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
            output_format="markdown",
        )

        assert isinstance(report, str)
        assert "# Azure Cost Report" in report
        assert "Total Cost" in report
        assert "150.00" in report
        assert "USD" in report
        assert "Virtual Machines" in report
        assert "Storage" in report

    @pytest.mark.asyncio
    async def test_generate_report_json_format(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test report generation in JSON format."""
        # Create test cost data
        async with neo4j_driver.session() as session:
            await session.run(
                """
                CREATE (c1:Cost {
                    id: 'test-cost-1',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                    date: date('2025-10-15'),
                    actual_cost: 100.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Virtual Machines'
                })
                CREATE (c2:Cost {
                    id: 'test-cost-2',
                    resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/storage1',
                    date: date('2025-10-15'),
                    actual_cost: 50.0,
                    currency: 'USD',
                    subscription_id: 'test-sub',
                    service_name: 'Storage'
                })
                """
            )

        # Generate JSON report
        report = await cost_service.generate_report(
            scope="/subscriptions/test-sub",
            start_date=date(2025, 10, 1),
            end_date=date(2025, 10, 31),
            output_format="json",
        )

        assert isinstance(report, str)

        # Parse JSON
        report_data = json.loads(report)

        assert report_data["scope"] == "/subscriptions/test-sub"
        assert report_data["summary"]["total_cost"] == 150.0
        assert report_data["summary"]["currency"] == "USD"
        assert report_data["summary"]["resource_count"] == 2
        assert "service_breakdown" in report_data

    @pytest.mark.asyncio
    async def test_generate_report_with_forecast(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test report generation with forecast included."""
        # Create historical cost data
        async with neo4j_driver.session() as session:
            for i in range(30):
                cost_date = date.today() - timedelta(days=30 - i)

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: 100.0,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                )

        # Generate report with forecast
        report = await cost_service.generate_report(
            scope="/subscriptions/test-sub",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            output_format="markdown",
            include_forecast=True,
        )

        assert "30-Day Forecast" in report
        assert "Predicted Total" in report
        assert "Confidence Range" in report

    @pytest.mark.asyncio
    async def test_generate_report_with_anomalies(
        self, cost_service: CostManagementService, neo4j_driver: AsyncDriver
    ) -> None:
        """Test report generation with anomalies included."""
        # Create cost data with spike
        async with neo4j_driver.session() as session:
            for i in range(30):
                cost_date = date.today() - timedelta(days=30 - i)
                cost_value = 500.0 if i == 15 else 100.0

                await session.run(
                    """
                    CREATE (c:Cost {
                        id: $id,
                        resource_id: '/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm1',
                        date: date($date),
                        actual_cost: $cost,
                        currency: 'USD',
                        subscription_id: 'test-sub',
                        service_name: 'Virtual Machines'
                    })
                    """,
                    id=f"test-cost-{i}",
                    date=cost_date.isoformat(),
                    cost=cost_value,
                )

        # Generate report with anomalies
        report = await cost_service.generate_report(
            scope="/subscriptions/test-sub",
            start_date=date.today() - timedelta(days=30),
            end_date=date.today(),
            output_format="markdown",
            include_anomalies=True,
        )

        assert "Cost Anomalies" in report
        assert "Severity" in report

    @pytest.mark.asyncio
    async def test_not_initialized_error(
        self, neo4j_driver: AsyncDriver, mock_credential: Mock
    ) -> None:
        """Test operations fail if service not initialized."""
        service = CostManagementService(
            neo4j_driver=neo4j_driver,
            credential=mock_credential,
        )

        # Should fail without initialization
        with pytest.raises(CostManagementError, match="Service not initialized"):
            await service.fetch_costs(
                scope="/subscriptions/test-sub",
                time_frame=TimeFrame.MONTH_TO_DATE,
            )

    @pytest.mark.asyncio
    async def test_rate_limiter_delays_requests(
        self, cost_service: CostManagementService, mock_cost_client: Mock
    ) -> None:
        """Test rate limiter delays requests appropriately."""
        scope = "/subscriptions/test-sub"

        # Reset rate limiter for test
        cost_service._rate_limiter.calls = []

        # Make multiple requests rapidly
        start_time = datetime.now()

        for _ in range(3):
            await cost_service.fetch_costs(
                scope=scope,
                time_frame=TimeFrame.MONTH_TO_DATE,
            )

        end_time = datetime.now()
        elapsed = (end_time - start_time).total_seconds()

        # Should complete without significant delay (under rate limit)
        assert elapsed < 5.0

        # Verify all requests were tracked
        assert len(cost_service._rate_limiter.calls) >= 3
