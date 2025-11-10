"""
Unit tests for configuration system.

Tests configuration loading, validation, merging, and error handling.
"""

import os
from pathlib import Path
from typing import Any

import pytest
import yaml

from src.config import (
    ConfigError,
    ConfigLoader,
    ScaleConfig,
    ScaleDownAlgorithm,
    ScaleStrategy,
    create_default_config,
    load_config,
)


class TestScaleConfigModel:
    """Test ScaleConfig pydantic model validation."""

    def test_default_config(self):
        """Test creating config with all defaults."""
        config = ScaleConfig()

        assert config.default_tenant_id is None
        assert config.scale_up.default_strategy == ScaleStrategy.TEMPLATE
        assert config.scale_up.default_scale_factor == 2.0
        assert config.scale_down.default_algorithm == ScaleDownAlgorithm.FOREST_FIRE
        assert config.scale_down.default_target_size == 0.1
        assert config.performance.batch_size == 500
        assert config.validation.strict_mode is True

    def test_partial_config(self):
        """Test creating config with partial settings."""
        config = ScaleConfig(
            scale_up={"default_scale_factor": 3.0},
            scale_down={"default_algorithm": "mhrw"},
        )

        assert config.scale_up.default_scale_factor == 3.0
        assert config.scale_down.default_algorithm == ScaleDownAlgorithm.MHRW
        # Other fields use defaults
        assert config.scale_up.default_strategy == ScaleStrategy.TEMPLATE

    def test_invalid_scale_factor(self):
        """Test scale factor validation."""
        with pytest.raises(ValueError, match="greater than 0"):
            ScaleConfig(scale_up={"default_scale_factor": 0.0})

        with pytest.raises(ValueError, match="greater than 0"):
            ScaleConfig(scale_up={"default_scale_factor": -1.0})

        with pytest.raises(ValueError, match="cannot exceed 1000"):
            ScaleConfig(scale_up={"default_scale_factor": 1001.0})

    def test_invalid_target_size(self):
        """Test target size validation."""
        with pytest.raises(ValueError, match="greater than 0"):
            ScaleConfig(scale_down={"default_target_size": 0.0})

        with pytest.raises(ValueError, match="less than or equal to 1"):
            ScaleConfig(scale_down={"default_target_size": 1.5})

    def test_invalid_burning_probability(self):
        """Test burning probability validation."""
        with pytest.raises(ValueError, match="less than or equal to 1"):
            ScaleConfig(
                scale_down={
                    "forest_fire": {"burning_probability": 1.5},
                }
            )

    def test_unknown_fields_rejected(self):
        """Test that unknown fields are rejected (extra=forbid)."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            ScaleConfig(unknown_field="value")

    def test_tenant_overrides_unique(self):
        """Test tenant override IDs must be unique."""
        with pytest.raises(ValueError, match="Duplicate tenant IDs"):
            ScaleConfig(
                tenant_overrides=[
                    {"tenant_id": "tenant-1"},
                    {"tenant_id": "tenant-1"},
                ]
            )

    def test_get_tenant_config(self):
        """Test getting tenant-specific configuration."""
        config = ScaleConfig(
            scale_up={"default_scale_factor": 2.0},
            tenant_overrides=[
                {
                    "tenant_id": "tenant-1",
                    "scale_up": {"default_scale_factor": 3.0},
                },
            ],
        )

        # Base config for non-overridden tenant
        base_config = config.get_tenant_config("tenant-2")
        assert base_config.scale_up.default_scale_factor == 2.0

        # Overridden config
        tenant_config = config.get_tenant_config("tenant-1")
        assert tenant_config.scale_up.default_scale_factor == 3.0


class TestConfigLoader:
    """Test ConfigLoader class."""

    @pytest.fixture
    def temp_config_dir(self, tmp_path: Path) -> Path:
        """Create temporary config directory."""
        config_dir = tmp_path / ".config" / "azure-tenant-grapher"
        config_dir.mkdir(parents=True)
        return config_dir

    @pytest.fixture
    def temp_config_file(self, temp_config_dir: Path) -> Path:
        """Create temporary config file."""
        return temp_config_dir / "scale-config.yaml"

    def test_load_nonexistent_file(self, temp_config_file: Path):
        """Test loading when file doesn't exist returns defaults."""
        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        assert isinstance(config, ScaleConfig)
        assert config.scale_up.default_scale_factor == 2.0

    def test_load_valid_file(self, temp_config_file: Path):
        """Test loading valid YAML file."""
        config_data = {
            "scale_up": {
                "default_scale_factor": 3.0,
                "default_strategy": "scenario",
            },
            "scale_down": {
                "default_algorithm": "mhrw",
                "default_target_size": 0.2,
            },
        }

        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        assert config.scale_up.default_scale_factor == 3.0
        assert config.scale_up.default_strategy == ScaleStrategy.SCENARIO
        assert config.scale_down.default_algorithm == ScaleDownAlgorithm.MHRW
        assert config.scale_down.default_target_size == 0.2

    def test_load_invalid_yaml(self, temp_config_file: Path):
        """Test loading invalid YAML raises error."""
        with open(temp_config_file, "w") as f:
            f.write("invalid: yaml: content:\n  - bad")

        loader = ConfigLoader(temp_config_file)

        with pytest.raises(ConfigError, match="Invalid YAML"):
            loader.load()

    def test_load_invalid_schema(self, temp_config_file: Path):
        """Test loading invalid schema raises error."""
        config_data = {
            "scale_up": {
                "default_scale_factor": -1.0,  # Invalid
            },
        }

        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        loader = ConfigLoader(temp_config_file)

        with pytest.raises(ConfigError, match="validation failed"):
            loader.load()

    def test_load_from_env(self, temp_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """Test loading from environment variables."""
        # Set environment variables
        monkeypatch.setenv("ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR", "3.5")
        monkeypatch.setenv("ATG_SCALE_SCALE_DOWN__DEFAULT_ALGORITHM", "mhrw")
        monkeypatch.setenv("ATG_SCALE_PERFORMANCE__BATCH_SIZE", "1000")
        monkeypatch.setenv("ATG_SCALE_VALIDATION__STRICT_MODE", "false")

        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        assert config.scale_up.default_scale_factor == 3.5
        assert config.scale_down.default_algorithm == ScaleDownAlgorithm.MHRW
        assert config.performance.batch_size == 1000
        assert config.validation.strict_mode is False

    def test_env_override_file(self, temp_config_file: Path, monkeypatch: pytest.MonkeyPatch):
        """Test environment variables override file config."""
        # Write file config
        config_data = {
            "scale_up": {
                "default_scale_factor": 2.0,
            },
        }
        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        # Set env override
        monkeypatch.setenv("ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR", "4.0")

        loader = ConfigLoader(temp_config_file)
        config = loader.load()

        # Env should win
        assert config.scale_up.default_scale_factor == 4.0

    def test_merge_cli_args(self, temp_config_file: Path):
        """Test merging CLI arguments."""
        loader = ConfigLoader(temp_config_file)
        base_config = loader.load()

        cli_args = {
            "scale_up": {
                "default_scale_factor": 5.0,
            },
            "scale_down": {
                "default_algorithm": "random-node",
            },
        }

        merged = loader.merge_cli_args(base_config, cli_args)

        assert merged.scale_up.default_scale_factor == 5.0
        assert merged.scale_down.default_algorithm == ScaleDownAlgorithm.RANDOM_NODE

    def test_cli_args_ignore_none(self, temp_config_file: Path):
        """Test CLI args with None values are ignored."""
        loader = ConfigLoader(temp_config_file)
        base_config = ScaleConfig(scale_up={"default_scale_factor": 2.0})

        cli_args = {
            "scale_up": {
                "default_scale_factor": None,  # Should be ignored
            },
        }

        merged = loader.merge_cli_args(base_config, cli_args)

        # Should keep original value
        assert merged.scale_up.default_scale_factor == 2.0

    def test_create_default_config(self, temp_config_file: Path):
        """Test creating default configuration file."""
        loader = ConfigLoader(temp_config_file)
        created_path = loader.create_default_config()

        assert created_path == temp_config_file
        assert temp_config_file.exists()

        # Verify it's valid YAML
        with open(temp_config_file, "r") as f:
            data = yaml.safe_load(f)

        assert isinstance(data, dict)

    def test_create_default_config_exists(self, temp_config_file: Path):
        """Test creating config when file exists."""
        # Create existing file
        temp_config_file.write_text("existing: content")

        loader = ConfigLoader(temp_config_file)

        # Should fail without force
        with pytest.raises(ConfigError, match="already exists"):
            loader.create_default_config(force=False)

        # Should succeed with force
        created_path = loader.create_default_config(force=True)
        assert created_path == temp_config_file

    def test_convert_env_value(self):
        """Test environment value type conversion."""
        loader = ConfigLoader()

        # Boolean conversion
        assert loader._convert_env_value("true") is True
        assert loader._convert_env_value("True") is True
        assert loader._convert_env_value("yes") is True
        assert loader._convert_env_value("1") is True
        assert loader._convert_env_value("false") is False
        assert loader._convert_env_value("False") is False
        assert loader._convert_env_value("no") is False
        assert loader._convert_env_value("0") is False

        # Numeric conversion
        assert loader._convert_env_value("42") == 42
        assert loader._convert_env_value("3.14") == 3.14

        # String fallback
        assert loader._convert_env_value("hello") == "hello"


class TestConvenienceFunctions:
    """Test convenience functions."""

    @pytest.fixture
    def temp_config_file(self, tmp_path: Path) -> Path:
        """Create temporary config file."""
        config_dir = tmp_path / ".config" / "azure-tenant-grapher"
        config_dir.mkdir(parents=True)
        return config_dir / "scale-config.yaml"

    def test_load_config_default(self, temp_config_file: Path):
        """Test load_config convenience function."""
        config_data = {
            "scale_up": {
                "default_scale_factor": 3.0,
            },
        }

        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_path=temp_config_file)

        assert config.scale_up.default_scale_factor == 3.0

    def test_load_config_with_cli_args(self, temp_config_file: Path):
        """Test load_config with CLI args."""
        config = load_config(
            config_path=temp_config_file,
            cli_args={
                "scale_up": {
                    "default_scale_factor": 4.0,
                },
            },
        )

        assert config.scale_up.default_scale_factor == 4.0

    def test_create_default_config_function(self, temp_config_file: Path):
        """Test create_default_config convenience function."""
        path = create_default_config(config_path=temp_config_file)

        assert path == temp_config_file
        assert temp_config_file.exists()


