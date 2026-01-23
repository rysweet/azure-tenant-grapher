# mypy: disable-error-code=misc
"""
Tests for config_manager module.
"""

import logging
import os
from unittest.mock import patch

import pytest

from src.config_manager import (
    AzureOpenAIConfig,
    AzureTenantGrapherConfig,
    LoggingConfig,
    Neo4jConfig,
    ProcessingConfig,
    create_config_from_env,
    setup_logging,
)


class TestNeo4jConfig:
    """Test cases for Neo4jConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",  # nosec # pragma: allowlist secret
            },
        ):
            config = Neo4jConfig()
            assert config.uri == "bolt://test:7687"
            assert config.user == "testuser"
            assert config.password == "testpass"  # nosec # pragma: allowlist secret

    def test_validation_missing_uri(self) -> None:
        """Test validation fails when URI is missing."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",  # pragma: allowlist secret
            },  # nosec
        ):
            with pytest.raises(ValueError, match="Neo4j URI is required"):
                Neo4jConfig()

    def test_validation_missing_user(self) -> None:
        """Test validation fails when user is missing."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "",
                "NEO4J_PASSWORD": "testpass",  # nosec # pragma: allowlist secret
            },
        ):
            with pytest.raises(ValueError, match="Neo4j user is required"):
                Neo4jConfig()

    def test_validation_missing_password(self) -> None:
        """Test validation fails when password is missing."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "",  # nosec
            },
        ):
            with pytest.raises(ValueError, match="Neo4j password is required"):
                Neo4jConfig()

    def test_get_connection_string(self) -> None:
        """Test connection string generation."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",  # nosec # pragma: allowlist secret
            },
        ):
            config = Neo4jConfig()
            conn_str = config.get_connection_string()
            assert "bolt://test:7687" in conn_str
            assert "testuser" in conn_str
            assert (
                "testpass" not in conn_str
            )  # Password should not be in connection string


class TestAzureOpenAIConfig:
    """Test cases for AzureOpenAIConfig."""

    def test_is_configured_true(self) -> None:
        """Test is_configured returns True when properly configured."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureOpenAIConfig()
            assert config.is_configured() is True

    def test_is_configured_false_missing_endpoint(self) -> None:
        """Test is_configured returns False when endpoint is missing."""
        with patch.dict(
            os.environ, {"AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_KEY": "test-key"}
        ):
            config = AzureOpenAIConfig()
            assert config.is_configured() is False

    def test_is_configured_false_missing_key(self) -> None:
        """Test is_configured returns False when key is missing."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "",
            },
        ):
            config = AzureOpenAIConfig()
            assert config.is_configured() is False

    def test_validate_success(self) -> None:
        """Test successful validation."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureOpenAIConfig()
            config.validate()  # Should not raise

    def test_validate_incomplete_config(self) -> None:
        """Test validation fails with incomplete config."""
        with patch.dict(
            os.environ, {"AZURE_OPENAI_ENDPOINT": "", "AZURE_OPENAI_KEY": "test-key"}
        ):
            config = AzureOpenAIConfig()
            with pytest.raises(
                ValueError, match="Azure OpenAI configuration is incomplete"
            ):
                config.validate()

    def test_validate_non_https_endpoint(self) -> None:
        """Test validation fails with non-HTTPS endpoint."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "http://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureOpenAIConfig()
            with pytest.raises(
                ValueError, match="Azure OpenAI endpoint must use HTTPS"
            ):
                config.validate()

    def test_get_safe_endpoint(self) -> None:
        """Test safe endpoint masking."""
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_ENDPOINT": "https://verylong-endpoint-name.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureOpenAIConfig()
            safe_endpoint = config.get_safe_endpoint()
            assert "verylong-e" in safe_endpoint
            assert "ure.com" in safe_endpoint
            assert len(safe_endpoint) < len(config.endpoint)


class TestProcessingConfig:
    """Test cases for ProcessingConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        with patch.dict(os.environ, {}):
            config = ProcessingConfig()
            assert config.resource_limit is None
            assert config.max_concurrency == 5
            assert config.max_retries == 3
            assert config.retry_delay == 1.0
            assert config.parallel_processing is True
            assert config.auto_start_container is True

    def test_environment_override(self) -> None:
        """Test environment variable overrides."""
        with patch.dict(
            os.environ,
            {
                "PROCESSING_BATCH_SIZE": "10",
                "PROCESSING_MAX_RETRIES": "5",
                "PROCESSING_RETRY_DELAY": "2.5",
                "PROCESSING_PARALLEL": "false",
                "AUTO_START_CONTAINER": "false",
            },
        ):
            config = ProcessingConfig()
            assert config.max_concurrency == 10
            assert config.max_retries == 5
            assert config.retry_delay == 2.5
            assert config.parallel_processing is False
            assert config.auto_start_container is False

    def test_validation_invalid_batch_size(self) -> None:
        """Test validation fails with invalid max concurrency."""
        with patch.dict(os.environ, {"PROCESSING_BATCH_SIZE": "0"}):
            with pytest.raises(ValueError, match="Max concurrency must be at least 1"):
                ProcessingConfig()

    def test_validation_invalid_max_retries(self) -> None:
        """Test validation fails with invalid max retries."""
        with patch.dict(os.environ, {"PROCESSING_MAX_RETRIES": "-1"}):
            with pytest.raises(ValueError, match="Max retries must be non-negative"):
                ProcessingConfig()

    def test_validation_invalid_retry_delay(self) -> None:
        """Test validation fails with invalid retry delay."""
        with patch.dict(os.environ, {"PROCESSING_RETRY_DELAY": "-1.0"}):
            with pytest.raises(ValueError, match="Retry delay must be non-negative"):
                ProcessingConfig()

    def test_validation_invalid_resource_limit(self) -> None:
        """Test validation fails with invalid resource limit."""
        config = ProcessingConfig()
        config.resource_limit = 0
        with pytest.raises(ValueError, match="Resource limit must be at least 1"):
            config.__post_init__()


