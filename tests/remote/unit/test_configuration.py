"""
Unit tests for configuration management.

Tests `.env` file parsing, environment selection, validation, and configuration
loading for both client and server components.

Philosophy:
- Test configuration logic in isolation
- Mock file I/O and environment variables
- Fast execution (< 100ms per test)
- Follow simplified architecture from Specs/SIMPLIFIED_ARCHITECTURE.md
"""

import os
from unittest.mock import mock_open, patch

import pytest

# =============================================================================
# Client Configuration Tests (Architecture Section 3.3)
# =============================================================================


def test_client_config_loads_from_env():
    """Test that ATGClientConfig loads from environment variables."""
    from src.remote.client.config import ATGClientConfig

    with patch.dict(
        os.environ,
        {
            "ATG_REMOTE_MODE": "true",
            "ATG_SERVICE_URL": "https://atg-dev.example.com",
            "ATG_API_KEY": f"atg_dev_{'a' * 64}",
            "ATG_REQUEST_TIMEOUT": "1800",
        },
    ):
        # This class doesn't exist yet - will fail!
        config = ATGClientConfig.from_env()

    assert config.remote_mode is True
    assert config.service_url == "https://atg-dev.example.com"
    assert config.api_key == f"atg_dev_{'a' * 64}"
    assert config.request_timeout == 1800


def test_client_config_defaults_to_local_mode():
    """Test that client defaults to local mode when ATG_REMOTE_MODE not set."""
    from src.remote.client.config import ATGClientConfig

    with patch.dict(os.environ, {}, clear=True):
        config = ATGClientConfig.from_env()

    assert config.remote_mode is False
    assert config.service_url is None
    assert config.api_key is None


def test_client_config_parses_remote_mode_boolean():
    """Test that ATG_REMOTE_MODE accepts various boolean formats."""
    from src.remote.client.config import ATGClientConfig

    test_cases = [
        ("true", True),
        ("True", True),
        ("TRUE", True),
        ("1", True),
        ("false", False),
        ("False", False),
        ("FALSE", False),
        ("0", False),
        ("", False),
    ]

    for env_value, expected in test_cases:
        with patch.dict(os.environ, {"ATG_REMOTE_MODE": env_value}, clear=True):
            config = ATGClientConfig.from_env(validate=False)
            assert config.remote_mode == expected


