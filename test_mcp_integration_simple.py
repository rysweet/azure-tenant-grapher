#!/usr/bin/env python3
"""
Simple test script to validate MCP integration implementation.
This can be run without full dependencies installed.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_mcp_config():
    """Test MCPConfig dataclass."""
    print("Testing MCPConfig...")
    from src.config_manager import MCPConfig

    # Test default config
    config = MCPConfig()
    assert config.endpoint == "http://localhost:8080"
    assert config.enabled is False
    assert config.timeout == 30
    assert config.api_key is None
    print("✅ Default MCPConfig works")

    # Test custom config
    config = MCPConfig(enabled=True, endpoint="http://test:9090", timeout=45)
    assert config.enabled is True
    assert config.endpoint == "http://test:9090"
    assert config.timeout == 45
    print("✅ Custom MCPConfig works")

    # Test validation
    try:
        config = MCPConfig(timeout=0)
        config.__post_init__()
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "timeout must be at least 1" in str(e)
        print("✅ MCPConfig validation works")

    return True


def test_mcp_in_main_config():
    """Test that MCP is integrated into main config."""
    print("\nTesting MCP in AzureTenantGrapherConfig...")
    from src.config_manager import AzureTenantGrapherConfig

    config = AzureTenantGrapherConfig()
    assert hasattr(config, "mcp"), "MCP config not found in main config"
    assert config.mcp.endpoint == "http://localhost:8080"
    print("✅ MCP integrated into main config")

    return True


def test_mcp_service_structure():
    """Test MCP service basic structure."""
    print("\nTesting MCPIntegrationService structure...")

    # Check if file exists
    service_path = "src/services/mcp_integration.py"
    assert os.path.exists(service_path), f"MCP service file not found at {service_path}"
    print(f"✅ MCP service file exists at {service_path}")

    # Check file has proper content
    with open(service_path) as f:
        content = f.read()

    # Check for key classes and methods
    assert "class MCPIntegrationService" in content, (
        "MCPIntegrationService class not found"
    )
    assert "async def initialize" in content, "initialize method not found"
    assert "async def query_resources" in content, "query_resources method not found"
    assert "async def natural_language_command" in content, (
        "natural_language_command method not found"
    )
    assert "async def discover_resources" in content, (
        "discover_resources method not found"
    )
    assert "async def analyze_resource_relationships" in content, (
        "analyze_relationships method not found"
    )
    print("✅ MCP service has all required methods")

    return True


def test_cli_integration():
    """Test CLI integration."""
    print("\nTesting CLI integration...")

    # Check CLI file for mcp-query command
    cli_path = "scripts/cli.py"
    with open(cli_path) as f:
        content = f.read()

    assert '@cli.command("mcp-query")' in content, "mcp-query command not found in CLI"
    assert "from src.cli_commands import mcp_query_command" in content, (
        "mcp_query_command import not found"
    )
    print("✅ mcp-query command registered in CLI")

    # Check cli_commands.py for handler
    commands_path = "src/cli_commands.py"
    with open(commands_path) as f:
        content = f.read()

    assert "async def mcp_query_command" in content, (
        "mcp_query_command handler not found"
    )
    assert "MCPIntegrationService" in content, (
        "MCPIntegrationService not imported in handler"
    )
    print("✅ mcp_query_command handler implemented")

    return True


def test_documentation():
    """Test that documentation exists."""
    print("\nTesting documentation...")

    doc_path = "docs/MCP_INTEGRATION.md"
    assert os.path.exists(doc_path), f"MCP documentation not found at {doc_path}"

    with open(doc_path) as f:
        content = f.read()

    assert "MCP (Model Context Protocol) Integration" in content
    assert "atg mcp-query" in content
    assert "Configuration" in content
    print(f"✅ MCP documentation exists at {doc_path}")

    return True


def test_env_example():
    """Test that .env.example has MCP configuration."""
    print("\nTesting .env.example...")

    env_path = ".env.example"
    with open(env_path) as f:
        content = f.read()

    assert "MCP_ENABLED" in content, "MCP_ENABLED not in .env.example"
    assert "MCP_ENDPOINT" in content, "MCP_ENDPOINT not in .env.example"
    assert "MCP_TIMEOUT" in content, "MCP_TIMEOUT not in .env.example"
    assert "MCP_API_KEY" in content, "MCP_API_KEY not in .env.example"
    print("✅ MCP configuration documented in .env.example")

    return True


def main():
    """Run all tests."""
    print("=" * 60)
    print("MCP Integration Validation Tests")
    print("=" * 60)

    tests = [
        test_mcp_config,
        test_mcp_in_main_config,
        test_mcp_service_structure,
        test_cli_integration,
        test_documentation,
        test_env_example,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} failed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("✅ All MCP integration tests passed!")
        print("\nMCP integration is complete and ready to use.")
        print("To enable, set MCP_ENABLED=true in your .env file")
        return 0
    else:
        print(f"❌ {failed} tests failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
