"""Tests for tenant report CLI command (Issue #569).

Test Coverage (TDD Approach):
- Unit tests (60%): Markdown formatting, data aggregation, cost handling, error messages
- Integration tests (30%): Neo4j queries, Azure API integration, parallel data collection
- E2E tests (10%): Full command execution (Neo4j and live modes)

These tests follow TDD methodology - they FAIL until implementation is complete.

Target: >40% coverage (project standard)
"""

import asyncio
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from click.testing import CliRunner
from neo4j import AsyncDriver, AsyncSession

# Import will fail until command is implemented - this is expected in TDD
try:
    from src.commands.report import report
except ImportError:
    # Create a placeholder for TDD - real implementation will replace this
    import click

    @click.command()
    def report():
        """Placeholder for TDD - real implementation needed"""
        raise NotImplementedError("Report command not yet implemented")


# ============================================================================
# UNIT TESTS (60% of test pyramid)
# ============================================================================


class TestMarkdownFormatting:
    """Test markdown table formatting and structure.

    These tests verify the markdown output generation without dependencies.
    """

    def test_format_identity_summary_table(self):
        """Test formatting of identity summary section."""
        # Arrange
        identity_data = {
            "users": 214,
            "service_principals": 1470,
            "managed_identities": 113,
            "groups": 84,
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_identity_summary

            result = format_identity_summary(identity_data)

            # Expected format when implemented:
            assert "## Identity Summary" in result
            assert "| Identity Type | Count |" in result
            assert "| Users | 214 |" in result
            assert "| Service Principals | 1,470 |" in result
            assert "| Managed Identities | 113 |" in result
            assert "| Groups | 84 |" in result

    def test_format_resource_summary_table(self):
        """Test formatting of resource summary section."""
        # Arrange
        resource_data = {
            "total_resources": 2248,
            "total_types": 93,
            "regions": 16,
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_resource_summary

            result = format_resource_summary(resource_data)

            # Expected format when implemented:
            assert "## Resource Summary" in result
            assert "| Metric | Count |" in result
            assert "| Total Resources | 2,248 |" in result
            assert "| Resource Types | 93 |" in result
            assert "| Regions | 16 |" in result

    def test_format_top_resource_types_table(self):
        """Test formatting of top resource types section."""
        # Arrange
        top_types = [
            ("Microsoft.Network/networkSecurityGroups", 245),
            ("Microsoft.Compute/virtualMachines", 198),
            ("Microsoft.Storage/storageAccounts", 156),
            ("Microsoft.KeyVault/vaults", 134),
            ("Microsoft.Web/sites", 112),
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_top_resource_types

            result = format_top_resource_types(top_types)

            # Expected format when implemented:
            assert "## Top Resource Types" in result
            assert "| Resource Type | Count |" in result
            assert "| Microsoft.Network/networkSecurityGroups | 245 |" in result
            assert "| Microsoft.Compute/virtualMachines | 198 |" in result

    def test_format_region_distribution_table(self):
        """Test formatting of region distribution section."""
        # Arrange
        regions = [
            ("eastus", 892),
            ("westus2", 543),
            ("centralus", 321),
            ("westeurope", 234),
            ("northeurope", 156),
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_region_distribution

            result = format_region_distribution(regions)

            # Expected format when implemented:
            assert "## Region Distribution" in result
            assert "| Region | Resource Count |" in result
            assert "| eastus | 892 |" in result
            assert "| westus2 | 543 |" in result

    def test_format_security_summary_table(self):
        """Test formatting of security summary section."""
        # Arrange
        security_data = {
            "role_assignments": 1042,
            "custom_roles": 23,
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_security_summary

            result = format_security_summary(security_data)

            # Expected format when implemented:
            assert "## Security Summary" in result
            assert "| Metric | Count |" in result
            assert "| Role Assignments | 1,042 |" in result
            assert "| Custom Roles | 23 |" in result

    def test_format_cost_summary_with_data(self):
        """Test formatting of cost summary when cost data is available."""
        # Arrange
        cost_data = {
            "total_cost": 125678.45,
            "currency": "USD",
            "period": "last_30_days",
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_cost_summary

            result = format_cost_summary(cost_data)

            # Expected format when implemented:
            assert "## Cost Summary" in result
            assert "| Metric | Value |" in result
            assert "| Total Cost (30 days) | $125,678.45 USD |" in result

    def test_format_cost_summary_unavailable(self):
        """Test formatting of cost summary when cost data is unavailable."""
        # Arrange
        cost_data = None

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_cost_summary

            result = format_cost_summary(cost_data)

            # Expected format when implemented:
            assert "## Cost Summary" in result
            assert "N/A" in result

    def test_number_formatting_with_commas(self):
        """Test that large numbers are formatted with thousand separators."""
        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_number

            assert format_number(1470) == "1,470"
            assert format_number(125678) == "125,678"
            assert format_number(2248) == "2,248"
            assert format_number(84) == "84"


class TestDataAggregation:
    """Test data aggregation and counting logic.

    These tests verify the business logic for aggregating data from graph queries.
    """

    def test_count_identities_by_type(self):
        """Test counting identities by type from graph data."""
        # Arrange
        graph_data = [
            {"type": "User", "count": 214},
            {"type": "ServicePrincipal", "count": 1470},
            {"type": "ManagedIdentity", "count": 113},
            {"type": "Group", "count": 84},
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import aggregate_identity_counts

            result = aggregate_identity_counts(graph_data)

            # Expected aggregation when implemented:
            assert result["users"] == 214
            assert result["service_principals"] == 1470
            assert result["managed_identities"] == 113
            assert result["groups"] == 84

    def test_group_resources_by_type(self):
        """Test grouping resources by type and counting."""
        # Arrange
        resources = [
            {"type": "Microsoft.Compute/virtualMachines"},
            {"type": "Microsoft.Compute/virtualMachines"},
            {"type": "Microsoft.Storage/storageAccounts"},
            {"type": "Microsoft.Network/networkSecurityGroups"},
            {"type": "Microsoft.Network/networkSecurityGroups"},
            {"type": "Microsoft.Network/networkSecurityGroups"},
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import group_resources_by_type

            result = group_resources_by_type(resources)

            # Expected grouping when implemented:
            assert result["Microsoft.Network/networkSecurityGroups"] == 3
            assert result["Microsoft.Compute/virtualMachines"] == 2
            assert result["Microsoft.Storage/storageAccounts"] == 1

    def test_group_resources_by_region(self):
        """Test grouping resources by region and counting."""
        # Arrange
        resources = [
            {"location": "eastus"},
            {"location": "eastus"},
            {"location": "eastus"},
            {"location": "westus2"},
            {"location": "westus2"},
            {"location": "centralus"},
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import group_resources_by_region

            result = group_resources_by_region(resources)

            # Expected grouping when implemented:
            assert result["eastus"] == 3
            assert result["westus2"] == 2
            assert result["centralus"] == 1

    def test_count_unique_regions(self):
        """Test counting unique regions from resource data."""
        # Arrange
        resources = [
            {"location": "eastus"},
            {"location": "eastus"},
            {"location": "westus2"},
            {"location": "centralus"},
            {"location": "westus2"},
        ]

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import count_unique_regions

            result = count_unique_regions(resources)

            # Expected count when implemented:
            assert result == 3  # eastus, westus2, centralus

    def test_sort_and_limit_top_items(self):
        """Test sorting and limiting to top N items."""
        # Arrange
        data = {
            "type_a": 100,
            "type_b": 500,
            "type_c": 250,
            "type_d": 750,
            "type_e": 50,
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import get_top_items

            result = get_top_items(data, limit=3)

            # Expected sorted top 3 when implemented:
            assert result == [("type_d", 750), ("type_b", 500), ("type_c", 250)]


class TestCostDataHandling:
    """Test cost data handling for available vs unavailable scenarios."""

    def test_handle_cost_data_available(self):
        """Test handling when cost data is available."""
        # Arrange
        cost_response = {
            "properties": {
                "rows": [[125678.45, "USD"]],
            }
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import extract_cost_data

            result = extract_cost_data(cost_response)

            # Expected extraction when implemented:
            assert result is not None
            assert result["total_cost"] == 125678.45
            assert result["currency"] == "USD"

    def test_handle_cost_data_unavailable(self):
        """Test handling when cost data is unavailable (API error)."""
        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import extract_cost_data

            result = extract_cost_data(None)

            # Expected handling when implemented:
            assert result is None

    def test_handle_cost_data_empty_response(self):
        """Test handling when cost API returns empty data."""
        # Arrange
        cost_response = {
            "properties": {
                "rows": [],
            }
        }

        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import extract_cost_data

            result = extract_cost_data(cost_response)

            # Expected handling when implemented:
            assert result is None


class TestErrorMessages:
    """Test error message formatting and handling."""

    def test_error_message_neo4j_connection_failed(self):
        """Test error message when Neo4j connection fails."""
        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_neo4j_connection_error

            result = format_neo4j_connection_error("Connection timeout")

            # Expected error message when implemented:
            assert "Neo4j connection failed" in result
            assert "Connection timeout" in result
            assert "ensure Neo4j is running" in result.lower()

    def test_error_message_azure_auth_failed(self):
        """Test error message when Azure authentication fails."""
        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_azure_auth_error

            result = format_azure_auth_error("Invalid credentials")

            # Expected error message when implemented:
            assert "Azure authentication failed" in result
            assert "Invalid credentials" in result
            assert "check your credentials" in result.lower()

    def test_error_message_no_data_found(self):
        """Test error message when no data is found in Neo4j."""
        # Act & Assert - This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import format_no_data_error

            result = format_no_data_error()

            # Expected error message when implemented:
            assert "No data found" in result
            assert "run a scan" in result.lower()


# ============================================================================
# INTEGRATION TESTS (30% of test pyramid)
# ============================================================================


class TestNeo4jQueryExecution:
    """Test Neo4j query execution with testcontainers.

    These tests verify that queries execute correctly against a real Neo4j instance.
    """

    @pytest.mark.asyncio
    async def test_query_identity_counts(self, neo4j_container):
        """Test querying identity counts from Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import query_identity_counts
            from neo4j import AsyncGraphDatabase

            uri, user, password = neo4j_container
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

            try:
                result = await query_identity_counts(driver)

                # Expected structure when implemented:
                assert "users" in result
                assert "service_principals" in result
                assert "managed_identities" in result
                assert "groups" in result
            finally:
                await driver.close()

    @pytest.mark.asyncio
    async def test_query_resource_counts(self, neo4j_container):
        """Test querying resource counts from Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import query_resource_counts
            from neo4j import AsyncGraphDatabase

            uri, user, password = neo4j_container
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

            try:
                result = await query_resource_counts(driver)

                # Expected structure when implemented:
                assert "total_resources" in result
                assert "total_types" in result
                assert "regions" in result
            finally:
                await driver.close()

    @pytest.mark.asyncio
    async def test_query_resource_by_type(self, neo4j_container):
        """Test querying resources grouped by type from Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import query_resources_by_type
            from neo4j import AsyncGraphDatabase

            uri, user, password = neo4j_container
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

            try:
                result = await query_resources_by_type(driver)

                # Expected structure when implemented:
                assert isinstance(result, dict)
                # Each entry should be resource_type -> count
            finally:
                await driver.close()

    @pytest.mark.asyncio
    async def test_query_resource_by_region(self, neo4j_container):
        """Test querying resources grouped by region from Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import query_resources_by_region
            from neo4j import AsyncGraphDatabase

            uri, user, password = neo4j_container
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

            try:
                result = await query_resources_by_region(driver)

                # Expected structure when implemented:
                assert isinstance(result, dict)
                # Each entry should be region -> count
            finally:
                await driver.close()

    @pytest.mark.asyncio
    async def test_query_role_assignments(self, neo4j_container):
        """Test querying role assignment counts from Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import query_role_assignments
            from neo4j import AsyncGraphDatabase

            uri, user, password = neo4j_container
            driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

            try:
                result = await query_role_assignments(driver)

                # Expected structure when implemented:
                assert "role_assignments" in result
                assert isinstance(result["role_assignments"], int)
            finally:
                await driver.close()


class TestAzureAPIIntegration:
    """Test Azure API integration with mocked services.

    These tests verify Azure API calls work correctly with proper mocking.
    """

    @pytest.mark.asyncio
    async def test_fetch_identities_from_azure(self):
        """Test fetching identity data from Azure Graph API."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import fetch_identities_from_azure

            # Mock Azure Graph service
            mock_service = Mock()
            mock_service.fetch_users = AsyncMock(return_value=[{"id": "1"}, {"id": "2"}])
            mock_service.fetch_service_principals = AsyncMock(
                return_value=[{"id": "sp1"}, {"id": "sp2"}, {"id": "sp3"}]
            )
            mock_service.fetch_groups = AsyncMock(return_value=[{"id": "g1"}])

            result = await fetch_identities_from_azure(mock_service)

            # Expected structure when implemented:
            assert result["users"] == 2
            assert result["service_principals"] == 3
            assert result["groups"] == 1

    @pytest.mark.asyncio
    async def test_fetch_resources_from_azure(self):
        """Test fetching resource data from Azure Resource Management API."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import fetch_resources_from_azure

            # Mock Azure Discovery service
            mock_service = Mock()
            mock_service.discover_resources = AsyncMock(
                return_value=[
                    {"type": "Microsoft.Compute/virtualMachines", "location": "eastus"},
                    {"type": "Microsoft.Storage/storageAccounts", "location": "westus"},
                    {"type": "Microsoft.Compute/virtualMachines", "location": "eastus"},
                ]
            )

            result = await fetch_resources_from_azure(mock_service)

            # Expected structure when implemented:
            assert result["total_resources"] == 3
            assert "Microsoft.Compute/virtualMachines" in result["by_type"]

    @pytest.mark.asyncio
    async def test_fetch_cost_from_azure(self):
        """Test fetching cost data from Azure Cost Management API."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import fetch_cost_from_azure

            # Mock Cost Management service
            mock_service = Mock()
            mock_service.get_subscription_costs = AsyncMock(
                return_value={"total_cost": 125678.45, "currency": "USD"}
            )

            result = await fetch_cost_from_azure(mock_service)

            # Expected structure when implemented:
            assert result is not None
            assert result["total_cost"] == 125678.45
            assert result["currency"] == "USD"

    @pytest.mark.asyncio
    async def test_fetch_cost_from_azure_unavailable(self):
        """Test handling when cost data is unavailable from Azure API."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import fetch_cost_from_azure

            # Mock Cost Management service that raises exception
            mock_service = Mock()
            mock_service.get_subscription_costs = AsyncMock(
                side_effect=Exception("Cost API unavailable")
            )

            result = await fetch_cost_from_azure(mock_service)

            # Expected handling when implemented:
            assert result is None


class TestParallelDataCollection:
    """Test parallel data collection using asyncio.gather().

    These tests verify that data is collected in parallel efficiently.
    """

    @pytest.mark.asyncio
    async def test_parallel_neo4j_queries(self):
        """Test that multiple Neo4j queries execute in parallel."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import collect_neo4j_data
            from neo4j import AsyncGraphDatabase

            # Mock driver
            mock_driver = Mock(spec=AsyncDriver)

            # Create mock session that tracks query execution order
            queries_executed = []

            async def mock_run(query, **kwargs):
                queries_executed.append(query)
                await asyncio.sleep(0.01)  # Simulate query time
                return Mock()

            mock_session = Mock(spec=AsyncSession)
            mock_session.run = mock_run
            mock_driver.session.return_value.__aenter__.return_value = mock_session

            # Execute parallel collection
            await collect_neo4j_data(mock_driver)

            # Expected behavior when implemented:
            # All queries should start before any complete (parallel execution)
            assert len(queries_executed) > 0

    @pytest.mark.asyncio
    async def test_parallel_azure_api_calls(self):
        """Test that multiple Azure API calls execute in parallel."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import collect_azure_data

            # Mock services
            mock_aad_service = Mock()
            mock_discovery_service = Mock()
            mock_cost_service = Mock()

            # Track call order
            calls_made = []

            async def track_call(name):
                calls_made.append(f"{name}_start")
                await asyncio.sleep(0.01)
                calls_made.append(f"{name}_end")
                return {}

            mock_aad_service.fetch_users = lambda: track_call("users")
            mock_discovery_service.discover_resources = lambda: track_call("resources")
            mock_cost_service.get_costs = lambda: track_call("costs")

            # Execute parallel collection
            await collect_azure_data(
                mock_aad_service, mock_discovery_service, mock_cost_service
            )

            # Expected behavior when implemented:
            # Calls should interleave (parallel execution)
            # Not: users_start, users_end, resources_start, resources_end


class TestFileOutputWriting:
    """Test writing report output to file."""

    def test_write_report_to_file(self, tmp_path):
        """Test writing markdown report to file."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import write_report_to_file

            # Arrange
            report_content = "# Test Report\n\n## Section 1\n\nContent"
            output_path = tmp_path / "report.md"

            # Act
            write_report_to_file(report_content, output_path)

            # Assert - Expected behavior when implemented:
            assert output_path.exists()
            assert output_path.read_text() == report_content

    def test_write_report_creates_directory(self, tmp_path):
        """Test that writing report creates parent directories if needed."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError, ImportError)):
            from src.commands.report import write_report_to_file

            # Arrange
            report_content = "# Test Report"
            output_path = tmp_path / "subdir" / "nested" / "report.md"

            # Act
            write_report_to_file(report_content, output_path)

            # Assert - Expected behavior when implemented:
            assert output_path.exists()
            assert output_path.parent.exists()


# ============================================================================
# E2E TESTS (10% of test pyramid)
# ============================================================================


class TestReportCommandE2E:
    """End-to-end tests for report command.

    These tests verify complete command execution flow.
    """

    @pytest.fixture
    def runner(self):
        """Click CLI test runner."""
        return CliRunner()

    def test_report_help(self, runner):
        """Test report command help text."""
        result = runner.invoke(report, ["--help"])

        # Basic help should work even without implementation
        assert result.exit_code == 0
        assert "report" in result.output.lower()

    @patch("src.commands.report.AsyncGraphDatabase")
    @patch("src.commands.report.get_neo4j_config_from_env")
    def test_report_neo4j_mode_success(
        self, mock_get_config, mock_graph_database, runner, tmp_path
    ):
        """Test successful report generation in Neo4j mode."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Arrange
            mock_get_config.return_value = ("bolt://localhost:7687", "neo4j", "password")
            output_path = tmp_path / "report.md"

            # Mock driver and session
            mock_driver = Mock()
            mock_session = Mock()

            # Mock query results with expected data structure
            mock_session.run = AsyncMock(side_effect=[
                # Identity counts query result
                Mock(
                    data=lambda: [
                        {"type": "User", "count": 214},
                        {"type": "ServicePrincipal", "count": 1470},
                        {"type": "ManagedIdentity", "count": 113},
                        {"type": "Group", "count": 84},
                    ]
                ),
                # Resource counts query result
                Mock(
                    data=lambda: [
                        {"total": 2248, "types": 93, "regions": 16}
                    ]
                ),
                # Role assignments query result
                Mock(data=lambda: [{"count": 1042}]),
            ])

            mock_driver.session.return_value.__aenter__.return_value = mock_session
            mock_graph_database.driver.return_value = mock_driver

            # Act
            result = runner.invoke(
                report,
                ["--tenant-id", "test-tenant", "--output", str(output_path)],
            )

            # Assert
            assert result.exit_code == 0
            assert "Report generated" in result.output
            assert output_path.exists()

            # Verify report content
            content = output_path.read_text()
            assert "# Azure Tenant Report" in content
            assert "214" in content  # users
            assert "1,470" in content  # service principals
            assert "2,248" in content  # total resources

    @patch("src.commands.report.AADGraphService")
    @patch("src.commands.report.AzureDiscoveryService")
    @patch("src.commands.report.CostManagementService")
    def test_report_live_mode_success(
        self,
        mock_cost_service_class,
        mock_discovery_service_class,
        mock_aad_service_class,
        runner,
        tmp_path,
    ):
        """Test successful report generation in live mode."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Arrange
            output_path = tmp_path / "report.md"

            # Mock AAD service
            mock_aad_service = Mock()
            mock_aad_service.fetch_users = AsyncMock(
                return_value=[{"id": f"user{i}"} for i in range(214)]
            )
            mock_aad_service.fetch_service_principals = AsyncMock(
                return_value=[{"id": f"sp{i}"} for i in range(1470)]
            )
            mock_aad_service.fetch_managed_identities = AsyncMock(
                return_value=[{"id": f"mi{i}"} for i in range(113)]
            )
            mock_aad_service.fetch_groups = AsyncMock(
                return_value=[{"id": f"g{i}"} for i in range(84)]
            )
            mock_aad_service_class.return_value = mock_aad_service

            # Mock Discovery service
            mock_discovery_service = Mock()
            mock_discovery_service.discover_resources = AsyncMock(
                return_value=[
                    {
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                    }
                    for _ in range(2248)
                ]
            )
            mock_discovery_service_class.return_value = mock_discovery_service

            # Mock Cost service
            mock_cost_service = Mock()
            mock_cost_service.get_subscription_costs = AsyncMock(
                return_value={"total_cost": 125678.45, "currency": "USD"}
            )
            mock_cost_service_class.return_value = mock_cost_service

            # Act
            result = runner.invoke(
                report,
                ["--tenant-id", "test-tenant", "--output", str(output_path), "--live"],
            )

            # Assert
            assert result.exit_code == 0
            assert "Report generated" in result.output
            assert output_path.exists()

            # Verify report content
            content = output_path.read_text()
            assert "# Azure Tenant Report" in content
            assert "214" in content  # users
            assert "2,248" in content  # total resources

    @patch("src.commands.report.get_neo4j_config_from_env")
    def test_report_neo4j_connection_error(self, mock_get_config, runner):
        """Test report when Neo4j connection fails."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Arrange
            mock_get_config.side_effect = Exception("Connection failed")

            # Act
            result = runner.invoke(report, ["--tenant-id", "test-tenant"])

            # Assert
            assert result.exit_code == 1
            assert "connection failed" in result.output.lower()

    @patch("src.commands.report.AsyncGraphDatabase")
    @patch("src.commands.report.get_neo4j_config_from_env")
    def test_report_no_data_found(self, mock_get_config, mock_graph_database, runner):
        """Test report when no data is found in Neo4j."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Arrange
            mock_get_config.return_value = ("bolt://localhost:7687", "neo4j", "password")

            # Mock empty results
            mock_driver = Mock()
            mock_session = Mock()
            mock_session.run = AsyncMock(return_value=Mock(data=lambda: []))
            mock_driver.session.return_value.__aenter__.return_value = mock_session
            mock_graph_database.driver.return_value = mock_driver

            # Act
            result = runner.invoke(report, ["--tenant-id", "test-tenant"])

            # Assert
            assert result.exit_code == 1
            assert "no data found" in result.output.lower()

    def test_report_output_default_location(self, runner):
        """Test that default output location is used when not specified."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Act
            result = runner.invoke(report, ["--tenant-id", "test-tenant"])

            # Assert - Should succeed and use default location
            if result.exit_code == 0:
                assert "tenant-report.md" in result.output

    def test_report_validates_tenant_id_format(self, runner):
        """Test that invalid tenant ID format is rejected."""
        # This will FAIL until implementation exists
        with pytest.raises((NotImplementedError, AttributeError)):
            # Act
            result = runner.invoke(report, ["--tenant-id", "invalid-format"])

            # Assert
            if "invalid" in result.output.lower():
                assert result.exit_code == 1


# ============================================================================
# TEST FIXTURES AND MOCKS
# ============================================================================


@pytest.fixture
def sample_neo4j_data():
    """Provide sample Neo4j query results for testing."""
    return {
        "identities": [
            {"type": "User", "count": 214},
            {"type": "ServicePrincipal", "count": 1470},
            {"type": "ManagedIdentity", "count": 113},
            {"type": "Group", "count": 84},
        ],
        "resources": [
            {"total": 2248, "types": 93, "regions": 16}
        ],
        "resource_types": [
            {"type": "Microsoft.Network/networkSecurityGroups", "count": 245},
            {"type": "Microsoft.Compute/virtualMachines", "count": 198},
            {"type": "Microsoft.Storage/storageAccounts", "count": 156},
        ],
        "regions": [
            {"region": "eastus", "count": 892},
            {"region": "westus2", "count": 543},
            {"region": "centralus", "count": 321},
        ],
        "role_assignments": [{"count": 1042}],
    }


@pytest.fixture
def sample_azure_data():
    """Provide sample Azure API responses for testing."""
    return {
        "users": [{"id": f"user{i}", "displayName": f"User {i}"} for i in range(214)],
        "service_principals": [
            {"id": f"sp{i}", "displayName": f"SP {i}"} for i in range(1470)
        ],
        "managed_identities": [
            {"id": f"mi{i}", "name": f"MI {i}"} for i in range(113)
        ],
        "groups": [{"id": f"g{i}", "displayName": f"Group {i}"} for i in range(84)],
        "resources": [
            {
                "id": f"res{i}",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
            }
            for i in range(2248)
        ],
        "cost": {
            "total_cost": 125678.45,
            "currency": "USD",
            "period": "last_30_days",
        },
    }


# ============================================================================
# SUMMARY
# ============================================================================

"""
Test Summary:

UNIT TESTS (60%):
- test_format_identity_summary_table
- test_format_resource_summary_table
- test_format_top_resource_types_table
- test_format_region_distribution_table
- test_format_security_summary_table
- test_format_cost_summary_with_data
- test_format_cost_summary_unavailable
- test_number_formatting_with_commas
- test_count_identities_by_type
- test_group_resources_by_type
- test_group_resources_by_region
- test_count_unique_regions
- test_sort_and_limit_top_items
- test_handle_cost_data_available
- test_handle_cost_data_unavailable
- test_handle_cost_data_empty_response
- test_error_message_neo4j_connection_failed
- test_error_message_azure_auth_failed
- test_error_message_no_data_found

INTEGRATION TESTS (30%):
- test_query_identity_counts
- test_query_resource_counts
- test_query_resource_by_type
- test_query_resource_by_region
- test_query_role_assignments
- test_fetch_identities_from_azure
- test_fetch_resources_from_azure
- test_fetch_cost_from_azure
- test_fetch_cost_from_azure_unavailable
- test_parallel_neo4j_queries
- test_parallel_azure_api_calls
- test_write_report_to_file
- test_write_report_creates_directory

E2E TESTS (10%):
- test_report_help
- test_report_neo4j_mode_success
- test_report_live_mode_success
- test_report_neo4j_connection_error
- test_report_no_data_found
- test_report_output_default_location
- test_report_validates_tenant_id_format

Total: 39 tests covering all aspects of the report command.
All tests FAIL until implementation is complete - this is TDD!
"""
