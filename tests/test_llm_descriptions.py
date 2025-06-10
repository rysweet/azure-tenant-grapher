# mypy: disable-error-code=misc
"""
Tests for llm_descriptions module.
"""

from unittest.mock import Mock, patch

import pytest

from src.llm_descriptions import (
    AzureLLMDescriptionGenerator,
    LLMConfig,
    create_llm_generator,
)


class TestLLMConfig:
    """Test cases for LLMConfig."""

    def test_from_env_default_values(self) -> None:
        """Test LLMConfig creation with default values."""
        # Clear any existing environment variables to test true defaults
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",  # nosec
            },
            clear=True,
        ):
            config = LLMConfig.from_env()
            assert config.endpoint == "https://test.openai.azure.com/"
            assert config.api_key == "test-key"
            assert config.api_version == "2025-04-16"  # The actual default from code
            assert config.model_chat == "gpt-4"
            assert config.model_reasoning == "gpt-4"

    def test_from_env_custom_values(self) -> None:
        """Test LLMConfig creation with custom environment values."""
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://custom.openai.azure.com/",
                "AZURE_OPENAI_KEY": "custom-key",  # nosec
                "AZURE_OPENAI_API_VERSION": "2024-12-01",
                "AZURE_OPENAI_MODEL_CHAT": "gpt-4o",
                "AZURE_OPENAI_MODEL_REASONING": "o1-preview",
            },
        ):
            config = LLMConfig.from_env()
            assert config.endpoint == "https://custom.openai.azure.com/"
            assert config.api_key == "custom-key"
            assert config.api_version == "2024-12-01"
            assert config.model_chat == "gpt-4o"
            assert config.model_reasoning == "o1-preview"

    def test_is_valid_true(self) -> None:
        """Test is_valid returns True for valid configuration."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",  # nosec
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )
        assert config.is_valid() is True

    def test_is_valid_false_missing_endpoint(self) -> None:
        """Test is_valid returns False when endpoint is missing."""
        config = LLMConfig(
            endpoint="",
            api_key="test-key",  # nosec
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )
        assert config.is_valid() is False

    def test_is_valid_false_missing_key(self) -> None:
        """Test is_valid returns False when API key is missing."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="",  # nosec
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )
        assert config.is_valid() is False


