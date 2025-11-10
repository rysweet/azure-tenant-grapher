"""
Configuration loader for scale operations.

Handles loading from multiple sources with proper priority:
CLI Args > Environment Variables > Config File > Defaults
"""

import os
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import ValidationError

from .models import ScaleConfig


class ConfigError(Exception):
    """Configuration loading or validation error."""

    pass


class ConfigLoader:
    """
    Loads and merges configuration from multiple sources.

    Priority order (highest to lowest):
    1. CLI arguments (passed directly to methods)
    2. Environment variables (ATG_SCALE_*)
    3. Configuration file
    4. Default values
    """

    DEFAULT_CONFIG_DIR = Path.home() / ".config" / "azure-tenant-grapher"
    DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "scale-config.yaml"
    ENV_PREFIX = "ATG_SCALE_"

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to configuration file. If None, uses default location.
        """
        self.config_path = config_path or self._get_config_path_from_env()

    @classmethod
    def _get_config_path_from_env(cls) -> Path:
        """Get configuration path from environment variable or default."""
        env_path = os.environ.get("SCALE_CONFIG_PATH")
        if env_path:
            return Path(env_path).expanduser()
        return cls.DEFAULT_CONFIG_FILE

    def load(self) -> ScaleConfig:
        """
        Load configuration from all sources and merge.

        Returns:
            Validated ScaleConfig object

        Raises:
            ConfigError: If configuration is invalid
        """
        try:
            # Start with defaults (empty dict - pydantic provides defaults)
            config_dict: dict[str, Any] = {}

            # Load from file if it exists
            if self.config_path.exists():
                file_config = self._load_file(self.config_path)
                config_dict = self._deep_merge(config_dict, file_config)

            # Load from environment variables
            env_config = self._load_from_env()
            config_dict = self._deep_merge(config_dict, env_config)

            # Validate and return
            return ScaleConfig.model_validate(config_dict)

        except ValidationError as e:
            raise ConfigError(f"Configuration validation failed: {e}") from e
        except Exception as e:
            raise ConfigError(f"Failed to load configuration: {e}") from e

    def _load_file(self, path: Path) -> dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            path: Path to YAML configuration file

        Returns:
            Configuration dictionary

        Raises:
            ConfigError: If file cannot be read or parsed
        """
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                return data or {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}") from e
        except OSError as e:
            raise ConfigError(f"Cannot read config file {path}: {e}") from e

    def _load_from_env(self) -> dict[str, Any]:
        """
        Load configuration from environment variables.

        Environment variable format:
        - ATG_SCALE_DEFAULT_TENANT_ID
        - ATG_SCALE_SCALE_UP__DEFAULT_STRATEGY
        - ATG_SCALE_SCALE_DOWN__DEFAULT_ALGORITHM
        - ATG_SCALE_PERFORMANCE__BATCH_SIZE

        Double underscore (__) separates nested keys.

        Returns:
            Configuration dictionary
        """
        config: dict[str, Any] = {}

        for key, value in os.environ.items():
            if not key.startswith(self.ENV_PREFIX):
                continue

            # Remove prefix and convert to lowercase
            config_key = key[len(self.ENV_PREFIX) :].lower()

            # Split nested keys (double underscore)
            parts = config_key.split("__")

            # Build nested dictionary
            current = config
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]

            # Set the value (attempt type conversion)
            current[parts[-1]] = self._convert_env_value(value)

        return config

    def _convert_env_value(self, value: str) -> Any:
        """
        Convert environment variable string to appropriate type.

        Args:
            value: Environment variable value as string

        Returns:
            Converted value (bool, int, float, or str)
        """
        # Boolean conversion
        if value.lower() in ("true", "yes", "1"):
            return True
        if value.lower() in ("false", "no", "0"):
            return False

        # Numeric conversion
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Return as string
        return value

    def _deep_merge(
        self, base: dict[str, Any], update: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Deep merge two dictionaries.

        Args:
            base: Base dictionary
            update: Dictionary with updates

        Returns:
            Merged dictionary (base is not modified)
        """
        result = base.copy()

        for key, value in update.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def merge_cli_args(
        self,
        config: ScaleConfig,
        cli_args: dict[str, Any],
    ) -> ScaleConfig:
        """
        Merge CLI arguments into configuration.

        CLI arguments have highest priority and override all other sources.

        Args:
            config: Base configuration
            cli_args: CLI arguments to merge (non-None values only)

        Returns:
            New ScaleConfig with CLI args applied
        """
        # Recursively filter out None values from CLI args
        filtered_args = self._filter_none_values(cli_args)

        if not filtered_args:
            return config

        # Convert to nested dict structure
        config_dict = config.model_dump()
        config_dict = self._deep_merge(config_dict, filtered_args)

        return ScaleConfig.model_validate(config_dict)

    def _filter_none_values(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Recursively filter out None values from a dictionary.

        Args:
            data: Dictionary to filter

        Returns:
            New dictionary without None values
        """
        result = {}
        for key, value in data.items():
            if value is None:
                continue
            elif isinstance(value, dict):
                filtered = self._filter_none_values(value)
                if filtered:  # Only include non-empty dicts
                    result[key] = filtered
            else:
                result[key] = value
        return result

    def create_default_config(self, force: bool = False) -> Path:
        """
        Create default configuration file with comments.

        Args:
            force: Overwrite existing file if True

        Returns:
            Path to created configuration file

        Raises:
            ConfigError: If file exists and force=False
        """
        if self.config_path.exists() and not force:
            raise ConfigError(
                f"Configuration file already exists at {self.config_path}. "
                "Use force=True to overwrite."
            )

        # Create directory if needed
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        # Write default configuration with comments
        default_config = self._get_default_config_yaml()

        try:
            with open(self.config_path, "w") as f:
                f.write(default_config)
        except OSError as e:
            raise ConfigError(
                f"Cannot write config file {self.config_path}: {e}"
            ) from e

        return self.config_path

    def _get_default_config_yaml(self) -> str:
        """
        Get default configuration as commented YAML.

        Returns:
            YAML string with inline documentation
        """
        return """\
# Azure Tenant Grapher - Scale Operations Configuration
# ======================================================

# Default tenant ID to use when not specified via CLI
# default_tenant_id: "00000000-0000-0000-0000-000000000000"

# Scale-Up Operation Settings
scale_up:
  # Default strategy: template, scenario, or random
  default_strategy: template

  # Default scale factor (multiplier for resource counts)
  default_scale_factor: 2.0

  # Number of resources to process per batch
  batch_size: 500

  # Template Strategy Settings
  template:
    # Maintain relative proportions of resource types
    preserve_proportions: true

    # Amount of random variation to introduce (0.0-1.0)
    variation_percentage: 0.1

  # Scenario Strategy Settings
  scenario:
    # Default scenario template to use
    default_scenario: "hub-spoke"

    # Path to custom scenario library (optional)
    # scenario_library_path: "/path/to/scenarios"

  # Random Strategy Settings
  random:
    # Default target resource count for random generation
    default_target_count: 1000

    # Random seed for reproducible generation (optional)
    # seed: 42

# Scale-Down Operation Settings
scale_down:
  # Default algorithm: forest-fire, mhrw, random-node, or random-edge
  default_algorithm: forest-fire

  # Default target size as fraction of original (0.0-1.0)
  default_target_size: 0.1

  # Output format for scale-down spec: yaml or json
  output_format: yaml

  # Forest Fire Algorithm Settings
  forest_fire:
    # Probability of 'burning' (selecting) a neighbor node (0.0-1.0)
    burning_probability: 0.4

    # Random seed for reproducible sampling
    seed: 42

    # Whether to treat graph as directed
    directed: false

  # Metropolis-Hastings Random Walk Settings
  mhrw:
    # Bias parameter (α=1 for unbiased walk)
    alpha: 1.0

    # Random seed for reproducible sampling
    seed: 42

    # Maximum walk iterations
    max_iterations: 1000000

  # Random Node Sampling Settings
  random_node:
    # Random seed for reproducible sampling
    seed: 42

    # Attempt to preserve graph connectivity
    preserve_connectivity: false

  # Random Edge Sampling Settings
  random_edge:
    # Random seed for reproducible sampling
    seed: 42

# Performance and Resource Limits
performance:
  # Default batch size for operations
  batch_size: 500

  # Memory limit in megabytes
  memory_limit_mb: 2048

  # Operation timeout in seconds
  timeout_seconds: 300

  # Maximum number of worker threads/processes (1-32)
  max_workers: 4

# Validation Settings
validation:
  # Validate configuration before operation
  pre_operation: true

  # Validate results after operation
  post_operation: true

  # Fail on validation warnings (not just errors)
  strict_mode: true

# Tenant-Specific Overrides
# tenant_overrides:
#   - tenant_id: "tenant-1-id"
#     scale_up:
#       default_scale_factor: 3.0
#     performance:
#       batch_size: 1000
#
#   - tenant_id: "tenant-2-id"
#     scale_down:
#       default_algorithm: mhrw
#       default_target_size: 0.2
"""


def load_config(
    config_path: Optional[Path] = None,
    cli_args: Optional[dict[str, Any]] = None,
) -> ScaleConfig:
    """
    Convenience function to load configuration.

    Args:
        config_path: Path to configuration file
        cli_args: CLI arguments to merge (highest priority)

    Returns:
        Validated ScaleConfig object

    Raises:
        ConfigError: If configuration is invalid
    """
    loader = ConfigLoader(config_path)
    config = loader.load()

    if cli_args:
        config = loader.merge_cli_args(config, cli_args)

    return config


def create_default_config(
    config_path: Optional[Path] = None,
    force: bool = False,
) -> Path:
    """
    Create default configuration file.

    Args:
        config_path: Path to configuration file
        force: Overwrite existing file if True

    Returns:
        Path to created configuration file

    Raises:
        ConfigError: If file exists and force=False
    """
    loader = ConfigLoader(config_path)
    return loader.create_default_config(force=force)
