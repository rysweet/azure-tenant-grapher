"""
Configuration management for scale operations.

Provides type-safe configuration loading and validation with support
for multiple configuration sources and priority-based merging.
"""

from .loader import ConfigError, ConfigLoader, create_default_config, load_config
from .models import (
    ForestFireConfig,
    MHRWConfig,
    OutputFormat,
    PerformanceConfig,
    RandomEdgeConfig,
    RandomNodeConfig,
    RandomStrategyConfig,
    ScaleConfig,
    ScaleDownAlgorithm,
    ScaleDownConfig,
    ScaleStrategy,
    ScaleUpConfig,
    ScenarioStrategyConfig,
    TemplateStrategyConfig,
    TenantOverrides,
    ValidationConfig,
)

__all__ = [
    "ConfigError",
    # Loader
    "ConfigLoader",
    # Algorithm configs
    "ForestFireConfig",
    "MHRWConfig",
    "OutputFormat",
    "PerformanceConfig",
    "RandomEdgeConfig",
    "RandomNodeConfig",
    "RandomStrategyConfig",
    # Models
    "ScaleConfig",
    "ScaleDownAlgorithm",
    "ScaleDownConfig",
    # Enums
    "ScaleStrategy",
    "ScaleUpConfig",
    "ScenarioStrategyConfig",
    # Strategy configs
    "TemplateStrategyConfig",
    "TenantOverrides",
    "ValidationConfig",
    "create_default_config",
    "load_config",
]