class TestAzureLLMDescriptionGenerator:
    """Test cases for AzureLLMDescriptionGenerator."""

    def test_initialization_valid_config(self) -> None:
        """Test successful initialization with valid configuration."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        with patch("src.llm_descriptions.AzureOpenAI") as mock_azure_openai:
            generator = AzureLLMDescriptionGenerator(config)
            assert generator.config == config
            assert mock_azure_openai.called

    def test_initialization_invalid_config(self) -> None:
        """Test initialization fails with invalid configuration."""
        config = LLMConfig(
            endpoint="",  # Invalid
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        with pytest.raises(ValueError, match="Invalid LLM configuration"):
            AzureLLMDescriptionGenerator(config)

    def test_extract_base_url_with_deployment(self) -> None:
        """Test base URL extraction from deployment endpoint."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/openai/deployments/gpt-4/chat/completions",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        with patch("src.llm_descriptions.AzureOpenAI"):
            generator = AzureLLMDescriptionGenerator(config)
            assert generator.base_url == "https://test.openai.azure.com"

    def test_extract_base_url_simple(self) -> None:
        """Test base URL extraction from simple endpoint."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        with patch("src.llm_descriptions.AzureOpenAI"):
            generator = AzureLLMDescriptionGenerator(config)
            assert generator.base_url == "https://test.openai.azure.com/"

    @pytest.mark.asyncio
    async def test_generate_resource_description_success(self) -> None:
        """Test successful resource description generation."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = "This is a mock Azure VM description."

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.llm_descriptions.AzureOpenAI", return_value=mock_client):
            generator = AzureLLMDescriptionGenerator(config)

            resource_data = {
                "name": "test-vm",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
                "properties": {"size": "Standard_D2s_v3"},
                "tags": {"Environment": "Test"},
            }

            description = await generator.generate_resource_description(resource_data)

            assert description == "This is a mock Azure VM description."
            assert mock_client.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_generate_resource_description_exception(self) -> None:
        """Test resource description generation handles exceptions."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with patch("src.llm_descriptions.AzureOpenAI", return_value=mock_client):
            generator = AzureLLMDescriptionGenerator(config)

            resource_data = {
                "name": "test-vm",
                "type": "Microsoft.Compute/virtualMachines",
                "location": "eastus",
            }

            description = await generator.generate_resource_description(resource_data)

            assert "Azure Microsoft.Compute/virtualMachines resource" in description

    @pytest.mark.asyncio
    async def test_generate_relationship_description_success(self) -> None:
        """Test successful relationship description generation."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = "VM depends on storage account for disk storage."

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.llm_descriptions.AzureOpenAI", return_value=mock_client):
            generator = AzureLLMDescriptionGenerator(config)

            source_resource = {
                "name": "test-vm",
                "type": "Microsoft.Compute/virtualMachines",
            }

            target_resource = {
                "name": "test-storage",
                "type": "Microsoft.Storage/storageAccounts",
            }

            description = await generator.generate_relationship_description(
                source_resource, target_resource, "DEPENDS_ON"
            )

            assert description == "VM depends on storage account for disk storage."

    @pytest.mark.asyncio
    async def test_process_resources_batch_success(self) -> None:
        """Test successful batch processing of resources."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Mock description"

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.llm_descriptions.AzureOpenAI", return_value=mock_client):
            generator = AzureLLMDescriptionGenerator(config)

            resources = [
                {
                    "name": "test-vm1",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "eastus",
                },
                {
                    "name": "test-vm2",
                    "type": "Microsoft.Compute/virtualMachines",
                    "location": "westus",
                },
            ]

            enhanced_resources = await generator.process_resources_batch(
                resources, batch_size=2
            )

            assert len(enhanced_resources) == 2
            assert all("llm_description" in resource for resource in enhanced_resources)
            assert all(
                resource["llm_description"] == "Mock description"
                for resource in enhanced_resources
            )

    @pytest.mark.asyncio
    async def test_generate_tenant_specification(self) -> None:
        """Test tenant specification generation."""
        config = LLMConfig(
            endpoint="https://test.openai.azure.com/",
            api_key="test-key",
            api_version="2025-04-16",
            model_chat="gpt-4",
            model_reasoning="gpt-4",
        )

        # Mock the OpenAI client response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[
            0
        ].message.content = (
            "# Azure Tenant Specification\n\nThis is a mock specification."
        )

        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response

        with patch("src.llm_descriptions.AzureOpenAI", return_value=mock_client):
            with patch("builtins.open", create=True) as mock_open:
                generator = AzureLLMDescriptionGenerator(config)

                resources = [
                    {
                        "name": "test-vm",
                        "type": "Microsoft.Compute/virtualMachines",
                        "location": "eastus",
                        "llm_description": "Test VM description",
                    }
                ]

                relationships = [
                    {
                        "relationship_type": "CONTAINS",
                        "source_type": "Subscription",
                        "target_type": "Resource",
                        "source_name": "Test Subscription",
                        "target_name": "test-vm",
                    }
                ]

                output_path = "/tmp/  # nosectest_spec.md"  # nosec
                result_path = await generator.generate_tenant_specification(
                    resources, relationships, output_path
                )

                assert result_path == output_path
                assert mock_open.called


class TestFactoryFunction:
    """Test cases for factory functions."""

    def test_create_llm_generator_valid_config(self) -> None:
        """Test successful LLM generator creation with valid config."""
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            with patch("src.llm_descriptions.AzureOpenAI"):
                generator = create_llm_generator()
                assert isinstance(generator, AzureLLMDescriptionGenerator)

    def test_create_llm_generator_invalid_config(self) -> None:
        """Test LLM generator creation fails with invalid config."""
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "",  # Invalid
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            generator = create_llm_generator()
            assert generator is None

    def test_create_llm_generator_exception(self) -> None:
        """Test LLM generator creation handles exceptions."""
        with patch.dict(
            "os.environ",
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            with patch(
                "src.llm_descriptions.AzureLLMDescriptionGenerator",
                side_effect=Exception("Init error"),
            ):
                generator = create_llm_generator()
                assert generator is None
