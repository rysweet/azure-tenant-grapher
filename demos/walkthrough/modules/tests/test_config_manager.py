#!/usr/bin/env python3
"""Tests for ConfigManager module"""

import os
import sys
import tempfile
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from modules.config_manager import ConfigManager, ConfigurationError


class TestConfigManager:
    """Test suite for ConfigManager"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "test_config.yaml"

    def teardown_method(self):
        """Cleanup test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_config(self, content: dict):
        """Helper to create config file"""
        with open(self.config_file, "w") as f:
            yaml.safe_dump(content, f)

    def test_load_valid_config(self):
        """Test loading valid configuration"""
        config_data = {
            "app": {"url": "http://localhost:3000"},
            "test": {
                "browser": "chromium",
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "info"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))
        config = manager.load_config()

        assert config["app"]["url"] == "http://localhost:3000"
        assert config["test"]["browser"] == "chromium"

    def test_config_not_found(self):
        """Test handling of missing config file"""
        manager = ConfigManager("nonexistent.yaml")

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        assert "not found" in str(exc_info.value)

    def test_invalid_yaml(self):
        """Test handling of invalid YAML"""
        with open(self.config_file, "w") as f:
            f.write("invalid: yaml: content: [")

        manager = ConfigManager(str(self.config_file))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        assert "Invalid YAML" in str(exc_info.value)

    def test_environment_variable_expansion(self):
        """Test environment variable expansion"""
        os.environ["TEST_URL"] = "http://test.example.com"

        config_data = {
            "app": {"url": "${TEST_URL}"},
            "test": {
                "browser": "chromium",
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "info"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))
        config = manager.load_config()

        assert config["app"]["url"] == "http://test.example.com"

    def test_dot_notation_access(self):
        """Test accessing config with dot notation"""
        config_data = {
            "app": {"url": "http://localhost:3000", "nested": {"value": 42}},
            "test": {
                "browser": "chromium",
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "info"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))
        manager.load_config()

        assert manager.get("app.url") == "http://localhost:3000"
        assert manager.get("app.nested.value") == 42
        assert manager.get("nonexistent.key", "default") == "default"

    def test_validation_missing_required(self):
        """Test validation of missing required fields"""
        config_data = {
            "app": {},  # Missing url
            "test": {"viewport": {"width": 1920, "height": 1080}},  # Missing browser
            "logging": {},  # Missing level
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        assert "Missing required configuration keys" in str(exc_info.value)

    def test_validation_invalid_browser(self):
        """Test validation of invalid browser value"""
        config_data = {
            "app": {"url": "http://localhost:3000"},
            "test": {
                "browser": "invalid_browser",
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "info"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))

        with pytest.raises(ConfigurationError) as exc_info:
            manager.load_config()

        assert "Invalid browser" in str(exc_info.value)

    def test_set_config_value(self):
        """Test setting configuration values"""
        config_data = {
            "app": {"url": "http://localhost:3000"},
            "test": {
                "browser": "chromium",
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "info"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))
        manager.load_config()

        manager.set("app.new_key", "new_value")
        assert manager.get("app.new_key") == "new_value"

        manager.set("test.headless", True)
        assert manager.is_headless() == True

    def test_helper_methods(self):
        """Test helper methods"""
        config_data = {
            "app": {"url": "http://example.com:8080"},
            "test": {
                "browser": "firefox",
                "headless": True,
                "viewport": {"width": 1920, "height": 1080},
            },
            "logging": {"level": "debug"},
        }
        self.create_config(config_data)

        manager = ConfigManager(str(self.config_file))
        manager.load_config()

        assert manager.get_app_url() == "http://example.com:8080"
        assert manager.get_browser() == "firefox"
        assert manager.is_headless() == True
        assert manager.get_app_config()["url"] == "http://example.com:8080"