def test_client_config_validates_service_url():
    """Test that client config validates service URL format."""
    from src.remote.client.config import ATGClientConfig, ConfigurationError

    with patch.dict(
        os.environ,
        {
            "ATG_REMOTE_MODE": "true",
            "ATG_SERVICE_URL": "invalid-url",  # Missing https://
            "ATG_API_KEY": f"atg_dev_{'a' * 64}",
        },
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            ATGClientConfig.from_env()

    assert "invalid url" in str(exc_info.value).lower()


def test_client_config_requires_api_key_in_remote_mode():
    """Test that client config requires API key when remote mode enabled."""
    from src.remote.client.config import ATGClientConfig, ConfigurationError

    with patch.dict(
        os.environ,
        {
            "ATG_REMOTE_MODE": "true",
            "ATG_SERVICE_URL": "https://atg-dev.example.com",
            # ATG_API_KEY missing
        },
        clear=True,
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            ATGClientConfig.from_env()

    assert "api key" in str(exc_info.value).lower()


def test_client_config_supports_custom_timeout():
    """Test that client config supports custom request timeout."""
    from src.remote.client.config import ATGClientConfig

    with patch.dict(
        os.environ,
        {
            "ATG_REMOTE_MODE": "true",
            "ATG_SERVICE_URL": "https://atg-dev.example.com",
            "ATG_API_KEY": f"atg_dev_{'a' * 64}",
            "ATG_REQUEST_TIMEOUT": "7200",  # 2 hours
        },
    ):
        config = ATGClientConfig.from_env()

    assert config.request_timeout == 7200


def test_client_config_default_timeout_is_60_minutes():
    """Test that client config defaults to 60-minute timeout (3600 seconds)."""
    from src.remote.client.config import ATGClientConfig

    with patch.dict(
        os.environ,
        {
            "ATG_REMOTE_MODE": "true",
            "ATG_SERVICE_URL": "https://atg-dev.example.com",
            "ATG_API_KEY": f"atg_dev_{'a' * 64}",
            # ATG_REQUEST_TIMEOUT not set
        },
    ):
        config = ATGClientConfig.from_env()

    assert config.request_timeout == 3600  # 60 minutes


# =============================================================================
# Server Configuration Tests (Architecture Section 3.3)
# =============================================================================


def test_server_config_loads_from_env():
    """Test that ATGServerConfig loads from environment variables."""
    from src.remote.server.config import ATGServerConfig

    with patch.dict(
        os.environ,
        {
            "ATG_SERVER_HOST": "0.0.0.0",
            "ATG_SERVER_PORT": "8443",
            "ATG_SERVER_WORKERS": "8",
            "ATG_API_KEYS": f"atg_dev_{'a' * 64},atg_dev_{'b' * 64}",
            "ATG_TARGET_TENANT_ID": "12345678-1234-1234-1234-123456789012",
            "ATG_USE_MANAGED_IDENTITY": "true",
            "ATG_MAX_CONCURRENT_OPS": "5",
        },
    ):
        # This class doesn't exist yet - will fail!
        config = ATGServerConfig.from_env()

    assert config.host == "0.0.0.0"
    assert config.port == 8443
    assert config.workers == 8
    assert len(config.api_keys) == 2
    assert config.target_tenant_id == "12345678-1234-1234-1234-123456789012"
    assert config.use_managed_identity is True
    assert config.max_concurrent_operations == 5


def test_server_config_defaults():
    """Test that server config has sensible defaults."""
    from src.remote.server.config import ATGServerConfig

    with patch.dict(os.environ, {}, clear=True):
        config = ATGServerConfig.from_env()

    assert config.host == "0.0.0.0"
    assert config.port == 8000
    assert config.workers == 4
    assert config.api_keys == []
    assert config.use_managed_identity is True
    assert config.max_concurrent_operations == 3


def test_server_config_parses_multiple_api_keys():
    """Test that server config parses comma-separated API keys."""
    from src.remote.server.config import ATGServerConfig

    keys = [f"atg_dev_{'a' * 64}", f"atg_dev_{'b' * 64}", f"atg_integration_{'c' * 64}"]
    keys_str = ",".join(keys)

    with patch.dict(os.environ, {"ATG_API_KEYS": keys_str}, clear=True):
        config = ATGServerConfig.from_env()

    assert len(config.api_keys) == 3
    assert config.api_keys == keys


def test_server_config_validates_tenant_id_format():
    """Test that server config validates tenant ID is valid UUID."""
    from src.remote.server.config import ATGServerConfig, ConfigurationError

    with patch.dict(
        os.environ,
        {
            "ATG_TARGET_TENANT_ID": "invalid-tenant-id"  # Not a UUID
        },
        clear=True,
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            config = ATGServerConfig.from_env()
            config.validate()

    assert "tenant" in str(exc_info.value).lower()


def test_server_config_validates_port_range():
    """Test that server config validates port is in valid range."""
    from src.remote.server.config import ATGServerConfig, ConfigurationError

    invalid_ports = ["-1", "0", "65536", "99999"]

    for port in invalid_ports:
        with patch.dict(os.environ, {"ATG_SERVER_PORT": port}, clear=True):
            with pytest.raises(ConfigurationError) as exc_info:
                config = ATGServerConfig.from_env()
                config.validate()

        assert "port" in str(exc_info.value).lower()


def test_server_config_validates_worker_count():
    """Test that server config validates worker count is positive."""
    from src.remote.server.config import ATGServerConfig, ConfigurationError

    with patch.dict(os.environ, {"ATG_SERVER_WORKERS": "0"}, clear=True):
        with pytest.raises(ConfigurationError) as exc_info:
            config = ATGServerConfig.from_env()
            config.validate()

    assert "workers" in str(exc_info.value).lower()


def test_server_config_requires_at_least_one_api_key():
    """Test that server config requires at least one API key in production."""
    from src.remote.server.config import ATGServerConfig, ConfigurationError

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ATG_API_KEYS": "",  # No keys
        },
        clear=True,
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            config = ATGServerConfig.from_env()
            config.validate()

    assert "api key" in str(exc_info.value).lower()


# =============================================================================
# Environment-Specific Configuration Tests
# =============================================================================


def test_config_supports_dev_environment():
    """Test that config supports dev environment configuration."""
    from src.remote.server.config import ATGServerConfig

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "dev",
            "ATG_TARGET_TENANT_ID": "dev-tenant-12345678-1234-1234-1234-123456789012",
        },
        clear=True,
    ):
        config = ATGServerConfig.from_env()

    assert config.environment == "dev"


