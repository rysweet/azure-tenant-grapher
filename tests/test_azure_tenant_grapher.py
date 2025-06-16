# mypy: disable-error-code=misc
"""
Tests for azure_tenant_grapher module (Phase 3 refactor).
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig


class TestAzureTenantGrapher:
    """Test cases for AzureTenantGrapher (coordinator, service composition)."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Provide a mock configuration."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"

        # Set up nested processing config
        processing_config = Mock()
        processing_config.auto_start_container = True
        processing_config.batch_size = 5
        processing_config.resource_limit = None
        config.processing = processing_config

        # Set up nested neo4j config
        neo4j_config = Mock()
        neo4j_config.uri = "bolt://localhost:7687"
        neo4j_config.user = "neo4j"
        neo4j_config.password = "test-password"  # nosec
        config.neo4j = neo4j_config

        # Set up nested azure_openai config
        azure_openai_config = Mock()
        azure_openai_config.is_configured.return_value = True
        config.azure_openai = azure_openai_config

        config.log_configuration_summary = Mock()
        config.specification = Mock()
        return config

    @pytest.fixture
    def mock_config_no_llm(self) -> Mock:
        """Provide a mock configuration without LLM."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"

        # Set up nested processing config
        processing_config = Mock()
        processing_config.auto_start_container = False
        processing_config.batch_size = 5
        processing_config.resource_limit = None
        config.processing = processing_config

        # Set up nested neo4j config
        neo4j_config = Mock()
        neo4j_config.uri = "bolt://localhost:7687"
        neo4j_config.user = "neo4j"
        neo4j_config.password = "test-password"  # nosec
        config.neo4j = neo4j_config

        # Set up nested azure_openai config
        azure_openai_config = Mock()
        azure_openai_config.is_configured.return_value = False
        config.azure_openai = azure_openai_config
        config.log_configuration_summary = Mock()
        config.specification = Mock()
        return config

    @pytest.mark.asyncio
    async def test_build_graph_success(self, mock_config: Mock):
        """Test successful complete graph building via service orchestration."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            # Patch service methods
            grapher.discovery_service.discover_subscriptions = AsyncMock(
                return_value=[{"id": "sub1", "display_name": "Test Sub"}]
            )
            grapher.discovery_service.discover_resources_in_subscription = AsyncMock(
                return_value=[
                    {"id": "res1", "name": "Resource1", "type": "TypeA"},
                    {"id": "res2", "name": "Resource2", "type": "TypeB"},
                ]
            )
            mock_stats = Mock()
            mock_stats.to_dict.return_value = {
                "total_resources": 2,
                "successful": 2,
                "failed": 0,
                "skipped": 0,
                "llm_generated": 2,
                "success_rate": 100.0,
            }
            grapher.processing_service.process_resources_batch = AsyncMock(
                return_value=mock_stats
            )
            # Patch session_manager context to avoid real DB connection
            from unittest.mock import MagicMock

            grapher.session_manager.__enter__ = MagicMock(
                return_value=grapher.session_manager
            )
            grapher.session_manager.__exit__ = MagicMock(return_value=None)
            grapher.session_manager.connect = MagicMock(return_value=None)

            result = await grapher.build_graph()
            assert result["success"] is True
            assert result["subscriptions"] == 1
            assert result["total_resources"] == 2
            assert result["successful"] == 2
            assert result["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_build_graph_no_subscriptions(self, mock_config: Mock):
        """Test graph building with no subscriptions found."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.discovery_service.discover_subscriptions = AsyncMock(
                return_value=[]
            )
            result = await grapher.build_graph()
            assert result["success"] is False
            assert result["subscriptions"] == 0

    @pytest.mark.asyncio
    async def test_build_graph_exception(self, mock_config: Mock):
        """Test graph building handles exceptions from services."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.discovery_service.discover_subscriptions = AsyncMock(
                side_effect=RuntimeError("fail")
            )
            result = await grapher.build_graph()
            assert result["success"] is False
            assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_tenant_specification_success(self, mock_config: Mock):
        """Test successful tenant specification generation."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.specification_service.generate_specification = AsyncMock(
                return_value="/tmp/spec.md"
            )
            await grapher.generate_tenant_specification()
            grapher.specification_service.generate_specification.assert_awaited()

    @pytest.mark.asyncio
    async def test_generate_tenant_specification_exception(self, mock_config: Mock):
        """Test tenant specification generation handles exceptions."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.specification_service.generate_specification = AsyncMock(
                side_effect=RuntimeError("fail")
            )
            # Should not raise
            await grapher.generate_tenant_specification()

    @pytest.mark.asyncio
    async def test_deprecated_discover_subscriptions(self, mock_config: Mock):
        """Test deprecated discover_subscriptions delegates to service."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.discovery_service.discover_subscriptions = AsyncMock(
                return_value=[{"id": "sub1"}]
            )
            with pytest.warns(DeprecationWarning):
                result = await grapher.discover_subscriptions()
            assert result == [{"id": "sub1"}]

    @pytest.mark.asyncio
    async def test_deprecated_discover_resources_in_subscription(
        self, mock_config: Mock
    ):
        """Test deprecated discover_resources_in_subscription delegates to service."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            grapher.discovery_service.discover_resources_in_subscription = AsyncMock(
                return_value=[{"id": "res1"}]
            )
            with pytest.warns(DeprecationWarning):
                result = await grapher.discover_resources_in_subscription("sub1")
            assert result == [{"id": "res1"}]

    @pytest.mark.asyncio
    async def test_deprecated_process_resources_with_enhanced_handling(
        self, mock_config: Mock
    ):
        """Test deprecated process_resources_with_enhanced_handling delegates to service."""
        with patch("src.azure_tenant_grapher.create_llm_generator"):
            grapher = AzureTenantGrapher(mock_config)
            mock_stats = Mock()
            mock_stats.to_dict.return_value = {"total_resources": 0}
            grapher.processing_service.process_resources_batch = AsyncMock(
                return_value=mock_stats
            )
            with pytest.warns(DeprecationWarning):
                result = await grapher.process_resources_with_enhanced_handling([])
            assert result == {"total_resources": 0}
