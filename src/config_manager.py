import logging
import os

# Removed unused imports tempfile and uuid to satisfy pyright
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

"""
Configuration Management for Azure Tenant Grapher

This module provides centralized configuration management with validation,
environment variable handling, and configuration validation.
"""


def _set_azure_http_log_level(log_level: str) -> None:
    http_loggers = [
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.core.pipeline.policies.HttpLoggingPolicy",
        "msrest",
        "azure",
        "urllib3",
        "http.client",
    ]
    for name in http_loggers:
        logging.getLogger(name).setLevel(
            logging.DEBUG if log_level == "DEBUG" else logging.WARNING
        )


logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j database connection."""

    uri: Optional[str] = None
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(
        default_factory=lambda: os.getenv("NEO4J_PASSWORD", "example-password")
    )

    def __post_init__(self) -> None:
        from src.debug_utils import debug_print
        debug_print(
            f"[DEBUG][Neo4jConfig] uri={self.uri}, NEO4J_PORT={os.getenv('NEO4J_PORT')}, NEO4J_URI={os.getenv('NEO4J_URI')}"
        )
        """Validate configuration after initialization."""
        if not self.uri or (self.uri.strip() == ""):
            self.uri = f"bolt://localhost:{os.environ.get('NEO4J_PORT', '7688')}"
            debug_print(f"[DEBUG][Neo4jConfig] After fallback assignment: uri={self.uri}")
        if not self.uri:
            raise ValueError("Neo4j URI is required")
        if not self.user:
            raise ValueError("Neo4j user is required")
        if not self.password:
            raise ValueError("Neo4j password is required")

    def get_connection_string(self) -> str:
        """Get formatted connection string for logging (without password)."""
        return f"{self.uri} (user: {self.user})"


@dataclass
class AzureOpenAIConfig:
    """Configuration for Azure OpenAI services."""

    endpoint: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_ENDPOINT", "")
    )
    api_key: str = field(default_factory=lambda: os.getenv("AZURE_OPENAI_KEY", ""))
    api_version: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_API_VERSION", "2025-04-16")
    )
    model_chat: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_MODEL_CHAT", "gpt-4")
    )
    model_reasoning: str = field(
        default_factory=lambda: os.getenv("AZURE_OPENAI_MODEL_REASONING", "gpt-4")
    )

    def is_configured(self) -> bool:
        """Check if Azure OpenAI is properly configured."""
        return bool(self.endpoint and self.api_key)

    def validate(self) -> None:
        """Validate Azure OpenAI configuration."""
        if not self.is_configured():
            raise ValueError(
                "Azure OpenAI configuration is incomplete. Please set AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_KEY"
            )

        if not self.endpoint.startswith("https://"):
            raise ValueError("Azure OpenAI endpoint must use HTTPS")

    def get_safe_endpoint(self) -> str:
        """Get endpoint for logging (masked for security)."""
        if self.endpoint:
            parts = self.endpoint.split("/")
            if len(parts) >= 3:
                return f"https://{parts[2][:10]}...{parts[2][-10:]}"
        return "Not configured"


@dataclass
class ProcessingConfig:
    """Configuration for resource processing behavior."""

    resource_limit: Optional[int] = field(default_factory=lambda: None)
    # Remove batch_size, add max_concurrency with migration shim
    max_concurrency: int = field(
        default_factory=lambda: (
            int(os.getenv("MAX_CONCURRENCY", "5"))
            if "MAX_CONCURRENCY" in os.environ
            or "PROCESSING_BATCH_SIZE" not in os.environ
            else int(os.getenv("PROCESSING_BATCH_SIZE", "5"))
        )
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("PROCESSING_MAX_RETRIES", "3"))
    )
    retry_delay: float = field(
        default_factory=lambda: float(os.getenv("PROCESSING_RETRY_DELAY", "1.0"))
    )
    parallel_processing: bool = field(
        default_factory=lambda: os.getenv("PROCESSING_PARALLEL", "true").lower()
        == "true"
    )
    auto_start_container: bool = field(
        default_factory=lambda: os.getenv("AUTO_START_CONTAINER", "true").lower()
        == "true"
    )

    def __post_init__(self) -> None:
        """Validate processing configuration and handle migration shim for batch_size."""
        # Migration shim: map legacy batch_size to max_concurrency with warning
        legacy_batch_size = os.getenv("PROCESSING_BATCH_SIZE")
        if legacy_batch_size and "MAX_CONCURRENCY" not in os.environ:
            try:
                self.max_concurrency = int(legacy_batch_size)
            except Exception:
                pass
        if self.max_concurrency < 1:
            raise ValueError("Max concurrency must be at least 1")
        if self.max_retries < 0:
            raise ValueError("Max retries must be non-negative")
        if self.retry_delay < 0:
            raise ValueError("Retry delay must be non-negative")
        if self.resource_limit is not None and self.resource_limit < 1:
            raise ValueError("Resource limit must be at least 1")


@dataclass
class LoggingConfig:
    """Configuration for logging behavior."""

    level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    format: str = field(
        default_factory=lambda: os.getenv(
            "LOG_FORMAT", "%(log_color)s%(levelname)s:%(name)s:%(message)s"
        )
    )
    file_output: Optional[str] = field(default_factory=lambda: os.getenv("LOG_FILE"))

    def __post_init__(self) -> None:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            raise ValueError(f"Log level must be one of: {valid_levels}")
        self.level = self.level.upper()

    def get_log_level(self) -> int:
        """Convert string log level to logging constant."""
        level_attr = getattr(logging, self.level, None)
        if level_attr is None:
            raise ValueError(f"Invalid log level: {self.level}")
        return int(level_attr)


# Removed unused function _generate_default_log_file to satisfy pyright


@dataclass
class SpecificationConfig:
    """Configuration for specification generation."""

    resource_limit: Optional[int] = field(default_factory=lambda: None)
    output_directory: str = field(
        default_factory=lambda: os.getenv("AZTG_SPEC_OUTPUT_DIR", ".")
    )
    include_ai_summaries: bool = field(
        default_factory=lambda: os.getenv("AZTG_SPEC_INCLUDE_AI", "true").lower()
        == "true"
    )
    include_configuration_details: bool = field(
        default_factory=lambda: os.getenv("AZTG_SPEC_INCLUDE_CONFIG", "true").lower()
        == "true"
    )
    anonymization_seed: Optional[str] = field(
        default_factory=lambda: os.getenv("AZTG_SPEC_ANONYMIZATION_SEED", None)
    )
    template_style: str = field(
        default_factory=lambda: os.getenv("AZTG_SPEC_TEMPLATE_STYLE", "comprehensive")
    )


@dataclass
class AzureTenantGrapherConfig:
    """Main configuration class that aggregates all configuration sections."""

    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    azure_openai: AzureOpenAIConfig = field(default_factory=AzureOpenAIConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    specification: SpecificationConfig = field(default_factory=SpecificationConfig)
    tenant_id: Optional[str] = None

    @classmethod
    def from_environment(
        cls,
        tenant_id: str,
        resource_limit: Optional[int] = None,
        max_retries: Optional[int] = None,
    ) -> "AzureTenantGrapherConfig":
        """
        Create configuration from environment variables.

        Args:
            tenant_id: Azure tenant ID
            resource_limit: Optional limit on resources to process
            max_retries: Optional max retries for failed resources

        Returns:
            AzureTenantGrapherConfig: Configured instance
        """
        config = cls()
        config.tenant_id = tenant_id

        # Override resource limit if provided
        if resource_limit is not None:
            config.processing.resource_limit = resource_limit
            config.specification.resource_limit = resource_limit
        if max_retries is not None:
            config.processing.max_retries = max_retries

        return config

    def validate_all(self) -> None:
        """Validate all configuration sections."""
        try:
            # Validate tenant ID
            if not self.tenant_id:
                raise ValueError("Tenant ID is required")

            # Validate individual sections
            self.neo4j.__post_init__()
            self.processing.__post_init__()
            self.logging.__post_init__()
            # No __post_init__ for specification, but could add validation if needed

            # Validate Azure OpenAI if enabled
            if self.azure_openai.is_configured():
                self.azure_openai.validate()

            logger.info("✅ Configuration validation successful")

        except Exception as e:
            logger.exception(f"❌ Configuration validation failed: {e}")
            raise

    def log_configuration_summary(self) -> None:
        """Log a summary of the current configuration (without sensitive data)."""
        logger.info("=" * 60)
        logger.info("🔧 AZURE TENANT GRAPHER CONFIGURATION")
        logger.info("=" * 60)
        logger.info(f"📋 Tenant ID: {self.tenant_id}")
        logger.info(f"🗄️  Neo4j: {self.neo4j.get_connection_string()}")
        logger.info(f"🤖 Azure OpenAI: {self.azure_openai.get_safe_endpoint()}")
        logger.info("⚙️  Processing:")
        logger.info(
            f"   - Resource Limit: {self.processing.resource_limit or 'Unlimited'}"
        )
        logger.info(f"   - Max Concurrency: {self.processing.max_concurrency}")
        logger.info(f"   - Max Retries: {self.processing.max_retries}")
        logger.info(f"   - Parallel Processing: {self.processing.parallel_processing}")
        logger.info(
            f"   - Auto Start Container: {self.processing.auto_start_container}"
        )
        logger.info("📄 Specification:")
        logger.info(f"   - Spec Resource Limit: {self.specification.resource_limit}")
        logger.info(f"   - Output Directory: {self.specification.output_directory}")
        logger.info(
            f"   - Include AI Summaries: {self.specification.include_ai_summaries}"
        )
        logger.info(
            f"   - Include Config Details: {self.specification.include_configuration_details}"
        )
        logger.info(f"   - Template Style: {self.specification.template_style}")
        logger.info(f"📝 Logging Level: {self.logging.level}")
        if self.logging.file_output:
            logger.info(f"📄 Log File: {self.logging.file_output}")
        logger.info("=" * 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "neo4j": {
                "uri": self.neo4j.uri,
                "user": self.neo4j.user,
                # Don't include password in serialization
            },
            "azure_openai": {
                "endpoint": self.azure_openai.get_safe_endpoint(),
                "api_version": self.azure_openai.api_version,
                "model_chat": self.azure_openai.model_chat,
                "model_reasoning": self.azure_openai.model_reasoning,
                "configured": self.azure_openai.is_configured(),
            },
            "processing": {
                "resource_limit": self.processing.resource_limit,
                "max_concurrency": self.processing.max_concurrency,
                "max_retries": self.processing.max_retries,
                "retry_delay": self.processing.retry_delay,
                "parallel_processing": self.processing.parallel_processing,
                "auto_start_container": self.processing.auto_start_container,
            },
            "logging": {
                "level": self.logging.level,
                "file_output": self.logging.file_output,
            },
            "specification": {
                "resource_limit": self.specification.resource_limit,
                "output_directory": self.specification.output_directory,
                "include_ai_summaries": self.specification.include_ai_summaries,
                "include_configuration_details": self.specification.include_configuration_details,
                "anonymization_seed": self.specification.anonymization_seed,
                "template_style": self.specification.template_style,
            },
        }


def setup_logging(config: LoggingConfig) -> None:
    """
    Setup logging configuration based on config.
    """
    _set_azure_http_log_level(config.level.upper())

    try:
        import colorlog

        use_colorlog = True
        colorlog_available = colorlog
    except ImportError:
        use_colorlog = False
        colorlog_available = None

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.handlers.clear()  # Remove any existing handlers
    root_logger.setLevel(config.get_log_level())

    # Always add console handler
    if use_colorlog and colorlog_available:
        console_handler = colorlog_available.StreamHandler()
        console_formatter = colorlog_available.ColoredFormatter(config.format)
    else:
        console_handler = logging.StreamHandler[Any]()
        # Use a simpler format without color placeholders when colorlog is not available
        simple_format = config.format.replace("%(log_color)s", "").replace(
            "%(reset)s", ""
        )
        console_formatter = logging.Formatter(simple_format)

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Add file handler if file output is configured
    if config.file_output:
        file_handler = logging.FileHandler(config.file_output)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s:%(name)s:%(message)s"
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    # Set specific loggers to appropriate levels
    azure_logger = logging.getLogger("azure")
    azure_logger.setLevel(logging.WARNING)  # Reduce Azure SDK noise

    # Specifically suppress Azure HTTP logging policy verbose output
    azure_http_logger = logging.getLogger(
        "azure.core.pipeline.policies.http_logging_policy"
    )
    azure_http_logger.setLevel(logging.DEBUG)  # Only show at DEBUG level

    openai_logger = logging.getLogger("openai")
    openai_logger.setLevel(logging.WARNING)  # Reduce OpenAI SDK noise

    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(
        logging.WARNING
    )  # Suppress INFO level HTTP requests, only show warnings/errors

    logger.info(
        f"📝 Logging configured: level={config.level}, file={config.file_output or 'console'}"
    )


def create_config_from_env(
    tenant_id: str,
    resource_limit: Optional[int] = None,
    max_retries: Optional[int] = None,
) -> AzureTenantGrapherConfig:
    """
    Factory function to create and validate configuration from environment.

    Args:
        tenant_id: Azure tenant ID
        resource_limit: Optional limit on resources to process
        max_retries: Optional max retries for failed resources

    Returns:
        AzureTenantGrapherConfig: Validated configuration instance

    Raises:
        ValueError: If configuration is invalid
    """
    config = AzureTenantGrapherConfig.from_environment(
        tenant_id, resource_limit, max_retries
    )
    config.validate_all()
    return config


def create_neo4j_config_from_env() -> AzureTenantGrapherConfig:
    """
    Factory function to create configuration for Neo4j-only operations (no tenant-id required).
    Returns:
        AzureTenantGrapherConfig: Configuration instance with only Neo4j, logging, and specification.
    """
    config = AzureTenantGrapherConfig()
    # Only validate Neo4j, logging, and specification sections
    try:
        config.neo4j.__post_init__()
        config.logging.__post_init__()
        # No __post_init__ for specification, but could add validation if needed
    except Exception as e:
        logger.exception(f"❌ Neo4j-only configuration validation failed: {e}")
        raise
    return config