def test_config_supports_integration_environment():
    """Test that config supports integration environment configuration."""
    from src.remote.server.config import ATGServerConfig

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "integration",
            "ATG_TARGET_TENANT_ID": "int-tenant-12345678-1234-1234-1234-123456789012",
        },
        clear=True,
    ):
        config = ATGServerConfig.from_env()

    assert config.environment == "integration"


def test_config_validates_environment_matches_api_key_prefix():
    """Test that config validates environment matches API key prefix in production."""
    from src.remote.server.config import ATGServerConfig, ConfigurationError

    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "production",
            "ATG_API_KEYS": f"atg_dev_{'a' * 64}",  # Mismatch!
        },
        clear=True,
    ):
        with pytest.raises(ConfigurationError) as exc_info:
            config = ATGServerConfig.from_env()
            config.validate()

    assert "environment mismatch" in str(exc_info.value).lower()


# =============================================================================
# Configuration File Loading Tests
# =============================================================================


def test_config_loads_from_dotenv_file():
    """Test that config loads from .env file when present."""
    from src.remote.client.config import ATGClientConfig

    env_content = """
ATG_REMOTE_MODE=true
ATG_SERVICE_URL=https://atg-dev.example.com
ATG_API_KEY=atg_dev_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
ATG_REQUEST_TIMEOUT=1800
"""

    with patch("builtins.open", mock_open(read_data=env_content)):
        with patch("pathlib.Path.exists", return_value=True):
            config = ATGClientConfig.from_file(".env")

    assert config.remote_mode is True
    assert config.service_url == "https://atg-dev.example.com"


def test_config_env_vars_override_file():
    """Test that environment variables override .env file values."""
    from src.remote.client.config import ATGClientConfig

    env_content = """
ATG_REMOTE_MODE=true
ATG_SERVICE_URL=https://atg-dev.example.com
ATG_API_KEY=atg_dev_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
"""

    with patch("builtins.open", mock_open(read_data=env_content)):
        with patch("pathlib.Path.exists", return_value=True):
            with patch.dict(
                os.environ, {"ATG_SERVICE_URL": "https://atg-override.example.com"}
            ):
                config = ATGClientConfig.from_file(".env")

    # Environment variable should override file
    assert config.service_url == "https://atg-override.example.com"


def test_config_handles_missing_env_file_gracefully():
    """Test that config handles missing .env file gracefully."""
    from src.remote.client.config import ATGClientConfig

    with patch("pathlib.Path.exists", return_value=False):
        # Should not raise, just return defaults
        config = ATGClientConfig.from_file(".env")

    assert config.remote_mode is False


def test_config_handles_malformed_env_file():
    """Test that config handles malformed .env file with clear error."""
    from src.remote.client.config import ATGClientConfig, ConfigurationError

    malformed_content = """
ATG_REMOTE_MODE=true
INVALID LINE WITHOUT EQUALS
ATG_SERVICE_URL=https://atg-dev.example.com
"""

    with patch("builtins.open", mock_open(read_data=malformed_content)):
        with patch("pathlib.Path.exists", return_value=True):
            with pytest.raises(ConfigurationError) as exc_info:
                ATGClientConfig.from_file(".env")

    assert "malformed" in str(exc_info.value).lower()


# =============================================================================
# Neo4j Configuration Tests (Neo4j Connection Design)
# =============================================================================


def test_neo4j_config_loads_from_env():
    """Test that Neo4j configuration loads from environment."""
    from src.remote.server.config import Neo4jConfig

    with patch.dict(
        os.environ,
        {
            "NEO4J_URI": "bolt://neo4j-dev:7687",
            "NEO4J_USER": "neo4j",
            "NEO4J_PASSWORD": "SecurePassword123!@#",
            "NEO4J_DEV_POOL_SIZE": "50",
            "NEO4J_INTEGRATION_POOL_SIZE": "30",
        },
    ):
        # This class doesn't exist yet - will fail!
        config = Neo4jConfig.from_env("dev")

    assert config.uri == "bolt://neo4j-dev:7687"
    assert config.user == "neo4j"
    assert config.password == "SecurePassword123!@#"
    assert config.max_pool_size == 50


