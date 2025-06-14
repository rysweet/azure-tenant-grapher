"""
Custom Exception Hierarchy for Azure Tenant Grapher

This module provides a comprehensive exception hierarchy that standardizes error
handling across the application, providing better error context and debugging
information.
"""

from typing import Any, Dict, Optional


class AzureTenantGrapherError(Exception):
    """
    Base exception class for all Azure Tenant Grapher related errors.

    Provides structured error information including context, error codes,
    and optional recovery suggestions.
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None,
        recovery_suggestion: Optional[str] = None,
    ) -> None:
        """
        Initialize the base exception.

        Args:
            message: Human-readable error message
            error_code: Optional error code for programmatic handling
            context: Optional dictionary with error context
            cause: Optional underlying exception that caused this error
            recovery_suggestion: Optional suggestion for error recovery
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        self.cause = cause
        self.recovery_suggestion = recovery_suggestion

    def __str__(self) -> str:
        """Return a formatted error message with context."""
        result = self.message
        if self.error_code:
            result = f"[{self.error_code}] {result}"
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            result += f" (context: {context_str})"
        if self.cause:
            result += f" (caused by: {self.cause})"
        if self.recovery_suggestion:
            result += f" (suggestion: {self.recovery_suggestion})"
        return result

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "error_code": self.error_code,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
            "recovery_suggestion": self.recovery_suggestion,
        }


# Azure-related exceptions
class AzureError(AzureTenantGrapherError):
    """Base class for Azure-related errors."""

    pass


