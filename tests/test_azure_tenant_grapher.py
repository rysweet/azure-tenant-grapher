"""
Tests for azure_tenant_grapher module.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.azure_tenant_grapher import AzureTenantGrapher
from src.config_manager import AzureTenantGrapherConfig


class TestAzureTenantGrapher:
    """Test cases for AzureTenantGrapher."""

    @pytest.fixture
    def mock_config(self):
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
        neo4j_config.password = "test-password"
        config.neo4j = neo4j_config

        # Set up nested azure_openai config
        azure_openai_config = Mock()
        azure_openai_config.is_configured.return_value = True
        config.azure_openai = azure_openai_config

        config.log_configuration_summary = Mock()
        return config

    @pytest.fixture
    def mock_config_no_llm(self):
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
        neo4j_config.password = "test-password"
        config.neo4j = neo4j_config

        # Set up nested azure_openai config
        azure_openai_config = Mock()
        azure_openai_config.is_configured.return_value = False
        config.azure_openai = azure_openai_config
        config.azure_openai.is_configured.return_value = False
        config.log_configuration_summary = Mock()
        return config

    def test_initialization_with_llm(self, mock_config):
        """Test successful initialization with LLM enabled."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.Neo4jContainerManager"):
                with patch(
                    "src.azure_tenant_grapher.create_llm_generator"
                ) as mock_llm_factory:
                    mock_llm_factory.return_value = Mock()

                    grapher = AzureTenantGrapher(mock_config)

                    assert grapher.config == mock_config
                    assert grapher.credential is not None
                    assert grapher.llm_generator is not None
                    assert grapher.container_manager is not None
                    assert mock_config.log_configuration_summary.called

    def test_initialization_without_llm(self, mock_config_no_llm):
        """Test initialization without LLM configuration."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            grapher = AzureTenantGrapher(mock_config_no_llm)

            assert grapher.config == mock_config_no_llm
            assert grapher.llm_generator is None
            assert grapher.container_manager is None

    def test_initialization_llm_failure(self, mock_config):
        """Test initialization handles LLM creation failure."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.Neo4jContainerManager"):
                with patch(
                    "src.azure_tenant_grapher.create_llm_generator",
                    side_effect=Exception("LLM Error"),
                ):
                    grapher = AzureTenantGrapher(mock_config)

                    assert grapher.llm_generator is None

    def test_connect_to_neo4j_success(self, mock_config):
        """Test successful Neo4j connection."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.Neo4jContainerManager"
            ) as mock_container_class:
                with patch("src.azure_tenant_grapher.GraphDatabase") as mock_graph_db:
                    with patch("src.azure_tenant_grapher.create_llm_generator"):
                        # Setup mocks
                        mock_container = Mock()
                        mock_container.is_neo4j_container_running.return_value = True
                        mock_container_class.return_value = mock_container

                        mock_driver = Mock()
                        mock_session = Mock()
                        mock_driver.session.return_value.__enter__ = Mock(
                            return_value=mock_session
                        )
                        mock_driver.session.return_value.__exit__ = Mock(
                            return_value=None
                        )
                        mock_graph_db.driver.return_value = mock_driver

                        grapher = AzureTenantGrapher(mock_config)
                        grapher.connect_to_neo4j()

                        assert grapher.driver == mock_driver
                        assert mock_graph_db.driver.called

    def test_connect_to_neo4j_container_start(self, mock_config):
        """Test Neo4j connection with container startup."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.Neo4jContainerManager"
            ) as mock_container_class:
                with patch("src.azure_tenant_grapher.GraphDatabase") as mock_graph_db:
                    with patch("src.azure_tenant_grapher.create_llm_generator"):
                        # Setup mocks
                        mock_container = Mock()
                        mock_container.is_neo4j_container_running.return_value = False
                        mock_container.setup_neo4j.return_value = True
                        mock_container_class.return_value = mock_container

                        mock_driver = Mock()
                        mock_session = Mock()
                        mock_driver.session.return_value.__enter__ = Mock(
                            return_value=mock_session
                        )
                        mock_driver.session.return_value.__exit__ = Mock(
                            return_value=None
                        )
                        mock_graph_db.driver.return_value = mock_driver

                        grapher = AzureTenantGrapher(mock_config)
                        grapher.connect_to_neo4j()

                        assert mock_container.setup_neo4j.called
                        assert grapher.driver == mock_driver

    def test_connect_to_neo4j_connection_failure(self, mock_config):
        """Test Neo4j connection failure."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.Neo4jContainerManager"
            ) as mock_container_class:
                with patch("src.azure_tenant_grapher.GraphDatabase") as mock_graph_db:
                    with patch("src.azure_tenant_grapher.create_llm_generator"):
                        # Setup mocks
                        mock_container = Mock()
                        mock_container.is_neo4j_container_running.return_value = True
                        mock_container_class.return_value = mock_container

                        mock_graph_db.driver.side_effect = Exception(
                            "Connection failed"
                        )

                        grapher = AzureTenantGrapher(mock_config)

                        with pytest.raises(Exception, match="Connection failed"):
                            grapher.connect_to_neo4j()

    def test_close_neo4j_connection(self, mock_config):
        """Test Neo4j connection closure."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                grapher = AzureTenantGrapher(mock_config)

                # Mock driver
                mock_driver = Mock()
                grapher.driver = mock_driver

                grapher.close_neo4j_connection()

                assert mock_driver.close.called

    @pytest.mark.asyncio
    async def test_discover_subscriptions_success(self, mock_config):
        """Test successful subscription discovery."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.SubscriptionClient"
            ) as mock_sub_client:
                with patch("src.azure_tenant_grapher.create_llm_generator"):
                    # Setup mock subscription
                    mock_subscription = Mock()
                    mock_subscription.subscription_id = "test-sub-id"
                    mock_subscription.display_name = "Test Subscription"
                    mock_subscription.state = "Enabled"
                    mock_subscription.tenant_id = "test-tenant-id"

                    mock_client = Mock()
                    mock_client.subscriptions.list.return_value = [mock_subscription]
                    mock_sub_client.return_value = mock_client

                    grapher = AzureTenantGrapher(mock_config)
                    subscriptions = await grapher.discover_subscriptions()

                    assert len(subscriptions) == 1
                    assert subscriptions[0]["id"] == "test-sub-id"
                    assert subscriptions[0]["display_name"] == "Test Subscription"

    @pytest.mark.asyncio
    async def test_discover_subscriptions_exception(self, mock_config):
        """Test subscription discovery handles exceptions."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.SubscriptionClient"
            ) as mock_sub_client:
                with patch("src.azure_tenant_grapher.create_llm_generator"):
                    mock_client = Mock()
                    mock_client.subscriptions.list.side_effect = Exception("API Error")
                    mock_sub_client.return_value = mock_client

                    grapher = AzureTenantGrapher(mock_config)

                    with pytest.raises(Exception, match="API Error"):
                        await grapher.discover_subscriptions()

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_success(self, mock_config):
        """Test successful resource discovery in subscription."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.ResourceManagementClient"
            ) as mock_resource_client:
                with patch("src.azure_tenant_grapher.create_llm_generator"):
                    # Setup mock resource
                    mock_resource = Mock()
                    mock_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm"
                    mock_resource.name = "test-vm"
                    mock_resource.type = "Microsoft.Compute/virtualMachines"
                    mock_resource.location = "eastus"
                    mock_resource.tags = {"Environment": "Test"}
                    mock_resource.kind = None
                    mock_resource.sku = None

                    mock_client = Mock()
                    mock_client.resources.list.return_value = [mock_resource]
                    mock_resource_client.return_value = mock_client

                    grapher = AzureTenantGrapher(mock_config)
                    resources = await grapher.discover_resources_in_subscription(
                        "test-sub-id"
                    )

                    assert len(resources) == 1
                    assert resources[0]["name"] == "test-vm"
                    assert resources[0]["type"] == "Microsoft.Compute/virtualMachines"
                    assert resources[0]["resource_group"] == "test-rg"

    @pytest.mark.asyncio
    async def test_discover_resources_in_subscription_exception(self, mock_config):
        """Test resource discovery handles exceptions."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.ResourceManagementClient"
            ) as mock_resource_client:
                with patch("src.azure_tenant_grapher.create_llm_generator"):
                    mock_client = Mock()
                    mock_client.resources.list.side_effect = Exception("API Error")
                    mock_resource_client.return_value = mock_client

                    grapher = AzureTenantGrapher(mock_config)
                    resources = await grapher.discover_resources_in_subscription(
                        "test-sub-id"
                    )

                    # Should return empty list on exception
                    assert len(resources) == 0

    def test_create_subscription_node(self, mock_config):
        """Test subscription node creation."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                grapher = AzureTenantGrapher(mock_config)

                mock_session = Mock()
                subscription = {
                    "id": "test-sub-id",
                    "display_name": "Test Subscription",
                    "state": "Enabled",
                    "tenant_id": "test-tenant-id",
                }

                grapher.create_subscription_node(mock_session, subscription)

                assert mock_session.run.called
                call_args = mock_session.run.call_args
                assert "MERGE (s:Subscription {id: $id})" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_process_resources_with_enhanced_handling_empty(self, mock_config):
        """Test enhanced resource processing with empty list."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                grapher = AzureTenantGrapher(mock_config)

                result = await grapher.process_resources_with_enhanced_handling([])

                assert result["total_resources"] == 0
                assert result["successful"] == 0
                assert result["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_process_resources_with_enhanced_handling_success(
        self, mock_config, sample_resources
    ):
        """Test successful enhanced resource processing."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                with patch.object(AzureTenantGrapher, "connect_to_neo4j"):
                    with patch.object(AzureTenantGrapher, "close_neo4j_connection"):
                        with patch(
                            "src.azure_tenant_grapher.create_resource_processor"
                        ) as mock_processor_factory:
                            # Setup mock processor
                            mock_processor = Mock()
                            mock_stats = Mock()
                            mock_stats.total_resources = 2
                            mock_stats.successful = 2
                            mock_stats.failed = 0
                            mock_stats.skipped = 0
                            mock_stats.llm_generated = 2
                            mock_stats.llm_skipped = 0
                            mock_stats.success_rate = 100.0
                            mock_processor.process_resources_batch = AsyncMock(
                                return_value=mock_stats
                            )
                            mock_processor_factory.return_value = mock_processor

                            grapher = AzureTenantGrapher(mock_config)
                            grapher.driver = Mock()
                            grapher.driver.session.return_value.__enter__ = Mock(
                                return_value=Mock()
                            )
                            grapher.driver.session.return_value.__exit__ = Mock(
                                return_value=None
                            )

                            result = (
                                await grapher.process_resources_with_enhanced_handling(
                                    sample_resources
                                )
                            )

                            assert result["total_resources"] == 2
                            assert result["successful"] == 2
                            assert result["success_rate"] == 100.0

    @pytest.mark.asyncio
    async def test_build_graph_success(self, mock_config, sample_resources):
        """Test successful complete graph building."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                with patch.object(AzureTenantGrapher, "connect_to_neo4j"):
                    with patch.object(AzureTenantGrapher, "close_neo4j_connection"):
                        with patch.object(
                            AzureTenantGrapher, "discover_subscriptions"
                        ) as mock_discover_subs:
                            with patch.object(
                                AzureTenantGrapher, "discover_resources_in_subscription"
                            ) as mock_discover_resources:
                                with patch.object(
                                    AzureTenantGrapher,
                                    "process_resources_with_enhanced_handling",
                                ) as mock_process:
                                    with patch.object(
                                        AzureTenantGrapher, "create_subscription_node"
                                    ):
                                        # Setup mocks
                                        mock_discover_subs.return_value = [
                                            {
                                                "id": "test-sub",
                                                "display_name": "Test Sub",
                                            }
                                        ]
                                        mock_discover_resources.return_value = (
                                            sample_resources
                                        )
                                        mock_process.return_value = {
                                            "total_resources": 2,
                                            "successful": 2,
                                            "failed": 0,
                                            "skipped": 0,
                                            "llm_generated": 2,
                                            "success_rate": 100.0,
                                        }

                                        grapher = AzureTenantGrapher(mock_config)
                                        grapher.driver = Mock()
                                        grapher.driver.session.return_value.__enter__ = Mock(
                                            return_value=Mock()
                                        )
                                        grapher.driver.session.return_value.__exit__ = (
                                            Mock(return_value=None)
                                        )

                                        result = await grapher.build_graph()

                                        assert result["success"] is True
                                        assert result["subscriptions"] == 1
                                        assert result["total_resources"] == 2
                                        assert result["successful_resources"] == 2

    @pytest.mark.asyncio
    async def test_build_graph_no_subscriptions(self, mock_config):
        """Test graph building with no subscriptions found."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                with patch.object(AzureTenantGrapher, "connect_to_neo4j"):
                    with patch.object(AzureTenantGrapher, "close_neo4j_connection"):
                        with patch.object(
                            AzureTenantGrapher, "discover_subscriptions"
                        ) as mock_discover_subs:
                            mock_discover_subs.return_value = []

                            grapher = AzureTenantGrapher(mock_config)
                            result = await grapher.build_graph()

                            assert result["success"] is False
                            assert result["subscriptions"] == 0

    @pytest.mark.asyncio
    async def test_build_graph_exception(self, mock_config):
        """Test graph building handles exceptions."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch("src.azure_tenant_grapher.create_llm_generator"):
                with patch.object(
                    AzureTenantGrapher,
                    "connect_to_neo4j",
                    side_effect=Exception("Connection failed"),
                ):
                    with patch.object(AzureTenantGrapher, "close_neo4j_connection"):
                        grapher = AzureTenantGrapher(mock_config)
                        result = await grapher.build_graph()

                        assert result["success"] is False
                        assert "error" in result

    @pytest.mark.asyncio
    async def test_generate_tenant_specification_no_llm(self, mock_config_no_llm):
        """Test tenant specification generation when LLM is not available."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            grapher = AzureTenantGrapher(mock_config_no_llm)

            # Should return without error
            await grapher.generate_tenant_specification()

    @pytest.mark.asyncio
    async def test_generate_tenant_specification_success(self, mock_config):
        """Test successful tenant specification generation."""
        with patch("src.azure_tenant_grapher.DefaultAzureCredential"):
            with patch(
                "src.azure_tenant_grapher.create_llm_generator"
            ) as mock_llm_factory:
                with patch.object(AzureTenantGrapher, "connect_to_neo4j"):
                    with patch.object(AzureTenantGrapher, "close_neo4j_connection"):
                        # Setup mock LLM generator
                        mock_llm = Mock()
                        mock_llm.generate_tenant_specification = AsyncMock(
                            return_value="/tmp/spec.md"
                        )
                        mock_llm_factory.return_value = mock_llm

                        grapher = AzureTenantGrapher(mock_config)
                        grapher.driver = Mock()

                        # Mock session and query results
                        mock_session = Mock()
                        mock_session.run.side_effect = [
                            Mock(
                                __iter__=lambda x: iter(
                                    [{"id": "test", "name": "test"}]
                                )
                            ),  # resources
                            Mock(
                                __iter__=lambda x: iter(
                                    [{"relationship_type": "CONTAINS"}]
                                )
                            ),  # relationships
                        ]
                        grapher.driver.session.return_value.__enter__ = Mock(
                            return_value=mock_session
                        )
                        grapher.driver.session.return_value.__exit__ = Mock(
                            return_value=None
                        )

                        await grapher.generate_tenant_specification()

                        assert mock_llm.generate_tenant_specification.called
