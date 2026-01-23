"""Test FilterConfig model for Azure resource filtering."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

# This will fail initially as FilterConfig doesn't exist yet
from src.models.filter_config import FilterConfig


class TestFilterConfig:
    """Test FilterConfig model validation and parsing."""

    def test_create_empty_filter_config(self):
        """Test creating a FilterConfig with no filters."""
        config = FilterConfig()
        assert config.subscription_ids == []
        assert config.resource_group_names == []

    def test_create_filter_config_with_subscription_ids(self):
        """Test creating a FilterConfig with subscription IDs."""
        sub_id1 = str(uuid4())
        sub_id2 = str(uuid4())

        config = FilterConfig(subscription_ids=[sub_id1, sub_id2])
        assert len(config.subscription_ids) == 2
        assert sub_id1 in config.subscription_ids
        assert sub_id2 in config.subscription_ids
        assert config.resource_group_names == []

    def test_create_filter_config_with_resource_groups(self):
        """Test creating a FilterConfig with resource group names."""
        rg_names = ["rg-prod-001", "rg-dev-002", "rg-test-003"]

        config = FilterConfig(resource_group_names=rg_names)
        assert config.subscription_ids == []
        assert len(config.resource_group_names) == 3
        assert all(rg in config.resource_group_names for rg in rg_names)

    def test_create_filter_config_with_both_filters(self):
        """Test creating a FilterConfig with both subscription IDs and resource groups."""
        sub_id = str(uuid4())
        rg_names = ["rg-prod", "rg-dev"]

        config = FilterConfig(subscription_ids=[sub_id], resource_group_names=rg_names)
        assert len(config.subscription_ids) == 1
        assert sub_id in config.subscription_ids
        assert len(config.resource_group_names) == 2
        assert all(rg in config.resource_group_names for rg in rg_names)

    def test_validate_subscription_id_format(self):
        """Test that subscription IDs must be valid UUIDs."""
        # Valid UUID should work
        valid_uuid = str(uuid4())
        config = FilterConfig(subscription_ids=[valid_uuid])
        assert valid_uuid in config.subscription_ids

        # Invalid UUID format should raise ValidationError
        with pytest.raises(ValidationError) as exc_info:
            FilterConfig(subscription_ids=["not-a-uuid"])

        errors = exc_info.value.errors()
        assert any("UUID" in str(error) for error in errors)

    def test_parse_comma_separated_subscription_ids(self):
        """Test parsing comma-separated subscription IDs from string."""
        sub_id1 = str(uuid4())
        sub_id2 = str(uuid4())
        sub_id3 = str(uuid4())

        # Test from_comma_separated class method
        comma_separated = f"{sub_id1},{sub_id2},{sub_id3}"
        config = FilterConfig.from_comma_separated(
            subscription_ids=comma_separated, resource_group_names=None
        )

        assert len(config.subscription_ids) == 3
        assert sub_id1 in config.subscription_ids
        assert sub_id2 in config.subscription_ids
        assert sub_id3 in config.subscription_ids

    def test_parse_comma_separated_resource_groups(self):
        """Test parsing comma-separated resource group names from string."""
        rg_string = "rg-prod-001, rg-dev-002,rg-test-003"

        config = FilterConfig.from_comma_separated(
            subscription_ids=None, resource_group_names=rg_string
        )

        assert len(config.resource_group_names) == 3
        # Should trim whitespace
        assert "rg-prod-001" in config.resource_group_names
        assert "rg-dev-002" in config.resource_group_names
        assert "rg-test-003" in config.resource_group_names

    def test_parse_comma_separated_with_whitespace(self):
        """Test that whitespace is properly trimmed when parsing."""
        sub_id1 = str(uuid4())
        sub_id2 = str(uuid4())

        # With various whitespace patterns
        comma_separated = f"  {sub_id1} , {sub_id2}  "
        config = FilterConfig.from_comma_separated(
            subscription_ids=comma_separated, resource_group_names=" rg-prod , rg-dev "
        )

        assert len(config.subscription_ids) == 2
        assert sub_id1 in config.subscription_ids
        assert sub_id2 in config.subscription_ids

        assert len(config.resource_group_names) == 2
        assert "rg-prod" in config.resource_group_names
        assert "rg-dev" in config.resource_group_names

    def test_empty_string_handling(self):
        """Test that empty strings are handled properly."""
        # Empty string should result in empty list
        config = FilterConfig.from_comma_separated(
            subscription_ids="", resource_group_names=""
        )

        assert config.subscription_ids == []
        assert config.resource_group_names == []

    def test_none_handling(self):
        """Test that None values are handled properly."""
        # None should result in empty list
        config = FilterConfig.from_comma_separated(
            subscription_ids=None, resource_group_names=None
        )

        assert config.subscription_ids == []
        assert config.resource_group_names == []

    def test_mixed_valid_invalid_subscription_ids(self):
        """Test that invalid UUIDs in a list raise validation errors."""
        valid_uuid = str(uuid4())

        with pytest.raises(ValidationError) as exc_info:
            FilterConfig.from_comma_separated(
                subscription_ids=f"{valid_uuid},invalid-uuid", resource_group_names=None
            )

        errors = exc_info.value.errors()
        assert any("UUID" in str(error) for error in errors)

    def test_duplicate_handling(self):
        """Test that duplicate values are handled (should keep unique values)."""
        sub_id = str(uuid4())

        config = FilterConfig.from_comma_separated(
            subscription_ids=f"{sub_id},{sub_id},{sub_id}",
            resource_group_names="rg-prod,rg-prod,rg-dev",
        )

        # Should deduplicate
        assert len(config.subscription_ids) == 1
        assert sub_id in config.subscription_ids

        assert len(config.resource_group_names) == 2
        assert "rg-prod" in config.resource_group_names
        assert "rg-dev" in config.resource_group_names

    def test_is_empty_property(self):
        """Test the is_empty property to check if any filters are set."""
        # Empty config
        config = FilterConfig()
        assert config.is_empty is True

        # With subscription IDs
        config = FilterConfig(subscription_ids=[str(uuid4())])
        assert config.is_empty is False

        # With resource groups
        config = FilterConfig(resource_group_names=["rg-prod"])
        assert config.is_empty is False

        # With both
        config = FilterConfig(
            subscription_ids=[str(uuid4())], resource_group_names=["rg-prod"]
        )
        assert config.is_empty is False

    def test_case_preservation_for_resource_groups(self):
        """Test that resource group names preserve their case."""
        rg_names = ["RG-Prod", "rg-dev", "Rg-Test"]

        config = FilterConfig(resource_group_names=rg_names)

        # Case should be preserved
        assert "RG-Prod" in config.resource_group_names
        assert "rg-dev" in config.resource_group_names
        assert "Rg-Test" in config.resource_group_names

    def test_special_characters_in_resource_groups(self):
        """Test that resource group names with valid Azure characters work."""
        # Azure allows alphanumeric, periods, underscores, hyphens, and parentheses
        rg_names = [
            "rg_prod_001",
            "rg.dev.002",
            "rg-test-003",
            "rg(staging)004",
            "RG_2024.prod-01",
        ]

        config = FilterConfig(resource_group_names=rg_names)
        assert len(config.resource_group_names) == 5
        assert all(rg in config.resource_group_names for rg in rg_names)


class TestFilterConfigReferencedResources:
    """Test FilterConfig include_referenced_resources field (Issue #228)."""

    def test_default_include_referenced_resources_is_true(self):
        """Test that include_referenced_resources defaults to True."""
        config = FilterConfig()
        assert config.include_referenced_resources is True

    def test_create_with_include_referenced_resources_true(self):
        """Test creating FilterConfig with include_referenced_resources=True."""
        config = FilterConfig(
            subscription_ids=[str(uuid4())], include_referenced_resources=True
        )
        assert config.include_referenced_resources is True

    def test_create_with_include_referenced_resources_false(self):
        """Test creating FilterConfig with include_referenced_resources=False."""
        config = FilterConfig(
            subscription_ids=[str(uuid4())], include_referenced_resources=False
        )
        assert config.include_referenced_resources is False

    def test_include_referenced_resources_persists_through_validation(self):
        """Test that include_referenced_resources survives model validation."""
        sub_id = str(uuid4())
        config = FilterConfig(
            subscription_ids=[sub_id],
            resource_group_names=["rg-prod"],
            include_referenced_resources=False,
        )

        assert config.subscription_ids == [sub_id]
        assert config.resource_group_names == ["rg-prod"]
        assert config.include_referenced_resources is False

    def test_from_comma_separated_preserves_default(self):
        """Test that from_comma_separated method preserves default include_referenced_resources=True."""
        config = FilterConfig.from_comma_separated(
            subscription_ids=str(uuid4()), resource_group_names="rg-prod,rg-dev"
        )

        assert config.include_referenced_resources is True
