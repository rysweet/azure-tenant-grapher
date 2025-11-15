import logging
import os

# Removed unused imports tempfile and uuid to satisfy pyright
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv(override=True)

"""
Configuration Management for Azure Tenant Grapher

This module provides centralized configuration management with validation,
environment variable handling, and configuration validation.
"""


def _set_azure_http_log_level(log_level: str) -> None:
    """Set log levels for HTTP-related loggers to reduce noise."""
    http_loggers = [
        "azure.core.pipeline.policies.http_logging_policy",
        "azure.core.pipeline.policies.HttpLoggingPolicy",
        "azure.core.pipeline",
        "azure.identity",
        "azure.mgmt",
        "msrest",
        "azure",
        "urllib3",
        "urllib3.connectionpool",
        "http.client",
        "requests.packages.urllib3",
        "httpx",
        "httpcore",
        "openai",
    ]
    # HTTP logging should only appear at DEBUG level
    target_level = logging.DEBUG if log_level == "DEBUG" else logging.WARNING
    for name in http_loggers:
        logging.getLogger(name).setLevel(target_level)


logger = logging.getLogger(__name__)


@dataclass
class Neo4jConfig:
    """Configuration for Neo4j database connection."""

    uri: Optional[str] = None
    user: str = field(default_factory=lambda: os.getenv("NEO4J_USER", "neo4j"))
    password: str = field(default_factory=lambda: os.getenv("NEO4J_PASSWORD", ""))

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        if not self.uri or (self.uri.strip() == ""):
            port = os.environ.get("NEO4J_PORT")
            if not port:
                raise ValueError(
                    "NEO4J_PORT environment variable is required when NEO4J_URI is not set"
                )
            self.uri = f"bolt://localhost:{port}"
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
            int(os.getenv("MAX_CONCURRENCY", "100"))
            if "MAX_CONCURRENCY" in os.environ
            or "PROCESSING_BATCH_SIZE" not in os.environ
            else int(os.getenv("PROCESSING_BATCH_SIZE", "100"))
        )
    )
    max_retries: int = field(
        default_factory=lambda: int(os.getenv("PROCESSING_MAX_RETRIES", "3"))
    )
    max_build_threads: int = field(
        default_factory=lambda: int(os.getenv("MAX_BUILD_THREADS", "20"))
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
    enable_aad_import: bool = field(
        default_factory=lambda: os.getenv("ENABLE_AAD_IMPORT", "true").lower() == "true"
    )

    def __post_init__(self) -> None:
        """Validate processing configuration and handle migration shim for batch_size."""
        # Migration shim: map legacy batch_size to max_concurrency with warning
        legacy_batch_size = os.getenv("PROCESSING_BATCH_SIZE")
        if legacy_batch_size and "MAX_CONCURRENCY" not in os.environ:
            try:
                self.max_concurrency = int(legacy_batch_size)
            except (ValueError, TypeError):
                # If legacy batch size is not a valid integer, keep default
                logger.debug(
                    f"Invalid legacy batch size value: {legacy_batch_size}, using default"
                )
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
class TenantConfig:
    """Configuration for multi-tenant support."""

    tenant_id: str
    display_name: str = ""
    subscription_ids: List[str] = field(default_factory=list)
    config_path: Optional[Path] = None
    auto_switch: bool = field(
        default_factory=lambda: os.getenv("AZTG_TENANT_AUTO_SWITCH", "false").lower()
        == "true"
    )

    def __post_init__(self) -> None:
        """Validate tenant configuration."""
        if not self.tenant_id:
            raise ValueError("Tenant ID is required")

        # Set default display name if not provided
        if not self.display_name:
            self.display_name = f"Tenant {self.tenant_id[:8]}"

        # Set default config path if not provided
        if not self.config_path:
            self.config_path = (
                Path.home() / ".atg" / "tenants" / f"{self.tenant_id}.json"
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "subscription_ids": self.subscription_ids,
            "config_path": str(self.config_path) if self.config_path else None,
            "auto_switch": self.auto_switch,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TenantConfig":
        """Create from dictionary."""
        config_path = data.get("config_path")
        if config_path:
            data["config_path"] = Path(config_path)
        return cls(**data)


@dataclass
class MCPConfig:
    """Configuration for MCP (Model Context Protocol) integration."""

    endpoint: str = field(
        default_factory=lambda: os.getenv("MCP_ENDPOINT", "http://localhost:8080")
    )
    enabled: bool = field(
        default_factory=lambda: os.getenv("MCP_ENABLED", "false").lower() == "true"
    )
    timeout: int = field(default_factory=lambda: int(os.getenv("MCP_TIMEOUT", "30")))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("MCP_API_KEY"))

    def __post_init__(self) -> None:
        """Validate MCP configuration."""
        if self.timeout < 1:
            raise ValueError("MCP timeout must be at least 1 second")
        if self.enabled and not self.endpoint:
            raise ValueError("MCP endpoint is required when MCP is enabled")


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
    mcp: MCPConfig = field(default_factory=MCPConfig)
    specification: SpecificationConfig = field(default_factory=SpecificationConfig)
    tenant_id: Optional[str] = None
    tenant: Optional[TenantConfig] = None

    @classmethod
    def from_environment(
        cls,
        tenant_id: str,
        resource_limit: Optional[int] = None,
        max_retries: Optional[int] = None,
        max_build_threads: Optional[int] = None,
        max_concurrency: Optional[int] = None,
        debug: bool = False,
        tenant_config: Optional[TenantConfig] = None,
    ) -> "AzureTenantGrapherConfig":
        """
        Create configuration from environment variables.

        Args:
            tenant_id: Azure tenant ID
            resource_limit: Optional limit on resources to process
            max_retries: Optional max retries for failed resources
            max_build_threads: Optional max build threads
            max_concurrency: Optional max concurrent workers
            debug: Enable debug output
            tenant_config: Optional tenant configuration

        Returns:
            AzureTenantGrapherConfig: Configured instance
        """
        config = cls()
        config.tenant_id = tenant_id

        # Set tenant configuration if provided
        if tenant_config:
            config.tenant = tenant_config
        else:
            # Create basic tenant config from tenant_id
            config.tenant = TenantConfig(tenant_id=tenant_id)

        # Override resource limit if provided
        if resource_limit is not None:
            config.processing.resource_limit = resource_limit
            config.specification.resource_limit = resource_limit
        if max_retries is not None:
            config.processing.max_retries = max_retries
        if max_build_threads is not None:
            config.processing.max_build_threads = max_build_threads
        if max_concurrency is not None:
            config.processing.max_concurrency = max_concurrency

        # Debug output after Neo4j config is initialized
        if debug:
            print(
                f"[DEBUG][Neo4jConfig] uri={config.neo4j.uri}, NEO4J_PORT={os.getenv('NEO4J_PORT')}, NEO4J_URI={os.getenv('NEO4J_URI')}"
            )

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
            self.mcp.__post_init__()
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
        if self.tenant:
            logger.info(f"   Display Name: {self.tenant.display_name}")
            if self.tenant.subscription_ids:
                logger.info(
                    f"   Subscriptions: {len(self.tenant.subscription_ids)} configured"
                )
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
        logger.info("🔌 MCP Integration:")
        logger.info(f"   - Enabled: {self.mcp.enabled}")
        if self.mcp.enabled:
            logger.info(f"   - Endpoint: {self.mcp.endpoint}")
            logger.info(f"   - Timeout: {self.mcp.timeout}s")
        logger.info(f"📝 Logging Level: {self.logging.level}")
        if self.logging.file_output:
            logger.info(f"📄 Log File: {self.logging.file_output}")
        logger.info("=" * 60)

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for serialization."""
        return {
            "tenant_id": self.tenant_id,
            "tenant": self.tenant.to_dict() if self.tenant else None,
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
            "mcp": {
                "enabled": self.mcp.enabled,
                "endpoint": self.mcp.endpoint,
                "timeout": self.mcp.timeout,
                # Don't include API key in serialization for security
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
    # These override any settings from _set_azure_http_log_level for fine control
    azure_logger = logging.getLogger("azure")
    azure_logger.setLevel(logging.WARNING)  # Reduce Azure SDK noise

    # Specifically suppress Azure HTTP logging policy verbose output
    azure_http_logger = logging.getLogger(
        "azure.core.pipeline.policies.http_logging_policy"
    )
    azure_http_logger.setLevel(logging.WARNING)  # Suppress HTTP request/response logs

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
    max_build_threads: Optional[int] = None,
    max_concurrency: Optional[int] = None,
    debug: bool = False,
) -> AzureTenantGrapherConfig:
    """
    Factory function to create and validate configuration from environment.

    Args:
        tenant_id: Azure tenant ID
        resource_limit: Optional limit on resources to process
        max_retries: Optional max retries for failed resources
        max_concurrency: Optional max concurrent workers

    Returns:
        AzureTenantGrapherConfig: Validated configuration instance

    Raises:
        ValueError: If configuration is invalid
    """
    config = AzureTenantGrapherConfig.from_environment(
        tenant_id, resource_limit, max_retries, max_build_threads, max_concurrency, debug
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


def get_config_for_tenant(tenant_num: int) -> dict[str, Any]:
    """Get configuration for a specific tenant.

    Args:
        tenant_num: Tenant number (1 or 2)

    Returns:
        Dictionary with tenant configuration
    """
    if tenant_num not in [1, 2]:
        raise ValueError(f"Invalid tenant number: {tenant_num}")

    prefix = f"AZURE_TENANT_{tenant_num}_"

    config = {
        "tenant_id": os.getenv(f"{prefix}ID", ""),
        "client_id": os.getenv(f"{prefix}CLIENT_ID", ""),
        "client_secret": os.getenv(f"{prefix}CLIENT_SECRET", ""),
        "subscription_id": os.getenv(
            f"{prefix}SUBSCRIPTION_ID", os.getenv("AZURE_SUBSCRIPTION_ID", "")
        ),
    }

    # Validate required fields
    if not config["tenant_id"]:
        raise ValueError(f"Missing {prefix}ID environment variable")
    if not config["client_id"]:
        raise ValueError(f"Missing {prefix}CLIENT_ID environment variable")
    if not config["client_secret"]:
        raise ValueError(f"Missing {prefix}CLIENT_SECRET environment variable")

    return config