class AzureAuthenticationError(AzureError):
    """Raised when Azure authentication fails."""

    def __init__(
        self, message: str, tenant_id: Optional[str] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if tenant_id:
            context["tenant_id"] = tenant_id
        kwargs["context"] = context
        kwargs.setdefault("error_code", "AZURE_AUTH_FAILED")
        kwargs.setdefault(
            "recovery_suggestion",
            "Try running 'az login' or check your Azure credentials",
        )
        super().__init__(message, **kwargs)


class AzureSubscriptionError(AzureError):
    """Raised when subscription operations fail."""

    def __init__(
        self, message: str, subscription_id: Optional[str] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if subscription_id:
            context["subscription_id"] = subscription_id
        kwargs["context"] = context
        kwargs.setdefault("error_code", "AZURE_SUBSCRIPTION_ERROR")
        super().__init__(message, **kwargs)


class AzureResourceDiscoveryError(AzureError):
    """Raised when resource discovery fails."""

    def __init__(
        self,
        message: str,
        subscription_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if subscription_id:
            context["subscription_id"] = subscription_id
        if resource_type:
            context["resource_type"] = resource_type
        kwargs["context"] = context
        kwargs.setdefault("error_code", "AZURE_RESOURCE_DISCOVERY_FAILED")
        super().__init__(message, **kwargs)


# Neo4j-related exceptions
class Neo4jError(AzureTenantGrapherError):
    """Base class for Neo4j-related errors."""

    pass


class Neo4jConnectionError(Neo4jError):
    """Raised when Neo4j connection fails."""

    def __init__(self, message: str, uri: Optional[str] = None, **kwargs: Any) -> None:
        context = kwargs.get("context", {})
        if uri:
            # Don't include credentials in context
            safe_uri = uri.split("@")[-1] if "@" in uri else uri
            context["uri"] = safe_uri
        kwargs["context"] = context
        kwargs.setdefault("error_code", "NEO4J_CONNECTION_FAILED")
        kwargs.setdefault(
            "recovery_suggestion",
            "Check Neo4j connection settings and ensure the database is running",
        )
        super().__init__(message, **kwargs)


class Neo4jQueryError(Neo4jError):
    """Raised when Neo4j query execution fails."""

    def __init__(
        self,
        message: str,
        query: Optional[str] = None,
        parameters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if query:
            # Truncate long queries for readability
            context["query"] = query[:200] + "..." if len(query) > 200 else query
        if parameters:
            context["parameter_count"] = len(parameters)
        kwargs["context"] = context
        kwargs.setdefault("error_code", "NEO4J_QUERY_FAILED")
        super().__init__(message, **kwargs)


class Neo4jContainerError(Neo4jError):
    """Raised when Neo4j container operations fail."""

    def __init__(
        self, message: str, operation: Optional[str] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if operation:
            context["operation"] = operation
        kwargs["context"] = context
        kwargs.setdefault("error_code", "NEO4J_CONTAINER_ERROR")
        kwargs.setdefault(
            "recovery_suggestion",
            "Check Docker installation and container configuration",
        )
        super().__init__(message, **kwargs)


# LLM-related exceptions
class LLMError(AzureTenantGrapherError):
    """Base class for LLM-related errors."""

    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is invalid."""

    def __init__(self, message: str, **kwargs: Any) -> None:
        kwargs.setdefault("error_code", "LLM_CONFIG_ERROR")
        kwargs.setdefault(
            "recovery_suggestion", "Check Azure OpenAI configuration and API keys"
        )
        super().__init__(message, **kwargs)


class LLMGenerationError(LLMError):
    """Raised when LLM content generation fails."""

    def __init__(
        self,
        message: str,
        resource_id: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if resource_id:
            context["resource_id"] = resource_id
        if model:
            context["model"] = model
        kwargs["context"] = context
        kwargs.setdefault("error_code", "LLM_GENERATION_FAILED")
        super().__init__(message, **kwargs)


class LLMThrottlingError(LLMError):
    """Raised when LLM service throttling occurs."""

    def __init__(
        self, message: str, retry_after: Optional[int] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if retry_after:
            context["retry_after"] = retry_after
        kwargs["context"] = context
        kwargs.setdefault("error_code", "LLM_THROTTLED")
        kwargs.setdefault(
            "recovery_suggestion",
            f"Rate limited. Retry after {retry_after} seconds"
            if retry_after
            else "Rate limited. Retry later",
        )
        super().__init__(message, **kwargs)


# Configuration-related exceptions
class ConfigurationError(AzureTenantGrapherError):
    """Base class for configuration-related errors."""

    pass


class InvalidConfigurationError(ConfigurationError):
    """Raised when configuration validation fails."""

    def __init__(
        self, message: str, config_section: Optional[str] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if config_section:
            context["config_section"] = config_section
        kwargs["context"] = context
        kwargs.setdefault("error_code", "INVALID_CONFIG")
        kwargs.setdefault(
            "recovery_suggestion", "Check configuration file and environment variables"
        )
        super().__init__(message, **kwargs)


class MissingConfigurationError(ConfigurationError):
    """Raised when required configuration is missing."""

    def __init__(
        self, message: str, missing_keys: Optional[list[str]] = None, **kwargs: Any
    ) -> None:
        context = kwargs.get("context", {})
        if missing_keys:
            context["missing_keys"] = missing_keys
        kwargs["context"] = context
        kwargs.setdefault("error_code", "MISSING_CONFIG")
        kwargs.setdefault(
            "recovery_suggestion",
            f"Set required configuration: {', '.join(missing_keys)}"
            if missing_keys
            else "Set required configuration",
        )
        super().__init__(message, **kwargs)


# Processing-related exceptions
class ProcessingError(AzureTenantGrapherError):
    """Base class for resource processing errors."""

    pass


class ResourceProcessingError(ProcessingError):
    """Raised when resource processing fails."""

    def __init__(
        self,
        message: str,
        resource_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if resource_id:
            context["resource_id"] = resource_id
        if resource_type:
            context["resource_type"] = resource_type
        kwargs["context"] = context
        kwargs.setdefault("error_code", "RESOURCE_PROCESSING_FAILED")
        super().__init__(message, **kwargs)


class BatchProcessingError(ProcessingError):
    """Raised when batch processing fails."""

    def __init__(
        self,
        message: str,
        batch_size: Optional[int] = None,
        failed_count: Optional[int] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if batch_size:
            context["batch_size"] = batch_size
        if failed_count:
            context["failed_count"] = failed_count
        kwargs["context"] = context
        kwargs.setdefault("error_code", "BATCH_PROCESSING_FAILED")
        super().__init__(message, **kwargs)


# Validation-related exceptions
class ValidationError(AzureTenantGrapherError):
    """Base class for validation errors."""

    pass


class ResourceValidationError(ValidationError):
    """Raised when resource validation fails."""

    def __init__(
        self,
        message: str,
        resource_id: Optional[str] = None,
        validation_errors: Optional[list[str]] = None,
        **kwargs: Any,
    ) -> None:
        context = kwargs.get("context", {})
        if resource_id:
            context["resource_id"] = resource_id
        if validation_errors:
            context["validation_errors"] = validation_errors
        kwargs["context"] = context
        kwargs.setdefault("error_code", "RESOURCE_VALIDATION_FAILED")
        super().__init__(message, **kwargs)


# Utility functions for exception handling
def wrap_azure_exception(
    exc: Exception, context: Optional[Dict[str, Any]] = None
) -> AzureError:
    """
    Wrap a generic Azure SDK exception in our custom exception hierarchy.

    Args:
        exc: The original exception
        context: Optional context information

    Returns:
        AzureError: Wrapped exception with enhanced context
    """
    error_message = str(exc)

    # Check for common Azure error patterns
    if (
        "authentication" in error_message.lower()
        or "unauthorized" in error_message.lower()
    ):
        return AzureAuthenticationError(
            f"Azure authentication failed: {error_message}", context=context, cause=exc
        )
    elif "subscription" in error_message.lower():
        return AzureSubscriptionError(
            f"Azure subscription error: {error_message}", context=context, cause=exc
        )
    else:
        return AzureError(
            f"Azure operation failed: {error_message}", context=context, cause=exc
        )


def wrap_neo4j_exception(
    exc: Exception, context: Optional[Dict[str, Any]] = None
) -> Neo4jError:
    """
    Wrap a generic Neo4j exception in our custom exception hierarchy.

    Args:
        exc: The original exception
        context: Optional context information

    Returns:
        Neo4jError: Wrapped exception with enhanced context
    """
    error_message = str(exc)

    # Check for common Neo4j error patterns
    if "connection" in error_message.lower() or "unavailable" in error_message.lower():
        return Neo4jConnectionError(
            f"Neo4j connection failed: {error_message}", context=context, cause=exc
        )
    elif "query" in error_message.lower() or "syntax" in error_message.lower():
        return Neo4jQueryError(
            f"Neo4j query failed: {error_message}", context=context, cause=exc
        )
    else:
        return Neo4jError(
            f"Neo4j operation failed: {error_message}", context=context, cause=exc
        )