class TestLoggingConfig:
    """Test cases for LoggingConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        with patch.dict(os.environ, {}):
            config = LoggingConfig()
            assert config.level == "INFO"
            assert config.file_output is None

    def test_environment_override(self) -> None:
        """Test environment variable overrides."""
        with patch.dict(
            os.environ,
            {"LOG_LEVEL": "DEBUG", "LOG_FILE": "/tmp/test.log"},  # nosec
        ):
            config = LoggingConfig()
            assert config.level == "DEBUG"
            assert config.file_output == "/tmp/test.log"  # nosec

    def test_validation_invalid_log_level(self) -> None:
        """Test validation fails with invalid log level."""
        with patch.dict(os.environ, {"LOG_LEVEL": "INVALID"}):
            with pytest.raises(ValueError, match="Log level must be one of"):
                LoggingConfig()

    def test_log_level_case_insensitive(self) -> None:
        """Test log level is case insensitive."""
        with patch.dict(os.environ, {"LOG_LEVEL": "debug"}):
            config = LoggingConfig()
            assert config.level == "DEBUG"

    def test_get_log_level(self) -> None:
        """Test get_log_level returns correct logging constant."""
        import logging

        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}):
            config = LoggingConfig()
            assert config.get_log_level() == logging.WARNING


class TestAzureTenantGrapherConfig:
    """Test cases for AzureTenantGrapherConfig."""

    def test_from_environment(self) -> None:
        """Test configuration creation from environment."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureTenantGrapherConfig.from_environment("test-tenant", 100)
            assert config.tenant_id == "test-tenant"
            assert config.processing.resource_limit == 100
            assert config.neo4j.uri == "bolt://test:7687"
            assert config.azure_openai.is_configured() is True

    def test_validate_all_success(self) -> None:
        """Test successful validation of all components."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureTenantGrapherConfig.from_environment("test-tenant")
            config.validate_all()  # Should not raise

    def test_validate_all_missing_tenant_id(self) -> None:
        """Test validation fails when tenant ID is missing."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
            },
        ):
            config = AzureTenantGrapherConfig()
            with pytest.raises(ValueError, match="Tenant ID is required"):
                config.validate_all()

    def test_to_dict(self) -> None:
        """Test configuration serialization to dictionary."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
                "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
                "AZURE_OPENAI_KEY": "test-key",
            },
        ):
            config = AzureTenantGrapherConfig.from_environment("test-tenant")
            config_dict = config.to_dict()

            assert config_dict["tenant_id"] == "test-tenant"
            assert "neo4j" in config_dict
            assert "azure_openai" in config_dict
            assert "processing" in config_dict
            assert "logging" in config_dict

            # Ensure password is not in serialized data
            assert "password" not in str(config_dict)


class TestFactoryFunctions:
    """Test cases for factory functions."""

    def test_setup_logging_console(self) -> None:
        """Test logging setup for console output."""
        config = LoggingConfig()
        config.level = "INFO"
        # This should not raise an exception
        setup_logging(config)

        # Verify logger is configured
        logger = logging.getLogger()
        assert logger.level == logging.INFO

    def test_setup_logging_file(self) -> None:
        """Test logging setup for file output."""
        with patch.dict(os.environ, {"LOG_FILE": "/tmp/test.log"}):  # nosec
            config = LoggingConfig()
            config.level = "DEBUG"
            config.file_output = "/tmp/test.log"  # nosec

            # This should not raise an exception
            setup_logging(config)

            # Verify logger is configured
            logger = logging.getLogger()
            assert logger.level == logging.DEBUG

    def test_create_config_from_env(self) -> None:
        """Test configuration creation and validation from environment."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "bolt://test:7687",
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
            },
        ):
            config = create_config_from_env("test-tenant", 50)
            assert config.tenant_id == "test-tenant"
            assert config.processing.resource_limit == 50

    def test_create_config_from_env_validation_error(self) -> None:
        """Test configuration creation fails with validation error."""
        with patch.dict(
            os.environ,
            {
                "NEO4J_URI": "",  # Invalid URI
                "NEO4J_USER": "testuser",
                "NEO4J_PASSWORD": "testpass",
            },
        ):
            with pytest.raises(ValueError):
                create_config_from_env("test-tenant")