class TestPriorityOrder:
    """Test configuration priority order: CLI > Env > File > Defaults."""

    @pytest.fixture
    def temp_config_file(self, tmp_path: Path) -> Path:
        """Create temporary config file."""
        config_dir = tmp_path / ".config" / "azure-tenant-grapher"
        config_dir.mkdir(parents=True)
        return config_dir / "scale-config.yaml"

    def test_priority_order(
        self,
        temp_config_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test full priority chain."""
        # 1. Default value is 2.0

        # 2. File config sets to 3.0
        config_data = {
            "scale_up": {
                "default_scale_factor": 3.0,
            },
        }
        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        # 3. Env var sets to 4.0
        monkeypatch.setenv("ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR", "4.0")

        # 4. CLI arg sets to 5.0
        config = load_config(
            config_path=temp_config_file,
            cli_args={
                "scale_up": {
                    "default_scale_factor": 5.0,
                },
            },
        )

        # CLI should win (highest priority)
        assert config.scale_up.default_scale_factor == 5.0

    def test_priority_without_cli(
        self,
        temp_config_file: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """Test priority without CLI args."""
        # File config
        config_data = {
            "scale_up": {
                "default_scale_factor": 3.0,
            },
        }
        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        # Env var
        monkeypatch.setenv("ATG_SCALE_SCALE_UP__DEFAULT_SCALE_FACTOR", "4.0")

        config = load_config(config_path=temp_config_file)

        # Env should win
        assert config.scale_up.default_scale_factor == 4.0

    def test_priority_file_only(self, temp_config_file: Path):
        """Test priority with file only."""
        config_data = {
            "scale_up": {
                "default_scale_factor": 3.0,
            },
        }
        with open(temp_config_file, "w") as f:
            yaml.dump(config_data, f)

        config = load_config(config_path=temp_config_file)

        # File should win
        assert config.scale_up.default_scale_factor == 3.0

    def test_priority_defaults_only(self, temp_config_file: Path):
        """Test priority with defaults only."""
        config = load_config(config_path=temp_config_file)

        # Defaults should be used
        assert config.scale_up.default_scale_factor == 2.0