def test_neo4j_config_validates_password_strength():
    """Test that Neo4j config validates password meets security requirements.

    Per security design: minimum 16 characters, uppercase, lowercase, digit, special.
    """
    from src.remote.server.config import ConfigurationError, Neo4jConfig

    weak_passwords = [
        "short",  # Too short
        "onlylowercaseletters1234567",  # No uppercase or special
        "ONLYUPPERCASELETTERS1234567",  # No lowercase or special
        "NoDigitsHere!@#$",  # No digits
        "NoSpecialChars123ABC",  # No special characters
    ]

    for weak_password in weak_passwords:
        with patch.dict(
            os.environ,
            {"NEO4J_URI": "bolt://localhost:7687", "NEO4J_PASSWORD": weak_password},
            clear=True,
        ):
            with pytest.raises(ConfigurationError) as exc_info:
                config = Neo4jConfig.from_env("dev")
                config.validate()

        assert "password" in str(exc_info.value).lower()


def test_neo4j_config_environment_specific_pool_sizes():
    """Test that Neo4j config supports different pool sizes per environment."""
    from src.remote.server.config import Neo4jConfig

    # Dev environment
    with patch.dict(
        os.environ,
        {
            "NEO4J_URI": "bolt://neo4j-dev:7687",
            "NEO4J_PASSWORD": "SecurePassword123!@#",
            "NEO4J_DEV_POOL_SIZE": "50",
        },
        clear=True,
    ):
        dev_config = Neo4jConfig.from_env("dev")

    # Integration environment
    with patch.dict(
        os.environ,
        {
            "NEO4J_URI": "bolt://neo4j-int:7687",
            "NEO4J_PASSWORD": "SecurePassword123!@#",
            "NEO4J_INTEGRATION_POOL_SIZE": "30",
        },
        clear=True,
    ):
        int_config = Neo4jConfig.from_env("integration")

    assert dev_config.max_pool_size == 50
    assert int_config.max_pool_size == 30


def test_neo4j_config_default_pool_size():
    """Test that Neo4j config has sensible default pool size."""
    from src.remote.server.config import Neo4jConfig

    with patch.dict(
        os.environ,
        {
            "NEO4J_URI": "bolt://localhost:7687",
            "NEO4J_PASSWORD": "SecurePassword123!@#",
        },
        clear=True,
    ):
        config = Neo4jConfig.from_env("dev")

    # Default should be 50 for dev
    assert config.max_pool_size == 50


# =============================================================================
# Configuration Serialization Tests
# =============================================================================


def test_config_to_dict():
    """Test that config can be serialized to dictionary."""
    from src.remote.client.config import ATGClientConfig

    config = ATGClientConfig(
        remote_mode=True,
        service_url="https://atg-dev.example.com",
        api_key="atg_dev_" + "a" * 64,
        request_timeout=1800,
    )

    config_dict = config.to_dict()

    assert config_dict["remote_mode"] is True
    assert config_dict["service_url"] == "https://atg-dev.example.com"
    # API key should be redacted in dict
    assert config_dict["api_key"] == "atg_dev_***"


def test_config_from_dict():
    """Test that config can be deserialized from dictionary."""
    from src.remote.client.config import ATGClientConfig

    config_dict = {
        "remote_mode": True,
        "service_url": "https://atg-dev.example.com",
        "api_key": "atg_dev_" + "a" * 64,
        "request_timeout": 1800,
    }

    config = ATGClientConfig.from_dict(config_dict)

    assert config.remote_mode is True
    assert config.service_url == "https://atg-dev.example.com"
    assert config.api_key == "atg_dev_" + "a" * 64


def test_config_redacts_secrets_in_string_representation():
    """Test that config redacts secrets when converted to string."""
    from src.remote.server.config import ATGServerConfig

    config = ATGServerConfig(
        host="0.0.0.0",
        port=8000,
        workers=4,
        api_keys=[f"atg_dev_{'a' * 64}"],
        target_tenant_id="12345678-1234-1234-1234-123456789012",
    )

    config_str = str(config)

    # Should not expose full API key
    assert "atg_dev_aaa" not in config_str
    assert "***" in config_str or "[REDACTED]" in config_str
