#!/usr/bin/env python3
"""
Config Manager Module

Purpose: Handle environment-specific configurations and validation
Contract: Load, validate, and provide configuration access
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing"""
    pass


class ConfigManager:
    """
    Manages configuration loading, validation, and access.

    Public Interface:
        - load_config(path): Load configuration from YAML file
        - get(key, default): Get configuration value with dot notation
        - validate(): Validate required configuration exists
        - expand_env_vars(): Expand environment variables in config
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize configuration manager."""
        self.config_path = Path(config_path) if config_path else Path("config.yaml")
        self.config: Dict[str, Any] = {}
        self._required_keys = [
            "app.url",
            "test.browser",
            "test.viewport",
            "logging.level"
        ]

    def load_config(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Load configuration from YAML file.

        Args:
            path: Optional path to config file

        Returns:
            Loaded configuration dictionary

        Raises:
            ConfigurationError: If config file not found or invalid
        """
        config_path = Path(path) if path else self.config_path

        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {config_path}\n"
                f"Please create a config.yaml file or specify --config path"
            )

        try:
            with open(config_path, 'r') as f:
                self.config = yaml.safe_load(f) or {}

            # Expand environment variables
            self.config = self._expand_env_vars(self.config)

            # Validate configuration
            self.validate()

            logger.info(f"Configuration loaded from {config_path}")
            return self.config

        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in configuration file: {e}\n"
                f"Please check the syntax of {config_path}"
            )
        except Exception as e:
            raise ConfigurationError(f"Failed to load configuration: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "app.url" or "test.browser")
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config

        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        Set configuration value using dot notation.

        Args:
            key: Configuration key (e.g., "app.url")
            value: Value to set
        """
        keys = key.split('.')
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def validate(self) -> None:
        """
        Validate required configuration exists.

        Raises:
            ConfigurationError: If required configuration is missing
        """
        missing_keys = []

        for key in self._required_keys:
            if self.get(key) is None:
                missing_keys.append(key)

        if missing_keys:
            raise ConfigurationError(
                f"Missing required configuration keys:\n"
                + "\n".join(f"  - {key}" for key in missing_keys) +
                f"\n\nPlease check your configuration file"
            )

        # Validate specific values
        browser = self.get("test.browser")
        if browser not in ["chromium", "firefox", "webkit"]:
            raise ConfigurationError(
                f"Invalid browser '{browser}'. "
                f"Must be one of: chromium, firefox, webkit"
            )

        log_level = self.get("logging.level", "info").upper()
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            raise ConfigurationError(
                f"Invalid log level '{log_level}'. "
                f"Must be one of: debug, info, warning, error"
            )

    def _expand_env_vars(self, obj: Any) -> Any:
        """
        Recursively expand environment variables in configuration.

        Args:
            obj: Configuration object to process

        Returns:
            Object with environment variables expanded
        """
        if isinstance(obj, dict):
            return {k: self._expand_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._expand_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            var_name = obj[2:-1]
            value = os.environ.get(var_name)
            if value is None:
                logger.warning(f"Environment variable {var_name} not set")
            return value
        return obj

    def get_app_config(self) -> Dict[str, Any]:
        """Get application-specific configuration."""
        return self.get("app", {})

    def get_test_config(self) -> Dict[str, Any]:
        """Get test-specific configuration."""
        return self.get("test", {})

    def get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        return self.get("logging", {})

    def is_headless(self) -> bool:
        """Check if running in headless mode."""
        return self.get("test.headless", False)

    def get_browser(self) -> str:
        """Get configured browser type."""
        return self.get("test.browser", "chromium")

    def get_app_url(self) -> str:
        """Get application URL."""
        url = self.get("app.url", "http://localhost:3000")
        if not url:
            raise ConfigurationError("Application URL not configured")
        return url
