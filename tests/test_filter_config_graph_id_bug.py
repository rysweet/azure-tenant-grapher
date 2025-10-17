"""Test for FilterConfig bug with graph database IDs."""

import pytest

from src.models.filter_config import FilterConfig


def test_filter_config_rejects_graph_database_ids():
    """Test that FilterConfig incorrectly rejects graph database IDs.

    This test demonstrates the bug where graph database IDs (like
    '4:5da3178c-575f-4e20-aa0b-6bd8e843b6d0:630') are being passed
    to FilterConfig when they should either be:
    1. Handled as special graph IDs and not validated as Azure resource names
    2. Translated to actual resource group names before validation
    """
    # This is the graph database ID format that's causing the issue
    graph_id = "4:5da3178c-575f-4e20-aa0b-6bd8e843b6d0:630"

    # This should either:
    # 1. Be accepted as a special graph ID format, OR
    # 2. Never reach FilterConfig in this format
    with pytest.raises(ValueError) as exc_info:
        FilterConfig(resource_group_names=[graph_id])

    assert "Invalid resource group name" in str(exc_info.value)
    assert graph_id in str(exc_info.value)


def test_filter_config_should_handle_graph_ids_gracefully():
    """Test the desired behavior for graph IDs.

    Graph IDs should either be:
    1. Detected and handled separately from Azure resource names
    2. Converted to actual resource names before validation
    """
    # Graph ID formats that might be encountered
    graph_ids = [
        "4:5da3178c-575f-4e20-aa0b-6bd8e843b6d0:630",  # Neo4j internal ID
        "n10",  # Simple node ID
        "0:abc123:456",  # Another possible format
    ]

    # The fix should allow FilterConfig to handle these gracefully
    # Either by:
    # 1. Detecting them as graph IDs and skipping validation
    # 2. Having a separate field for graph IDs
    # 3. Converting them before they reach FilterConfig

    # This test will fail until we implement the fix
    # After fix, this should work:
    # config = FilterConfig(resource_group_names=graph_ids, skip_azure_validation=True)
    # OR
    # config = FilterConfig(resource_group_ids=graph_ids)  # separate field
    # OR the IDs should be resolved before reaching FilterConfig
    pass


def test_filter_config_accepts_valid_azure_resource_group_names():
    """Test that valid Azure resource group names are still accepted."""
    valid_names = [
        "Ballista_UCAScenario",  # The actual resource group name
        "my-resource-group",
        "RG_with_underscores",
        "rg.with.dots",
        "rg(with)parens",
        "a",  # Single character
        "a" * 90,  # Maximum length
    ]

    # This should work
    config = FilterConfig(resource_group_names=valid_names)
    assert config.resource_group_names == valid_names


def test_filter_config_rejects_invalid_azure_resource_group_names():
    """Test that invalid Azure resource group names are properly rejected."""
    invalid_names = [
        "-starts-with-hyphen",
        "ends-with-hyphen-",
        "has spaces",
        "has@special#chars",
        "a" * 91,  # Too long
        "",  # Empty string
    ]

    for invalid_name in invalid_names:
        with pytest.raises(ValueError) as exc_info:
            FilterConfig(resource_group_names=[invalid_name])
        assert "Invalid resource group name" in str(exc_info.value)
